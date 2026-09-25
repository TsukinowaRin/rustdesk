#!/usr/bin/env python3
"""点検の入口。1 本で全部を見る。落ちたら最後の行に直し方が 1 行出る。

  python3 harness/check.py              点検（形の点検 + tests/ の試験）
  python3 harness/check.py --list       何を見るかの一覧

点検の中身は tests/ の各試験と、下の CHECKS。ここには走らせる仕組みだけ置き、判定を増やすときは
tests/ に場面を 1 行足す。「点検の点検」（壊した複製で落ちるか）は 2026-09-23 にやめた。
維持の費用が高い割に見つけた不具合が 0 で、自分自身が嘘の合格を出していたため（ユーザーの判断）。
"""
from __future__ import annotations

import json
import os
import hashlib
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS_MAX_LINES, AGENTS_MAX_BYTES = 60, 6000
TESTS = ["tests/test_guard.py", "tests/test_wiring.py", "tests/test_judgment.py", "tests/test_setup.py", "tests/test_dsh_launcher.py", "tests/test_delegate.py", "tests/test_admin_window.py", "tests/test_notify.py", "tests/test_dashboard.py", "tests/test_dashboard_round2.py", "tests/test_dashboard_watch.py", "tests/test_hub.py", "tests/test_bridge_discord.py", "tests/test_bridge_slack.py"]


# ---------------------------------------------------------------- 形の点検（1 つ 1 関数。失敗なら直し方の文字列を返す）

def agents_budget(root: Path) -> str | None:
    p = root / "AGENTS.md"
    if not p.exists():
        return "AGENTS.md がありません"
    text = p.read_bytes()
    lines, size = text.count(b"\n"), len(text)
    if lines > AGENTS_MAX_LINES or size > AGENTS_MAX_BYTES:
        return f"AGENTS.md が予算を超えています（{lines} 行 / {size} バイト。上限 {AGENTS_MAX_LINES} 行 / {AGENTS_MAX_BYTES} バイト）。常時読む物を太らせず、skills か docs/ へ移してください"
    return None


def claude_bridge(root: Path) -> str | None:
    p = root / "CLAUDE.md"
    if not p.exists() or "@AGENTS.md" not in p.read_text(encoding="utf-8").splitlines()[0]:
        return "CLAUDE.md の 1 行目は @AGENTS.md（Claude Code は AGENTS.md を直接読まない）"
    return None


def claude_settings(root: Path) -> str | None:
    p = root / ".claude" / "settings.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return f".claude/settings.json が読めません（{e}）。壊れた形だと Claude Code の道具が全部止まります"
    hooks = d.get("hooks", {}).get("PreToolUse", [])
    if not any("harness/guard.py" in h.get("command", "") for m in hooks for h in m.get("hooks", [])):
        return ".claude/settings.json の PreToolUse が harness/guard.py を呼んでいません"
    if "Agent" not in d.get("permissions", {}).get("deny", []):
        return ".claude/settings.json の permissions.deny に Agent がありません（標準の子エージェントは使わない）"
    return None


def codex_settings(root: Path) -> str | None:
    p = root / ".codex" / "config.toml"
    try:
        d = tomllib.loads(p.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        return f".codex/config.toml が読めません（{e}）"
    if d.get("features", {}).get("multi_agent") is not False or d.get("features", {}).get("hooks") is not True:
        return ".codex/config.toml の [features] は hooks = true, multi_agent = false"
    return None


def startup_hooks(root: Path) -> str | None:
    """開始 hook がある CLI は setup.py auto へつながっているか。"""
    checks = (
        (".claude/settings.json", lambda s: any(
            "harness/setup.py" in h.get("command", "") and h["command"].endswith(" auto")
            for m in json.loads(s).get("hooks", {}).get("SessionStart", []) for h in m.get("hooks", []))),
        (".codex/config.toml", lambda s: any(
            "harness/setup.py" in h.get("command", "") and h["command"].endswith(" auto")
            for m in tomllib.loads(s).get("hooks", {}).get("SessionStart", []) for h in m.get("hooks", []))),
        (".cursor/hooks.json", lambda s: any(
            "harness/setup.py" in h.get("command", "") and h["command"].endswith(" auto")
            for h in json.loads(s).get("hooks", {}).get("sessionStart", []))),
        (".opencode/plugins/guard.js", lambda s: all(x in s for x in ("session.created", "execFile", "harness/setup.py", '"auto"'))),
        (".kilo/plugins/guard.js", lambda s: all(x in s for x in ("session.created", "execFile", "harness/setup.py", '"auto"'))),
        (".omp/extensions/guard.ts", lambda s: all(x in s for x in ("session_start", "execFile", "harness/setup.py", '"auto"'))),
        (".dsh/guard.patch.yml", lambda s: "configPath: ./.claude/settings.json" in s),
    )
    for name, valid in checks:
        p = root / name
        if p.exists():
            try:
                if not valid(p.read_text(encoding="utf-8")):
                    return f"{name} の開始 hook が harness/setup.py auto を呼んでいません"
            except (OSError, ValueError, KeyError, tomllib.TOMLDecodeError) as e:
                return f"{name} の開始 hook を読めません（{e}）"
    return None


def vendor_hashes(root: Path) -> str | None:
    v = root / "vendor" / "kagemusha"
    if not (v / "SHA256SUMS").exists():
        return "vendor/kagemusha/SHA256SUMS がありません"
    r = subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=v, capture_output=True, text=True)
    if r.returncode != 0:
        bad = [l.split(":")[0] for l in (r.stdout + r.stderr).splitlines() if ": FAILED" in l or "No such" in l]
        return f"vendor/kagemusha の写しが上流と違います: {bad[:5]}。中は編集しない決まり（UPSTREAM.md）。上流から写し直すか、写し直した上で SHA256SUMS を作り直してください"
    listed = set((v / "FILES.txt").read_text(encoding="utf-8").split("\n")) - {""}
    # __pycache__ は python が勝手に作る物なので数えない（上流の script を動かすと増える）
    on_disk = {str(p.relative_to(v)) for p in v.rglob("*") if p.is_file() and "__pycache__" not in p.parts} - {"FILES.txt", "SHA256SUMS", "UPSTREAM.md"}
    extra = on_disk - listed
    if extra:
        return f"vendor/kagemusha に一覧（FILES.txt）に無いファイルがあります: {sorted(extra)[:5]}"
    return None


def no_secrets_tracked(root: Path) -> str | None:
    r = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True)
    if r.returncode != 0:
        return None  # git が無い展開先では飛ばす
    bad = [f for f in r.stdout.split("\n") if f and (f.startswith(".loop/") or f.endswith((".env", ".pem", ".key")) or "/.env" in f or ".local.patch.yml" in f)]
    if bad:
        return f"git に入れてはいけないファイルが追跡されています: {bad[:5]}（.loop/ は人ごとの設定、鍵は CLI 本体の置き場へ）"
    return None


def skills_reachable(root: Path) -> str | None:
    """全 CLI からスキルが読めるか（写しと設定のずれ）。"""
    r = subprocess.run([sys.executable, "-B", str(root / "harness" / "sync_skills.py"), "--check"],
                       capture_output=True, text=True, cwd=root)
    if r.returncode != 0:
        return "スキルが一部の CLI から読めません: " + " / ".join(l[4:] for l in r.stdout.splitlines() if l.startswith("NG"))[:200] + "。python3 harness/sync_skills.py で直せます"
    return None


def skills_unmodified(root: Path) -> str | None:
    """外から取り込んだスキルが上流のままか（中は編集しない決まり）。"""
    man = root / "harness" / "skills.json"
    if not man.exists():
        return None
    data = json.loads(man.read_text(encoding="utf-8"))["skills"]
    src = root / ".agents" / "skills"
    have = {d.name for d in src.iterdir() if d.is_dir() and (d / "SKILL.md").exists()} if src.exists() else set()
    missing = set(data) - have
    extra = have - set(data)
    if missing or extra:
        return f"スキルの一覧（harness/skills.json）と中身が違います。足りない: {sorted(missing)} / 一覧に無い: {sorted(extra)}"
    for name, e in data.items():
        if not e.get("commit"):
            continue  # 自前のスキルは hash で縛らない（普通に直すため）
        for rel, want in e["sha256"].items():
            p = src / name / rel
            if not p.exists():
                return f"{name}/{rel} がありません（上流の写しです）"
            if hashlib.sha256(p.read_bytes()).hexdigest()[:16] != want:
                return f"{name}/{rel} が上流と違います。外から取り込んだスキルは編集しない決まりです（harness/skills.json）"
    return None


CHECKS = [agents_budget, claude_bridge, claude_settings, codex_settings, startup_hooks, vendor_hashes, no_secrets_tracked,
          skills_reachable, skills_unmodified]


# ---------------------------------------------------------------- 走らせる

def run_checks(root: Path, quiet: bool = False) -> list[str]:
    fails: list[str] = []
    for fn in CHECKS:
        msg = fn(root)
        if msg:
            fails.append(msg)
        elif not quiet:
            print(f"ok  {fn.__name__}")
    env = dict(os.environ, HARNESS_TESTING="1")
    for t in TESTS:
        r = subprocess.run([sys.executable, "-B", str(root / t)], capture_output=True, text=True, cwd=root, env=env)
        last = (r.stdout.strip().splitlines() or ["(出力なし)"])[-1]
        if r.returncode != 0:
            fails.append(f"{t}: {last}。NG の行: " + " / ".join(l for l in r.stdout.splitlines() if l.startswith("NG"))[:400])
        elif not quiet:
            print(f"ok  {last}")
    return fails


def main(argv: list[str]) -> int:
    if "--list" in argv:
        print("形の点検:", [f.__name__ for f in CHECKS])
        print("試験:", TESTS)
        return 0
    fails = run_checks(ROOT)
    if fails:
        for f in fails:
            print("NG  " + f)
        print(f"\n点検が落ちました（{len(fails)} 件）。直し方: {fails[0]}")
        return 1
    print("\n点検が通りました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
