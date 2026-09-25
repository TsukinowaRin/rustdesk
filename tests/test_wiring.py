#!/usr/bin/env python3
"""9 本の CLI の配線の試験。正本 harness/clis.json と各設定ファイルを突き合わせる（CLI は起動しない）。"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
bad: list[str] = []
count = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global count
    count += 1
    if not cond:
        bad.append(f"{name} :: {detail[-300:]}")


def main() -> int:
    clis = json.loads((ROOT / "harness" / "clis.json").read_text(encoding="utf-8"))["clis"]
    check("対応する CLI は 9 本", len(clis) == 9, str(list(clis)))
    for name, c in clis.items():
        p = ROOT / c["guard_config"]
        check(f"{name}: 設定ファイルがある", p.exists(), str(p))
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        needle = c["must_contain"]
        check(f"{name}: 守り（guard.py）を dialect={c['dialect']} で呼んでいる",
              needle in text or json.dumps(needle)[1:-1] in text, needle)
        if p.suffix == ".json":
            try:
                json.loads(text)
                ok = True
            except ValueError:
                ok = False
            check(f"{name}: JSON として読める", ok)
        if p.suffix == ".toml":
            try:
                tomllib.loads(text)
                ok = True
            except tomllib.TOMLDecodeError:
                ok = False
            check(f"{name}: TOML として読める", ok)
        check(f"{name}: dialect は guard.py が知っている形", c["dialect"] in ("claude", "cursor", "agy", "plain"))
    # CLI ごとの落とし穴（実測で分かったもの）
    grok = (ROOT / ".grok/hooks/guard.json").read_text(encoding="utf-8")
    vars_ = set(re.findall(r"\$\{?([A-Za-z_]+)", grok))
    check("grok: command の変数は既定値つきの 1 つだけ（未設定の変数があると素通りになる）", vars_ == {"GROK_WORKSPACE_ROOT"} and "${GROK_WORKSPACE_ROOT:-.}" in grok, str(vars_))
    cursor = json.loads((ROOT / ".cursor/hooks.json").read_text(encoding="utf-8"))["hooks"]
    guard_scenes = {"beforeShellExecution", "beforeReadFile", "preToolUse", "subagentStart"}
    check("cursor: 守りの 4 つの場面すべてで failClosed", guard_scenes <= set(cursor)
          and all(cursor[k][0].get("failClosed") is True for k in guard_scenes))
    check("cursor: sessionStart は setup.py auto を呼び、失敗しても会話を止めない（failClosed 無し）",
          "setup.py" in cursor.get("sessionStart", [{}])[0].get("command", "") and cursor["sessionStart"][0].get("failClosed") is not True)
    codex = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))
    check("codex: hooks を有効にし、標準の子エージェントを切る", codex["features"] == {"hooks": True, "multi_agent": False})
    check("agy: 起動の形に --add-dir {root} が入っている（無いと hook も AGENTS.md も読まれない）", clis["agy"]["headless"][1:3] == ["--add-dir", "{root}"])
    check("dsh: 起動の形は harness/dsh.sh 経由", clis["dsh"]["headless"][:2] == ["bash", "harness/dsh.sh"])
    # JS の橋: 守りが見つからない場所では止める側へ倒れる
    js = ('import("' + (ROOT / "harness/guard_bridge.mjs").as_posix() + '").then(m=>console.log(JSON.stringify(['
          'm.judge("bash",{command:"ls"},"' + ROOT.as_posix() + '"),m.judge("bash",{command:"ls"},"/"),m.judge("task",{},"' + ROOT.as_posix() + '")])))')
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    if r.returncode == 0:
        a, b, c3 = json.loads(r.stdout)
        check("橋: 普通の命令は通す", a["action"] == "allow", r.stdout)
        check("橋: 守りが見つからない場所では止める", b["action"] == "deny", r.stdout)
        check("橋: 標準の子エージェントは止める", c3["action"] == "deny", r.stdout)
    else:
        print("（node が無いので橋の試験は飛ばしました）")
    for b_ in bad:
        print("NG  " + b_)
    print(f"配線の試験: {count} 場面、ずれ {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
