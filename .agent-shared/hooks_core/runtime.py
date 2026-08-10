#!/usr/bin/env python3

from __future__ import annotations

import json
import sys


def load_payload() -> dict:
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else {}


def emit_codex_deny(reason: str) -> int:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    return 0


def emit_grok_deny(reason: str) -> int:
    # Grok project hooks use camelCase input and a small decision schema. Exit 2
    # is intentional: Grok accepts the JSON reason and treats the hook as a
    # blocking decision even if a future build stops parsing stdout.
    json.dump({"decision": "deny", "reason": reason}, sys.stdout)
    return 2


def emit_antigravity_deny(reason: str) -> int:
    json.dump({"decision": "deny", "reason": reason}, sys.stdout)
    return 0


def emit_cursor_deny(reason: str) -> int:
    # Cursor hooks は exit code 2 でもブロックできるが、JSON の permission deny は
    # user / agent 両方へ理由を渡せるため、他 CLI adapter と同じ「理由つき deny」に
    # そろえる。schema は cursor.com/docs/agent/hooks の documented 形式。
    json.dump(
        {
            "permission": "deny",
            "userMessage": reason,
            "agentMessage": reason,
        },
        sys.stdout,
    )
    return 0
