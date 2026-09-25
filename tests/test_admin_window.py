#!/usr/bin/env python3
"""管理者の窓の試験。断る形を確かめる（実際に管理者になる実行はしない）。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
bad: list[str] = []
count = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global count
    count += 1
    if not cond:
        bad.append(f"{name} :: {detail[-200:]}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        def run(*args: str) -> tuple[int, str]:
            env = dict(os.environ, HARNESS_LOOP_DIR=tmp)
            # --dry-run を必ず付ける（試験が本物の同意の窓を出さないため）
            r = subprocess.run([sys.executable, "-B", str(ROOT / "harness" / "admin_window.py"), "--dry-run", *args],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
            return r.returncode, r.stdout + r.stderr

        # 連結・展開・入力の転送を断る（旧版の sudo 窓から引き継いだ決まり）
        for cmd, why in ((["id", ";", "whoami"], "連結"), (["id", "|", "tee"], "縦棒"),
                         (["echo", "$HOME"], "変数の展開"), (["cat", "/etc/hosts", ">", "/tmp/x"], "書き出し"),
                         (["id", "&&", "id"], "連結 2"), (["ls", "*.txt"], "展開"), (["id", "`", "x"], "逆引用符")):
            code, out = run("--why", "試験", "--", *cmd)
            check(f"{why}を断る", code == 2 and "記号" in out, out)
        for shell in (["sh", "-c"], ["bash"], ["powershell.exe"], ["python3", "x.py"], ["xargs", "rm"]):
            code, out = run("--why", "試験", "--", *shell)
            check(f"{shell[0]} を断る（中で何でもできるため）", code == 2 and "使えません" in out, out)
        code, out = run("--why", "試験", "--", "-la")
        check("旗から始まる命令を断る", code == 2, out)
        code, out = run("--why", "試験")
        check("命令が無ければ断る", code == 2, out)
        code, out = run("--", "id")
        check("理由が無ければ断る", code == 2 and "--why" in out, out)
        code, out = run("--why", "試験", "--", "id", "x" * 5000)
        check("長すぎる命令を断る", code == 2, out)
        # 通る形（実行はしない: 通る命令であることだけ確かめる）
        sys.path.insert(0, str(ROOT / "harness"))
        import admin_window
        check("普通の命令は通す", admin_window.check(["systemctl", "restart", "nginx"]) == ["systemctl", "restart", "nginx"])
        check("OS に合わせて練習の命令を持つ", set(admin_window.DEMO) == {"windows", "posix"})
        src = (ROOT / "harness" / "admin_window.py").read_text(encoding="utf-8")
        check("sudo は認証を保存しない（-k）", '"sudo", "-k"' in src, src[:0])
        check("Windows は UAC（RunAs）に任せる", "-Verb RunAs" in src)
        check("パスワードを受け取る口を自分で持たない", "getpass" not in src and "password" not in src.lower())
        # Windows の組み立て（実行はしない）
        ps = admin_window.windows_script(["net", "localgroup", "Users"], "C:\\out.txt")
        check("昇格と出力の取り出しを同時に指定しない（PowerShell が断る組み合わせ）",
              "-Verb RunAs" in ps and "-RedirectStandardOutput" not in ps, ps[:200])
        check("失敗しても終了値 0 にしない", "exit 1" in ps and "$p.ExitCode" in ps, ps[:200])
        check("渡した語を引用符で包む", "''net'' ''localgroup'' ''Users''" in ps, ps[:300])
        check("引用符を含む語を閉じ込める", "''" in admin_window.windows_script(["a'b"], "C:\\o.txt"))
        ps2 = admin_window.windows_script(["Add-LocalGroupMember", "-Group", "Hyper-V Administrators"], "C:\\o.txt")
        check("旗（-Group）は名前として渡す（引用符で包まない）", "''Add-LocalGroupMember'' -Group ''Hyper-V Administrators''" in ps2, ps2[:300])
        check("cmdlet の失敗も終了値に出す（try/catch）", "catch {" in ps2 and "exit 1" in ps2)
        # 記録
        code, out = run("--why", "試験", "--", "systemctl", "restart", "nginx")
        check("普通の命令は通ると言う", code == 0 and "通る形です" in out, out)
        code, out = run("--why", "試験", "--", "id", ";")
        log = Path(tmp) / "admin-window.jsonl"
        check("断ったときは記録しない", not log.exists() or "id" not in log.read_text(encoding="utf-8"))
    for b in bad:
        print("NG  " + b)
    print(f"管理者の窓の試験: {count} 場面、ずれ {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
