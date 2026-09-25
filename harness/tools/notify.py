#!/usr/bin/env python3
"""Windows / Linux / macOS で通知音付きのデスクトップ通知を出す。

  python3 harness/tools/notify.py --title "<題>" "<本文>"

旧版（v3.0.x の scripts/notify.py）から引き継いだ。旧版の守り（hooks_core）には依存しない。
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


# 既定値の単一の出どころ。テスト側で数値を書き直すと、実装を変えても気付けない
# （2026-08-20 の review で、まさにその状態を指摘された）。
DEFAULT_MIN_INTERVAL_SECONDS = 30
DEFAULT_MAX_PER_HOUR = 20

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
    # WSL からは呼ばない。環境変数は WSL から Windows プロセスへ渡らないため
    # （2026-08-18 に実測: title/message とも空で届く）、この env 経由の script は
    # ネイティブ Windows でしか成立しない。WSL 側は toast / msg.exe 経路を使う。
    if is_wsl():
        return None
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
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    # text=True にすると Python が stdout と stderr の両方を UTF-8 として読む。
    # Windows 側の道具は cp932 の警告を stderr へ出すことがあり、2026-09-14 には
    # その 0x8f で UnicodeDecodeError になって通知そのものが落ちた。受け取りは
    # bytes にして、使う stdout だけ読めない部分を置き換えながら文字にする。
    # stderr は文字にせず、通知の本文へも写さない（Windows の警告を人へ流さない）。
    output = result.stdout.decode("utf-8", errors="replace").strip()
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
        # 最後の手段として端末へ BEL とテキストを出す。ただしこれは「OS 通知が
        # 出せなかった」ことを意味するので、成功として返さない。常に True を返すと
        # 呼出側が失敗を exit code で検知できず、通知が出ていないことに気付けない。
        sys.stderr.write(f"\a{title}: {message}\n")
        sys.stderr.flush()
    return delivered


def throttle_state_path() -> Path:
    # gitignore 済みの .loop/ に置く。repo 外へは書かない。
    # HARNESS_NOTIFY_STATE は fixture 用。実運用で使う想定ではない。
    override = os.environ.get("HARNESS_NOTIFY_STATE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / ".loop" / "notify-state.json"


def notifications_disabled() -> str | None:
    """鳴らさない理由を返す（鳴らしてよいなら None）。

    HARNESS_TESTING は HARNESS_NOTIFY より強い。テストが通知を出さないことを、
    テスト作者の規律ではなく env の優先順位で保証する。
    """
    if os.environ.get("HARNESS_TESTING") == "1":
        return "HARNESS_TESTING=1"
    if os.environ.get("HARNESS_NOTIFY") == "0":
        return "HARNESS_NOTIFY=0"
    return None


@contextlib.contextmanager
def state_lock(path: Path):
    """状態ファイルの読み書きを1プロセスずつに直列化する。

    2026-08-19 の事故: 抑制判定を「起動した子プロセス側」に置いたため、同時に
    何十個も起動したとき全員が「まだ鳴っていない」と読んで全員が鳴った。
    判定と記録を同じ lock の中で行い、鳴らす前に枠を予約することで防ぐ。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    handle = lock_path.open("a+")
    try:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            # lock が使えない環境では抑制を保証できない。鳴らさない側に倒す。
            raise RuntimeError("notify state lock unavailable")
        yield
    finally:
        handle.close()


def reserve_slot(min_interval: float, max_per_hour: int) -> str | None:
    """鳴らしてよければ枠を予約して None を返す。抑えるなら理由を返す。

    予約は「鳴らす前」に行う。鳴らしたあとに記録すると、送信中に来た別プロセスが
    すり抜ける。送信に失敗しても予約は戻さない（戻すと失敗時に連打できてしまう）。
    """
    path = throttle_state_path()
    now = time.time()

    try:
        with state_lock(path):
            state = {}
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    state = loaded
            except (OSError, ValueError):
                state = {}

            # title 別にすると題名を変えるだけで上限を回避できるので、全体で1つ数える。
            recent = [v for v in state.get("recent", []) if isinstance(v, (int, float)) and now - v < 3600]

            if max_per_hour > 0 and len(recent) >= max_per_hour:
                return f"1時間あたりの上限({max_per_hour}回)に達しています"

            last = max(recent) if recent else None
            if min_interval > 0 and last is not None and now - last < min_interval:
                return f"前回の通知から{min_interval:.0f}秒たっていません"

            recent.append(now)
            state["recent"] = recent[-max(max_per_hour, 1) * 2 :]
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(state), encoding="utf-8")
            os.replace(tmp, path)
    except (RuntimeError, OSError) as exc:
        # 状態を確実に扱えないなら鳴らさない。鳴らし続けるより静かな方が安全。
        return f"抑制状態を扱えません: {exc}"

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="OS 標準機能で通知音付き通知を出す")
    parser.add_argument("message", nargs="?", default="作業が完了しました")
    parser.add_argument("--title", default="Agent Harness")
    parser.add_argument("--dry-run", action="store_true", help="通知せず選択される backend を表示する")
    parser.add_argument(
        "--min-interval",
        type=float,
        default=float(os.environ.get("HARNESS_NOTIFY_MIN_INTERVAL", str(DEFAULT_MIN_INTERVAL_SECONDS))),
        help="前回の通知からこの秒数が経つまで鳴らさない（既定 30）",
    )
    parser.add_argument(
        "--max-per-hour",
        type=int,
        default=int(os.environ.get("HARNESS_NOTIFY_MAX_PER_HOUR", str(DEFAULT_MAX_PER_HOUR))),
        help="1時間あたりの上限。0 で無制限（推奨しない）",
    )
    args = parser.parse_args()
    if args.dry_run:
        print(f"backend: {backend_name()}")
        return 0

    disabled = notifications_disabled()
    if disabled:
        print(f"通知は無効です（{disabled}）", file=sys.stderr)
        return 0

    suppressed = reserve_slot(args.min_interval, args.max_per_hour)
    if suppressed:
        print(f"通知を抑制しました（{suppressed}）", file=sys.stderr)
        return 0

    return 0 if notify(args.title, args.message) else 1


if __name__ == "__main__":
    raise SystemExit(main())
