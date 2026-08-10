#!/usr/bin/env python3
"""Windows / Linux / macOS で通知音付きのデスクトップ通知を出す。"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


WINDOWS_NOTIFY_TIMEOUT_SECONDS = 8
WINDOWS_TOAST_COMPILE_TIMEOUT_SECONDS = 8
WINDOWS_TOAST_RUN_TIMEOUT_SECONDS = 8
WINDOWS_MESSAGE_TIMEOUT_SECONDS = 8
WINDOWS_MESSAGE_VISIBLE_SECONDS = 5

WINDOWS_SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$title = $env:HARNESS_NOTIFY_TITLE
$message = $env:HARNESS_NOTIFY_MESSAGE
if ([string]::IsNullOrWhiteSpace($title) -or [string]::IsNullOrWhiteSpace($message)) {
  throw 'notification title/message was not passed to PowerShell'
}
$notify.BalloonTipTitle = $title
$notify.BalloonTipText = $message
$notify.Visible = $true
[System.Media.SystemSounds]::Asterisk.Play()
$notify.ShowBalloonTip(3000)
Start-Sleep -Milliseconds 3500
$notify.Dispose()
""".strip()


def is_wsl() -> bool:
    return sys.platform.startswith("linux") and "microsoft" in platform.release().lower()


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def windows_command() -> list[str] | None:
    if is_wsl():
        wrapper = Path(__file__).resolve().with_name("win_pwsh.sh")
        return [str(wrapper), WINDOWS_SCRIPT] if wrapper.is_file() else None
    for command in ("pwsh", "powershell"):
        if command_exists(command):
            return [command, "-NoProfile", "-NonInteractive", "-Command", WINDOWS_SCRIPT]
    return None


def windows_message_command(title: str, message: str) -> list[str] | None:
    for command in ("msg.exe", "msg"):
        if command_exists(command):
            # msg.exe receives one argv for the text. Do not route user input through cmd.exe.
            return [
                command,
                "*",
                f"/TIME:{WINDOWS_MESSAGE_VISIBLE_SECONDS}",
                f"{title}: {message}",
            ]
    return None


def run_command(
    command: list[str], *, env: dict[str, str] | None = None, timeout: int
) -> bool:
    try:
        return (
            subprocess.run(command, env=env, timeout=timeout, check=False).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


def capture_command(command: list[str], *, timeout: int) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output if output else None


def windows_directory() -> Path | None:
    if not is_wsl():
        value = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
        return Path(value) if value else None
    value = capture_command(
        ["cmd.exe", "/d", "/c", "echo", "%WINDIR%"], timeout=4
    )
    if value is None:
        return None
    wsl_value = capture_command(["wslpath", "-u", value], timeout=4)
    return Path(wsl_value) if wsl_value else None


def windows_temp_directory() -> Path | None:
    if not is_wsl():
        return None  # tempfile uses the native Windows temp directory.
    value = capture_command(
        ["cmd.exe", "/d", "/c", "echo", "%TEMP%"], timeout=4
    )
    if value is None:
        return None
    wsl_value = capture_command(["wslpath", "-u", value], timeout=4)
    return Path(wsl_value) if wsl_value else None


def windows_path(path: Path) -> str | None:
    if not is_wsl():
        return str(path)
    return capture_command(["wslpath", "-w", str(path)], timeout=4)


def windows_csc_command() -> str | None:
    direct = shutil.which("csc.exe") or shutil.which("csc")
    if direct:
        return direct
    root = windows_directory()
    if root is None:
        return None
    for framework in ("Framework64", "Framework"):
        candidate = root / "Microsoft.NET" / framework / "v4.0.30319" / "csc.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def run_windows_toast(title: str, message: str) -> bool:
    # The helper deliberately borrows Windows Terminal's registered notification
    # identity. If Terminal or the inbox compiler is absent, use the normal fallback.
    if not command_exists("wt.exe"):
        return False
    compiler = windows_csc_command()
    source = Path(__file__).resolve().with_name("windows_toast.cs")
    if compiler is None or not source.is_file():
        return False
    temp_root = windows_temp_directory()
    if is_wsl() and temp_root is None:
        return False
    try:
        with tempfile.TemporaryDirectory(
            prefix="agent-harness-toast-", dir=temp_root
        ) as temp_name:
            executable = Path(temp_name) / "agent-harness-toast.exe"
            source_arg = windows_path(source)
            output_arg = windows_path(executable)
            if source_arg is None or output_arg is None:
                return False
            if not run_command(
                [
                    compiler,
                    "/nologo",
                    "/target:exe",
                    f"/out:{output_arg}",
                    source_arg,
                ],
                timeout=WINDOWS_TOAST_COMPILE_TIMEOUT_SECONDS,
            ):
                return False
            return run_command(
                [str(executable), title, message],
                timeout=WINDOWS_TOAST_RUN_TIMEOUT_SECONDS,
            )
    except OSError:
        return False


def run_windows_message(title: str, message: str) -> bool:
    command = windows_message_command(title, message)
    if command is None:
        return False
    return run_command(command, timeout=WINDOWS_MESSAGE_TIMEOUT_SECONDS)


def run_windows(title: str, message: str) -> bool:
    if run_windows_toast(title, message):
        return True

    # PowerShell launched through WSL can hang before its script starts. Keep the WSL
    # fallback PowerShell-free; msg.exe remains useful when toast prerequisites are absent.
    if is_wsl():
        return run_windows_message(title, message)

    command = windows_command()
    if command is not None:
        env = os.environ.copy()
        env["HARNESS_NOTIFY_TITLE"] = title
        env["HARNESS_NOTIFY_MESSAGE"] = message
        if run_command(command, env=env, timeout=WINDOWS_NOTIFY_TIMEOUT_SECONDS):
            return True

    # Native Windows reaches this path when toast and PowerShell are unavailable.
    return run_windows_message(title, message)


def run_macos(title: str, message: str) -> bool:
    if not command_exists("osascript"):
        return False
    script = 'on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"\nend run'
    return subprocess.run(["osascript", "-e", script, "--", title, message], check=False).returncode == 0


def play_linux_sound() -> bool:
    if command_exists("canberra-gtk-play"):
        if subprocess.run(["canberra-gtk-play", "-i", "complete"], check=False).returncode == 0:
            return True
    sound = Path("/usr/share/sounds/freedesktop/stereo/complete.oga")
    if sound.is_file() and command_exists("paplay"):
        if subprocess.run(["paplay", str(sound)], check=False).returncode == 0:
            return True
    sys.stderr.write("\a")
    sys.stderr.flush()
    return True


def run_linux(title: str, message: str) -> bool:
    delivered = False
    if command_exists("notify-send"):
        delivered = subprocess.run(
            ["notify-send", "--app-name", "Agent Harness", "--", title, message], check=False
        ).returncode == 0
    sounded = play_linux_sound()
    return delivered or sounded


def backend_name() -> str:
    if sys.platform == "win32" or is_wsl():
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    return "terminal"


def notify(title: str, message: str) -> bool:
    backend = backend_name()
    if backend == "windows":
        delivered = run_windows(title, message)
    elif backend == "macos":
        delivered = run_macos(title, message)
    elif backend == "linux":
        delivered = run_linux(title, message)
    else:
        delivered = False
    if not delivered:
        sys.stderr.write(f"\a{title}: {message}\n")
        sys.stderr.flush()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="OS 標準機能で通知音付き通知を出す")
    parser.add_argument("message", nargs="?", default="作業が完了しました")
    parser.add_argument("--title", default="Agent Harness")
    parser.add_argument("--dry-run", action="store_true", help="通知せず選択される backend を表示する")
    args = parser.parse_args()
    if args.dry_run:
        print(f"backend: {backend_name()}")
        return 0
    return 0 if notify(args.title, args.message) else 1


if __name__ == "__main__":
    raise SystemExit(main())
