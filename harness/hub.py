#!/usr/bin/env python3
"""中継（hub）: Telegram・Discord・画面で複数の作業場を扱う。この機械に 1 本だけ動かす。

受信は hub だけが行い、宛先の作業場の .loop/inbox.jsonl へ振り分ける。
各作業場の見張りは .loop/outbox.jsonl に書き、hub がそれを送る。設計は docs/design/HUB.md。
"""
from __future__ import annotations

import argparse
import hmac
import html
import ipaddress
import json
import math
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inbox
from bridge import discord, slack, telegram

TRANSPORTS = {"telegram": telegram, "discord": discord, "slack": slack}

USAGE = ('~/.config/harness/hub.json が無い。例: {"workspaces": {"harness": {"path": "/abs/path/to/repo"}}, "current": "harness"}'
         "（HARNESS_CONFIG_HOME があればその下）")
LEADER_PROMPT = ("あなたは指示役です。`AGENTS.md` と `leader` skill に従い、この依頼を依頼書にして担い手へ回し、"
                 "報告を読んで採否を決めてください。終わったら要点を 10 行以内で書いてください。依頼: ")
_runs: dict[str, subprocess.Popen] = {}
_runs_lock = threading.Lock()
_route_lock = threading.RLock()


def hub_path() -> Path:
    return telegram.config_home() / "hub.json"


def load() -> dict:
    return json.loads(hub_path().read_text(encoding="utf-8"))


def save(config: dict) -> None:
    tmp = hub_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(hub_path())


def ensure_topics(config: dict, token: str) -> None:
    if not config.get("chat_id"):
        return
    topics = config.setdefault("topics", {})
    for name in config["workspaces"]:
        if name not in topics:
            result = telegram._api("createForumTopic", {"chat_id": config["chat_id"], "name": name}, token)
            topics[name] = result["result"]["message_thread_id"]
            save(config)


def _thread(config: dict, name: str, chat_id: int) -> int | None:
    return (config.get("topics") or {}).get(name) if chat_id == config.get("chat_id") else None


def workspace_loop(config: dict, name: str) -> Path:
    return Path(config["workspaces"][name]["path"]) / ".loop"


def attached(loop: Path) -> str | None:
    """この .loop が hub.json に載っていれば、その作業場の名前を返す（見張りが Telegram に触らない印）。"""
    try:
        config = load()
    except (OSError, ValueError):
        return None
    for name, ws in (config.get("workspaces") or {}).items():
        try:
            if (Path(ws["path"]) / ".loop").resolve() == loop.resolve():
                return name
        except (KeyError, TypeError, OSError):
            continue
    return None


def log(**fields: object) -> None:
    if "text" in fields:
        fields["text"] = str(fields["text"])[:80]
    line = json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields}, ensure_ascii=False) + "\n"
    path = telegram.config_home() / "hub.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def enabled_transports(config: dict) -> list[str]:
    names = list(config.get("transports", {"telegram": {}}))
    if any(name not in TRANSPORTS for name in names):
        raise ValueError("未対応の通信手段が transports にあります")
    return names


def _reply(text: str, *, message: dict, document: Path | None = None) -> None:
    name = message.get("transport", "telegram")
    bridge = TRANSPORTS[name]
    if name == "telegram":
        destination = {"chat_id": message.get("chat_id"), "thread_id": message.get("thread_id")}
    else:
        if not message.get("target"):
            raise ValueError("送信先チャンネルがありません")
        destination = {"target": message["target"], "thread": message.get("thread")}
    if document is None:
        bridge.send(text, **destination)
    else:
        bridge.send_document(document, text, **destination)


def _outbox_destination(config: dict, name: str, row: dict) -> dict:
    """送る先は hub.json（話題・チャンネル・保存した返信先）だけで決める。送信箱の行の宛先の欄は信じない。"""
    ws = config["workspaces"][name]
    if any(key in row for key in ("thread_id", "target", "thread")):
        log(action="ignored-destination", workspace=name, text=row.get("text") or row.get("path") or "")
    transports = enabled_transports(config)
    if not transports:
        raise ValueError("送信箱の通信手段が無効です")
    reply = ws.get("reply_routes", {}).get(str(row.get("chat_id")), ws.get("reply", {}))
    bridge = next((b for b in (row.get("transport"), reply.get("transport")) if b in transports), transports[0])
    if bridge == "telegram":
        chat_id = config.get("chat_id") or row.get("chat_id")   # 個人宛は telegram._recipients が許可した人に限る
        return {"transport": bridge, "chat_id": chat_id, "thread_id": _thread(config, name, chat_id)}
    channel = config["transports"][bridge].get("channels", {}).get(name)
    same = reply.get("transport") == bridge and str(reply.get("target")) == str(channel)
    return {"transport": bridge, "target": channel, "thread": reply.get("thread") if same else None}


def setup_channels() -> None:
    config = load()
    settings = config.get("transports", {}).get("discord")
    if settings is not None:
        guild = settings.get("guild_id") or discord._config().get("DISCORD_GUILD_ID")
        if guild:
            channels = settings.setdefault("channels", {})
            for name in config["workspaces"]:
                if name not in channels:
                    channel = discord._api("POST", f"/guilds/{guild}/channels", {"name": name, "type": 0})
                    channels[name] = str(channel["id"])
                    save(config)
    settings = config.get("transports", {}).get("slack")
    if settings is not None:
        channels = settings.setdefault("channels", {})
        missing = [name for name in config["workspaces"] if name not in channels]
        existing = {}
        cursor = ""
        while missing:
            params = {"types": "public_channel", "limit": 200}
            if cursor:
                params["cursor"] = cursor
            result = slack._api("conversations.list", params)
            existing.update({channel["name"]: channel["id"] for channel in result.get("channels", [])})
            cursor = (result.get("response_metadata") or {}).get("next_cursor") or ""
            if not cursor:
                break
        for name in config["workspaces"]:
            if name not in channels:
                channel_name = slack.channel_name(name)
                channel_id = existing.get(channel_name)
                if channel_id is None:
                    channel_id = slack._api("conversations.create", {"name": channel_name})["channel"]["id"]
                channels[name] = str(channel_id)
                save(config)
            slack._api("conversations.join", {"channel": channels[name]})


def poll_transport(name: str, *, timeout: int = 25) -> int:
    if name == "telegram":
        return poll_once(timeout=timeout)
    count = 0
    for message in TRANSPORTS[name].poll():
        with _route_lock:
            action, target = route(load(), message["text"], transport=name,
                                   **{k: message.get(k) for k in ("chat_id", "update_id", "target", "thread")})
        log(transport=name, chat_id=message["chat_id"], action=action, workspace=target, text=message["text"])
        count += 1
    return count


# ---------------------------------------------------------------- 命令（足すときは COMMANDS に 1 行）

WEB = "web"   # 画面から来た文の送り元の印（chat_id）


def _say(config: dict, target: str, message: dict, text: str) -> None:
    """命令への返事を送り元へ。画面からなら送信箱に書く（画面に出て、Telegram には送らない）。"""
    if message["chat_id"] == WEB:
        inbox.outbox_append({"kind": "note", "text": text, "chat_id": WEB}, workspace_loop(config, target))
    else:
        reply = dict(message)
        if reply.get("transport", "telegram") == "telegram":
            reply["thread_id"] = _thread(config, target, message["chat_id"])
            if reply["thread_id"] is not None:
                text = text.removeprefix(f"[{target}] ")
        _reply(text, message=reply)


def _cmd_ws(config: dict, target: str, args: str, message: dict) -> str:
    if args:
        if args not in config["workspaces"]:
            _say(config, target, message, f"知らない作業場: {args}")
            return "unknown"
        config["current"] = args
        save(config)
        _say(config, args, message, f"今の相手: {args}")
        return "switch"
    lines = [("▶ " if name == config.get("current") else "・") + name for name in config["workspaces"]]
    _say(config, target, message, "作業場:\n" + "\n".join(lines))
    return "list"


def _cmd_signal(config: dict, target: str, args: str, message: dict) -> str:
    inbox.outbox_append({"kind": message["command"][1:], "chat_id": message["chat_id"],
                         "thread_id": _thread(config, target, message["chat_id"])}, workspace_loop(config, target))
    return "signal"


def _leader_argv(spec: dict, root: Path, model: str, prompt: str) -> tuple[list[str], str | None]:
    stdin = prompt if spec.get("prompt") == "stdin" else None
    argv = []
    for token in spec["leader"]:
        if token == "{prompt}":
            if stdin is None:
                argv.append(prompt)
        elif "{model}" in token and not model:
            if argv and argv[-1].startswith("-"):
                argv.pop()
        else:
            argv.append(token.replace("{root}", str(root)).replace("{model}", model)
                        .replace("{timeout}", "28800"))
    return argv, stdin


def _watch_leader(name: str, loop: Path, chat_id: int, thread_id: int | None,
                  process: subprocess.Popen, stdin: str | None, reply: dict | None = None) -> None:
    try:
        output, errors = process.communicate(stdin)
        if process.returncode:
            tail = "\n".join((output + "\n" + errors).splitlines()[-5:])[-1800:]
            result = f"落ちた（exit {process.returncode}）" + (f"\n{tail}" if tail else "")
        else:
            try:
                parsed = json.loads(output)
                result = str(parsed["result"])[-2000:]
            except (ValueError, TypeError, KeyError):
                result = output[-2000:]
        inbox.outbox_append({"kind": "text", "chat_id": chat_id, "text": f"[{name}] {result}",
                             **{k: v for k, v in (reply or {}).items() if k == "transport"}}, loop)
        log(action="run-end", workspace=name, chat_id=chat_id, exit=process.returncode)
    finally:
        with _runs_lock:
            if _runs.get(name) is process:
                del _runs[name]


def _run_seen(update_id: int | str) -> bool:
    """この update_id の /run を既に起動したか（再配送で二度起動しない）。記録は hub.log の action=run。"""
    path = telegram.config_home() / "hub.log"
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("action") == "run" and row.get("update_id") == update_id:
            return True
    return False


def _cmd_run(config: dict, target: str, args: str, message: dict) -> str:
    if message.get("update_id") is not None and _run_seen(message["update_id"]):
        return "duplicate"
    name, space, rest = args.partition(" ")
    if message.get("transport", "telegram") == "telegram" and space and name in config["workspaces"]:
        target, args = name, rest.strip()
    if not args:
        _say(config, target, message, "使い方: /run [<名前>] <依頼の文>")
        return "usage"
    leader = config["workspaces"][target].get("leader") or {}
    cli = leader.get("cli")
    clis = json.loads(Path(os.environ.get("HARNESS_CLIS") or Path(__file__).with_name("clis.json"))
                      .read_text(encoding="utf-8"))["clis"]
    spec = clis.get(cli) or {}
    if not spec.get("leader"):
        _say(config, target, message, f"[{target}] この CLI は指示役の外からの起動に未対応")
        return "unsupported"
    root = Path(config["workspaces"][target]["path"])
    argv, stdin = _leader_argv(spec, root, leader.get("model") or "", LEADER_PROMPT + args)
    env = os.environ.copy()
    for key in ("HARNESS_ROLE", "HARNESS_HANDS", "HARNESS_WORKTREE", "HARNESS_GUARD_EDIT",
                "HARNESS_REPORT", "HARNESS_ATTENDED"):
        env.pop(key, None)
    env["HARNESS_UNATTENDED"] = "1"
    with _runs_lock:
        if target in _runs:
            _say(config, target, message, f"[{target}] 実行中")
            return "running"
        try:
            process = subprocess.Popen(argv, cwd=root, env=env, stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except OSError as error:
            _say(config, target, message, f"[{target}] 起動できません: {error}")
            log(action="run-failed", workspace=target, chat_id=message["chat_id"], text=args)
            return "failed"
        _runs[target] = process
    log(action="run", workspace=target, chat_id=message["chat_id"], update_id=message.get("update_id"), text=args)
    threading.Thread(target=_watch_leader, args=(target, workspace_loop(config, target), message["chat_id"],
                                                  _thread(config, target, message["chat_id"]), process, stdin,
                            {k: message[k] for k in ("transport", "target", "thread") if k in message}),
                     daemon=True).start()
    _say(config, target, message, f"[{target}] 起動しました（作業場 {target}）")
    return "run"


def _cmd_stop(config: dict, target: str, args: str, message: dict) -> str:
    if args and message.get("transport", "telegram") == "telegram":
        if args not in config["workspaces"]:
            _say(config, target, message, f"知らない作業場: {args}")
            return "unknown"
        target = args
    with _runs_lock:
        process = _runs.get(target)
        if process and process.poll() is None:
            process.terminate()
            stopped = True
        else:
            stopped = False
    if stopped:
        _say(config, target, message, f"[{target}] 停止を求めました")
        log(action="stop", workspace=target, chat_id=message["chat_id"])
        return "stop"
    _say(config, target, message, f"[{target}] 実行中の指示役はありません")
    return "idle"


COMMANDS = {"/ws": _cmd_ws, "/dash": _cmd_signal, "/status": _cmd_signal,
            "/run": _cmd_run, "/stop": _cmd_stop}


def route(config: dict, text: str, *, chat_id: int | str, update_id: int | str | None = None,
          thread_id: int | None = None, transport: str = "telegram", target=None, thread=None) -> tuple[str, str | None]:
    """1 通を振り分ける。戻り値は（した事, 宛先の作業場）。"""
    reply = {"transport": transport, "target": target, "thread": thread}
    if transport == "telegram":
        target = next((name for name, topic in (config.get("topics") or {}).items()
                       if chat_id == config.get("chat_id") and topic == thread_id), config.get("current")) if thread_id is not None else config.get("current")
    else:
        channels = config.get("transports", {}).get(transport, {}).get("channels", {})
        target = next((name for name, channel in channels.items() if str(channel) == str(target)), None)
    body = text.strip()
    if transport == "telegram" and body.startswith("@"):
        name, _, body = body[1:].partition(" ")
        target, body = name, body.strip()
    if target not in config["workspaces"]:
        _say(config, target, {"chat_id": chat_id, **reply}, f"知らない作業場: {target}（/ws で一覧）")
        return "unknown", target
    if "transports" in config:
        ws = config["workspaces"][target]
        ws["reply"] = reply
        ws.setdefault("reply_routes", {})[str(chat_id)] = reply
        save(config)
    return receive(config, target, body, chat_id=chat_id, update_id=update_id, reply=reply), target


def receive(config: dict, target: str, body: str, *, chat_id: int | str, update_id: int | str | None = None,
            reply: dict | None = None) -> str:
    """宛先の決まった 1 通を処理する（各橋と画面の共通入口。送り元の印は chat_id）。"""
    command, _, args = body.partition(" ")
    if command in COMMANDS:
        return COMMANDS[command](config, target, args.strip(),
                                 {"chat_id": chat_id, "update_id": update_id, "command": command, **(reply or {})})
    inbox.append(body, loop=workspace_loop(config, target), chat_id=chat_id, update_id=update_id)
    return "inbox"


# ---------------------------------------------------------------- 受信と送信

def _offset_path() -> Path:
    return telegram.config_home() / "hub.offset"


def poll_once(*, timeout: int = 25) -> int:
    token, chats, _ = telegram._config()
    path = _offset_path()
    offset = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    result = telegram._api("getUpdates", {"offset": offset, "timeout": timeout, "allowed_updates": '["message"]'}, token)
    count = 0
    for update in result.get("result", []):
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        text = message.get("text")
        config = load()
        private = chat.get("type") == "private" and chat.get("id") in chats
        group = chat.get("type") == "supergroup" and chat.get("id") == config.get("chat_id")
        forwarded = "is_automatic_forward" in message or any(key.startswith("forward_") for key in message)   # 許可した人の手で運ばれた他人の文は受けない
        if (private or group) and not forwarded and (message.get("from") or {}).get("id") in chats and isinstance(text, str):
            with _route_lock:
                action, target = route(load(), text.replace(token, "[REDACTED]"), chat_id=chat["id"],
                                       update_id=update["update_id"], thread_id=message.get("message_thread_id"))
            log(chat_id=chat["id"], action=action, workspace=target, text=text.replace(token, "[REDACTED]"))
            count += 1
        else:
            log(chat_id=chat.get("id"), action="dropped")
        offset = max(offset, update["update_id"] + 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(offset), encoding="utf-8")
    return count


def flush_outbox() -> int:
    """各作業場の送信箱の未送信の行を送り、印を付ける。通信の失敗は次の回にもう一度。"""
    config = load()
    sent = 0
    for name in config["workspaces"]:
        loop = workspace_loop(config, name)
        for row in inbox.outbox_pending(loop):
            if row.get("chat_id") == WEB:   # 画面から頼まれた返事は画面に出るだけ
                inbox.outbox_mark(row["id"], loop, via=WEB)
                continue
            body = row.get("text") or ""
            text = body.rstrip() if body.startswith(f"[{name}]") else f"[{name}] {body}".rstrip()   # 見張りが付けた名前と二重にしない
            try:
                message = _outbox_destination(config, name, row)
                topic = message["transport"] == "telegram" and message.get("thread_id") is not None
                if topic:
                    text = text.removeprefix(f"[{name}] ")
                if row["kind"] == "document":
                    dashboard = (loop / "dashboard").resolve()   # dir 自体の symlink も解く
                    if (dashboard != Path(config["workspaces"][name]["path"]).resolve() / ".loop" / "dashboard"
                            or not Path(row["path"]).resolve().is_relative_to(dashboard)):
                        raise ValueError("dashboard の外の文書")   # 作業場の外の秘密を送らない
                    _reply(text if row.get("text") else ("ダッシュボード" if topic else f"[{name}] ダッシュボード"),
                           message=message, document=Path(row["path"]))
                else:
                    _reply(text, message=message)
            except RuntimeError as error:
                print(f"送信失敗（後で再送）: {(str(error).splitlines() or [type(error).__name__])[0]}", flush=True)
                return sent
            except (OSError, ValueError, KeyError) as error:
                inbox.outbox_mark(row["id"], loop, error=type(error).__name__)
                log(action="send-failed", workspace=name, text=row.get("text") or row.get("path") or "")
                continue
            inbox.outbox_mark(row["id"], loop)
            log(action="sent", workspace=name, text=row.get("text") or row.get("path") or "")
            sent += 1
    return sent


def _poll_loop(end: float, stop: threading.Event, transport: str = "telegram") -> None:
    while not stop.is_set() and time.monotonic() < end:
        try:
            poll_transport(transport, timeout=25)
            if transport != "telegram":
                stop.wait(3)
        except Exception as error:
            print(f"{transport} 受信失敗: {(str(error).splitlines() or [type(error).__name__])[0]}", flush=True)
            stop.wait(5)


def run(*, hours: float, once: bool = False, telegram_on: bool = True) -> None:
    transports = [name for name in enabled_transports(load()) if name != "telegram" or telegram_on]
    if not transports:   # 画面だけなら外への送信待ちは残す
        if not once:
            time.sleep(hours * 3600)
        return
    setup_channels()
    if once:
        for transport in transports:
            try:   # 1 つの橋が落ちても他の橋は受ける
                poll_transport(transport, timeout=0)
            except Exception as error:
                print(f"{transport} 受信失敗: {(str(error).splitlines() or [type(error).__name__])[0]}", flush=True)
        flush_outbox()
        return
    end = time.monotonic() + hours * 3600
    stop = threading.Event()
    for transport in transports:
        threading.Thread(target=_poll_loop, args=(end, stop, transport), daemon=True).start()
    try:
        while time.monotonic() < end:
            try:
                flush_outbox()
            except Exception as error:
                print(f"送信箱の処理に失敗: {(str(error).splitlines() or [type(error).__name__])[0]}", flush=True)
            time.sleep(2)
    finally:
        stop.set()


# ---------------------------------------------------------------- 画面（通信手段に依らない 1 つの受信箱）

STYLE = ("body{font-family:sans-serif;max-width:40em;margin:auto;padding:1em}"
         ".m{margin:.4em 0;padding:.5em .7em;border-radius:.6em;white-space:pre-wrap;max-width:85%}"
         ".h{background:#d8f0d0;margin-left:auto}.a{background:#eee}.t{font-size:.75em;color:#666}"
         "form{display:flex;gap:.4em;margin-top:.6em}textarea,input[type=text]{flex:1}")
WEB_MAX = 4000   # 画面から受ける本文の上限（字）


def _running(name: str) -> bool:
    with _runs_lock:
        process = _runs.get(name)
        return bool(process and process.poll() is None)


def conversation(loop: Path) -> list[tuple[str, str, str]]:
    """受信箱（人 → AI）と送信箱（AI → 人）を時刻で 1 本に並べる。戻り値は（時刻, "h" か "a", 本文）。"""
    rows = [(r.get("ts") or "", "h", r.get("text") or "") for r in inbox.all_rows(loop)]
    path = loop / "outbox.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("id") and row.get("type") != "sent" and row.get("kind") in ("text", "note", "document"):
                rows.append((row.get("ts") or "", "a", row.get("text") or row.get("path") or ""))
    return sorted(rows, key=lambda r: r[0])


def _page(title: str, body: str) -> bytes:
    return (f'<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            f'<meta http-equiv="refresh" content="15"><title>{html.escape(title)}</title><style>{STYLE}</style>'
            f"<body><h1>{html.escape(title)}</h1>{body}</body></html>").encode("utf-8")


def index_page(config: dict) -> bytes:
    items = []
    for name, ws in config["workspaces"].items():
        loop = workspace_loop(config, name)
        items.append(f'<li><a href="/ws/{quote(name)}">{html.escape(name)}</a> 未読 {len(inbox.unread(loop))}'
                     f'{" ・/run 実行中" if _running(name) else ""}<br><span class="t">{html.escape(str(ws["path"]))}</span></li>')
    return _page("作業場", f"<ul>{''.join(items)}</ul>")


def workspace_page(config: dict, name: str, csrf: str = "") -> bytes:
    lines = "".join(f'<div class="m {side}"><span class="t">{html.escape(ts)}</span>\n{html.escape(text)}</div>'
                    for ts, side, text in conversation(workspace_loop(config, name)))
    action = f"/ws/{quote(name)}/reply"
    token = f'<input type="hidden" name="csrf" value="{html.escape(csrf)}">'
    body = (f'<p><a href="/">← 作業場の一覧</a>{" ・/run 実行中" if _running(name) else ""}</p>{lines or "<p>まだ会話はありません</p>"}'
            f'<form method="post" action="{action}">{token}<textarea name="text" rows="3" maxlength="{WEB_MAX}" required></textarea>'
            f'<button>送る</button></form>'
            f'<form method="post" action="{action}">{token}<input type="text" name="text" value="/run " maxlength="{WEB_MAX}">'
            f'<button>/run</button></form><p class="t">/dash /status /stop も返事の欄から送れます</p>')
    return _page(name, body)


def start_server(address: str) -> ThreadingHTTPServer:
    host, sep, port_text = address.rpartition(":")
    if not sep or not host or not port_text.isdecimal() or int(port_text) > 65535:
        raise ValueError("--serve は <host>:<port> で指定してください")
    for *_, sockaddr in socket.getaddrinfo(host, int(port_text), type=socket.SOCK_STREAM):
        ip = ipaddress.ip_address(sockaddr[0].split("%")[0])
        if ip.is_unspecified or getattr(ip, "ipv4_mapped", None) and ip.ipv4_mapped.is_unspecified:
            raise ValueError("私設の網の住所か 127.0.0.1 を指定してください")   # 全部の網で待ち受けない
    csrf = secrets.token_urlsafe()   # 画面の form に埋める印。起動ごとに 1 回作る

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, content: bytes = b"", location: str | None = None) -> None:
            self.send_response(status)
            if location:
                self.send_header("Location", location)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _workspace(self, path: str) -> tuple[dict, str | None]:
            config = load()
            name = unquote(path[len("/ws/"):]) if path.startswith("/ws/") else None
            return config, name if name in config["workspaces"] else None

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            try:
                if path == "/":
                    self._send(200, index_page(load()))
                    return
                config, name = self._workspace(path)
            except (OSError, ValueError, KeyError):
                self._send(500)
                return
            if name is None:
                self._send(404)
                return
            self._send(200, workspace_page(config, name, csrf))

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            source = self.headers.get("Origin") or self.headers.get("Referer") or ""
            port = self.server.server_address[1]
            served = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
            if not path.endswith("/reply") or urlsplit(source).netloc != served:
                self._send(403)   # --serve で配った画面から来た POST だけ受ける（要求の Host は信じない）
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > WEB_MAX * 12:   # 1 字は URL の符号化で最大 12 バイト
                self._send(413)
                return
            form = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
            if not hmac.compare_digest((form.get("csrf") or [""])[0].encode(), csrf.encode()):
                self._send(403)   # 画面に埋めた印が無い・違う
                return
            text = (form.get("text") or [""])[0].strip()
            if len(text) > WEB_MAX:
                self._send(413)
                return
            try:
                config, name = self._workspace(path[:-len("/reply")])
            except (OSError, ValueError, KeyError):
                self._send(500)
                return
            if name is None:
                self._send(404)
                return
            if text:
                with _route_lock:
                    action = receive(load(), name, text, chat_id=WEB)   # 本文は受信箱か argv へ。shell には渡さない
                log(chat_id=WEB, action=action, workspace=name, text=text)
            self._send(303, location=f"/ws/{quote(name)}")

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer((host, int(port_text)), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=("whoami",))
    parser.add_argument("--hours", type=float, default=8, help="上限時間（時間、既定 8）")
    parser.add_argument("--once", action="store_true", help="1 回受信して送信箱を 1 回送って終わる")
    parser.add_argument("--serve", help="私設の網の <host>:<port> で hub 画面を配る")
    args = parser.parse_args(argv)
    if args.command == "whoami":
        try:
            transports = enabled_transports(load() if hub_path().exists() else {})
            for name in transports:
                if name != "telegram":
                    print(f"[{name}]")
                    for row in TRANSPORTS[name].whoami():
                        print(json.dumps(row, ensure_ascii=False))
            if "telegram" not in transports:
                return 0
            token, _, _ = telegram._config(allow_empty_chats=True)
            me = telegram._api("getMe", {}, token).get("result", {})
            hook = telegram._api("getWebhookInfo", {}, token).get("result", {})
            print(f"bot: @{me.get('username', '?')}（{me.get('first_name', '')}）" +
                  ("  ※ webhook が設定されていて getUpdates が使えません: " + hook["url"] if hook.get("url") else ""))
            updates = telegram._api("getUpdates", {"timeout": 0, "allowed_updates": '["message"]'}, token)
            found = False
            for update in updates.get("result", []):
                message = update.get("message") or {}
                chat = message.get("chat") or {}
                if chat.get("type") == "supergroup":
                    print(f"chat_id={chat['id']}  type=supergroup  name={chat.get('title', '')}  message_thread_id={message.get('message_thread_id')}")
                    found = True
            if not found:
                print("グループの発言がまだ届いていません。グループで /start を送ってからもう一度打ってください")
        except (OSError, ValueError, RuntimeError) as error:
            print(str(error).splitlines()[0], file=sys.stderr)
            return 1
        return 0
    if not math.isfinite(args.hours) or args.hours <= 0:
        parser.error("--hours は正の数にしてください")
    try:
        config = load()
        if not config.get("workspaces"):
            raise ValueError
    except (OSError, ValueError):
        print(USAGE, file=sys.stderr)
        return 1
    try:
        transports = enabled_transports(config)
        for name in transports:
            if name != "telegram":
                TRANSPORTS[name]._config()
    except ValueError as error:
        print(str(error).splitlines()[0], file=sys.stderr)
        return 1
    telegram_on = "telegram" in transports
    try:
        if telegram_on:
            token, _, _ = telegram._config()
    except ValueError as error:
        if not args.serve:
            print(str(error).splitlines()[0], file=sys.stderr)
            return 1
        print("Telegram の設定が無いので、画面だけで動かします", flush=True)
        telegram_on = False
    try:
        server = start_server(args.serve) if args.serve else None
    except (ValueError, OSError) as error:
        print(str(error).splitlines()[0], file=sys.stderr)
        return 1
    if telegram_on and config.get("chat_id"):
        try:
            ensure_topics(config, token)
        except (RuntimeError, KeyError, ValueError) as error:
            print(f"話題を作れません: {str(error).splitlines()[0]}", file=sys.stderr)
            return 1
    elif telegram_on:
        print("グループを作り → 設定でトピックを有効に → bot を管理者（トピックの管理）で追加 → グループで /start → python3 harness/hub.py whoami で chat_id を取り → hub.json に書く")
    print(f"hub を開始します（作業場 {len(config['workspaces'])} 個、今の相手 {config.get('current')}）", flush=True)
    if server:
        print(f"http://{args.serve.rpartition(':')[0]}:{server.server_port}/ で配っています（同じ私設の網の中だけ）", flush=True)
    try:
        run(hours=args.hours, once=args.once, telegram_on=telegram_on)
    except KeyboardInterrupt:
        pass
    except RuntimeError as error:
        print(str(error).splitlines()[0], file=sys.stderr)
        return 1
    finally:
        if server:
            server.shutdown()
            server.server_close()
    print("hub を終了します", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
