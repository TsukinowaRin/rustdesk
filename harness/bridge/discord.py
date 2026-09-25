#!/usr/bin/env python3
"""Discord REST API の橋。poll は一巡だけ読み、待ち時間は hub が管理する。"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def config_home() -> Path:
    return Path(os.environ.get('HARNESS_CONFIG_HOME') or Path.home() / '.config/harness')


def configured() -> bool:
    return (config_home() / 'discord.env').exists()


def _config(*, allow_empty_users: bool = False) -> dict:
    try:
        lines = (config_home() / 'discord.env').read_text(encoding='utf-8').splitlines()
    except FileNotFoundError:
        raise ValueError('Discord の設定が無い: ~/.config/harness/discord.env') from None
    config = {}
    for line in lines:
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            config[key.strip()] = value.strip().strip('"\'')
    if not config.get('DISCORD_BOT_TOKEN'):
        raise ValueError('DISCORD_BOT_TOKEN が必要です')
    users = {u.strip() for u in config.get('DISCORD_USER_IDS', '').split(',') if u.strip()}
    if not users and not allow_empty_users:
        raise ValueError('DISCORD_USER_IDS が必要です')
    config['users'] = users
    return config


def _api(method: str, path: str, data: dict | None = None):
    """外部通信の唯一の入口。429 は指定された retry_after 秒待って再送する。"""
    if os.environ.get('HARNESS_TESTING') == '1':
        raise RuntimeError('HARNESS_TESTING=1 では外部通信しません')
    token = _config(allow_empty_users=True)['DISCORD_BOT_TOKEN']
    headers = {'Authorization': f'Bot {token}', 'Content-Type': 'application/json',
               'User-Agent': 'Harness Discord bridge'}
    if data is not None and 'document' in data:
        document = Path(data['document'])
        boundary = uuid.uuid4().hex
        payload = {k: v for k, v in data.items() if k != 'document'}
        filename = document.name.replace('"', '_').replace('\r', '_').replace('\n', '_')
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\n'
                f'Content-Type: application/json\r\n\r\n{json.dumps(payload, ensure_ascii=False)}\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="files[0]"; filename="{filename}"\r\n'
                f'Content-Type: {content_type}\r\n\r\n').encode('utf-8')
        body += document.read_bytes() + f'\r\n--{boundary}--\r\n'.encode('ascii')
        headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
    else:
        body = json.dumps(data, ensure_ascii=False).encode('utf-8') if data is not None else None
    request = urllib.request.Request('https://discord.com/api/v10' + path, data=body,
                                     headers=headers, method=method)
    while True:
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                try:
                    delay = float(json.load(error)['retry_after'])
                except (ValueError, KeyError, TypeError):
                    raise RuntimeError('Discord API: retry_after が不正です') from None
                finally:
                    error.close()
                time.sleep(delay)
                continue
            code = error.code
            error.close()
            raise RuntimeError(f'Discord API: HTTP {code}') from None
        except (OSError, ValueError):
            raise RuntimeError('Discord API に接続できません') from None


def send(text: str, *, target, thread=None) -> None:
    _config()
    # Discord の本文上限は 2000 文字。長い指示役の結果も分割して届ける。
    for start in range(0, len(text), 2000):
        _api('POST', f'/channels/{thread or target}/messages',
             {'content': text[start:start + 2000], 'allowed_mentions': {'parse': []}})


def send_document(path: Path, caption: str, *, target, thread=None) -> None:
    _config()
    _api('POST', f'/channels/{thread or target}/messages',
         {'content': caption[:2000], 'document': Path(path), 'allowed_mentions': {'parse': []}})


def _channels() -> dict:
    config = json.loads((config_home() / 'hub.json').read_text(encoding='utf-8'))
    return config.get('transports', {}).get('discord', {}).get('channels', {})


def poll() -> list[dict]:
    config = _config()
    path = config_home() / 'discord.offset'
    offsets = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    accepted = []
    for channel in _channels().values():
        channel = str(channel)
        last = int(offsets.get(channel, 0))
        messages = _api('GET', f'/channels/{channel}/messages?after={last}&limit=100', None)
        # after の応答が満杯なら過去側も読み、読み飛ばして offset を進めない。
        page = messages
        while len(page) == 100 and min(int(m['id']) for m in page) > last:
            before = min(int(m['id']) for m in page)
            page = _api('GET', f'/channels/{channel}/messages?before={before}&limit=100', None)
            messages.extend(m for m in page if int(m['id']) > last)
        for message in sorted(messages, key=lambda m: int(m['id'])):
            mid = int(message['id'])
            if mid <= last:
                continue
            author = message.get('author') or {}
            text = message.get('content')
            if (not author.get('bot') and not message.get('webhook_id') and str(author.get('id')) in config['users']
                    and isinstance(text, str) and text):
                accepted.append({'text': text.replace(config['DISCORD_BOT_TOKEN'], '[REDACTED]'),
                                 'chat_id': str(author['id']), 'target': channel, 'thread': None,
                                 'update_id': f'discord:{mid}'})
            offsets[channel] = str(mid)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(offsets) + '\n', encoding='utf-8')
    tmp.replace(path)
    return accepted


def whoami() -> list[dict]:
    _config(allow_empty_users=True)
    me = _api('GET', '/users/@me', None)
    print(f"bot: {me.get('username', '?')}  id={me.get('id', '?')}")
    seen = {}
    for channel in _channels().values():
        for message in _api('GET', f'/channels/{channel}/messages?limit=100', None):
            author = message.get('author') or {}
            if author.get('id') and not author.get('bot'):
                seen[str(author['id'])] = {'chat_id': author['id'], 'target': channel,
                                          'name': author.get('username', '')}
    return list(seen.values())
