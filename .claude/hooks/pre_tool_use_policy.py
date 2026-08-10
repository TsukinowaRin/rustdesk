#!/usr/bin/env python3

from __future__ import annotations

import sys
import pathlib


def _load_shared_module() -> None:
    project_root = pathlib.Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root / ".agent-shared"))


def main() -> int:
    _load_shared_module()
    from hooks_core import emit_codex_deny, emit_grok_deny, evaluate_tool_use, load_payload

    payload = load_payload()
    is_grok = "toolName" in payload or "toolInput" in payload
    tool_name = payload.get("tool_name") or payload.get("toolName") or ""
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    reason = evaluate_tool_use(tool_name, tool_input)
    if reason:
        if is_grok:
            return emit_grok_deny(reason)
        return emit_codex_deny(reason)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
