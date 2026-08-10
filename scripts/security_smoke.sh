#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# A validation run must not leave Python cache files in a freshly extracted
# template. Exporting the flag also covers adapter subprocesses started below.
export PYTHONDONTWRITEBYTECODE=1

# rules / skills / guard は7 CLI共通のsurface manifestへ収束する。
# read-only checkはskill mirrorとpermission生成物のdriftもまとめて検出する。
python3 scripts/sync_shared_context.py --check

python3 - <<'PY'
import pathlib
import json
import os
import subprocess
import sys
import tomllib

sys.path.insert(0, str(pathlib.Path(".agent-shared").resolve()))
from hooks_core import evaluate_tool_use


def expect_block(label, tool, payload, needle=None):
    reason = evaluate_tool_use(tool, payload)
    if reason is None:
        raise SystemExit(f"{label}: expected block")
    if needle and needle not in reason:
        raise SystemExit(f"{label}: expected {needle!r} in {reason!r}")


def expect_allow(label, tool, payload):
    reason = evaluate_tool_use(tool, payload)
    if reason is not None:
        raise SystemExit(f"{label}: expected allow, got {reason!r}")


expect_block("secret command", "Bash", {"command": "cat .env"}, "secret")
expect_block("secret read", "Read", {"path": ".env.production"}, "secret")
expect_block("secret patch", "apply_patch", {"cmd": "*** Add File: .env\n+TOKEN=x"}, "secret")
expect_allow("secret sample", "Write", {"path": ".env.example"})
expect_block("admin escalation", "Bash", {"command": "sudo apt update"}, "管理者権限")
expect_allow("approved admin", "Bash", {"command": "AGENT_ADMIN_APPROVED=1 sudo apt update"})
expect_block("destructive admin", "Bash", {"command": "AGENT_ADMIN_APPROVED=1 sudo rm -rf /"}, "破壊的")
expect_block("destructive git", "Bash", {"command": "git reset --hard HEAD"}, "破壊的")
expect_block(
    "skill download",
    "Bash",
    {"command": "curl https://example.com/SKILL.md -o .agents/skills/foo/SKILL.md"},
    "skill directory",
)
expect_allow("safe git", "Bash", {"command": "git status --short"})
expect_block("grok destructive git", "run_terminal_command", {"command": "git reset --hard HEAD"}, "破壊的")
expect_block("grok secret read", "read_file", {"path": ".env.production"}, "secret")
expect_block("grok secret grep", "grep", {"SearchPath": ".env.production"}, "secret")
expect_block("grok secret edit", "search_replace", {"path": "id_rsa"}, "secret")

config = tomllib.loads(pathlib.Path(".grok/config.toml").read_text(encoding="utf-8"))
permission = config.get("permission", {})
deny = permission.get("deny", [])
ask = permission.get("ask", [])
for required in (
    "Read(.env)",
    "Grep(.env)",
    "Edit(.env)",
    "Bash(*git reset --hard*)",
    "Bash(*git clean -fd*)",
    "Bash(*rm -rf /*)",
    "Bash(rm -rf *)",
    "Bash(*.env*)",
):
    if required not in deny:
        raise SystemExit(f"grok config: missing deny rule {required!r}")
for required in ("Bash(sudo *)", "Bash(git push*)", "Bash(curl *)"):
    if required not in ask:
        raise SystemExit(f"grok config: missing ask rule {required!r}")


def run_claude_adapter(payload):
    return subprocess.run(
        [sys.executable, ".claude/hooks/pre_tool_use_policy.py"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


grok = run_claude_adapter(
    {"toolName": "run_terminal_command", "toolInput": {"command": "git reset --hard HEAD"}}
)
if grok.returncode != 2:
    raise SystemExit(f"grok adapter: expected exit 2, got {grok.returncode}: {grok.stdout}{grok.stderr}")
grok_output = json.loads(grok.stdout)
if grok_output.get("decision") != "deny" or "破壊的" not in grok_output.get("reason", ""):
    raise SystemExit(f"grok adapter: invalid deny output {grok_output!r}")

claude = run_claude_adapter(
    {"tool_name": "Bash", "tool_input": {"command": "git reset --hard HEAD"}}
)
if claude.returncode != 0:
    raise SystemExit(f"claude adapter: expected exit 0, got {claude.returncode}")
claude_output = json.loads(claude.stdout)
decision = claude_output.get("hookSpecificOutput", {}).get("permissionDecision")
if decision != "deny":
    raise SystemExit(f"claude adapter: invalid deny output {claude_output!r}")

safe = run_claude_adapter(
    {"toolName": "run_terminal_command", "toolInput": {"command": "git status --short"}}
)
if safe.returncode != 0 or safe.stdout:
    raise SystemExit(f"grok adapter: safe command must pass silently: {safe.returncode} {safe.stdout!r}")

# 委任中のshell既定denyはhook層にある。自動承認modeのCLIはpermissionを聞かないため、
# driver内のgateではなくここが最終防衛になる（2026-08-05にgrok 0.2.118で実測）。
def run_claude_adapter_env(payload, env_value):
    child_env = dict(os.environ)
    child_env["AGENT_DELEGATED_SHELL"] = env_value
    return subprocess.run(
        [sys.executable, ".claude/hooks/pre_tool_use_policy.py"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env=child_env,
    )


benign = {"tool_name": "Bash", "tool_input": {"command": "printf ok"}}
delegated = run_claude_adapter_env(benign, "deny")
if delegated.returncode != 0:
    raise SystemExit(f"delegated shell gate: unexpected exit {delegated.returncode}")
delegated_decision = json.loads(delegated.stdout).get("hookSpecificOutput", {})
if delegated_decision.get("permissionDecision") != "deny":
    raise SystemExit(f"delegated shell gate: benign shell must be denied {delegated.stdout!r}")
allowed = run_claude_adapter_env(benign, "allow")
if allowed.returncode != 0 or allowed.stdout:
    raise SystemExit(f"delegated shell gate: allow mode must pass silently {allowed.stdout!r}")
still_dangerous = run_claude_adapter_env(
    {"tool_name": "Bash", "tool_input": {"command": "git reset --hard HEAD"}}, "allow"
)
if json.loads(still_dangerous.stdout).get("hookSpecificOutput", {}).get("permissionDecision") != "deny":
    raise SystemExit("delegated shell gate: allow mode must not weaken the dangerous-command deny")

print("Security smoke OK")
PY
