#!/usr/bin/env python3
"""Telegram Bot API と受信箱をつなぐ。poll は一回の long polling。"""
from __future__ import annotations

import json
import os
import argparse
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inbox


def _api(method: str, params: dict, token: str) -> dict:
    """外部通信の唯一の入口。試験ではこの関数を差し替える。"""
    if os.environ.get("HARNESS_TESTING") == "1":
        raise RuntimeError("HARNESS_TESTING=1 では外部通信しません")
    if method == "sendDocument":
        boundary = uuid.uuid4().hex
        path = Path(params["document"])
        thread = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"message_thread_id\"\r\n\r\n{params['message_thread_id']}\r\n"
                  if params.get("message_thread_id") is not None else "")
        data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{params['chat_id']}\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{params['caption']}\r\n"
                + thread + f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{path.name}\"\r\n"
                "Content-Type: text/html\r\n\r\n").encode("utf-8") + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
        request = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=data,
                                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        request = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}",
                                         data=urllib.parse.urlencode(params).encode("utf-8"))
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            result = json.load(response)
    except Exception:
        # 例外の URL に bot token が含まれるので、元の例外を表示しない。
        raise RuntimeError("Telegram API に接続できません") from None
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API: {result.get('description', 'error')}")
    return result


def config_home() -> Path:
    """この機械の全体の置き場（hub.json・全体の telegram.env）。"""
    return Path(os.environ.get("HARNESS_CONFIG_HOME") or Path.home() / ".config/harness")


def _global_env() -> Path:
    return config_home() / "telegram.env"


def configured(loop: Path | None = None) -> bool:
    return ((loop or inbox.loop_dir()) / "telegram.env").exists() or _global_env().exists()


def _config(*, allow_empty_chats: bool = False) -> tuple[str, set[int], Path]:
    loop = inbox.loop_dir()
    config = {}
    local = loop / "telegram.env"
    source = local if local.exists() else _global_env()
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise ValueError("Telegram の設定が無い: .loop/telegram.env または ~/.config/harness/telegram.env。"
                         "cp harness/telegram.env.example ~/.config/harness/telegram.env を打ち、"
                         "TELEGRAM_BOT_TOKEN と TELEGRAM_CHAT_IDS を書く") from None
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip().strip('"\'')
    token = config.get("TELEGRAM_BOT_TOKEN", "")
    chats = {int(s.strip()) for s in config.get("TELEGRAM_CHAT_IDS", "").split(",") if s.strip()}
    if not token or (not chats and not allow_empty_chats):
        raise ValueError("TELEGRAM_BOT_TOKEN と TELEGRAM_CHAT_IDS が必要です")
    return token, chats, loop


def whoami() -> list[dict]:
    """初回の手助け: bot に届いている発言の chat ID と名前を出す（TELEGRAM_CHAT_IDS を決めるため）。token は出さない。"""
    token, _, _ = _config(allow_empty_chats=True)
    me = _api("getMe", {}, token).get("result", {})
    hook = _api("getWebhookInfo", {}, token).get("result", {})
    print(f"bot: @{me.get('username', '?')}（{me.get('first_name', '')}）" + ("  ※ webhook が設定されていて getUpdates が使えません: " + hook.get("url", "") if hook.get("url") else ""))
    result = _api("getUpdates", {"timeout": 0, "allowed_updates": '["message"]'}, token)
    seen: dict[int, dict] = {}
    for update in result.get("result", []):
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if chat.get("id") is not None:
            seen[chat["id"]] = {"chat_id": chat["id"], "type": chat.get("type"), "name": chat.get("first_name") or chat.get("title") or "",
                                "from_id": sender.get("id"), "from": sender.get("first_name") or sender.get("username") or ""}
    return list(seen.values())


def _recipients(chats: set[int], chat_id: int | None) -> list[int]:
    if chat_id is not None and chat_id not in chats:
        try:
            group_id = json.loads((config_home() / "hub.json").read_text(encoding="utf-8")).get("chat_id")
        except (OSError, ValueError):
            group_id = None
        if chat_id != group_id:
            raise ValueError("許可されていない chat ID")
    return [chat_id] if chat_id is not None else sorted(chats)


def send(text: str, *, chat_id: int | None = None, thread_id: int | None = None) -> None:
    token, chats, _ = _config()
    for target in _recipients(chats, chat_id):
        params = {"chat_id": target, "text": text}
        if thread_id is not None:
            params["message_thread_id"] = thread_id
        _api("sendMessage", params, token)


def send_document(path: Path, caption: str, *, chat_id: int | None = None, thread_id: int | None = None) -> None:
    token, chats, _ = _config()
    for target in _recipients(chats, chat_id):
        params = {"chat_id": target, "caption": caption, "document": Path(path)}
        if thread_id is not None:
            params["message_thread_id"] = thread_id
        _api("sendDocument", params, token)


def poll(*, timeout: int = 30) -> list[dict]:
    token, chats, loop = _config()
    offset_path = loop / "telegram.offset"
    offset = int(offset_path.read_text(encoding="utf-8")) if offset_path.exists() else 0
    result = _api("getUpdates", {"offset": offset, "timeout": timeout, "allowed_updates": '["message"]'}, token)
    accepted = []
    for update in result.get("result", []):
        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        if ((message.get("chat") or {}).get("type") == "private"
                and chat_id in chats and (message.get("from") or {}).get("id") in chats
                and isinstance(message.get("text"), str)):
            row = inbox.append(message["text"].replace(token, "[REDACTED]"), loop=loop,
                               chat_id=chat_id, update_id=update["update_id"])
            if row is not None:
                accepted.append(row)
        offset = max(offset, update["update_id"] + 1)
        offset_path.write_text(str(offset), encoding="utf-8")
    return accepted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    send_cmd = sub.add_parser("send")
    send_cmd.add_argument("text")
    poll_cmd = sub.add_parser("poll")
    poll_cmd.add_argument("--timeout", type=int, default=30)
    sub.add_parser("whoami", help="bot に届いた発言の chat ID を出す（初回に TELEGRAM_CHAT_IDS を決めるため）")
    args = parser.parse_args(argv)
    try:
        if args.command == "send":
            send(args.text)
        elif args.command == "whoami":
            rows = whoami()
            if not rows:
                print("まだ発言が届いていません。Telegram で bot を開き、何か 1 通送ってからもう一度打ってください")
            for r in rows:
                print(f"chat_id={r['chat_id']}  type={r['type']}  name={r['name']}  from_id={r['from_id']}  from={r['from']}")
        else:
            if not 0 <= args.timeout <= 30:
                parser.error("--timeout は 0〜30 秒")
            print(f"受信 {len(poll(timeout=args.timeout))} 件")
    except (ValueError, RuntimeError) as error:
        print(str(error).splitlines()[0], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
