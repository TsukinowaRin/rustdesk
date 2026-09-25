#!/usr/bin/env python3
"""担い手へ渡す道具の試験。偽の CLI（モデルを呼ばない）と使い捨ての .loop で、4 つのギアを確かめる。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
bad: list[str] = []
count = 0
FAKE = '''#!/usr/bin/env python3
import os, re, subprocess, sys, time, json
from pathlib import Path
prompt = sys.argv[-1]
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "quota": print("usage limit", flush=True); sys.exit(1)
if mode == "credential": print("MISSING_CREDENTIAL", flush=True); sys.exit(1)
if mode == "probe": print("OK", flush=True); sys.exit(0 if os.environ.get("HARNESS_ROLE") == "worker" else 9)
print(f"fake role={os.environ.get('HARNESS_ROLE')} hands={os.environ.get('HARNESS_HANDS')} cwd={os.getcwd()}")
Path("fake-env.txt").write_text(repr({k: v for k, v in os.environ.items() if k.startswith("HARNESS") or k == "CLIPROXY_API_KEY"}) + "\\nARGV=" + " ".join(sys.argv) + "\\n" + prompt, encoding="utf-8")
if mode == "silent": sys.exit(0)
if mode == "crash": sys.exit(3)
if mode == "hang": time.sleep(60)
subprocess.run([sys.executable, "-B", "harness/guard.py", "--dialect", "plain"],
               input=json.dumps({"tool_name": "Read", "tool_input": {"file_path": "README.md"}}), text=True,
               capture_output=True, check=True)
print("tokens used\\n1,234")
if mode == "claude": print(json.dumps({"total_cost_usd": 0.9696650000000001, "usage": {"input_tokens": 36, "cache_creation_input_tokens": 63848, "cache_read_input_tokens": 963485, "output_tokens": 13302, "output_tokens_details": {"thinking_tokens": 100}}}))
if mode == "json": print(json.dumps({"type": "result", "total_tokens": 42}))
m = re.search(r"報告を (\\S+) に書きます", prompt)
Path("touched.txt").write_text("worker wrote\\n", encoding="utf-8")
report = "# 報告\\n## 何をした\\n- 偽の CLI\\n"
if mode == "eval":
    if "評価課題: greet" in prompt:
        Path("hello.py").write_text("def greet(name):\\n    return f'Hello, {name}!'\\n", encoding="utf-8")
        Path("test_hello.py").write_text("from hello import greet\\nassert greet('Ada') == 'Hello, Ada!'\\n", encoding="utf-8")
    elif "評価課題: read" in prompt:
        report += "判定: ALLOW\\n理由: -n は dry-run\\n"
    elif "評価課題: fix" in prompt:
        p = Path("harness/evals/fix/total.py")
        p.write_text(p.read_text().replace("values[:-1]", "values"), encoding="utf-8")
if m: Path(m.group(1)).write_text(report, encoding="utf-8")
'''


def check(name: str, cond: bool, detail: str = "") -> None:
    global count
    count += 1
    if not cond:
        bad.append(f"{name} :: {detail[-300:]}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        repo = tmp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        (repo / "harness").mkdir()
        for name in ("delegate.py", "guard.py", "clis.json"):
            (repo / "harness" / name).write_bytes((ROOT / "harness" / name).read_bytes())
        import shutil
        shutil.copytree(ROOT / "harness" / "evals", repo / "harness" / "evals")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@local.invalid",
                        "commit", "-qm", "initial"], check=True)
        fake = tmp / "fake.py"
        fake.write_text(FAKE, encoding="utf-8")
        clis = tmp / "clis.json"
        clis.write_text(json.dumps({"clis": {
            "fake": {"worker": ["python3", str(fake), "{prompt}"], "notes": "試験用", "usage": r"tokens used\s*\n([\d,]+)"},
            "fake-model": {"worker": ["python3", str(fake), "--model", "{model}", "{prompt}"]},
            "fake-stdin": {"worker": ["python3", str(fake), "{prompt}"], "prompt": "stdin"},
            "claude": {"worker": ["python3", str(fake), "{prompt}"], "usage": json.loads((ROOT / "harness/clis.json").read_text(encoding="utf-8"))["clis"]["claude"]["usage"]},
            "fake-json": {"worker": ["python3", str(fake), "--format", "json", "{prompt}"], "usage": r'"total_tokens"\s*:\s*(\d+)'},
            "no-worker": {"headless": ["x"]},
        }}, ensure_ascii=False), encoding="utf-8")
        loop = tmp / "loop"
        loop.mkdir()
        (loop / "team.json").write_text(json.dumps({"members": [
            {"name": "cheap", "cli": "fake", "model": "", "vendor": "acme", "cost": 1, "max_parallel": 3},
            {"name": "other", "cli": "fake-model", "model": "m-1", "vendor": "other-corp", "cost": 2, "max_parallel": 1, "argv_extra": ["--extra-flag", "x"]},
            {"name": "same", "cli": "fake", "model": "", "vendor": "acme", "cost": 2, "max_parallel": 1},
            {"name": "gone", "cli": "fake", "model": "", "vendor": "acme", "cost": 1, "max_parallel": 1, "quota_until": "2099-01-01T00:00:00+09:00"},
            {"name": "broken", "cli": "no-worker", "model": "", "vendor": "acme", "cost": 1, "max_parallel": 1},
            {"name": "claude-test", "cli": "claude", "model": "", "vendor": "other-corp", "cost": 1, "max_parallel": 1},
            {"name": "json-test", "cli": "fake-json", "model": "", "vendor": "other-corp", "cost": 1, "max_parallel": 1},
        ]}, ensure_ascii=False), encoding="utf-8")

        def run(*args: str, mode: str = "ok") -> tuple[int, str]:
            env = dict(os.environ, HARNESS_LOOP_DIR=str(loop), HARNESS_CLIS=str(clis), HARNESS_ROOT=str(repo), FAKE_MODE=mode, HARNESS_TESTING="1")
            r = subprocess.run([sys.executable, "-B", str(ROOT / "harness" / "delegate.py"), *args], capture_output=True, text=True, env=env, cwd=repo)
            return r.returncode, r.stdout + r.stderr

        def write_task(tid: str, **gears) -> None:
            d = loop / "tasks" / tid
            d.mkdir(parents=True, exist_ok=True)
            head = "\n".join(f"{k}: {v}" for k, v in gears.items())
            (d / "task.md").write_text(f"---\n{head}\n---\n# 試験\n## 受け入れ条件\n- 報告を書く\n", encoding="utf-8")

        before_probe = {str(p.relative_to(loop)): p.read_bytes() if p.is_file() else None for p in loop.rglob("*")}
        code, out = run("team", "--probe", mode="probe")
        after_probe = {str(p.relative_to(loop)): p.read_bytes() if p.is_file() else None for p in loop.rglob("*")}
        check("probe は担い手の形で動き結果と秒を出し .loop に書かない", code == 0 and "cheap" in out and "使える" in out and "秒" in out and before_probe == after_probe, out)
        code, out = run("team")
        check("編成を表で出す", code == 0 and "cheap" in out and "acme" in out, out)
        check("枠切れを知らせる", "gone" in out and "枠切れ" in out, out)
        check("担い手として起動できない CLI を知らせる", "broken" in out and "起動の形がありません" in out, out)
        code, out = run("new", "試験の依頼", "--id", "T-1", "--member", "nobody")
        check("編成にいない担い手は断る", code == 1 and "いません" in out, out)
        code, out = run("new", "試験の依頼", "--id", "T-1", "--member", "cheap")
        check("依頼書のひな形を作る", code == 0 and (loop / "tasks/T-1/task.md").exists(), out)
        check("ひな形にギアの欄がある", all(k in (loop / "tasks/T-1/task.md").read_text(encoding="utf-8") for k in ("member:", "hands:", "fanout:", "minutes:")))

        # ① 費用のギア: 指定の担い手で動く。作業木は別の場所
        secret = "test-only-worker-key-20260925"
        (loop / "worker.env").write_text(f"# 担い手だけ\nCLIPROXY_API_KEY='{secret}'\n", encoding="utf-8")
        write_task("T-1", member="cheap", hands="workspace", fanout=1, minutes=1)
        code, out = run("run", "T-1")
        res = json.loads(out.strip().splitlines()[-1])
        check("担い手が変えたファイルだけ数える（写した未 commit の変更は数えない）", res["changed_files"] == 2 and "touched.txt" in str(res["changed"]) and "delegate.py" not in str(res["changed"]), out)
        check("担い手が動いて報告を返す", code == 0 and res["exit"] == 0 and res["report"], out)
        check("報告は依頼のフォルダに、担い手の名前付きで出る", (loop / "tasks/T-1/report-cheap.md").exists())
        check("未 commit の変更も作業木へ写す（担い手が今の木と同じ物を見る）", (loop / "work/T-1-cheap/harness/delegate.py").exists())
        wt = loop / "work" / "T-1-cheap"
        check("担い手は別の作業木で動く（本体を汚さない）", (wt / "touched.txt").exists() and not (repo / "touched.txt").exists())
        branch = subprocess.run(["git", "-C", str(wt), "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
        check("試験用の branch は一時フォルダごとに固有", branch.startswith("work/test-") and branch.endswith("-T-1-cheap"), branch)
        env_seen = (wt / "fake-env.txt").read_text(encoding="utf-8")
        event_text = (loop / "events.jsonl").read_text(encoding="utf-8")
        log_text = (loop / "tasks/T-1/log-cheap.txt").read_text(encoding="utf-8")
        report_text = (loop / "tasks/T-1/report-cheap.md").read_text(encoding="utf-8")
        check("worker.env の値は担い手だけに渡り、記録と標準出力には出ない",
              f"'CLIPROXY_API_KEY': '{secret}'" in env_seen
              and all(secret not in text for text in (event_text, log_text, report_text, out))
              and json.loads(event_text.splitlines()[0]).get("worker_env") == 1)
        check("担い手の印が付く", "'HARNESS_ROLE': 'worker'" in env_seen, env_seen[:200])
        check("担い手に作業木の絶対 path を渡す", f"'HARNESS_WORKTREE': '{wt.resolve()}'" in env_seen, env_seen[:300])
        check("依頼文に作業場所・報告先・skill の場所が入る", str(wt) in env_seen and "REPORT.md" in env_seen and "skills/worker" in env_seen, env_seen[:300])
        check("報告は作業木の中に書かせ、依頼のフォルダへ写す", not (wt / "REPORT.md").exists())
        check("依頼書の本文が入る", "受け入れ条件" in env_seen)
        code, out = run("status", "T-1")
        check("status が終了を出す", "終了 exit=0" in out, out)
        check("守りの跡と使用量を記録する", res["guard_calls"] == 1 and res["tokens"] == 1234, out)
        check("status に守りと使用量を出す", "guard_calls=1" in run("status", "T-1")[1] and "tokens=1234" in run("status", "T-1")[1])
        code, adopted = run("adopt", "T-1", "--member", "cheap")
        history = subprocess.run(["git", "-C", str(repo), "log", "--oneline", "--all"], capture_output=True, text=True).stdout
        check("偽 CLI の成果を本流に取り込む", code == 0 and "T-1: cheap の成果" in history and (repo / "touched.txt").exists(), adopted)

        # ② 手の有無のギア
        write_task("T-2", member="cheap", hands="none", fanout=1, minutes=1)
        code, out = run("run", "T-2")
        env_seen = (loop / "work/T-2-cheap/fake-env.txt").read_text(encoding="utf-8")
        check("手なしの印が付く（守りが書く道具を止める）", "'HARNESS_HANDS': 'none'" in env_seen, env_seen[:200])

        # ③ 並べるギア
        write_task("T-3", member="cheap", hands="workspace", fanout=3, minutes=1)
        code, out = run("run", "T-3")
        reports = sorted((loop / "tasks/T-3").glob("report-*.md"))
        check("3 人に同じ依頼を出し、報告が 3 つ出る", code == 0 and len(reports) == 3, out)
        check("3 人は別々の作業木", len(list((loop / "work").glob("T-3-*"))) == 3)
        write_task("T-4", member="other", hands="workspace", fanout=2, minutes=1)
        code, out = run("run", "T-4")
        check("同時に動かせる数を超えたら断る", code == 1 and "max_parallel" in out, out)

        # ④ 独立のギア
        write_task("T-5", member="same", hands="workspace", fanout=1, minutes=1, independent_of="T-1")
        code, out = run("run", "T-5")
        check("同じ会社の担い手で確認しようとしたら知らせる", "同じ会社" in out, out)
        write_task("T-6", member="other", hands="workspace", fanout=1, minutes=1, independent_of="T-1")
        code, out = run("run", "T-6")
        check("別の会社なら黙って通す", code == 0 and "同じ会社" not in out, out)
        env6 = (loop / "work/T-6-other/fake-env.txt").read_text(encoding="utf-8")
        check("担い手ごとの追加の旗（argv_extra）が渡る", "--extra-flag" in env6, env6[:200])

        # 失敗の形
        write_task("T-7", member="cheap", hands="workspace", fanout=1, minutes=1)
        code, out = run("run", "T-7", mode="silent")
        check("報告を書かずに終わった担い手は失敗にする", code == 1 and json.loads(out.strip().splitlines()[-1])["report"] is None, out)
        write_task("T-8", member="cheap", hands="workspace", fanout=1, minutes=1)
        code, out = run("run", "T-8", mode="crash")
        check("異常終了を記録する", code == 1 and json.loads(out.strip().splitlines()[-1])["exit"] == 3, out)
        write_task("T-11", member="claude-test", hands="workspace", fanout=1, minutes=1)
        code, out = run("run", "T-11", mode="claude")
        claude_result = json.loads(out.strip().splitlines()[-1])
        check("Claude の入れ子を含む JSON usage と報告を一緒に取る", code == 0 and claude_result["tokens"] == 1040671 and claude_result["report"], out)
        write_task("T-json", member="json-test", hands="workspace", fanout=1, minutes=1)
        code, out = run("run", "T-json", mode="json")
        json_result = json.loads(out.strip().splitlines()[-1])
        check("JSON 出力でも使用量と REPORT.md を取る", code == 0 and json_result["tokens"] == 42 and json_result["report"] and Path(json_result["report"]).exists(), out)
        write_task("T-quota", member="cheap", hands="workspace", fanout=1, minutes=1)
        before_quota = datetime.now(timezone(timedelta(hours=9)))
        code, out = run("run", "T-quota", mode="quota")
        members = json.loads((loop / "team.json").read_text(encoding="utf-8"))["members"]
        until = next(m for m in members if m["name"] == "cheap").get("quota_until")
        quota_events = [json.loads(line) for line in (loop / "events.jsonl").read_text(encoding="utf-8").splitlines() if '"event": "quota"' in line]
        check("usage limit で 1 時間の枠切れを記録する", code == 1 and until and timedelta(minutes=59) <= datetime.fromisoformat(until) - before_quota <= timedelta(minutes=61) and until.endswith("+09:00") and any(e.get("task") == "T-quota" for e in quota_events), out)
        code, out = run("retry", "T-quota")
        check("枠切れ中の retry は起動せず残り時間を出す", code == 1 and "枠切れ" in out and "残り" in out, out)
        write_task("T-credential", member="other", hands="workspace", fanout=1, minutes=1)
        code, out = run("run", "T-credential", mode="credential")
        members_after_credential = json.loads((loop / "team.json").read_text(encoding="utf-8"))["members"]
        check("鍵なしは枠切れにしない", code == 1 and not next(m for m in members_after_credential if m["name"] == "other").get("quota_until"), out)
        members[0]["quota_until"] = "2000-01-01T00:00:00+09:00"
        (loop / "team.json").write_text(json.dumps({"members": members}, ensure_ascii=False), encoding="utf-8")
        code, out = run("retry", "T-quota")
        check("期限後の retry は同じ依頼を 1 回流す", code == 0 and json.loads(out.strip().splitlines()[-1])["report"] and sum(1 for e in json.loads('[' + ','.join((loop / "events.jsonl").read_text(encoding="utf-8").splitlines()) + ']') if e.get("task") == "T-quota" and e.get("event") == "start") == 2, out)
        write_task("T-9", member="gone", hands="workspace", fanout=1, minutes=1)
        code, out = run("run", "T-9")
        check("枠切れの担い手には出さない", code == 1 and "枠切れ" in out, out)
        (loop / "tasks/T-10").mkdir(parents=True)
        (loop / "tasks/T-10/task.md").write_text("# ギアの欄が無い依頼書\n", encoding="utf-8")
        code, out = run("run", "T-10")
        check("ギアの欄が無い依頼書は断る", code == 1 and "ギア" in out, out)

        code, out = run("stats")
        check("実績を出す", "cheap" in out and "件数" in out, out)
        check("実績に守りと使用量の列を出す", "guard_calls" in out and "tokens" in out, out)
        cheap = next(line for line in out.splitlines() if line.startswith("cheap"))
        check("報告なしは成功に数えない", cheap.split()[2] == "6", cheap)
        check("決めるのは指示役だと書いてある", "指示役が決めます" in out, out)
        check("評価が無いと未評価を出す", "未評価" in out, out)

        code, out = run("eval", "--member", "cheap,other", "--task", "greet", mode="eval")
        check("eval コマンドを使える", code == 0, out)
        if code:
            for b in bad:
                print("NG  " + b)
            return 1
        eval_file = loop / "evals" / f"{date.today().isoformat()}.jsonl"
        evals = [json.loads(l) for l in eval_file.read_text(encoding="utf-8").splitlines()]
        print(f"偽 CLI: python3 harness/delegate.py eval --member cheap,other --task greet → .loop/evals/{eval_file.name} に {len(evals)} 行")
        print("評価行: " + ", ".join(f"{e['member']}={e['passed']} tokens={e['tokens']} guard_calls={e['guard_calls']}" for e in evals))
        check("評価を担い手ごとに記録する", code == 0 and len(evals) == 2 and all(e["passed"] and e["task"] == "greet" and e["guard_calls"] == 1 for e in evals) and evals[0]["tokens"] == 1234 and evals[1]["tokens"] is None, out)
        check("評価の依頼は E 番号で残る", len(list((loop / "tasks").glob("E-*/task.md"))) == 2)
        code, out = run("eval", "--member", "cheap", "--task", "read", mode="eval")
        check("読んで答える課題も判定できる", code == 0 and json.loads(out.strip().splitlines()[-1])["passed"], out)
        code, out = run("eval", "--member", "cheap", "--task", "fix", mode="eval")
        check("直す課題は試験で判定できる", code == 0 and json.loads(out.strip().splitlines()[-1])["passed"], out)
        code, out = run("eval", "--member", "same", "--task", "read")
        check("答えが違えば評価を落とす", code == 1 and not json.loads(out.strip().splitlines()[-1])["passed"], out)
        code, out = run("stats")
        cheap = next(line for line in out.splitlines() if line.startswith("cheap"))
        check("stats に評価の合格数と平均を出す", "評価" in out and "3/3" in cheap and "1234" in cheap, cheap)
        ev = [json.loads(l) for l in (loop / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        check("events に start と end が 1 行ずつ残る", sum(1 for e in ev if e["event"] == "start") == sum(1 for e in ev if e["event"] == "end") > 0)
    for b in bad:
        print("NG  " + b)
    print(f"担い手へ渡す道具の試験: {count} 場面、ずれ {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
