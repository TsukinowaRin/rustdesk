#!/usr/bin/env python3
""".loop の材料を、この案件の画面が読める JSON にする。"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import inbox
import judgment

ROOT = Path(__file__).resolve().parents[1]


def _events(loop: Path) -> list[dict]:
    p = loop / "events.jsonl"
    out = []
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    out.append(row)
            except ValueError:
                continue
    return out


def _cards(loop: Path) -> list[dict]:
    p = judgment.cards_home(loop) / "approval_queue.md"
    if not p.exists():
        return []
    return [{"id": title.split()[0], "text": body.strip()}
            for title, body in judgment.open_cards(p.parent)]


def _summary(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"(?ms)^## 何をした\s*\n(.*?)(?=^## |\Z)", text)
    return " ".join(re.findall(r"(?m)^- (.+)$", m.group(1)))[:400] if m else ""


def collect(loop: Path | None = None) -> dict:
    loop = loop or inbox.loop_dir()
    events = _events(loop)
    latest = {}
    for e in events:
        if e.get("task") and e.get("member"):
            latest[(e["task"], e["member"])] = e
    costs: dict[str, int | None] = {}
    tasks = []
    for d in sorted((loop / "tasks").glob("*/task.md")):
        tid = d.parent.name
        body = d.read_text(encoding="utf-8", errors="replace")
        member = re.search(r"(?m)^member:\s*(\S+)", body)
        name = member.group(1) if member else ""
        title = re.search(r"(?m)^# (.+)$", body)
        related = [(mem, e) for (task, mem), e in latest.items() if task == tid]
        if not related:
            related = [(name, {})]
        for mem, e in related:
            tokens = e.get("tokens") if e.get("event") == "end" else None
            if mem:
                costs[mem] = (costs.get(mem) or 0) + tokens if tokens is not None else costs.get(mem)
            tasks.append({"id": tid, "title": title.group(1) if title else "", "member": mem,
                          "status": "実行中" if e.get("event") == "start" else ("終了" if e.get("exit") == 0 else "失敗") if e else "未着手",
                          "seconds": e.get("seconds"), "tokens": tokens,
                          "summary": _summary(d.parent / f"report-{mem}.md")})
    return {"tasks": tasks, "cards": _cards(loop),
            "inbox": inbox.all_rows(loop), "costs": costs}


def refresh(loop: Path | None = None) -> None:
    loop = loop or inbox.loop_dir()
    output = loop / "dashboard" / "data.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(collect(loop), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    build = loop / "dashboard" / "build"
    if build.exists():
        subprocess.run([str(build), str(output.resolve()), str((output.parent / "index.html").resolve())], cwd=ROOT, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", type=Path)
    args = ap.parse_args()
    text = json.dumps(collect(), ensure_ascii=False, indent=2) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
