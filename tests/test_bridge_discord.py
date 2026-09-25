#!/usr/bin/env python3
"""Discord の REST 境界と hub の往復。実際の網と設定は使わない。"""
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
from contextlib import redirect_stdout
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'harness'))
import hub
import inbox
import dashboard_watch
from bridge import discord, telegram


class DiscordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'HARNESS_CONFIG_HOME': str(self.root),
                                          'HARNESS_TESTING': '1',
                                          'HARNESS_LOOP_DIR': str(self.root / 'hub-loop')})
        self.env.start()
        self.addCleanup(self.env.stop)
        (self.root / 'discord.env').write_text(
            'DISCORD_BOT_TOKEN=fake-secret\nDISCORD_USER_IDS=42,7\nDISCORD_GUILD_ID=90\n')
        self.cfg = {'workspaces': {n: {'path': str(self.root / n)} for n in ('a', 'b')},
                    'current': 'a', 'transports': {'discord': {'guild_id': '90', 'channels': {'a': '10'}}}}
        hub.save(self.cfg)
        self.calls = []
        self.messages = {}
        self.api = patch.object(discord, '_api', side_effect=self.fake_api)
        self.api.start()
        self.addCleanup(self.api.stop)

    def fake_api(self, method, path, data=None):
        self.calls.append((method, path, data))
        if path == '/users/@me':
            return {'id': '7', 'username': 'helper', 'bot': True}
        if path == '/guilds/90/channels':
            return {'id': '20', 'name': data['name']}
        if method == 'GET':
            return self.messages.pop(path.split('?')[0], [])
        return {'id': '999'}

    def message(self, mid, content, author='42', bot=False):
        return {'id': str(mid), 'content': content,
                'author': {'id': author, 'bot': bot, 'username': 'person'}}

    def test_channels_and_inbox_filtering_offsets(self):
        # 作業場違い、許可判定の欠落、古い発言の再配送を検出する。
        self.messages['/channels/20/messages'] = [
            self.message(104, 'bot自身', '7', True), self.message(103, '許可外', '99'),
            dict(self.message(105, 'webhook の発言'), webhook_id='555'),
            self.message(102, '次'), self.message(101, 'fake-secret を確認')]
        with patch.object(telegram, '_api', side_effect=AssertionError('Telegram を呼んだ')):
            self.assertEqual(hub.main(['--once']), 0)
        self.assertEqual(hub.load()['transports']['discord']['channels'], {'a': '10', 'b': '20'})
        self.assertIn(('POST', '/guilds/90/channels', {'name': 'b', 'type': 0}), self.calls)
        self.assertEqual(inbox.all_rows(self.root / 'a/.loop'), [])
        self.assertEqual([r['text'] for r in inbox.all_rows(self.root / 'b/.loop')],
                         ['[REDACTED] を確認', '次'])
        self.assertEqual(json.loads((self.root / 'discord.offset').read_text())['20'], '105')
        self.calls.clear()
        hub.run(hours=1, once=True)
        self.assertFalse(any(m == 'POST' for m, _, _ in self.calls))
        self.assertTrue(any('/channels/20/messages?after=105' in p for _, p, _ in self.calls))

    def test_signal_and_outbox_reply_transport(self):
        # watcher が生成する返信は transport が無くても届いた橋へ返す。
        self.messages['/channels/10/messages'] = [self.message(1, '/status'), self.message(2, '/dash')]
        hub.run(hours=1, once=True)
        dashboard_watch.handle_requests(self.root / 'a/.loop')
        self.assertEqual(hub.flush_outbox(), 2)
        posted = [(p, d) for m, p, d in self.calls if m == 'POST' and p.endswith('/messages')]
        self.assertEqual(len(posted), 2)
        self.assertTrue(all(p == '/channels/10/messages' for p, _ in posted))
        self.assertEqual(inbox.outbox_pending(self.root / 'a/.loop'), [])
        inbox.outbox_append({'kind': 'text', 'transport': 'discord', 'text': '明示'}, self.root / 'b/.loop')
        self.assertEqual(hub.flush_outbox(), 1)
        self.assertIn(('POST', '/channels/20/messages', {'content': '[b] 明示',
                        'allowed_mentions': {'parse': []}}), self.calls)

    def test_run_replies_to_channel(self):
        # 起動通知と遅れて届く結果の双方が Discord に戻る。
        fake = self.root / 'leader.py'
        fake.write_text("print('仕事の結果')\n")
        clis = self.root / 'clis.json'
        clis.write_text(json.dumps({'clis': {'fake': {'leader': [sys.executable, str(fake)]}}}))
        self.cfg['workspaces']['b']['leader'] = {'cli': 'fake'}
        (self.root / 'b').mkdir()
        hub.save(self.cfg)
        self.messages['/channels/20/messages'] = [self.message(1, '/run 依頼')]
        with patch.dict(os.environ, {'HARNESS_CLIS': str(clis)}):
            hub.run(hours=1, once=True)
            import time
            for _ in range(100):
                if 'b' not in hub._runs:
                    break
                time.sleep(.02)
            hub.flush_outbox()
        posted = [d['content'] for m, p, d in self.calls if m == 'POST' and p == '/channels/20/messages']
        self.assertTrue(any('起動しました' in t for t in posted), posted)
        self.assertTrue(any('仕事の結果' in t for t in posted), posted)

    def test_topics_channels_and_web_keep_their_destinations(self):
        # グループの chat_id が Discord の返信先を上書きする統合ミスを検出する。
        (self.root / 'telegram.env').write_text('TELEGRAM_BOT_TOKEN=tg-test\nTELEGRAM_CHAT_IDS=43\n')
        self.cfg.update(chat_id=-100, topics={'a': 101, 'b': 102})
        self.cfg['transports']['telegram'] = {}
        hub.save(self.cfg)
        self.messages['/channels/20/messages'] = [self.message(1, '/status')]
        tg_calls = []
        def tg_api(method, params, token):
            tg_calls.append((method, params))
            if method == 'getUpdates':
                return {'ok': True, 'result': [{'update_id': 1, 'message': {
                    'chat': {'id': -100, 'type': 'supergroup'}, 'from': {'id': 43},
                    'message_thread_id': 101, 'text': '/status'}}]}
            return {'ok': True, 'result': {}}
        with patch.object(telegram, '_api', side_effect=tg_api):
            self.assertEqual(hub.main(['--once']), 0)
            for name in ('a', 'b'):
                dashboard_watch.handle_requests(self.root / name / '.loop')
            self.assertEqual(hub.flush_outbox(), 2)
            self.assertTrue(any(m == 'sendMessage' and p['chat_id'] == -100
                                and p['message_thread_id'] == 101 for m, p in tg_calls))
            self.assertTrue(any(m == 'POST' and p == '/channels/20/messages'
                                for m, p, _ in self.calls))
            # 画面への返事と dashboard 外の文書は、どちらの橋にも出さない。
            hub.receive(hub.load(), 'b', '/status', chat_id=hub.WEB)
            dashboard_watch.handle_requests(self.root / 'b/.loop')
            inbox.outbox_append({'kind': 'document', 'transport': 'discord',
                                 'path': str(self.root / 'outside.html')}, self.root / 'b/.loop')
            self.calls.clear()
            tg_calls.clear()
            self.assertEqual(hub.flush_outbox(), 0)
            self.assertEqual(self.calls, [])
            self.assertEqual(tg_calls, [])
            self.assertEqual(inbox.outbox_pending(self.root / 'b/.loop'), [])

    def test_web_only_keeps_external_replies_pending(self):
        # 橋が無い画面専用の起動で、送信待ちを失敗扱いにして捨てない。
        del self.cfg['transports']
        hub.save(self.cfg)
        row = inbox.outbox_append({'kind': 'text', 'chat_id': 43, 'text': '送信待ち'},
                                  self.root / 'a/.loop')
        with redirect_stdout(io.StringIO()):
            self.assertEqual(hub.main(['--serve', '127.0.0.1:0', '--once']), 0)
        self.assertEqual(inbox.outbox_pending(self.root / 'a/.loop'), [row])
        self.assertEqual(self.calls, [])

    def test_transports_poll_concurrently_and_outbox_selects_bridge(self):
        # Telegram の long polling 中にも Discord を受信できる。
        (self.root / 'telegram.env').write_text('TELEGRAM_BOT_TOKEN=tg-test\nTELEGRAM_CHAT_IDS=43\n')
        self.cfg['transports']['telegram'] = {}
        hub.save(self.cfg)
        discord_received = threading.Event()
        telegram_started = threading.Event()
        receiver_threads = {}
        tg_calls = []
        def tg_api(method, params, token):
            tg_calls.append((method, params))
            if method == 'getUpdates':
                receiver_threads['telegram'] = threading.get_ident()
                telegram_started.set()
                if not discord_received.wait(1):
                    raise AssertionError('Discord の受信が Telegram に塞がれた')
                return {'ok': True, 'result': [{'update_id': 1, 'message': {
                    'chat': {'id': 43, 'type': 'private'}, 'from': {'id': 43}, 'text': 'Telegram から'}}]}
            return {'ok': True, 'result': {}}
        original_fake = self.fake_api
        def discord_api(method, path, data=None):
            if method == 'GET':
                receiver_threads['discord'] = threading.get_ident()
                telegram_started.wait(1)
                discord_received.set()
            return original_fake(method, path, data)
        self.messages['/channels/10/messages'] = [self.message(1, 'Discord から')]
        with patch.object(discord, '_api', side_effect=discord_api), \
                patch.object(telegram, '_api', side_effect=tg_api):
            hub.run(hours=.05 / 3600)
            self.assertEqual(set(receiver_threads), {'discord', 'telegram'})
            self.assertNotEqual(receiver_threads['discord'], receiver_threads['telegram'])
            self.assertNotIn(threading.get_ident(), receiver_threads.values())
            self.assertEqual({r['text'] for r in inbox.all_rows(self.root / 'a/.loop')},
                             {'Discord から', 'Telegram から'})
            for row in ({'chat_id': '42', 'text': 'Discord への返事'},
                        {'chat_id': 43, 'text': 'Telegram への返事'},
                        {'transport': 'discord', 'target': '20', 'text': '明示指定'}):
                inbox.outbox_append({'kind': 'text', **row}, self.root / 'a/.loop')
            self.assertEqual(hub.flush_outbox(), 3)
        self.assertTrue(any(m == 'sendMessage' and p['chat_id'] == 43
                            and 'Telegram への返事' in p['text'] for m, p in tg_calls))
        self.assertTrue(any(p == '/channels/10/messages' and 'Discord への返事' in d['content']
                            for m, p, d in self.calls if m == 'POST' and p.endswith('/messages')))
        self.assertTrue(any(p == '/channels/10/messages' and '明示指定' in d['content']   # 行の target は信じない
                            for m, p, d in self.calls if m == 'POST' and p.endswith('/messages')))
        self.assertFalse(any(p == '/channels/20/messages' for m, p, d in self.calls if m == 'POST'))

    def test_whoami_does_not_require_allowed_users_or_consume_offsets(self):
        (self.root / 'discord.env').write_text('DISCORD_BOT_TOKEN=fake-secret\nDISCORD_USER_IDS=\n')
        self.messages['/channels/10/messages'] = [self.message(1, 'hello', '99')]
        with redirect_stdout(output := io.StringIO()):
            self.assertEqual(hub.main(['whoami']), 0)
        self.assertIn('99', output.getvalue())
        self.assertIn('helper', output.getvalue())
        self.assertFalse((self.root / 'discord.offset').exists())

    def test_http_429_and_multipart(self):
        # 実 _api のヘッダー、multipart 本文、429 の待ち時間を HTTP 境界で見る。
        self.api.stop()
        doc = self.root / 'report.html'
        doc.write_bytes(b'<html>report</html>')
        requests = []
        def urlopen(req, **kwargs):
            requests.append(req)
            if len(requests) == 1:
                raise urllib.error.HTTPError(req.full_url, 429, 'rate limited', {},
                                             io.BytesIO(b'{"retry_after": 0.25}'))
            return io.BytesIO(b'{"id": "123"}')
        with patch.dict(os.environ, {'HARNESS_TESTING': '0'}), \
                patch('urllib.request.urlopen', side_effect=urlopen), \
                patch.object(discord.time, 'sleep') as sleep:
            discord.send_document(doc, '資料', target='10')
        sleep.assert_called_once_with(0.25)
        req = requests[-1]
        self.assertEqual(req.full_url, 'https://discord.com/api/v10/channels/10/messages')
        self.assertEqual(req.get_header('Authorization'), 'Bot fake-secret')
        msg = BytesParser(policy=policy.default).parsebytes(
            ('Content-Type: ' + req.get_header('Content-type') + '\r\n\r\n').encode() + req.data)
        parts = list(msg.iter_parts())
        self.assertEqual(json.loads(parts[0].get_payload(decode=True))['content'], '資料')
        self.assertEqual(parts[1].get_filename(), 'report.html')
        self.assertEqual(parts[1].get_payload(decode=True), b'<html>report</html>')


if __name__ == '__main__':
    unittest.main()
