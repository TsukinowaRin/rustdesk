#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import pathlib
import sys


def _load_shared_module() -> None:
    project_root = pathlib.Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root / ".agent-shared"))


def main() -> int:
    _load_shared_module()
    from hooks_core import emit_antigravity_deny, evaluate_tool_use, load_payload

    payload = load_payload()
    tool_call = payload.get("toolCall", {})
    if tool_call.get("name") in {"invoke_subagent", "define_subagent"}:
        # Antigravityにはsubagent無効化flagがない。対話時は毎回確認し、runnerが
        # HARNESS_UNATTENDEDを付けた無人実行では確認待ちにせずfail-closedで拒否する。
        unattended = os.environ.get("HARNESS_UNATTENDED") == "1"
        print(json.dumps({
            "decision": "deny" if unattended else "force_ask",
            "reason": (
                "unattended harnessではsubagent再委任を禁止しています"
                if unattended
                else "subagent起動は使用量を増やすため、人間の明示承認が必要です"
            ),
        }, ensure_ascii=False))
        return 0
    reason = evaluate_tool_use(tool_call.get("name", ""), tool_call.get("args", {}))
    if reason:
        return emit_antigravity_deny(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
