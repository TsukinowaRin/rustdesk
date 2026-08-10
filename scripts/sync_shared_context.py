#!/usr/bin/env python3
"""全7 CLIの共有rules・skills・guardを生成またはread-only検査する。"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import tomllib


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / ".agent-shared" / "context-surfaces.json"
EXPECTED_CLIS = {
    "claude",
    "codex",
    "antigravity",
    "cursor",
    "opencode",
    "kilo",
    "grok",
}
EXPECTED_CLAUDE_MIRROR = ".claude/skills"
EXPECTED_PERMISSION_TARGETS = {
    "opencode": "opencode.jsonc",
    "kilo": "kilo.jsonc",
}


def run_helper(script_name: str, *args: str) -> bool:
    command = [sys.executable, str(REPO_ROOT / "scripts" / script_name), *args]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    output = completed.stdout + completed.stderr
    if output.strip():
        print(output.rstrip())
    return completed.returncode == 0


def read_jsonc(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    stripped = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    return json.loads(stripped)


def first_nonempty_line(path: pathlib.Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            return line.strip()
    return ""


def require_path(relative: str, kind: str, problems: list[str]) -> pathlib.Path:
    path = REPO_ROOT / relative
    exists = path.is_dir() if kind == "dir" else path.is_file()
    if not exists:
        problems.append(f"missing {kind}: {relative}")
    return path


def check_surfaces(manifest: dict) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    rows: list[str] = []
    if manifest.get("version") != 1:
        problems.append("context manifest version must be 1")

    canonical = manifest.get("canonical", {})
    rules_source = canonical.get("rules", "")
    skills_source = canonical.get("skills", "")
    hook_core = canonical.get("hook_core", "")
    permission_source = canonical.get("permissions", "")
    require_path(rules_source, "file", problems)
    require_path(skills_source, "dir", problems)
    hook_core_path = require_path(hook_core, "dir", problems)
    if hook_core_path.is_dir():
        require_path(f"{hook_core}/__init__.py", "file", problems)
        require_path(f"{hook_core}/common.py", "file", problems)
    require_path(permission_source, "file", problems)

    clis = manifest.get("clis", {})
    actual_clis = set(clis)
    if actual_clis != EXPECTED_CLIS:
        missing = ", ".join(sorted(EXPECTED_CLIS - actual_clis)) or "none"
        extra = ", ".join(sorted(actual_clis - EXPECTED_CLIS)) or "none"
        problems.append(f"CLI set mismatch: missing={missing}; extra={extra}")

    for cli in sorted(EXPECTED_CLIS & actual_clis):
        surface = clis[cli]
        rules = surface.get("rules", {})
        skills = surface.get("skills", {})
        guard = surface.get("guard", {})

        rules_mode = rules.get("mode")
        rules_path = rules.get("path", "")
        rules_file = require_path(rules_path, "file", problems)
        if rules_mode == "native":
            if rules_path != rules_source:
                problems.append(f"{cli}: native rules must use {rules_source}")
        elif rules_mode == "import":
            marker = rules.get("marker", "")
            if rules_file.is_file() and first_nonempty_line(rules_file) != marker:
                problems.append(f"{cli}: rules bridge must start with {marker}")
            if marker != f"@{rules_source}":
                problems.append(f"{cli}: rules bridge marker must import {rules_source}")
        else:
            problems.append(f"{cli}: unsupported rules mode {rules_mode!r}")

        skills_mode = skills.get("mode")
        skills_path = skills.get("path", "")
        require_path(skills_path, "dir", problems)
        if skills_mode == "native":
            if skills_path != skills_source:
                problems.append(f"{cli}: native skills must use {skills_source}")
        elif skills_mode == "mirror":
            if cli != "claude" or skills_path != EXPECTED_CLAUDE_MIRROR:
                problems.append(
                    f"{cli}: mirror path must be {EXPECTED_CLAUDE_MIRROR} for Claude"
                )
        else:
            problems.append(f"{cli}: unsupported skills mode {skills_mode!r}")
        if "config" in skills:
            config_path = require_path(skills["config"], "file", problems)
            if config_path.is_file():
                configured = read_jsonc(config_path).get("skills", {}).get("paths", [])
                if skills_source not in configured:
                    problems.append(f"{cli}: config does not include skills path {skills_source}")

        guard_mode = guard.get("mode")
        guard_config = require_path(guard.get("config", ""), "file", problems)
        if guard_mode == "hook_adapter":
            adapter = require_path(guard.get("adapter", ""), "file", problems)
            if adapter.is_file() and "hooks_core" not in adapter.read_text(encoding="utf-8"):
                problems.append(f"{cli}: guard adapter does not import shared hooks_core")
            if guard_config.is_file() and guard.get("adapter", "") not in guard_config.read_text(encoding="utf-8"):
                problems.append(f"{cli}: guard config does not reference adapter")
        elif guard_mode == "generated_permission":
            if guard.get("source") != permission_source:
                problems.append(f"{cli}: generated permission source mismatch")
            if guard.get("config") != EXPECTED_PERMISSION_TARGETS.get(cli):
                problems.append(f"{cli}: generated permission target mismatch")
        elif guard_mode == "native_permission+hook_adapter":
            adapter = require_path(guard.get("adapter", ""), "file", problems)
            hook_config = require_path(guard.get("hook_config", ""), "file", problems)
            if guard_config.is_file() and "permission" not in tomllib.loads(
                guard_config.read_text(encoding="utf-8")
            ):
                problems.append(f"{cli}: native permission block missing")
            if adapter.is_file():
                adapter_text = adapter.read_text(encoding="utf-8")
                if "hooks_core" not in adapter_text or "emit_grok_deny" not in adapter_text:
                    problems.append(f"{cli}: Claude-compatible adapter lacks Grok support")
            if hook_config.is_file() and guard.get("adapter", "") not in hook_config.read_text(encoding="utf-8"):
                problems.append(f"{cli}: hook config does not reference adapter")
        else:
            problems.append(f"{cli}: unsupported guard mode {guard_mode!r}")

        rows.append(
            f"{cli}: rules={rules_mode}; skills={skills_mode}; guard={guard_mode}"
        )

    return problems, rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="生成せず、7 CLIの共有contextとdriftをread-only検査する",
    )
    args = parser.parse_args()

    if not MANIFEST_PATH.is_file():
        print(f"missing context manifest: {MANIFEST_PATH.relative_to(REPO_ROOT)}")
        return 1
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    if not args.check:
        if not run_helper("sync_shared_skills.py"):
            return 1
        if not run_helper("sync_permissions.py"):
            return 1

    helpers_ok = run_helper("sync_shared_skills.py", "--check")
    helpers_ok = run_helper("sync_permissions.py", "--check") and helpers_ok
    problems, rows = check_surfaces(manifest)

    for row in rows:
        print(row)
    if problems:
        print("shared context drift:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    if not helpers_ok:
        return 1

    print("Shared context OK: 7 CLI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
