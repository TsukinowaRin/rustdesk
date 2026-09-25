#!/usr/bin/env python3
"""初回セットアップ。人に 1 回だけ尋ねて決めることを、ここで記録する（決めたら、もう尋ねない）。

  status                     何が決まっていて、何がまだか（指示役が始めに見る）
  notify off                 スマホへの通知を使わない
  notify skip                この作業場では決めない（例: 配布物を作るための repo）。催促しない
  notify new                 ntfy.sh を使う。題目は機械が乱数で作る（名前が他人と被らない）
  notify existing            既に持っている ntfy の設定を指す（サーバー・題目・トークン）
  notify selfhost            自前のサーバー（Tailscale などの私設の網の中）を指す
  notify test                試しに 1 通送る
  docs-tools                 文書の skill（docx / xlsx / pptx / pdf）が使う python の道具を、版を固定して入れる

題目は実質パスワード（ntfy 公式の説明）。だから題目とトークンは引数で受け取らず、人が端末で直接入れる
（Claude Code なら `! python3 harness/setup.py notify existing`）。会話や log に乗せないため。
保存先 .loop/notify.env は git に入れず、守り（guard.py）の秘密の一覧にも入っている。
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import shutil
import subprocess
import shlex
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cmd_auto(a) -> int:
    """展開先だけを、開始 hook から何度でも初期化できる形にする。"""
    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)

    try:
        top = git("rev-parse", "--show-toplevel")
        if top.returncode != 0 or Path(top.stdout.strip()).resolve() != ROOT:
            if git("init").returncode == 0:
                for key, value in (("user.name", "harness"), ("user.email", "harness@localhost")):
                    if git("config", "--get", key).returncode != 0:
                        git("config", "--local", key, value)
                        print(f"git の {key} をこの作業場だけ仮設定しました。")
                if git("add", "-A").returncode == 0 and git("commit", "-m", "init").returncode == 0:
                    print("この作業場に git の最初の commit を作りました。")
                else:
                    print("git の最初の commit を作れませんでした。")
            else:
                print("git init ができませんでした。")

        work = ROOT / ".loop"
        team = work / "team.json"
        if not team.exists():
            work.mkdir(parents=True, exist_ok=True)
            template = json.loads((ROOT / "harness/team.example.json").read_text(encoding="utf-8"))
            clis = json.loads((ROOT / "harness/clis.json").read_text(encoding="utf-8"))["clis"]
            available = [m for m in template["members"] if shutil.which(clis[m["cli"]]["bin"])]
            if available:
                template["members"] = available
                team.write_text(json.dumps(template, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            else:
                shutil.copyfile(ROOT / "harness/team.example.json", team)
                print("担い手の CLI が見つからないため、編成の雛形をそのまま写しました。")
            print(".loop/team.json を作りました。")
        tasks = work / "tasks"
        if not tasks.is_dir():
            tasks.mkdir(parents=True, exist_ok=True)
            print(".loop/tasks/ を作りました。")
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as e:
        print(f"初回の準備を続けられませんでした（{type(e).__name__}）。")
    return 0


def loop() -> Path:
    import inbox
    d = inbox.loop_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def state() -> dict:
    p = loop() / "setup.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save(**kw) -> None:
    (loop() / "setup.json").write_text(json.dumps({**state(), **kw}, ensure_ascii=False, indent=1), encoding="utf-8")


def ask(label: str, secret: bool = False) -> str:
    if not sys.stdin.isatty() and not os.environ.get("HARNESS_SETUP_STDIN"):
        print(f"setup: 「{label}」は人が端末で直接入れます（会話に乗せないため）。"
              f"Claude Code なら行頭に ! を付けて同じ命令を打ってください。", file=sys.stderr)
        raise SystemExit(2)
    if os.environ.get("HARNESS_SETUP_STDIN"):  # 試験用
        return sys.stdin.readline().strip()
    return (getpass.getpass(label + ": ") if secret else input(label + ": ")).strip()


def write_notify(server: str, topic: str, token: str, mode: str) -> None:
    q = shlex.quote
    p = loop() / "notify.env"
    p.write_text(f"NTFY_ENABLED=1\nNTFY_SERVER={q(server.rstrip('/'))}\nNTFY_TOPIC={q(topic)}\n"
                 + (f"NTFY_TOKEN={q(token)}\n" if token else ""), encoding="utf-8")
    p.chmod(0o600)
    save(notify=mode, notify_decided=datetime.now().astimezone().isoformat(timespec="seconds"))


def read_notify() -> dict:
    p = loop() / "notify.env"
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            out[k] = shlex.split(v)[0] if v else ""
    return out


def cmd_notify(a) -> int:
    if a.mode == "skip":
        save(notify="skip", notify_decided=datetime.now().astimezone().isoformat(timespec="seconds"))
        print("この作業場では通知を決めません。催促もしません（決めたくなったら notify off / new / existing / selfhost）。")
    elif a.mode == "off":
        (loop() / "notify.env").unlink(missing_ok=True)
        save(notify="off", notify_decided=datetime.now().astimezone().isoformat(timespec="seconds"))
        print("スマホへの通知は使いません。もう尋ねません（変えるときは notify new / existing / selfhost）。")
    elif a.mode == "new":
        write_notify("https://ntfy.sh", secrets.token_urlsafe(24), "", "ntfy.sh")
        print("ntfy.sh を使います。題目は乱数 32 文字で作り、.loop/notify.env に置きました（画面と会話には出しません）。\n"
              "スマホの ntfy アプリで、そのファイルの NTFY_TOPIC の値を購読してください。\n"
              "知っておくこと: 題目を知っている人は通知を読めます。送るのは件数と状態だけで、コードや本文は送りません。\n"
              "もっと堅くするなら: ntfy.sh で題目を予約してトークンを付ける（notify existing）か、自前のサーバー（notify selfhost）。")
    elif a.mode in ("existing", "selfhost"):
        if a.mode == "selfhost":
            print("自前のサーバーは、Tailscale などの私設の網の中に置き、auth-default-access: deny-all とトークンで守ってください。\n"
                  "iPhone ですぐ届かせるには upstream-base-url が要ります（ntfy.sh へ渡るのは ID と題目の hash だけ。本文は渡りません）。")
        server = ask("サーバーの URL（例 https://ntfy.sh や http://100.x.y.z:8080）")
        topic = ask("題目（推測されにくい名前）", secret=True)
        token = ask("アクセストークン（無ければ空で Enter）", secret=True)
        if not server.startswith(("http://", "https://")) or not topic:
            print("setup: URL は http(s):// で始め、題目は空にしないでください", file=sys.stderr)
            return 1
        if topic.startswith("change-me") or len(topic) < 12:
            print("setup: その題目は推測されやすいので使いません（12 文字以上の、他人と被らない名前に）。notify new なら機械が作ります", file=sys.stderr)
            return 1
        write_notify(server, topic, token, a.mode)
        print("通知の設定を .loop/notify.env に置きました。試すには: python3 harness/setup.py notify test")
    elif a.mode == "test":
        n = read_notify()
        if n.get("NTFY_ENABLED") != "1":
            print("通知は切です")
            return 1
        req = urllib.request.Request(f"{n['NTFY_SERVER']}/{n['NTFY_TOPIC']}", data="通知の試し送りです".encode(), headers={"Title": "harness"})
        if n.get("NTFY_TOKEN"):
            req.add_header("Authorization", f"Bearer {n['NTFY_TOKEN']}")
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"送りました（HTTP {r.status}）。スマホに届いたか見てください。")
    return 0


# 文書の skill が使う道具。skill は「どの道具でどうやるか」を教えるだけで、道具は同梱しない。
# 版は 2026-09-23 にこの機械で動かして確かめた物。LibreOffice / poppler / tesseract は OS の道具なので別（管理者の窓）。
DOCS_TOOLS = ["pypdf==6.19.0", "pdfplumber==0.11.10", "reportlab==5.0.1", "openpyxl==3.1.5",
              "python-docx==1.2.0", "python-pptx==1.0.2", "markitdown==0.1.8"]


def docs_tools_missing() -> list[str]:
    import importlib.metadata as m
    out = []
    for spec in DOCS_TOOLS:
        name = spec.split("==")[0]
        try:
            m.version(name)
        except m.PackageNotFoundError:
            out.append(name)
    return out


def cmd_docs_tools(a) -> int:
    missing = docs_tools_missing()
    if not missing and not a.force:
        print("文書の道具はそろっています: " + ", ".join(DOCS_TOOLS))
        return 0
    # 利用者の領域（--user）だけに入れる。Ubuntu などはシステムの python を守る印（PEP 668）があるので、その旗も付ける
    cmd = [sys.executable, "-m", "pip", "install", "--quiet", "--user", "--break-system-packages", *DOCS_TOOLS]
    print("入れます: " + " ".join(DOCS_TOOLS))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("setup: pip が失敗しました。ネットワークか python の環境を確かめてください", file=sys.stderr)
        return 1
    print("入りました。OS の道具（LibreOffice・poppler・tesseract）が要る作業は、skill が案内します（管理者の窓を通します）")
    return 0


def cmd_status(a) -> int:
    from bridge import telegram
    s = state()
    todo = []
    print(f"スマホへの通知: {s.get('notify', '未定')}")
    if (loop() / "telegram.env").exists():
        tg = "あり（この作業場）"
    elif telegram.configured():
        tg = "あり（全体）"
    else:
        tg = "なし（cp harness/telegram.env.example ~/.config/harness/telegram.env → 値を入れる）"
    print(f"Telegram の橋: {tg}")
    worker_env = loop() / "worker.env"
    if worker_env.exists():
        count = sum("=" in line and bool(line.strip()) and not line.lstrip().startswith("#")
                    for line in worker_env.read_text(encoding="utf-8").splitlines())
        print(f"担い手に渡す秘密（`.loop/worker.env`）: あり {count} 個")
    else:
        print("担い手に渡す秘密（`.loop/worker.env`）: なし")
    if "notify" not in s:
        todo.append("スマホへ進捗の通知を送るか、人に 1 回だけ尋ねる（使わない → python3 harness/setup.py notify off / 使う → notify new・existing・selfhost から選ぶ / ここでは決めない → notify skip）")
    from judgment import cards_home
    jhome = cards_home(loop())
    if not (jhome / "config.env").exists():
        todo.append("判断の置き場を選ぶ: 新規に作る → python3 harness/judgment.py init --new / "
                    "既存を読み込む → python3 harness/judgment.py init --from <URL か path>")
    if not (loop() / "team.json").exists():
        todo.append("担い手の編成を決める: cp harness/team.example.json .loop/team.json を打ち、人と決める")
    missing = docs_tools_missing()
    print(f"文書の道具（docx / xlsx / pptx / pdf の skill が使う）: " + ("そろっている" if not missing else "足りない: " + ", ".join(missing)))
    if missing:
        todo.append("文書の道具を入れる: python3 harness/setup.py docs-tools")
    for t in todo:
        print("まだ: " + t)
    if not todo:
        print("初回の準備は済んでいます")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="初回セットアップ")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auto")
    sub.add_parser("status")
    n = sub.add_parser("notify"); n.add_argument("mode", choices=("skip", "off", "new", "existing", "selfhost", "test"))
    dt = sub.add_parser("docs-tools"); dt.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    return {"auto": cmd_auto, "status": cmd_status, "notify": cmd_notify, "docs-tools": cmd_docs_tools}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
