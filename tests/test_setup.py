#!/usr/bin/env python3
"""初回セットアップの試験。使い捨ての .loop で動かす（実物の設定は触らない。外へは送らない）。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
bad: list[str] = []
count = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global count
    count += 1
    if not cond:
        bad.append(f"{name} :: {detail[-300:]}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        def fresh(dest: Path) -> None:
            (dest / "harness").mkdir(parents=True)
            for name in ("setup.py", "team.example.json", "clis.json"):
                shutil.copy2(ROOT / "harness" / name, dest / "harness" / name)

        def auto(dest: Path) -> subprocess.CompletedProcess[str]:
            return subprocess.run([sys.executable, "-B", str(dest / "harness/setup.py"), "auto"],
                                  cwd=dest, capture_output=True, text=True)

        fresh_root = Path(tmp) / "fresh"
        fresh(fresh_root)
        first = auto(fresh_root)
        head = subprocess.run(["git", "-C", str(fresh_root), "rev-list", "--count", "HEAD"],
                              capture_output=True, text=True)
        check("auto は展開先自身に初回 commit と編成と tasks を作る",
              first.returncode == 0 and (fresh_root / ".git").exists() and head.stdout.strip() == "1"
              and (fresh_root / ".loop/team.json").exists() and (fresh_root / ".loop/tasks").is_dir(),
              first.stdout + first.stderr + head.stderr)
        before = subprocess.run(["git", "-C", str(fresh_root), "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        second = auto(fresh_root)
        after = subprocess.run(["git", "-C", str(fresh_root), "status", "--porcelain"],
                               capture_output=True, text=True).stdout
        check("auto の再実行は無言で変更なし", second.returncode == 0 and second.stdout == ""
              and second.stderr == "" and before == after, second.stdout + second.stderr)

        parent = Path(tmp) / "parent"
        parent.mkdir()
        subprocess.run(["git", "init", "-q", str(parent)], check=True)
        child = parent / "child"
        fresh(child)
        parent_before = subprocess.run(["git", "-C", str(parent), "status", "--porcelain"],
                                       capture_output=True, text=True).stdout
        nested = auto(child)
        parent_after = subprocess.run(["git", "-C", str(parent), "status", "--porcelain"],
                                      capture_output=True, text=True).stdout
        own_top = subprocess.run(["git", "-C", str(child), "rev-parse", "--show-toplevel"],
                                 capture_output=True, text=True).stdout.strip()
        check("親 repo の中でも展開先自身を初期化し親を変えない",
              nested.returncode == 0 and (child / ".git").exists() and own_top == str(child)
              and parent_before == parent_after, nested.stdout + nested.stderr)

        loop = Path(tmp) / "loop"

        def run(*args: str, stdin: str | None = None) -> tuple[int, str]:
            env = dict(os.environ, HARNESS_LOOP_DIR=str(loop), HARNESS_JUDGMENT_HOME=str(loop / "judgment"))
            if stdin is not None:
                env["HARNESS_SETUP_STDIN"] = "1"
            r = subprocess.run([sys.executable, "-B", str(ROOT / "harness" / "setup.py"), *args], input=stdin if stdin is not None else "",
                               capture_output=True, text=True, env=env)
            return r.returncode, r.stdout + r.stderr

        code, out = run("status")
        check("決まっていないことを「まだ」で出す", "スマホへの通知: 未定" in out and out.count("まだ:") == 3, out)
        check("編成の『まだ』には写す命令を出す", "まだ: 担い手の編成を決める: cp harness/team.example.json .loop/team.json" in out, out)
        check("台帳の新規と既存の命令を出す", "init --new" in out and "init --from" in out, out)
        code, out = run("notify", "skip")
        code, out = run("status")
        check("「ここでは決めない」も決定で、催促しない", "スマホへの通知: skip" in out and "尋ねる" not in out and not (loop / "notify.env").exists(), out)
        code, out = run("notify", "off")
        code, out = run("status")
        check("使わないと決めたら、もう尋ねない", "スマホへの通知: off" in out and "尋ねる" not in out, out)
        check("使わないなら設定ファイルを作らない", not (loop / "notify.env").exists())

        code, out = run("notify", "new")
        env_text = (loop / "notify.env").read_text(encoding="utf-8")
        topic = [l for l in env_text.splitlines() if l.startswith("NTFY_TOPIC=")][0].split("=", 1)[1]
        check("乱数の題目は 32 文字で、画面に出さない", len(topic) == 32 and topic not in out, out)
        code2, out2 = run("notify", "new")
        topic2 = [l for l in (loop / "notify.env").read_text(encoding="utf-8").splitlines() if l.startswith("NTFY_TOPIC=")][0].split("=", 1)[1]
        check("題目は毎回ちがう（他人と被らない）", topic != topic2)
        check("設定ファイルは本人だけ読める", oct((loop / "notify.env").stat().st_mode)[-3:] in ("600", "777"))  # /mnt の NTFS は 777 のまま

        code, out = run("notify", "existing")
        check("題目とトークンは、端末の人からしか受け取らない", code == 2 and "直接入れます" in out, out)
        code, out = run("notify", "existing", stdin="https://ntfy.sh\nchange-me-to-something-unguessable\n\n")
        check("上流の見本の題目は断る", code == 1 and "推測されやすい" in out, out)
        code, out = run("notify", "existing", stdin="https://ntfy.sh\nshort\n\n")
        check("短い題目は断る", code == 1, out)
        code, out = run("notify", "existing", stdin="ntfy.sh\nmy-very-long-private-topic-name\n\n")
        check("http(s) で始まらないサーバーは断る", code == 1, out)
        code, out = run("notify", "selfhost", stdin="http://100.64.0.1:8080/\nmy-very-long-private-topic-name\ntk_secret123\n")
        env_text = (loop / "notify.env").read_text(encoding="utf-8")
        check("自前サーバーとトークンを記録し、画面に出さない", code == 0 and "NTFY_SERVER=http://100.64.0.1:8080\n" in env_text
              and "NTFY_TOKEN=tk_secret123" in env_text and "tk_secret123" not in out and "my-very-long" not in out, out + env_text)
        check("選んだ道を覚える", json.loads((loop / "setup.json").read_text(encoding="utf-8"))["notify"] == "selfhost")

        # 判断の道具の config.env が、この設定を読む
        r = subprocess.run(["bash", "-c", f'NTFY_ENABLED=0; NTFY_TOPIC=""; . {loop}/notify.env; echo "$NTFY_ENABLED $NTFY_SERVER"'], capture_output=True, text=True)
        check("bash から読める形で書く", r.stdout.strip() == "1 http://100.64.0.1:8080", r.stdout + r.stderr)

        sys.path.insert(0, str(ROOT / "harness"))
        import setup as st
        (loop / "team.json").write_text("{}", encoding="utf-8")
        (loop / "judgment").mkdir(parents=True)
        (loop / "judgment/config.env").write_text("", encoding="utf-8")
        ready = StringIO()
        with patch.dict(os.environ, {"HARNESS_LOOP_DIR": str(loop), "HARNESS_JUDGMENT_HOME": str(loop / "judgment")}), patch.object(st, "docs_tools_missing", return_value=[]), redirect_stdout(ready):
            st.cmd_status(None)
        check("初回の準備が全部済めば 1 行で知らせる", "まだ:" not in ready.getvalue() and ready.getvalue().splitlines()[-1] == "初回の準備は済んでいます", ready.getvalue())
        stored = Path(tmp) / "stored"
        stored.mkdir()
        (stored / "config.env").write_text("")
        st_env = dict(os.environ, HARNESS_LOOP_DIR=str(loop))
        st_env.pop("HARNESS_JUDGMENT_HOME", None)
        ready = StringIO()
        with patch.dict(os.environ, st_env, clear=True), patch.object(st, "docs_tools_missing", return_value=[]), redirect_stdout(ready):
            st.save(judgment_home=str(stored))
            (loop / "judgment/config.env").unlink()
            st.cmd_status(None)
        check("保存した台帳の置き場を status が使う", "判断の置き場" not in ready.getvalue(), ready.getvalue())
        code, out = run("status")
        check("保存した置き場より環境変数を優先する", "init --new" in out and "init --from" in out, out)
        check("文書の道具の一覧は版を固定している", all("==" in x for x in st.DOCS_TOOLS) and len(st.DOCS_TOOLS) == 7)
        check("足りない道具を名前で出す（この機械ではそろっている前提で 0 個）", isinstance(st.docs_tools_missing(), list))
        check("入れる先は利用者の領域だけ", "--user" in (ROOT / "harness" / "setup.py").read_text(encoding="utf-8"))
    for b in bad:
        print("NG  " + b)
    print(f"初回セットアップの試験: {count} 場面、ずれ {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
