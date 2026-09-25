#!/usr/bin/env python3
""".loop の変更と Telegram の返事を、時間を限って見張る。"""
from __future__ import annotations

import argparse
import math
import os
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import dashboard_data
import hub
import inbox
from bridge import telegram


def snapshot(loop: Path) -> tuple[tuple[str, int], ...]:
    paths = [loop / name for name in ("events.jsonl", "judgment/approval_queue.md", "inbox.jsonl")]
    paths += list((loop / "tasks").glob("*/task.md"))
    paths += list((loop / "tasks").glob("*/report-*.md"))
    result = []
    for path in paths:
        try:
            result.append((str(path.relative_to(loop)), path.stat().st_mtime_ns))
        except FileNotFoundError:
            pass
    return tuple(sorted(result))


def status(loop: Path) -> str:
    data = dashboard_data.collect(loop)
    tasks = data["tasks"]
    return (f"[{loop.parent.name}] 依頼: 終了 {sum(t['status'] == '終了' for t in tasks)}件、"
            f"失敗 {sum(t['status'] == '失敗' for t in tasks)}件。"
            f"未回答カード {len(data['cards'])}件、未読 {len(inbox.unread(loop))}件。")


def start_server(loop: Path, address: str) -> ThreadingHTTPServer:
    host, sep, port_text = address.rpartition(":")
    if not sep or not host or not port_text.isdecimal() or int(port_text) > 65535:
        raise ValueError("--serve は <host>:<port> で指定してください")
    if host == "0.0.0.0":
        raise ValueError("私設の網の住所か 127.0.0.1 を指定してください")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            filename = {"/": "index.html", "/index.html": "index.html", "/data.json": "data.json"}.get(self.path)
            if filename is None:
                self.send_error(404)
                return
            try:
                content = (loop / "dashboard" / filename).read_bytes()
            except FileNotFoundError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8" if filename.endswith(".html") else "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer((host, int(port_text)), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def handle_replies(loop: Path, rows: list[dict]) -> None:
    """受信箱に入った返事のうち、合図（/dash /status）にその場で応える。"""
    for row in rows:
        text = row["text"].strip()
        if text == "/dash":
            telegram.send_document(loop / "dashboard/index.html", f"[{loop.parent.name}] ダッシュボード", chat_id=row["chat_id"])
        elif text == "/status":
            telegram.send(status(loop), chat_id=row["chat_id"])


def handle_requests(loop: Path) -> None:
    """hub があるとき: 送信箱の合図（dash / status）に、送信箱へ返事を書いて応える。"""
    for row in inbox.outbox_pending(loop, kinds=("dash", "status")):
        if row["kind"] == "dash":
            inbox.outbox_append({"kind": "document", "path": str(loop / "dashboard/index.html"), "text": "ダッシュボード",
                                 "chat_id": row.get("chat_id")}, loop)
        else:
            inbox.outbox_append({"kind": "text", "text": status(loop), "chat_id": row.get("chat_id")}, loop)
        inbox.outbox_mark(row["id"], loop)


def reply_loop(loop: Path, end: float, stop: threading.Event) -> None:
    """返事だけを別のスレッドで long polling（25 秒）する。画面の描き直し（30 秒ごと）と切り離して、
    返事への応答を数秒にする（9/25、ユーザー:「Bot の返信に時間がかかってる」）。失敗したら 5 秒休んで続ける。"""
    while not stop.is_set() and time.monotonic() < end:
        if hub.attached(loop):   # 受信は hub が行う。ここは送信箱の合図だけ見る
            try:
                handle_requests(loop)
            except Exception as error:
                print(f"送信箱の処理に失敗: {(str(error).splitlines() or [type(error).__name__])[0]}", flush=True)
            stop.wait(2)
            continue
        if not telegram.configured(loop):
            stop.wait(5)
            continue
        try:
            handle_replies(loop, telegram.poll(timeout=25))
        except Exception as error:
            print(f"Telegram 受信失敗: {(str(error).splitlines() or [type(error).__name__])[0]}", flush=True)
            stop.wait(5)


def watch(loop: Path, *, interval: float, hours: float, once: bool = False,
          digest_minutes: float = 10) -> None:
    if once:
        dashboard_data.refresh(loop)
        return
    end = time.monotonic() + hours * 3600
    stop = threading.Event()
    threaded = os.environ.get("HARNESS_TESTING") != "1"   # 試験は偽の poll を本線で 1 回ずつ呼ぶ
    if threaded:
        threading.Thread(target=reply_loop, args=(loop, end, stop), daemon=True).start()
    previous = None
    last_digest = None
    last_sent = -float("inf")
    while time.monotonic() < end:
        current = snapshot(loop)
        if current != previous:
            dashboard_data.refresh(loop)
            previous = current
            via_hub = hub.attached(loop)
            if (via_hub or telegram.configured(loop)) and digest_minutes > 0:
                digest = status(loop)
                now = time.monotonic()
                if digest != last_digest and now - last_sent >= digest_minutes * 60:
                    try:
                        if via_hub:
                            inbox.outbox_append({"kind": "text", "text": digest}, loop)
                        else:
                            telegram.send(digest)
                        last_digest, last_sent = digest, now
                    except Exception as error:
                        print(f"Telegram 送信失敗: {(str(error).splitlines() or [type(error).__name__])[0]}")
        if not threaded and hub.attached(loop):
            handle_requests(loop)
        elif not threaded and telegram.configured(loop):
            try:
                handle_replies(loop, telegram.poll(timeout=0))
            except Exception as error:
                print(f"Telegram 受信失敗: {(str(error).splitlines() or [type(error).__name__])[0]}")
        remaining = end - time.monotonic()
        if remaining > 0:
            time.sleep(min(interval, remaining))
    stop.set()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=30, help="確認する間隔（秒、既定 30）")
    parser.add_argument("--hours", type=float, default=8, help="上限時間（時間、既定 8）")
    parser.add_argument("--once", action="store_true", help="1 回作り直して終わる")
    parser.add_argument("--digest-minutes", type=float, default=10, help="要点の最短間隔（分、0 で停止）")
    parser.add_argument("--serve", help="私設の網の <host>:<port> で画面を配る")
    args = parser.parse_args()
    if not all(math.isfinite(value) and value > 0 for value in (args.interval, args.hours)):
        parser.error("--interval と --hours は正の数にしてください")
    if not math.isfinite(args.digest_minutes) or args.digest_minutes < 0:
        parser.error("--digest-minutes は 0 以上にしてください")
    loop = inbox.loop_dir()
    try:
        server = start_server(loop, args.serve) if args.serve else None
    except (ValueError, OSError) as error:
        print(str(error).splitlines()[0])
        return 1
    if server:
        print(f"http://{args.serve.rpartition(':')[0]}:{server.server_port}/ で配っています（同じ私設の網の中だけ）", flush=True)
    print("ダッシュボードの見張りを開始します", flush=True)
    try:
        watch(loop, interval=args.interval, hours=args.hours, once=args.once, digest_minutes=args.digest_minutes)
    except KeyboardInterrupt:
        pass
    finally:
        if server:
            server.shutdown()
            server.server_close()
        print("ダッシュボードの見張りを終了します", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
