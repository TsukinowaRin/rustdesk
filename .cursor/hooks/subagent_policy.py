#!/usr/bin/env python3

"""Cursorの自動subagent起動をproject境界で拒否する。"""

from __future__ import annotations

import json
import sys


def main() -> int:
    # JSONを読めない場合は非ゼロにし、hooks.jsonのfailClosedで起動を止める。
    payload = json.load(sys.stdin)
    subagent_type = payload.get("subagent_type", "unknown")
    print(json.dumps({
        "permission": "deny",
        "user_message": (
            f"subagent '{subagent_type}' はproject policyで無効です。"
            "明示的な並列作業はscripts/agent_mailbox.pyで別CLIへ配送してください。"
        ),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
