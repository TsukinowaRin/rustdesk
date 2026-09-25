#!/usr/bin/env python3
"""守りの試験。場面は guard_cases.tsv の 1 行 1 場面。ここには走らせる仕組みだけ置く。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
import guard  # noqa: E402

GUARD = [sys.executable, "-B", str(ROOT / "harness" / "guard.py")]


def cases():
    for n, line in enumerate((ROOT / "tests" / "guard_cases.tsv").read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        expect, tool, raw, why = line.split("\t")
        raw = raw.replace("{ROOT}", ROOT.as_posix()).replace("{HOME}", Path.home().as_posix())
        tool_input = json.loads(raw) if raw.startswith("{") else {"command": raw.replace("\\n", "\n")}
        yield n, expect, tool, tool_input, why


def run_table() -> list[str]:
    # 表は「素の判定」を見る。担い手の中で流すと HARNESS_ROLE=worker が付いていて OK の印などが効かず、
    # 期待とずれる（2026-09-24、配布物の試験を GPT-6 Sol に担い手として流したら 2 件落ちた）ので、役の印を外す
    for k in ("HARNESS_ROLE", "HARNESS_HANDS", "HARNESS_ATTENDED"):
        os.environ.pop(k, None)
    bad = []
    for n, expect, tool, tool_input, why in cases():
        got = guard.evaluate(tool, tool_input, ROOT).action
        if got != expect:
            bad.append(f"guard_cases.tsv:{n}: 期待 {expect} / 実際 {got}: {why}: {json.dumps(tool_input, ensure_ascii=False)}")
    return bad


def hook(dialect: str, payload: dict, role: str = "", extra_env: dict | None = None) -> tuple[int, str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("HARNESS_ROLE", "HARNESS_HANDS", "HARNESS_ATTENDED", "HARNESS_GUARD_EDIT", "HARNESS_WORKTREE")}
    if role:
        env["HARNESS_ROLE"] = role
    env.update(extra_env or {})
    r = subprocess.run(GUARD + ["--dialect", dialect], input=json.dumps(payload), capture_output=True, text=True, env=env, cwd=ROOT)
    return r.returncode, r.stdout, r.stderr


def run_dialects() -> list[str]:
    bad = []

    def check(name, cond, detail=""):
        if not cond:
            bad.append(f"入出力の形: {name} {detail[:200]}")

    deny, ask, ok = {"command": "rm -rf /"}, {"command": "git push origin x"}, {"command": "ls"}
    cwd = ROOT.as_posix()
    # Claude 形式（Claude Code / Codex / Grok / DeepSeek Harness）
    code, out, err = hook("claude", {"tool_name": "Bash", "tool_input": deny, "cwd": cwd})
    check("claude deny は exit 2 と stderr", code == 2 and err.strip() and not out)
    attended = {"HARNESS_ATTENDED": "1"}   # 形を見る試験。既定では ask が止まるので、人がいる印を付ける
    code, out, _ = hook("claude", {"tool_name": "Bash", "tool_input": ask, "cwd": cwd}, extra_env=attended)
    check("claude ask（人がいる印つき）", code == 0 and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "ask")
    code, out, _ = hook("claude", {"tool_name": "Bash", "tool_input": ok, "cwd": cwd})
    check("claude allow は無出力", code == 0 and out == "")
    code, _, _ = hook("claude", {"toolName": "Bash", "toolInput": deny, "cwd": cwd})
    check("claude 形式の camelCase（Grok）", code == 2)
    # Antigravity
    code, out, _ = hook("agy", {"toolCall": {"name": "run_command", "args": {"CommandLine": "rm -rf /"}}})
    check("agy deny", json.loads(out)["decision"] == "deny")
    code, out, _ = hook("agy", {"toolCall": {"name": "run_command", "args": {"CommandLine": "git push origin x"}}}, extra_env=attended)
    check("agy ask は force_ask（人がいる印つき）", json.loads(out)["decision"] == "force_ask")
    code, out, _ = hook("agy", {"toolCall": {"name": "run_command", "args": {"CommandLine": "git push origin x"}}})
    check("agy でも既定の ask は deny（承認待ちで止まらない）", json.loads(out)["decision"] == "deny")
    code, out, _ = hook("agy", {"toolCall": {"name": "view_file", "args": {"AbsolutePath": str(Path.home() / ".ssh/id_rsa")}}})
    check("agy の path の欄", json.loads(out)["decision"] == "deny")
    # Cursor
    code, out, _ = hook("cursor", {"hook_event_name": "beforeShellExecution", "command": "rm -rf /", "cwd": cwd})
    check("cursor deny", json.loads(out)["permission"] == "deny")
    code, out, _ = hook("cursor", {"hook_event_name": "beforeShellExecution", "command": "ls", "cwd": cwd})
    check("cursor allow も JSON を返す", json.loads(out)["permission"] == "allow")
    code, out, _ = hook("cursor", {"hook_event_name": "beforeReadFile", "file_path": ".env", "cwd": cwd})
    check("cursor の読み", json.loads(out)["permission"] == "deny")
    code, out, _ = hook("cursor", {"hook_event_name": "subagentStart", "subagent_type": "x", "cwd": cwd})
    check("cursor の子エージェントの起動は止める", json.loads(out)["permission"] == "deny")
    # JS 拡張（omp / opencode / Kilo）
    code, out, _ = hook("plain", {"tool_name": "bash", "tool_input": deny, "cwd": cwd})
    check("plain deny", json.loads(out)["decision"] == "deny")
    code, out, _ = hook("plain", {"tool_name": "bash", "tool_input": ok, "cwd": cwd})
    check("plain allow", json.loads(out)["decision"] == "allow")
    # 読めない入力は通さない
    r = subprocess.run(GUARD, input="not json", capture_output=True, text=True)
    check("壊れた入力は止める", r.returncode == 2)
    code, _, _ = hook("claude", {"tool_input": deny})
    check("道具の名前が無い入力は止める", code == 2)
    # 担い手（聞く相手がいない）では ask を deny にする
    code, _, err = hook("claude", {"tool_name": "Bash", "tool_input": ask, "cwd": cwd}, role="worker")
    check("担い手の ask は deny", code == 2 and "指示役" in err)
    code, _, _ = hook("claude", {"tool_name": "Bash", "tool_input": ok, "cwd": cwd}, role="worker")
    check("担い手でも allow は通る", code == 0)
    worker_cases = [
        ("Write で守り本体", "Write", {"file_path": "harness/guard.py"}),
        ("Edit で守り本体", "Edit", {"file_path": "harness/guard.py"}),
        ("作業木の外への Write", "Write", {"file_path": str(Path.home() / ".bashrc")}),
        ("外へのリダイレクト", "Bash", {"command": "echo x > ../../../harness/guard.py"}),
        ("git checkout の巻き戻し", "Bash", {"command": "git -C ../../.. checkout -- docs/dashboard/index.html"}),
        ("git restore の巻き戻し", "Bash", {"command": "git restore README.md"}),
        ("git stash drop", "Bash", {"command": "git stash drop"}),
        ("git branch -D", "Bash", {"command": "git branch -D main"}),
        ("truncate -s0", "Bash", {"command": "truncate -s0 ../../../harness/guard.py"}),
        ("別の CLI 起動", "Bash", {"command": "codex exec hi"}),
        ("delegate run", "Bash", {"command": "python3 harness/delegate.py run T-1"}),
    ]
    for label, tool, inp in worker_cases:
        code, _, err = hook("claude", {"tool_name": tool, "tool_input": inp, "cwd": cwd}, role="worker")
        check("担い手: " + label, code == 2, err)
    # 実行はせず hook への入力だけを渡す。各 deny に、隣の allow を置いて止めすぎも見る。
    worker_pairs = [
        ("env の印解除", "env -u HARNESS_ROLE codex", "env FOO=1 ls"),
        ("env の空印", "env HARNESS_ROLE= ls", "env FOO= ls"),
        ("先頭の印代入", "HARNESS_ROLE= ls", "FOO= ls"),
        ("unset の印解除", "unset HARNESS_ROLE", "unset FOO"),
        ("HANDS の印解除", "env -u HARNESS_HANDS ls", "env -u FOO ls"),
        ("GUARD_EDIT の印解除", "unset HARNESS_GUARD_EDIT", "unset FOO"),
        ("WORKTREE の印変更", "HARNESS_WORKTREE=/tmp ls", "FOO=/tmp ls"),
        ("dsh の相対 path", "bash ./harness/dsh.sh", "bash ./harness/other.sh"),
        ("dsh の絶対 path", f"bash {cwd}/harness/dsh.sh", "bash harness/other.sh"),
        ("dsh の sh 起動", "sh harness/dsh.sh", "sh harness/other.sh"),
        ("dsh の直接起動 ./", "./harness/dsh.sh", "./harness/other.sh"),
        ("dsh の直接起動", "harness/dsh.sh", "harness/other.sh"),
        ("dsh の source", "source harness/dsh.sh", "source harness/other.sh"),
        ("dsh の dot source", ". harness/dsh.sh", ". harness/other.sh"),
        ("dsh の入れ子 shell", "bash -c './harness/dsh.sh'", "bash -c './harness/other.sh'"),
        ("dsh の shell 旗", "bash -x harness/dsh.sh", "bash -x harness/other.sh"),
        ("cd の後の dsh", "cd harness && ./dsh.sh", "cd harness && ./other.sh"),
        ("cd の後の delegate", "cd harness && python3 delegate.py run T-1", "cd harness && python3 delegate.py adopt T-1"),
        ("Python -B", "python3 -B harness/delegate.py run T-1", "python3 -B harness/delegate.py adopt T-1"),
        ("Python -u", "python3 -u harness/delegate.py run T-1", "python3 -u harness/delegate.py new T-1"),
        ("Python -X", "python -X utf8 harness/delegate.py run T-1", "python -X utf8 harness/delegate.py adopt T-1"),
        ("Python の絶対 path", f"/usr/bin/python3 {cwd}/harness/delegate.py run T-1", "python3 harness/delegate.py new T-1"),
        ("delegate の dot path", "python3 harness/./delegate.py run T-1", "python3 harness/./delegate.py adopt T-1"),
        ("delegate の親 path", "python3 harness/foo/../delegate.py run T-1", "python3 harness/foo/../delegate.py adopt T-1"),
        ("cp の directory", "cp /tmp/guard.py harness/", "cp a.txt b.txt"),
        ("mv の directory", "mv /tmp/guard.py harness/", "mv a.txt b.txt"),
        ("cp の複数元", "cp a.txt /tmp/guard.py harness/", "cp a.txt b.txt harness/"),
        ("cp -t", "cp -t .. README.md", "cp -t harness README.md"),
        ("mv --target-directory", "mv --target-directory=.. README.md", "mv --target-directory=harness README.md"),
        ("find exec cp の置換元", r"find . -name README.md -exec cp {} ../outside-dir/ \;", r"find . -name README.md -exec cp {} notes/ \;"),
        ("find の外の出発点", r"find .. -name x -exec truncate -s 0 {} \;", r"find . -name x -exec truncate -s 0 {} \;"),
        ("find の 2 つ目の -exec", r"find . -exec true \; -exec cp {} ../outside-dir/ \;", r"find . -exec true \; -exec cp {} notes/ \;"),
        ("xargs truncate", "printf x | xargs truncate -s 0", "printf x | xargs ls"),
        ("xargs cp", "printf x | xargs cp README.md", "printf x | xargs grep x"),
        ("xargs mv", "printf x | xargs mv README.md", "printf x | xargs ls"),
        ("xargs tee", "printf x | xargs tee", "printf x | xargs grep x"),
        ("xargs sed -i", "printf x | xargs sed -i s/x/y/", "printf x | xargs sed s/x/y/"),
        ("xargs の包み", "printf x | xargs nice cp README.md", "printf x | xargs nice ls"),
        ("xargs -I", "printf x | xargs -I{} cp README.md {}", "printf x | xargs -I{} cp {} notes/"),
        ("busybox cp", "busybox cp README.md ../outside.txt", "busybox cp README.md notes.txt"),
        ("exec -a", "exec -a x codex", "exec -a x ls"),
        ("exec", "exec codex", "exec ls"),
        ("exec の旗の後の -a", "exec -l -a x codex", "exec -l -a x ls"),
        ("rsync", "rsync -a README.md ../outside.txt", "rsync -a README.md notes.txt"),
        ("rsync 複数元", "rsync a.txt b.txt ../outside-dir/", "rsync a.txt b.txt notes/"),
        ("rsync -t は時刻", "rsync -t README.md ../outside.txt", "rsync -t README.md notes.txt"),
        ("install", "install README.md ../outside.txt", "install README.md notes.txt"),
        ("install -t", "install -t .. README.md", "install -t notes README.md"),
        ("install --target-directory", "install --target-directory=.. README.md", "install --target-directory=notes README.md"),
        ("install -d", "install -d ../outside-dir", "install -d notes/sub"),
        ("perl -pi", "perl -pi -e s/x/y/ ../outside.txt", "perl -pi -e s/x/y/ notes.txt"),
        ("perl -i", "perl -i -e s/x/y/ ../outside.txt", "perl -i -e s/x/y/ notes.txt"),
        ("perl -pie", "perl -pie s/x/y/ ../outside.txt", "perl -pie s/x/y/ notes.txt"),
        ("perl の旗に付いたコード", "perl -i -pes/x/y/ ../outside.txt", "perl -lne print ../outside.txt"),
        ("cd と &&", "cd .. && echo x > outside.txt", "cd harness && ls"),
        ("cd と ;", "cd ..; echo x > outside.txt", "cd harness; ls"),
        ("cd 後の読み", "cd /tmp && echo x > outside.txt", "cd .. && ls"),
        ("cd の旗", "cd -P .. && echo x > outside.txt", "cd -P harness && echo x > notes.txt"),
        ("先の読めない cd", "cd - && echo x > notes.txt", "cd && ls"),
        ("cd の失敗", "cd nonexist || echo x > ../outside.txt", "cd harness || echo x > notes.txt"),
        ("sed -i.bak", "sed -i.bak s/x/y/ ../outside.txt", "sed -i.bak s/x/y/ notes.txt"),
        ("sed --in-place", "sed --in-place=.bak s/x/y/ ../outside.txt", "sed --in-place=.bak s/x/y/ notes.txt"),
        ("sed の複数ファイル", "sed -i s/x/y/ ../outside.txt notes.txt", "sed -i s/x/y/ notes.txt other.txt"),
        ("sed -e の複数ファイル", "sed -i -e s/x/y/ ../outside.txt notes.txt", "sed -i -e s/x/y/ notes.txt other.txt"),
        ("&> の出力", "echo x &> ../outside.txt", "echo x &> notes.txt"),
        ("&>> の出力", "echo x &>> ../outside.txt", "echo x &>> notes.txt"),
        (">| の出力", "echo x >| ../outside.txt", "echo x >| notes.txt"),
        ("1>| の出力", "echo x 1>| ../outside.txt", "echo x 1>| notes.txt"),
        ("2>| の出力", "echo x 2>| ../outside.txt", "echo x 2>| notes.txt"),
        ("<> の出力", "echo x <> ../outside.txt", "echo x <> notes.txt"),
        ("restore --staged --worktree", "git restore --staged --worktree README.md", "git restore --staged README.md"),
        ("restore の短旗", "git restore -W README.md", "git restore -S README.md"),
    ]
    for label, stopped, allowed in worker_pairs:
        for command, want in ((stopped, 2), (allowed, 0)):
            code, out, err = hook("claude", {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}, role="worker")
            check("担い手: " + label + f" exit {want}: " + command, code == want, out + err)
    for redirect in ("> /dev/null", "2>/dev/null", "&>/dev/null", "> /dev/stdout", "> /dev/stderr", "> /dev/tty"):
        code, out, err = hook("claude", {"tool_name": "Bash", "tool_input": {"command": "echo x " + redirect}, "cwd": cwd}, role="worker")
        check("担い手の標準デバイスへの出力: " + redirect, code == 0, out + err)
    code, out, err = hook("claude", {"tool_name": "Bash", "tool_input": {"command": "echo x > /dev/not-null"}, "cwd": cwd}, role="worker")
    check("標準デバイス以外の /dev への出力は止める", code == 2, out + err)
    import tempfile
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        nested = Path(tmp) / "nested"
        subprocess.run(["git", "init", "-q", str(nested)], check=True)
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(ROOT / "REPORT.md")}, "cwd": str(nested)}
        code, out, err = hook("claude", payload, role="worker", extra_env={"HARNESS_WORKTREE": str(ROOT)})
        check("入れ子の repo から作業木内へ書ける", code == 0, out + err)
        payload["tool_input"]["file_path"] = str(Path.home() / "outside.txt")
        code, out, err = hook("claude", payload, role="worker", extra_env={"HARNESS_WORKTREE": str(ROOT)})
        check("入れ子の repo から作業木の外へは書けない", code == 2, out + err)
    # 守りを直す依頼（依頼書の guard: edit → delegate.py が HARNESS_GUARD_EDIT=1 を付ける）だけ、作業木の中の守りを書ける
    edit = {"HARNESS_GUARD_EDIT": "1"}
    code, _, err = hook("claude", {"tool_name": "Edit", "tool_input": {"file_path": "harness/guard.py"}, "cwd": cwd}, role="worker", extra_env=edit)
    check("guard: edit の担い手は作業木の中の守りを書ける", code == 0, err)
    code, _, err = hook("claude", {"tool_name": "Write", "tool_input": {"file_path": str(Path.home() / ".bashrc")}, "cwd": cwd}, role="worker", extra_env=edit)
    check("guard: edit でも作業木の外には書けない", code == 2, err)
    for command in ("claude -p hi", "agy -p hi", "cursor-agent -p hi", "opencode run hi", "kilo run hi",
                    "grok -p hi", "omp -p hi", "bash harness/dsh.sh --profile headless hi"):
        code, _, err = hook("claude", {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}, role="worker")
        check("担い手の起動禁止: " + command, code == 2 and "担い手は担い手を起こさない" in err, err)
    for command in ("git checkout -- README.md", "git restore README.md", "git stash clear", "git branch -D main"):
        code, _, err = hook("claude", {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd})
        check("指示役の巻き戻しは判断カード: " + command, code == 2 and "判断カード" in err, err)
    # 既定（印なし）は「人がいない」扱い: ask は承認画面を出さず止めて、判断カードへ（2026-09-24、ユーザーの判断）
    code, _, err = hook("claude", {"tool_name": "Bash", "tool_input": ask, "cwd": cwd})
    check("既定では指示役の ask も止めて判断カードへ（承認待ちで止まらない）", code == 2 and "判断カード" in err and "HARNESS_APPROVED" in err, err)
    code, _, err = hook("claude", {"tool_name": "Bash", "tool_input": {"command": "rm -rf $BUILD"}, "cwd": cwd})
    check("変数を含む削除も、既定では止まる", code == 2, err)
    code, out, _ = hook("claude", {"tool_name": "Bash", "tool_input": ask, "cwd": cwd}, extra_env={"HARNESS_ATTENDED": "1"})
    check("人がいる印（HARNESS_ATTENDED=1）があるときだけ、CLI の承認画面に回す", code == 0 and '"ask"' in out, out)
    code, out, _ = hook("claude", {"tool_name": "Bash", "tool_input": ask, "cwd": cwd}, role="worker", extra_env={"HARNESS_ATTENDED": "1"})
    check("担い手は、人がいる印があっても ask は止まる", code == 2, out)
    # ギア「手なし」: 書く道具と shell を止め、読む道具は通す（9 CLI で同じ効き方）
    env_none = {"HARNESS_HANDS": "none"}
    for tool, inp, want in (("Write", {"file_path": "a.md", "content": "x"}, 2), ("Bash", ok, 2),
                            ("apply_patch", {"command": "*** Begin Patch"}, 2), ("Read", {"file_path": "README.md"}, 0),
                            ("Grep", {"pattern": "x"}, 0), ("WebFetch", {"url": "https://example.com"}, 0)):
        code, out, err = hook("claude", {"tool_name": tool, "tool_input": inp, "cwd": cwd}, extra_env=env_none)
        check(f"手なし: {tool} は {'止める' if want else '通す'}", code == want, out + err)
    code, _, _ = hook("claude", {"tool_name": "Write", "tool_input": {"file_path": "a.md"}, "cwd": cwd})
    check("手ありの担い手は Write を通す", code == 0)
    rep = {"HARNESS_HANDS": "none", "HARNESS_REPORT": cwd + "/REPORT.md"}
    code, out, err = hook("claude", {"tool_name": "Write", "tool_input": {"file_path": "REPORT.md", "content": "x"}, "cwd": cwd}, extra_env=rep)
    check("手なしでも報告 1 本は書ける", code == 0, out + err)
    code, _, _ = hook("claude", {"tool_name": "Write", "tool_input": {"file_path": "other.md"}, "cwd": cwd}, extra_env=rep)
    check("手なしで報告以外は書けない", code == 2)
    # 引数なしの git push は「今の branch」で決まる。試験を動かす場所の branch に依らないよう、使い捨ての repo で両方を見る
    # （2026-09-24、配布物を別の場所に展開して点検したら master 上で落ちた）
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        for branch, want in (("feature", 2), ("master", 2)):
            d = Path(tmp) / branch
            subprocess.run(["git", "init", "-q", "-b", branch, str(d)], check=True)
            # commit が無いと HEAD が解けず branch が分からない（→ ask に倒れる）ので、空の commit を 1 つ置く
            subprocess.run(["git", "-C", str(d), "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "x"], check=True)
            code, out, err = hook("claude", {"tool_name": "Bash", "tool_input": {"command": "git push"}, "cwd": d.as_posix()}, extra_env={"HARNESS_ATTENDED": "1"} if branch == "feature" else None)
            if branch == "feature":
                check("引数なしの push は今の branch（feature）で ask", code == 0 and '"ask"' in out, out + err)
            else:
                check("引数なしの push は今の branch（master）で deny", code == 2 and "main / master" in err, err)
    return bad


def main() -> int:
    bad = run_table() + run_dialects()
    total = sum(1 for _ in cases())
    for b in bad:
        print("NG  " + b)
    print(f"守りの試験: 場面 {total} + 入出力 101、ずれ {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
