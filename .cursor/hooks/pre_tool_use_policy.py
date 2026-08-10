#!/usr/bin/env python3

from __future__ import annotations

import pathlib
import sys


def _load_shared_module() -> None:
    project_root = pathlib.Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root / ".agent-shared"))


def main() -> int:
    _load_shared_module()
    from hooks_core import emit_cursor_deny, evaluate_tool_use, load_payload

    # Cursor は他 CLI と違い tool_name を渡さず、event ごとに payload の形が変わる。
    # beforeShellExecution は command を、beforeReadFile は file path 系の key を含む
    # ため、command の有無で shell 検査と read 検査に振り分ける。key 名の揺れは
    # hooks_core 側の _extract_command / _extract_path が吸収する。
    payload = load_payload()
    command = payload.get("command") or payload.get("cmd")
    if command:
        reason = evaluate_tool_use("Bash", {"command": str(command)})
    else:
        reason = evaluate_tool_use("Read", payload)

    if reason:
        return emit_cursor_deny(reason)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
