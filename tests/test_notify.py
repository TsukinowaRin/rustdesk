#!/usr/bin/env python3
"""通知の試験。送らずに、引数の組み立てと OS の見分けだけを確かめる。"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "tools"))
import notify  # noqa: E402

bad: list[str] = []
count = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global count
    count += 1
    if not cond:
        bad.append(f"{name} :: {detail[-200:]}")


def backend(platform: str, release: str) -> str:
    with mock.patch.object(notify.sys, "platform", platform), mock.patch.object(notify.platform, "release", lambda: release):
        return notify.backend_name()


def main() -> int:
    # OS の見分け
    check("WSL は windows", backend("linux", "6.18.33.2-microsoft-standard-WSL2") == "windows")
    check("素の Linux は linux", backend("linux", "6.8.0-generic") == "linux")
    check("Windows は windows", backend("win32", "11") == "windows")
    check("macOS は macos", backend("darwin", "24.0") == "macos")
    check("知らない OS は terminal", backend("freebsd14", "14.0") == "terminal")

    # 引数の組み立て（cmd.exe を通さず、本文は 1 つの引数で渡す）
    with mock.patch.object(notify, "command_exists", lambda c: c == "msg.exe"):
        cmd = notify.windows_message_command("題", "本文 & del x")
    check("msg.exe は本文を 1 引数で渡す", cmd == ["msg.exe", "*", "/TIME:5", "題: 本文 & del x"], str(cmd))
    with mock.patch.object(notify, "command_exists", lambda c: False):
        check("msg.exe が無ければ None", notify.windows_message_command("a", "b") is None)
    with mock.patch.object(notify, "is_wsl", lambda: True):
        check("WSL からは env 渡しの PowerShell を使わない", notify.windows_command() is None)
    with mock.patch.object(notify, "is_wsl", lambda: False), mock.patch.object(notify, "command_exists", lambda c: c == "pwsh"):
        cmd = notify.windows_command()
    check("Windows では pwsh を -NoProfile で起動する", bool(cmd) and cmd[:3] == ["pwsh", "-NoProfile", "-NonInteractive"], str(cmd))
    check("本文を script に埋め込まない（env で渡す）", bool(cmd) and "$env:HARNESS_NOTIFY_TITLE" in cmd[-1])
    check("toast の元が道具の隣にある", (ROOT / "harness" / "tools" / "windows_toast.cs").is_file())

    # 送らない決まり: 試験中は鳴らさない。抑制の状態は使い捨ての場所へ
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, HARNESS_TESTING="1", HARNESS_NOTIFY_STATE=str(Path(tmp) / "s.json"))
        r = subprocess.run([sys.executable, "-B", str(ROOT / "harness" / "tools" / "notify.py"), "--title", "t", "m"],
                           capture_output=True, text=True, env=env, timeout=30)
        check("HARNESS_TESTING=1 なら送らず 0 で終わる", r.returncode == 0 and "HARNESS_TESTING=1" in r.stderr, r.stderr)
        check("送らないときは抑制の状態も書かない", not (Path(tmp) / "s.json").exists())
        with mock.patch.dict(os.environ, {"HARNESS_NOTIFY_STATE": str(Path(tmp) / "t.json")}):
            first = notify.reserve_slot(30, 20)
            second = notify.reserve_slot(30, 20)
        check("1 回目は枠が取れる", first is None, str(first))
        check("30 秒以内の 2 回目は抑える", second is not None and "30秒" in second, str(second))
    check("抑制の状態は repo の .loop/ に置く", notify.throttle_state_path() == ROOT / ".loop" / "notify-state.json"
          or "HARNESS_NOTIFY_STATE" in os.environ)

    for b in bad:
        print("NG  " + b)
    print(f"通知の試験: {count} 場面、ずれ {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
