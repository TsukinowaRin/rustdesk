#!/usr/bin/env python3
"""Slack の Web API と hub の往復を、使い捨て設定と偽 API で確かめる。"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'harness'))
import hub
import inbox
from bridge import slack, telegram


class SlackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = patch.dict(os.environ, {'HARNESS_CONFIG_HOME': str(self.root), 'HARNESS_TESTING': '1'})
        env.start()
        self.addCleanup(env.stop)
        (self.root / 'slack.env').write_text('SLACK_BOT_TOKEN=fake-secret\nSLACK_USER_IDS=U1\n')
        hub.save({'workspaces': {n: {'path': str(self.root / n)} for n in ('a', 'b')},
                  'current': 'a', 'transports': {'slack': {'channels': {'a': 'C1'}}}})
        self.calls = []
        self.messages = {'C1': [], 'C2': []}
        self.api = patch.object(slack, '_api', side_effect=self.fake_api)
        self.api.start()
        self.addCleanup(self.api.stop)

    def fake_api(self, method, params):
        self.calls.append((method, params))
        if method == 'conversations.list':
            return {'channels': []}
        if method == 'conversations.create':
            return {'channel': {'id': 'C2'}}
        if method == 'conversations.history':
            return {'messages': self.messages[params['channel']]}
        if method == 'auth.test':
            return {'user': 'helper', 'user_id': 'UBOT'}
        return {}

    def test_channel_routing_filtering_and_outbox(self):
        self.messages['C2'] = [
            {'ts': '5.0', 'text': 'bot_message', 'user': 'U1', 'subtype': 'bot_message'},
            {'ts': '4.0', 'text': 'bot', 'user': 'UBOT', 'bot_id': 'B1'},
            {'ts': '3.0', 'text': 'outside', 'user': 'U9'},
            {'ts': '2.0', 'text': 'next', 'user': 'U1'},
            {'ts': '1.0', 'text': 'fake-secret seen', 'user': 'U1'},
        ]
        with patch.object(telegram, '_api', side_effect=AssertionError('Telegram を呼んだ')):
            self.assertEqual(hub.main(['--once']), 0)
        self.assertEqual(hub.load()['transports']['slack']['channels'], {'a': 'C1', 'b': 'C2'})
        self.assertIn(('conversations.create', {'name': 'b'}), self.calls)
        self.assertIn(('conversations.join', {'channel': 'C2'}), self.calls)
        self.assertEqual([r['text'] for r in inbox.all_rows(self.root / 'b/.loop')],
                         ['[REDACTED] seen', 'next'])
        self.assertEqual(inbox.all_rows(self.root / 'a/.loop'), [])
        self.assertEqual(json.loads((self.root / 'slack.offset').read_text())['C2'], '5.0')
        inbox.outbox_append({'kind': 'text', 'transport': 'slack', 'text': 'reply'}, self.root / 'b/.loop')
        self.assertEqual(hub.flush_outbox(), 1)
        self.assertIn(('chat.postMessage', {'channel': 'C2', 'text': '[b] reply'}), self.calls)
        self.messages['C2'] = [{'ts': '5.0', 'text': 'duplicate', 'user': 'U1'}]
        hub.run(hours=1, once=True)
        self.assertEqual(len(inbox.all_rows(self.root / 'b/.loop')), 2)

    def test_thread_reply_and_document_fallback(self):
        slack.send('thread reply', target='C1', thread='12.34')
        slack.send_document(self.root / 'dashboard.html', 'caption', target='C1', thread='12.34')
        self.assertIn(('chat.postMessage', {'channel': 'C1', 'text': 'thread reply',
                                             'thread_ts': '12.34'}), self.calls)
        self.assertIn(('chat.postMessage', {'channel': 'C1',
                                             'text': 'caption\nファイルは私設の網の HTML で',
                                             'thread_ts': '12.34'}), self.calls)

    def test_existing_channel_and_whoami(self):
        cfg = hub.load()
        cfg['transports']['slack']['channels'] = {}
        hub.save(cfg)
        def api(method, params):
            self.calls.append((method, params))
            if method == 'conversations.list':
                return {'channels': [{'id': 'CA', 'name': 'a'}, {'id': 'CB', 'name': 'b'}]}
            if method == 'auth.test':
                return {'user': 'helper', 'user_id': 'UBOT'}
            if method == 'conversations.history':
                return {'messages': [{'ts': '1.0', 'user': 'U1', 'text': 'hello'}]}
            return {}
        with patch.object(slack, '_api', side_effect=api):
            hub.run(hours=1, once=True)
            (self.root / 'slack.env').write_text('SLACK_BOT_TOKEN=fake-secret\nSLACK_USER_IDS=\n')
            with redirect_stdout(output := io.StringIO()):
                self.assertEqual(hub.main(['whoami']), 0)
        self.assertEqual(hub.load()['transports']['slack']['channels'], {'a': 'CA', 'b': 'CB'})
        self.assertFalse(any(m == 'conversations.create' for m, _ in self.calls))
        self.assertIn('helper', output.getvalue())
        self.assertIn('U1', output.getvalue())

    def test_http_429_waits_retry_after(self):
        self.api.stop()
        response = io.BytesIO(b'{"ok": true, "channel": "C1"}')
        requests = []
        def urlopen(request, **kwargs):
            requests.append(request)
            if len(requests) == 1:
                raise urllib.error.HTTPError(request.full_url, 429, 'limited', {'Retry-After': '0.25'}, None)
            return response
        with patch.dict(os.environ, {'HARNESS_TESTING': '0'}), \
                patch('urllib.request.urlopen', side_effect=urlopen), \
                patch.object(slack.time, 'sleep') as sleep:
            self.assertEqual(slack._api('conversations.history', {'channel': 'C1'})['channel'], 'C1')
        sleep.assert_called_once_with(0.25)
        self.assertEqual(requests[-1].full_url, 'https://slack.com/api/conversations.history')
        self.assertEqual(requests[-1].get_header('Authorization'), 'Bearer fake-secret')


if __name__ == '__main__':
    unittest.main()
