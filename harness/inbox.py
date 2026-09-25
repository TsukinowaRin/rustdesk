#!/usr/bin/env python3
"""返事の追記と既読の記録。本文は常にデータとして扱う。"""
from __future__ import annotations

import json
import os
import re
import uuid
import argparse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def loop_dir() -> Path:
    if os.environ.get("HARNESS_LOOP_DIR"):
        return Path(os.environ["HARNESS_LOOP_DIR"])
    if ROOT.parent.name == "work" and ROOT.parents[1].name == ".loop":
        return ROOT.parents[1]
    return ROOT / ".loop"


def _reference(text: str, loop: Path) -> str | None:
    from judgment import cards_home, open_cards
    names = {p.name for p in (loop / "tasks").iterdir() if p.is_dir()} if (loop / "tasks").exists() else set()
    home = cards_home(loop)
    if (home / "approval_queue.md").exists():
        names.update(title.split()[0] for title, _ in open_cards(home))
    if not names:
        return None
    pattern = re.compile(r"(?<![A-Za-z0-9-])(?:" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?![A-Za-z0-9-])")
    found = pattern.search(text)
    return found.group() if found else None


def _write(row: dict, loop: Path, name: str = "inbox.jsonl") -> None:
    loop.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(loop / name, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def append(text: str, *, loop: Path | None = None, chat_id: int | None = None,
           update_id: int | None = None) -> dict | None:
    loop = loop or loop_dir()
    if update_id is not None and any(r.get("update_id") == update_id for r in all_rows(loop)):
        return None
    text = "".join(c for c in text if c in "\n\t" or ord(c) >= 32 and ord(c) != 127)
    signal = text.strip() in ("/dash", "/status")
    row = {"id": uuid.uuid4().hex, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "text": text, "ref": None if signal else _reference(text, loop), "chat_id": chat_id,
           "update_id": update_id, "read": signal}
    _write(row, loop)
    return row


def all_rows(loop: Path | None = None) -> list[dict]:
    p = (loop or loop_dir()) / "inbox.jsonl"
    rows: dict[str, dict] = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") == "read":
                if row.get("id") in rows:
                    rows[row["id"]]["read"] = True
            elif row.get("id"):
                rows[row["id"]] = row
    return list(rows.values())


def unread(loop: Path | None = None) -> list[dict]:
    return [r for r in all_rows(loop) if not r.get("read")]


def mark_read(row_id: str, loop: Path | None = None) -> None:
    loop = loop or loop_dir()
    rows = {r["id"]: r for r in all_rows(loop)}
    if row_id not in rows:
        raise KeyError(row_id)
    if not rows[row_id].get("read"):
        _write({"type": "read", "id": row_id}, loop)


def outbox_append(row: dict, loop: Path | None = None) -> dict:
    """送信箱（.loop/outbox.jsonl）に 1 行足す。hub が読んで送り、{"type":"sent"} を追記する。"""
    loop = loop or loop_dir()
    row = {"id": uuid.uuid4().hex, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "sent": False, **row}
    _write(row, loop, "outbox.jsonl")
    return row


def outbox_pending(loop: Path | None = None, kinds: tuple[str, ...] = ("text", "document")) -> list[dict]:
    p = (loop or loop_dir()) / "outbox.jsonl"
    rows: dict[str, dict] = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") == "sent":
                rows.pop(row.get("id"), None)
            elif row.get("id") and not row.get("sent") and row.get("kind") in kinds:
                rows[row["id"]] = row
    return list(rows.values())


def outbox_mark(row_id: str, loop: Path | None = None, **extra: object) -> None:
    _write({"type": "sent", "id": row_id, **extra}, loop or loop_dir(), "outbox.jsonl")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("read")
    group = read.add_mutually_exclusive_group(required=True)
    group.add_argument("id", nargs="?")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    try:
        for row_id in ([r["id"] for r in unread()] if args.all else [args.id]):
            mark_read(row_id)
            print(f"既読: {row_id}")
    except KeyError as error:
        parser.error(f"返事がありません: {error.args[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
