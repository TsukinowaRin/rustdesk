#!/usr/bin/env python3

from __future__ import annotations

import os
import pathlib
import re


DANGEROUS_COMMAND_PATTERNS = [
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-fd\b",
    r"\brm\s+-rf\s+/\b",
    r"\bsudo\s+rm\s+-rf\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
]

ADMIN_ESCALATION_PATTERNS = [
    r"\bsudo\b",
    r"\bdoas\b",
    r"\bpkexec\b",
    r"\brunas\b",
    r"\bstart-process\b[\s\S]*\b-verb\s+runas\b",
]

SECRET_FILE_BASENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".npmrc",
    "id_rsa",
    "known_hosts",
    "credentials",
}

SECRET_PATH_PATTERNS = [
    r"(^|[ /])\.env($|[ .])",
    r"(^|[ /])\.env\.[A-Za-z0-9_-]+($|[ .])",
    r"\bid_rsa\b",
    r"\baws/credentials\b",
    r"\.pem\b",
    r"\.p12\b",
]

SECRET_SUFFIXES = (".pem", ".p12", ".key")
ALLOWED_SECRET_EXAMPLES = (".env.example", ".env.sample", ".env.template")

SHELL_TOOL_NAMES = {"Bash", "run_shell_command", "run_command", "run_terminal_command"}
APPLY_PATCH_TOOL_NAMES = {"apply_patch"}
READ_TOOL_NAMES = {"Read", "view_file", "read_file", "hashline_read", "grep", "hashline_grep"}
WRITE_TOOL_NAMES = {
    "Edit",
    "Write",
    "write_file",
    "replace",
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
    "search_replace",
    "hashline_edit",
}
SKILL_DIRECTORY_HINTS = (".agents/skills", ".claude/skills")
SKILL_DOWNLOAD_PATTERNS = [
    r"\bcurl\b",
    r"\bwget\b",
    r"\bgit\s+clone\b",
    r"\bgh\s+repo\s+clone\b",
]

# 委任セッションの shell 既定 deny を hook 層へ置くための env var。
# 承認プロンプトを自動承認する mode（grok の permission_mode = "always-approve" 等）では
# CLI が client へ permission を聞かないため、driver 側の gate が動かない。hook は自動承認でも
# 発火することを実測したので（2026-08-05, grok 0.2.118）、shell の可否はここで判定する。
DELEGATED_SHELL_ENV = "AGENT_DELEGATED_SHELL"

ADMIN_APPROVAL_PATTERNS = [
    r"(^|\s)AGENT_ADMIN_APPROVED=1(\s|$)",
    r"\$env:AGENT_ADMIN_APPROVED\s*=\s*['\"]?1['\"]?",
]


def _is_allowed_secret_example(value: str) -> bool:
    lowered = value.lower()
    return any(example in lowered for example in ALLOWED_SECRET_EXAMPLES)


def _extract_command(tool_input: dict) -> str:
    return str(tool_input.get("command") or tool_input.get("cmd") or tool_input.get("CommandLine") or "")


def _extract_path(tool_input: dict) -> str:
    candidates = [
        tool_input.get("file_path"),
        tool_input.get("path"),
        tool_input.get("target_file"),
        tool_input.get("target"),
        tool_input.get("AbsolutePath"),
        tool_input.get("TargetFile"),
        tool_input.get("DirectoryPath"),
        tool_input.get("SearchPath"),
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return ""


def _has_admin_approval_marker(command: str) -> bool:
    return any(re.search(pattern, command, flags=re.IGNORECASE) for pattern in ADMIN_APPROVAL_PATTERNS)


def _command_violation(command: str) -> str | None:
    lowered = command.lower()

    for pattern in DANGEROUS_COMMAND_PATTERNS:
        if re.search(pattern, lowered):
            return "破壊的な shell コマンドはデフォルトで禁止です。必要ならユーザー確認を取ってください。"

    for pattern in ADMIN_ESCALATION_PATTERNS:
        if re.search(pattern, lowered) and not _has_admin_approval_marker(command):
            return (
                "管理者権限の使用は毎回ユーザーの明示許可が必要です。"
                "目的、変更対象、rollback / recovery、失敗判定、検証方法を説明し、"
                "ユーザーが直前に OK した場合だけ AGENT_ADMIN_APPROVED=1 を付けて再実行してください。"
            )

    if any(skill_dir in lowered for skill_dir in SKILL_DIRECTORY_HINTS):
        for pattern in SKILL_DOWNLOAD_PATTERNS:
            if re.search(pattern, lowered):
                return "skill directory への外部ダウンロードは避け、`.agents/skills/local-skill-bootstrap/` で local skill を作成してください。"

    if not _is_allowed_secret_example(lowered):
        for pattern in SECRET_PATH_PATTERNS:
            if re.search(pattern, lowered):
                return "secret の可能性が高いファイルへのアクセスを禁止しました。sample や mask 済みの代替を使ってください。"

    return None


def _path_violation(path_value: str, action: str = "編集") -> str | None:
    if not path_value:
        return None

    lowered = path_value.lower()
    if _is_allowed_secret_example(lowered):
        return None

    basename = pathlib.Path(path_value).name
    if basename in SECRET_FILE_BASENAMES or basename.endswith(SECRET_SUFFIXES):
        return f"secret の可能性が高いファイルの{action}を禁止しました。example / sample だけを扱ってください。"

    return None


def _patch_violation(patch_value: str) -> str | None:
    for line in patch_value.splitlines():
        if line.startswith(("*** Add File: ", "*** Update File: ", "*** Delete File: ")):
            reason = _path_violation(line.split(": ", 1)[1])
            if reason:
                return reason
        if line.startswith("*** Move to: "):
            reason = _path_violation(line.split(": ", 1)[1])
            if reason:
                return reason

    return None


def _delegated_shell_violation() -> str | None:
    mode = os.environ.get(DELEGATED_SHELL_ENV, "").strip().lower()
    if mode in {"", "allow"}:
        return None
    return (
        "委任セッションでの shell 実行は既定で禁止です"
        f"（{DELEGATED_SHELL_ENV}={mode}）。"
        "shell が必要な作業は、依頼元が明示的に許可した委任でだけ実行してください。"
    )


def evaluate_tool_use(tool_name: str, tool_input: dict) -> str | None:
    if tool_name in SHELL_TOOL_NAMES:
        return _delegated_shell_violation() or _command_violation(_extract_command(tool_input))

    if tool_name in APPLY_PATCH_TOOL_NAMES:
        return _patch_violation(_extract_command(tool_input))

    if tool_name in READ_TOOL_NAMES:
        return _path_violation(_extract_path(tool_input), "読み取り")

    if tool_name in WRITE_TOOL_NAMES:
        return _path_violation(_extract_path(tool_input))

    return None
