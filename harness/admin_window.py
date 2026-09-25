#!/usr/bin/env python3
"""管理者の権限で命令を 1 つ実行する。パスワードも同意もエージェントを通さない。

  python3 harness/admin_window.py --why "<なぜ要るか>" -- <命令> [引数...]
  python3 harness/admin_window.py --demo              練習（危なくない命令で通り道だけ確かめる）

なぜ要るか: エージェントが管理者の命令を提示して、人がそれを別の端末へ写す運用は危ない。
写す途中で中身が変わっても気づけないし、パスワードの扱いが人任せになる。この道具は、
**命令をエージェントが渡し、資格の確認は OS に任せ、結果だけをエージェントへ返す。**

OS ごとの違い（実物に合わせる。同じに見せかけない）:
  Windows … UAC。`Start-Process -Verb RunAs` で OS が同意を求める。多くの場合パスワードは要らない
  macOS / Linux … `sudo`。**端末でパスワードを打つ**（UAC のような仕組みは無い）。
                   この道具は自分の端末で `sudo -k` を 1 回だけ走らせ、認証を保存しない

守り（旧版の sudo 窓から引き継いだ決まり）:
  - 受け取るのは**命令 1 つだけ**。`;` `&&` `|` `>` `$` などの記号があれば断る（連結・展開・入力の転送を防ぐ）
  - 認証を保存しない（`sudo -k`）
  - エージェントが受け取るのは、標準出力・標準エラー・終了値だけ。パスワードは通らない
  - 何を実行したかを .loop/admin-window.jsonl に残す（中身ではなく、命令と結果）

実測で踏んだ落とし穴（2026-09-20、Windows 11 Pro）:
  - `-Verb RunAs`（昇格）と `-RedirectStandardOutput`（出力の取り出し）は**同時に指定できない**。
    昇格した側の中でファイルへ書く
  - PowerShell の命令（cmdlet）は `$LASTEXITCODE` を設定しない。前の成功が残り、**失敗を 0 と誤報**する。
    try/catch で捕まえて終了値にする
  - 旗（`-Group` など）を引用符で包むと「ただの文字列」として渡り、名前として効かない
  - 出力の文字コードが既定だと UTF-16 と UTF-8 が混ざる。`Out-File -Encoding utf8` でそろえる
  - Windows の利用者名で駄目なときは SID（`(Get-LocalUser -Name x).SID.Value`）で指す
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 命令をつなげたり、中身を展開したりできる記号。1 つでもあれば断る
SHELL_DECORATION = frozenset(";|&><$`(){}*?!#\n\r[]~'\"")  # \ / : は Windows の path と利用者名に要るので通す
DEMO = {"windows": ["cmd", "/c", "whoami"], "posix": ["id"]}
# shell を管理者で起動すると、その中で何でもできる。「命令 1 つ」の決まりが意味を失うので断る
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "csh", "tcsh", "cmd", "cmd.exe",
          "powershell", "powershell.exe", "pwsh", "pwsh.exe", "wsl", "wsl.exe",
          "env", "eval", "xargs", "nohup", "setsid", "script", "python", "python3", "node", "perl", "ruby"}


def die(msg: str) -> "NoReturn":  # noqa: F821
    print(f"admin_window: {msg}", file=sys.stderr)
    raise SystemExit(2)


def check(words: list[str]) -> list[str]:
    if not words:
        die("実行する命令がありません")
    joined = " ".join(words)
    if len(joined) > 4096:
        die("命令が長すぎます")
    bad = sorted(set(joined) & SHELL_DECORATION)
    if bad:
        die(f"この窓は命令 1 つだけを受け取ります。使えない記号: {' '.join(bad)}"
            "（連結・展開・入力の転送はできません。必要なら script にして、その script を渡してください）")
    if words[0].startswith("-"):
        die("最初の語は命令の名前にしてください")
    head = os.path.basename(words[0]).lower()
    if head in SHELLS:
        die(f"`{head}` は中で別の命令を動かせるので、この窓では使えません"
            "（管理者で動かしたい処理は script にして、その script の path を渡してください）")
    return words


def log(entry: dict) -> None:
    p = Path(os.environ.get("HARNESS_LOOP_DIR") or ROOT / ".loop")
    p.mkdir(parents=True, exist_ok=True)
    with (p / "admin-window.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().astimezone().isoformat(timespec="seconds"), **entry}, ensure_ascii=False) + "\n")


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def windows_script(words: list[str], out_path: str) -> str:
    """UAC で上げた側が、自分で出力をファイルへ書く形。

    `-Verb RunAs`（昇格）と `-RedirectStandardOutput`（出力の取り出し）は同時に指定できないので、
    昇格した PowerShell の中でリダイレクトする。ここで組み立てる PowerShell は**この道具のもの**で、
    人やエージェントが渡した語ではない（渡せる語は check() が記号も shell も弾いている）。
    """
    # `-Name` のような旗は引用符で包むと「ただの文字列」になり、名前として渡らない。
    # 危なくない形（記号を含まない）の旗だけ、そのまま渡す。
    parts = [w if re.fullmatch(r"-[A-Za-z][A-Za-z0-9-]*", w) else _ps_quote(w) for w in words]
    # cmdlet は $LASTEXITCODE を設定しない。命令が無事に終わったかは try/catch と $? で見る。
    # 出力は必ず UTF-8 で 1 つの形にそろえる（既定だと UTF-16 と UTF-8 が混ざって読めなくなる）
    inner = ("$ErrorActionPreference='Stop'; $global:LASTEXITCODE = 0; try { (& " + " ".join(parts)
             + " 2>&1 | Out-String) | Out-File -FilePath " + _ps_quote(out_path) + " -Encoding utf8; "
             "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; exit 0 } "
             "catch { ($_ | Out-String) | Out-File -FilePath " + _ps_quote(out_path) + " -Append -Encoding utf8; exit 1 }")
    return ("$ErrorActionPreference='Stop'; try { "
            "$p = Start-Process -Verb RunAs -Wait -PassThru -FilePath 'powershell' -ArgumentList "
            "@('-NoProfile','-ExecutionPolicy','Bypass','-Command'," + _ps_quote(inner) + "); "
            "if ($null -eq $p) { exit 1 }; exit $p.ExitCode } "
            "catch { Write-Output ('起動できませんでした: ' + $_.Exception.Message); exit 1 }")


def run_windows(words: list[str], why: str, timeout: int) -> int:
    """UAC に任せる。パスワードは（求められるとしても）OS のダイアログが受け取る。"""
    out = Path(os.environ.get("HARNESS_LOOP_DIR") or ROOT / ".loop") / "admin-window-out.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("", encoding="utf-8")
    win_out = subprocess.run(["wslpath", "-w", str(out)], capture_output=True, text=True).stdout.strip() or str(out)
    print(f"\n── 管理者の窓（Windows）──\n理由: {why}\n命令: {' '.join(words)}\n"
          "画面に UAC の同意を求める窓が出ます。内容を読んで、よければ「はい」を押してください。\n", flush=True)
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", windows_script(words, win_out)],
                           timeout=timeout, capture_output=True, text=True, encoding="utf-8", errors="replace")
        code = r.returncode
        if r.stdout.strip():
            print(r.stdout.strip())
    except subprocess.TimeoutExpired:
        code = 124
    raw = out.read_bytes() if out.exists() else b""
    for enc in ("utf-8-sig", "utf-16", "cp932"):
        try:
            text = raw.decode(enc).strip()
            if text and "\x00" not in text:
                break
        except UnicodeDecodeError:
            text = ""
    else:
        text = raw.decode("utf-8", errors="replace").strip()
    if text:
        print("--- 実行した側の出力 ---\n" + text)
    return code


def run_posix(words: list[str], why: str, timeout: int) -> int:
    """sudo。パスワードはこの端末が直接受け取る（エージェントのプロセスは読めない）。"""
    print(f"\n── 管理者の窓（{platform.system()}）──\n理由: {why}\n命令: sudo {' '.join(words)}\n"
          "この端末でパスワードを聞かれます。打った文字は表示されず、エージェントにも渡りません。\n"
          "（macOS と Linux には Windows の UAC のような画面はありません）\n", flush=True)
    # -k: 前の認証を使わず、この 1 回の認証も保存しない
    try:
        r = subprocess.run(["sudo", "-k", "--", *words], timeout=timeout)
        return r.returncode
    except FileNotFoundError:
        die("sudo が見つかりません")
    except subprocess.TimeoutExpired:
        return 124


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="管理者の権限で命令を 1 つ実行する")
    ap.add_argument("--why", default="", help="なぜ管理者の権限が要るか（人が読んで判断する）")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--demo", action="store_true", help="危なくない命令で通り道だけ確かめる")
    ap.add_argument("--dry-run", action="store_true", help="断るかどうかだけ見る（実行も同意の窓も出さない）")
    ap.add_argument("command", nargs="*", help="実行する命令（-- のあと）")
    a = ap.parse_args(argv)
    windows = platform.system() == "Windows" or (
        Path("/proc/version").exists() and "microsoft" in Path("/proc/version").read_text().lower())
    if a.demo:
        words, why = DEMO["windows" if windows else "posix"], "練習（この窓が通るかを確かめるだけ）"
    else:
        words, why = check(list(a.command)), a.why.strip()
        if not why:
            die("--why に「なぜ管理者の権限が要るか」を書いてください（人が読んで決めます）")
    if a.dry_run:
        print("通る形です: " + " ".join(words) + f"\n（{'Windows: UAC の同意' if windows else 'sudo: この端末でパスワード'} を求めます）")
        return 0
    code = run_windows(words, why, a.timeout) if windows else run_posix(words, why, a.timeout)
    log({"os": "windows(uac)" if windows else platform.system().lower() + "(sudo)",
         "command": words, "why": why, "exit": code})
    print(f"\n終了値: {code}" + ("（うまくいきました）" if code == 0 else "（失敗、または同意されませんでした）"))
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
