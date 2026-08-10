#!/usr/bin/env python3

from __future__ import annotations

import pathlib
import sys


def _load_shared_module() -> None:
    project_root = pathlib.Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root / ".agent-shared"))


def main() -> int:
    _load_shared_module()
    from hooks_core import emit_codex_deny, evaluate_tool_use, load_payload

    payload = load_payload()
    reason = evaluate_tool_use(payload.get("tool_name", ""), payload.get("tool_input", {}))
    if reason:
        return emit_codex_deny(reason)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
