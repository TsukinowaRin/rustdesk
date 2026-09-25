#!/usr/bin/env python3
"""Slack Web API の橋。poll は一巡だけ読み、待ち時間は hub が管理する。"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def config_home() -> Path:
    return Path(os.environ.get("HARNESS_CONFIG_HOME") or Path.home() / ".config/harness")


def configured() -> bool:
    return (config_home() / "slack.env").exists()


def _config(*, allow_empty_users: bool = False) -> dict:
    try:
        lines = (config_home() / "slack.env").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise ValueError("Slack の設定が無い: ~/.config/harness/slack.env") from None
    config = {}
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip().strip('"\'')
    if not config.get("SLACK_BOT_TOKEN"):
        raise ValueError("SLACK_BOT_TOKEN が必要です")
    users = {u.strip() for u in config.get("SLACK_USER_IDS", "").split(",") if u.strip()}
    if not users and not allow_empty_users:
        raise ValueError("SLACK_USER_IDS が必要です")
    config["users"] = users
    return config


def _api(method: str, params: dict) -> dict:
    """Web API への唯一の出口。試験ではこの関数を差し替える。"""
    if os.environ.get("HARNESS_TESTING") == "1":
        raise RuntimeError("HARNESS_TESTING=1 では外部通信しません")
    token = _config(allow_empty_users=True)["SLACK_BOT_TOKEN"]
    request = urllib.request.Request(
        "https://slack.com/api/" + method,
        data=urllib.parse.urlencode(params).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    while True:
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                result = json.load(response)
            break
        except urllib.error.HTTPError as error:
            if error.code == 429:
                try:
                    delay = float(error.headers["Retry-After"])
                    if not 0 <= delay < float("inf"):
                        raise ValueError
                except (KeyError, TypeError, ValueError):
                    raise RuntimeError("Slack API: Retry-After が不正です") from None
                finally:
                    error.close()
                time.sleep(delay)
                continue
            code = error.code
            error.close()
            raise RuntimeError(f"Slack API: HTTP {code}") from None
        except (OSError, ValueError):
            raise RuntimeError("Slack API に接続できません") from None
    if not result.get("ok"):
        raise RuntimeError(f"Slack API: {result.get('error', 'error')}")
    return result


def send(text: str, *, target, thread=None) -> None:
    _config()
    params = {"channel": str(target), "text": text}
    if thread is not None:
        params["thread_ts"] = str(thread)
    _api("chat.postMessage", params)


def send_document(path: Path, caption: str, *, target, thread=None) -> None:
    # ponytail: 最小版は添付を送らない。添付が必要になったら Slack の外部 upload 3 段階を足す。
    send(f"{caption}\nファイルは私設の網の HTML で", target=target, thread=thread)


def _channels() -> dict:
    config = json.loads((config_home() / "hub.json").read_text(encoding="utf-8"))
    return config.get("transports", {}).get("slack", {}).get("channels", {})


def channel_name(name: str) -> str:
    return re.sub(r"[^\w]+", "-", name.lower().replace("_", "-")).strip("-")


def _history(channel: str, oldest: str) -> list[dict]:
    messages = []
    cursor = ""
    while True:
        params = {"channel": channel, "oldest": oldest, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        result = _api("conversations.history", params)
        messages.extend(result.get("messages", []))
        cursor = (result.get("response_metadata") or {}).get("next_cursor") or ""
        if not cursor:
            return messages


def poll() -> list[dict]:
    config = _config()
    path = config_home() / "slack.offset"
    offsets = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    accepted = []
    for channel in _channels().values():
        channel = str(channel)
        last = offsets.get(channel, "0")
        messages = _history(channel, last)
        for message in sorted(messages, key=lambda m: tuple(int(s) for s in m["ts"].split("."))):
            ts = message["ts"]
            if tuple(int(s) for s in ts.split(".")) <= tuple(int(s) for s in last.split(".")):
                continue
            body = message.get("text")
            if (not message.get("bot_id") and message.get("subtype") != "bot_message" and message.get("user") in config["users"]
                    and isinstance(body, str) and body):
                accepted.append({"text": body.replace(config["SLACK_BOT_TOKEN"], "[REDACTED]"),
                                 "chat_id": message["user"], "target": channel,
                                 "thread": message.get("thread_ts"), "update_id": f"slack:{channel}:{ts}"})
            offsets[channel] = ts
            last = ts
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(offsets) + "\n", encoding="utf-8")
        tmp.replace(path)
    return accepted


def whoami() -> list[dict]:
    _config(allow_empty_users=True)
    me = _api("auth.test", {})
    print(f"bot: {me.get('user', '?')}  id={me.get('user_id', '?')}")
    seen = {}
    for channel in _channels().values():
        for message in _history(str(channel), "0"):
            user = message.get("user")
            if user and not message.get("bot_id"):
                seen[user] = {"chat_id": user, "target": channel}
    return list(seen.values())
