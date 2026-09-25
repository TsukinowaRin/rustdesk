#!/usr/bin/env python3
"""担い手へ仕事を渡す道具（MoA のギア 4 つを実行するだけの薄い包み）。

  new <題名> --member <名> [--independent-of <依頼ID>] [--hands none|workspace] [--fanout N] [--minutes M]
        依頼書のひな形を .loop/tasks/<依頼ID>/task.md に作る。中身は指示役が書く
  run <依頼ID>      依頼書を読み、担い手を別の作業木で起動する（fanout の数だけ並行）
  retry <依頼ID>    枠切れの期限後に同じ依頼を 1 回だけ流す
  status [<依頼ID>] events.jsonl から今の状態を出す
  team              編成の表と、気づいた食い違い
  stats             担い手ごとの実績（何件・何分・合否・守り・費用）
  eval --member 名   小さな課題を流し、合否・秒・使用量を記録する
  adopt <依頼ID>    担い手の変更を commit して今の枝へ merge する

振り分けはしない。誰に頼むかを決めるのは指示役（AGENTS.md）。この道具がするのは
「作業木を用意して、編成の起動の形で 1 回動かし、報告と events を残す」だけ。
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dashboard_data
import inbox

ROOT = Path(os.environ.get("HARNESS_ROOT") or Path(__file__).resolve().parents[1]).resolve()
# 試験は HARNESS_CLIS で偽の CLI の一覧を指す（本番の一覧に試験用の項目を混ぜないため）
CLIS = json.loads(Path(os.environ.get("HARNESS_CLIS") or ROOT / "harness" / "clis.json").read_text(encoding="utf-8"))["clis"]
DEFAULT_MINUTES = 20
JST = timezone(timedelta(hours=9))
QUOTA_MARKER = re.compile(r"usage limit|rate limit|\b429\b|(?:^|[\s:])quota(?:[\s:!]|$)|Retry budget exhausted", re.I | re.M)

TASK_TEMPLATE = """---
member: {member}
hands: {hands}
guard: 
fanout: {fanout}
minutes: {minutes}
independent_of: {independent_of}
---
# {title}

## 目的
＜1〜3 行。何のためにやるか＞

## 受け入れ条件
- ＜機械で確かめられる形で書く。例: python3 harness/check.py が通る＞
- REPORT.md は起動の前置きが書かせるので、変更の一覧に数えてよい。

## 触ってよい場所
- ＜path。ここ以外は変えない＞

## 手順の指定（あれば）
- ＜順番が大事なときだけ。普通は結果だけ書いて、やり方は任せる＞
"""

PREAMBLE = """あなたは担い手です。下の依頼書 1 枚を実行してください。

- 作業する場所は {root}（あなた専用の作業木。ほかの人は触りません）。
- 規則は {root}/AGENTS.md。やり方は {root}/.agents/skills/worker/SKILL.md を読んでください。
- 終わったら報告を {report} に書きます（あなたの作業木の中です。30 行以内）。**報告はファイルに書いてください**（画面に出すだけでは届きません）。書く欄は: 何をした / 検証の結果（打った命令と出力の要点）/ 残り / 人の判断が要ること / 変更したファイル。
- 依頼書に無い変更をしないでください。**自分が作った物**を自分で検収しないでください（確かめるのは別の担い手です）。独立の確認を頼まれたときは合否を書きます。
- 止められた操作を別の書き方で回避しないでください。人の判断が要ることは、実行せず報告に書いてください。

--- ここから依頼書 ---
{task}
--- ここまで依頼書 ---
"""


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def loop() -> Path:
    d = inbox.loop_dir()
    (d / "tasks").mkdir(parents=True, exist_ok=True)
    return d


def die(msg: str):
    print(f"delegate: {msg}", file=sys.stderr)
    raise SystemExit(1)


def team() -> list[dict]:
    p = inbox.loop_dir() / "team.json"
    if not p.exists():
        die(f"編成がありません。harness/team.example.json を {p} へ写し、人と決めてください")
    return json.loads(p.read_text(encoding="utf-8"))["members"]


def member(name: str) -> dict:
    for m in team():
        if m["name"] == name:
            return m
    die(f"編成に担い手 `{name}` がいません（いるのは: {', '.join(m['name'] for m in team())}）")


def quota_deadline(m: dict) -> datetime | None:
    value = m.get("quota_until")
    return datetime.fromisoformat(value) if value else None


def quota_remaining(m: dict) -> timedelta:
    return (quota_deadline(m) or datetime.min.replace(tzinfo=JST)) - datetime.now(JST)


def worker_environment() -> dict[str, str]:
    values = {}
    path = inbox.loop_dir() / "worker.env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                continue
            if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
                value = value[1:-1]
            values[key] = value
    return values


def record_quota(tid: str, m: dict) -> None:
    until = (datetime.now(JST) + timedelta(hours=1)).isoformat(timespec="seconds")
    path = loop() / "team.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    next(x for x in data["members"] if x["name"] == m["name"])["quota_until"] = until
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    event(event="quota", task=tid, member=m["name"], quota_until=until)


def event(**kw) -> None:
    # 同時に動く担い手が 2 人以上いると、行が混ざることがある（/mnt の DrvFS では追記の原子性が保証されない）。
    # 1 行を 1 回の os.write で書き、読む側は壊れた行を飛ばす
    line = (json.dumps({"ts": now(), **kw}, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(loop() / "events.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def task_dir(tid: str) -> Path:
    d = loop() / "tasks" / tid
    if not d.exists():
        die(f"依頼 {tid} がありません")
    return d


def read_task(tid: str) -> tuple[dict, str]:
    text = (task_dir(tid) / "task.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        die(f"{tid}/task.md の先頭にギアの欄（--- で囲む）がありません")
    gears = {k.strip(): v.strip() for k, _, v in (l.partition(":") for l in m.group(1).splitlines() if ":" in l)}
    return gears, m.group(2)


# ---------------------------------------------------------------- new

def cmd_new(a) -> int:
    if a.member:
        member(a.member)
    tid = a.id or f"T-{datetime.now().strftime('%m%d')}-{len(list((loop() / 'tasks').iterdir())) + 1:02d}"
    d = loop() / "tasks" / tid
    if d.exists():
        die(f"{tid} はもうあります")
    d.mkdir(parents=True)
    (d / "task.md").write_text(TASK_TEMPLATE.format(
        member=a.member or "", hands=a.hands, fanout=a.fanout, minutes=a.minutes,
        independent_of=a.independent_of or "", title=a.title), encoding="utf-8")
    print(d / "task.md")
    print(f"目的・受け入れ条件・触ってよい場所を書いたら: python3 harness/delegate.py run {tid}")
    return 0


# ---------------------------------------------------------------- run

def worktree(tid: str, tag: str) -> Path:
    """担い手ごとの作業木。同じ場所を 2 人が書き換えないため、依頼 1 件につき 1 つ作る。"""
    wt = loop() / "work" / f"{tid}-{tag}"
    if wt.exists():
        # 流し直し（run / retry）は今の HEAD から作り直す。前の作業木を使い回すと、そのあとの直しが担い手に届かない
        # （9/25 実測: dsh.sh の直しを入れて流し直したのに、古い作業木の古い dsh.sh が動いた）
        subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(wt)], capture_output=True)
        if wt.exists():
            shutil.rmtree(wt, ignore_errors=True)
    wt.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(ROOT), "worktree", "prune"], capture_output=True)  # 消えた作業木の登録を掃除
    branch = f"work/{tid}-{tag}"
    if os.environ.get("HARNESS_TESTING") == "1":
        marker = hashlib.sha256(str(loop()).encode()).hexdigest()[:12]
        branch = f"work/test-{marker}-{tid}-{tag}"
    r = subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "-f", "-B", branch, str(wt), "HEAD"], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"作業木を作れません: {r.stderr.strip()[:300]}")
    return wt


def build_argv(cli: str, m: dict, root: Path, prompt: str, seconds: int) -> tuple[list[str], str | None]:
    spec = CLIS.get(cli) or die(f"知らない CLI `{cli}`（harness/clis.json）")
    argv_t = spec.get("worker") or die(f"{cli} に担い手としての起動の形がありません（clis.json の worker）")
    stdin = prompt if spec.get("prompt") == "stdin" else None
    argv: list[str] = []
    extra = list(m.get("argv_extra") or [])  # 担い手ごとの追加の旗。依頼文の直前（旗の並びの最後）に入れる
    for tok in argv_t:
        if tok == "{prompt}":
            argv += extra
            extra = []
            if stdin is None:
                argv.append(prompt)
            continue
        if "{model}" in tok:
            if not m.get("model"):  # モデルの指定が無ければ、その旗ごと落とす
                if argv and argv[-1].startswith("-"):
                    argv.pop()
                continue
            tok = tok.replace("{model}", m["model"])
        argv.append(tok.replace("{root}", str(root)).replace("{timeout}", str(seconds)))
    argv += extra  # {prompt} が無い形（標準入力で渡す CLI）は末尾に
    return argv, stdin


def run_one(tid: str, m: dict, gears: dict, body: str, tag: str) -> dict:
    d = task_dir(tid)
    wt = worktree(tid, tag)
    # commit していない変更も作業木へ写す（担い手が、今の木と同じ物を見るため）。
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all"],
                           capture_output=True, text=True).stdout.splitlines()
    for line in dirty:
        rel = line[3:].split(" -> ")[-1].strip('"')
        if rel.startswith(".loop/") or rel.startswith("old/"):
            continue
        src, dst = ROOT / rel, wt / rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
    # 報告は担い手の作業木の中に書かせる（外へ書かせると、CLI 自身が「作業場所の外」として断る）。
    # 終わったら依頼のフォルダへ写す。
    inside = wt / "REPORT.md"
    report = d / f"report-{tag}.md"
    prompt = PREAMBLE.format(root=wt, report=inside, task=body)
    seconds = int(gears.get("minutes") or DEFAULT_MINUTES) * 60
    argv, stdin = build_argv(m["cli"], m, wt, prompt, seconds)
    worker_env = worker_environment()
    env = dict(os.environ)
    env.update(worker_env)
    env.update(HARNESS_ROLE="worker", HARNESS_TASK=tid, HARNESS_MEMBER=m["name"], HARNESS_WORKTREE=str(wt.resolve()))
    env["HARNESS_REPORT"] = str(inside)
    trace = d / f"guard-{tag}.jsonl"
    trace.unlink(missing_ok=True)
    env["HARNESS_GUARD_TRACE"] = str(trace)
    if gears.get("hands") == "none":
        env["HARNESS_HANDS"] = "none"  # 守りが、書く道具と shell を止める（例外は報告 1 本だけ）
    if gears.get("guard") == "edit":
        # 守り自身を直す依頼だけ。担い手は守りのファイルを書けない決まり（9/25）の、指示役が依頼書で開ける例外。
        # 作業木の外に書けない決まりはそのまま効く
        env["HARNESS_GUARD_EDIT"] = "1"
    before = set(subprocess.run(["git", "-C", str(wt), "status", "--porcelain", "--untracked-files=all"],
                                capture_output=True, text=True).stdout.splitlines())
    event(event="start", task=tid, member=m["name"], cli=m["cli"], hands=gears.get("hands", "workspace"), worktree=str(wt), worker_env=len(worker_env))
    t0 = time.time()
    log = d / f"log-{tag}.txt"
    with log.open("w", encoding="utf-8") as f:
        try:
            r = subprocess.run(argv, cwd=wt, env=env, input=stdin or "", stdout=f, stderr=subprocess.STDOUT,
                               text=True, timeout=seconds)
            code = r.returncode
        except subprocess.TimeoutExpired:
            code = 124
        except OSError as e:
            f.write(f"\n起動できません: {e}\n")
            code = 127
    took = round(time.time() - t0)
    log_text = log.read_text(encoding="utf-8", errors="replace")
    guard_calls = len(trace.read_text(encoding="utf-8").splitlines()) if trace.exists() else 0
    usage = CLIS[m["cli"]].get("usage")
    tokens = None
    if usage:
        matches = list(re.finditer(usage, log_text, re.M))
        if matches:
            value = matches[-1].group(1)
            if m["cli"] == "claude":
                # usage の中には配列や 2 段の入れ子（iterations など）があるので、先頭の平らな部分だけを読む
                counts = {k: int(v) for k, v in re.findall(r'"(\w+_tokens)"\s*:\s*(\d+)', value)}
                tokens = sum(counts.get(k, 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            else:
                tokens = int(value.replace(",", ""))
    if inside.exists():
        report.write_text(inside.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        inside.unlink()
    # 数えるのは担い手が変えた分だけ（起動前に写した未 commit の変更は引く）
    after = set(subprocess.run(["git", "-C", str(wt), "status", "--porcelain", "--untracked-files=all"],
                               capture_output=True, text=True).stdout.splitlines())
    changed = sorted(after - before)
    out = {"task": tid, "member": m["name"], "exit": code, "seconds": took,
           "report": str(report) if report.exists() else None, "changed_files": len(changed), "changed": changed[:20],
           "log": str(log), "worktree": str(wt), "guard_calls": guard_calls, "tokens": tokens}
    event(event="end", **out)
    if QUOTA_MARKER.search(log_text) and "MISSING_CREDENTIAL" not in log_text:
        record_quota(tid, m)
    return out


def cmd_run(a) -> int:
    gears, body = read_task(a.id)
    name = a.member or gears.get("member")
    if not name:
        die("依頼書に member がありません（誰に頼むかは指示役が決めます）")
    m = member(name)
    if quota_remaining(m) > timedelta():
        die(f"{name} は枠切れ（{quota_deadline(m).astimezone(JST):%H:%M} に戻る）")
    if gears.get("independent_of"):
        prev = [e for e in events() if e.get("event") == "end" and e.get("task") == gears["independent_of"]]
        vendors = {member(e["member"]).get("vendor") for e in prev}
        if m.get("vendor") in vendors:
            print(f"注意: {gears['independent_of']} を実行したのと同じ会社（{m.get('vendor')}）の担い手です。"
                  "同じモデルは同じ所で間違えるので、別の会社の担い手を勧めます。", file=sys.stderr)
    n = int(gears.get("fanout") or 1)
    limit = int(m.get("max_parallel") or 1)
    if n > limit:
        die(f"fanout {n} は {name} の max_parallel {limit} を超えます")
    results = []
    if n == 1:
        results.append(run_one(a.id, m, gears, body, m["name"]))
    else:
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(max_workers=n) as ex:
            futs = [ex.submit(run_one, a.id, m, gears, body, f"{m['name']}-{i + 1}") for i in range(n)]
            results = [f.result() for f in futs]
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    try:
        dashboard_data.refresh(loop())
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"dashboard の更新に失敗しました: {error}", file=sys.stderr)
    return 0 if all(r["exit"] == 0 and r["report"] for r in results) else 1


def cmd_retry(a) -> int:
    gears, _ = read_task(a.id)
    name = gears.get("member")
    if not name:
        die("依頼書に member がありません（誰に頼むかは指示役が決めます）")
    m = member(name)
    remaining = quota_remaining(m)
    if remaining > timedelta():
        minutes = int((remaining.total_seconds() + 59) // 60)
        die(f"{name} は枠切れ（{quota_deadline(m).astimezone(JST):%H:%M} に戻る、残り {minutes} 分）")
    return cmd_run(argparse.Namespace(id=a.id, member=None))


# ---------------------------------------------------------------- 見る

def events() -> list[dict]:
    p = loop() / "events.jsonl"
    out: list[dict] = []
    if not p.exists():
        return out
    for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            if l.strip():
                out.append(json.loads(l))
        except ValueError:
            print(f"注意: events.jsonl に読めない行があります（同時書き込みで混ざった可能性）: {l[:80]}", file=sys.stderr)
    return out


def cmd_status(a) -> int:
    rows = [e for e in events() if not a.id or e.get("task") == a.id]
    if not rows:
        print("まだ何も動いていません")
        return 0
    live = {}
    for e in rows:
        if e["event"] == "quota":
            continue
        key = (e.get("task"), e.get("member"))
        live[key] = e
    for (tid, mem), e in sorted(live.items()):
        if e["event"] == "start":
            print(f"{tid} {mem}: 実行中（{e['ts']} から）")
        else:
            ok = "報告あり" if e.get("report") else "報告なし"
            print(f"{tid} {mem}: 終了 exit={e['exit']} {e['seconds']}秒 {ok} 変更 {e.get('changed_files', 0)} ファイル "
                  f"guard_calls={e.get('guard_calls', 0)} tokens={e.get('tokens') if e.get('tokens') is not None else '不明'}"
                  + (" 守りが呼ばれていない" if not e.get("guard_calls") else ""))
    return 0


def cmd_team(a) -> int:
    ms = team()
    print(f"{'名前':10s} {'CLI':9s} {'会社':10s} 費用 同時 モデル")
    for m in ms:
        print(f"{m['name']:10s} {m['cli']:9s} {m.get('vendor', ''):10s} {m.get('cost', '?'):>3} {m.get('max_parallel', 1):>3}  {m.get('model') or '(CLI の既定)'}")
    for m in ms:
        if m["cli"] not in CLIS:
            print(f"注意: {m['name']} の CLI `{m['cli']}` は harness/clis.json にありません")
        elif not CLIS[m["cli"]].get("worker"):
            print(f"注意: {m['name']} の CLI `{m['cli']}` は担い手としての起動の形がありません")
        if quota_remaining(m) > timedelta():
            print(f"注意: {m['name']} は {m['quota_until']} まで枠切れです")
    if len({m.get("vendor") for m in ms}) < 2:
        print("注意: 会社が 1 つだけです。独立の確認は別の会社の担い手に頼めません")
    if a.probe:
        print("名前       状態       秒")
        for m in ms:
            start = time.monotonic()
            if quota_remaining(m) > timedelta():
                state = "枠切れ"
            elif not CLIS.get(m["cli"], {}).get("worker"):
                state = "起動失敗"
            else:
                argv, stdin = build_argv(m["cli"], m, ROOT, "OK とだけ返して", 60)
                env = dict(os.environ)
                env.update(worker_environment())
                env.update(HARNESS_ROLE="worker", HARNESS_TASK="probe", HARNESS_MEMBER=m["name"], HARNESS_WORKTREE=str(ROOT))
                try:
                    result = subprocess.run(argv, cwd=ROOT, env=env, input=stdin or "", capture_output=True, text=True, timeout=60)
                    output = result.stdout + result.stderr
                    if "MISSING_CREDENTIAL" in output:
                        state = "鍵なし"
                    elif QUOTA_MARKER.search(output):
                        state = "枠切れ"
                    elif result.returncode == 0 and re.search(r"\bOK\b", output, re.I):
                        state = "使える"
                    else:
                        state = "起動失敗"
                except subprocess.TimeoutExpired:
                    state = "時間切れ"
                except OSError:
                    state = "起動失敗"
            print(f"{m['name']:10s} {state:8s} {time.monotonic() - start:.1f}秒")
    return 0


def eval_rows() -> list[dict]:
    folder = loop() / "evals"
    rows = []
    for path in sorted(folder.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                print(f"注意: {path} に読めない行があります", file=sys.stderr)
    return rows


def cmd_eval(a) -> int:
    tasks = {p.name: p for p in (ROOT / "harness" / "evals").iterdir()
             if p.is_dir() and (p / "task.md").is_file() and (p / "check.py").is_file()}
    selected = [a.task] if a.task else sorted(tasks)
    for name in selected:
        if name not in tasks:
            die(f"評価課題 `{name}` がありません（あるのは: {', '.join(sorted(tasks))}）")
    names = list(dict.fromkeys(n.strip() for n in a.member.split(",")))
    if not all(names):
        die("--member に担い手の名前を指定してください")
    for name in names:
        member(name)
    folder = loop() / "evals"
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"{datetime.now().date().isoformat()}.jsonl"
    all_passed = True
    for name in names:
        for task_name in selected:
            prefix = f"E-{datetime.now().strftime('%Y%m%d')}-"
            seq = 1
            while (loop() / "tasks" / f"{prefix}{seq:03d}").exists():
                seq += 1
            tid = f"{prefix}{seq:03d}"
            with contextlib.redirect_stdout(io.StringIO()):
                cmd_new(argparse.Namespace(title=f"評価課題: {task_name}", id=tid, member=name,
                                           hands="workspace", fanout=1, minutes=5, independent_of=None))
            source = (tasks[task_name] / "task.md").read_text(encoding="utf-8")
            (task_dir(tid) / "task.md").write_text(source.replace("member:\n", f"member: {name}\n", 1), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    cmd_run(argparse.Namespace(id=tid, member=None))
                except SystemExit:
                    pass
            result = next((e for e in reversed(events()) if e.get("event") == "end" and e.get("task") == tid), {})
            passed = False
            if result.get("exit") == 0 and result.get("report"):
                try:
                    check = subprocess.run([sys.executable, "-B", str(tasks[task_name] / "check.py"),
                                            result["worktree"], result["report"]],
                                           cwd=ROOT, capture_output=True, text=True, timeout=20)
                    passed = check.returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    pass
            row = {"member": name, "task": task_name, "passed": passed,
                   "seconds": result.get("seconds"), "tokens": result.get("tokens"),
                   "guard_calls": result.get("guard_calls", 0)}
            with output.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(json.dumps(row, ensure_ascii=False))
            all_passed &= passed
    return 0 if all_passed else 1


def cmd_stats(a) -> int:
    ends = [e for e in events() if e.get("event") == "end"]
    evals = eval_rows()
    print(f"{'名前':10s} 件数 成功 平均秒 報告あり guard_calls tokens 評価")
    if not ends and not evals:
        print("まだ実績がありません（評価: 未評価）")
        return 0
    by: dict[str, list[dict]] = {}
    evaluated: dict[str, list[dict]] = {}
    for e in ends:
        by.setdefault(e["member"], []).append(e)
    for e in evals:
        evaluated.setdefault(e["member"], []).append(e)
    for name in sorted(by.keys() | evaluated.keys()):
        rows = by.get(name, [])
        measured = evaluated.get(name, [])
        ok = sum(1 for r in rows if r["exit"] == 0 and r.get("report"))
        rep = sum(1 for r in rows if r.get("report"))
        tokens = sum(r["tokens"] for r in rows if isinstance(r.get("tokens"), int))
        known = any(isinstance(r.get("tokens"), int) for r in rows)
        calls = sum(r.get("guard_calls", 0) for r in rows)
        if measured:
            avg_seconds = (str(round(sum(r["seconds"] for r in measured) / len(measured)))
                           if all(isinstance(r.get("seconds"), int) for r in measured) else "不明")
            avg_tokens = (str(round(sum(r["tokens"] for r in measured) / len(measured)))
                          if all(isinstance(r.get("tokens"), int) for r in measured) else "不明")
            score = f"合格 {sum(bool(r['passed']) for r in measured)}/{len(measured)}、平均 {avg_seconds} 秒、平均 {avg_tokens} トークン"
        else:
            score = "未評価"
        print(f"{name:10s} {len(rows):>4} {ok:>4} {round(sum(r['seconds'] for r in rows) / len(rows)) if rows else '不明':>6} {rep:>8} {calls:>11} {tokens if known else '不明'} 評価: {score}"
              + (" 守りが呼ばれていない" if not calls else ""))
    print("この表は材料です。誰に頼むかは指示役が決めます（AGENTS.md）。")
    return 0


def cmd_adopt(a) -> int:
    ends = [e for e in events() if e.get("event") == "end" and e.get("task") == a.id]
    if a.member:
        ends = [e for e in ends if e.get("member") == a.member][-1:]  # 同じ担い手で打ち直したときは最後の 1 回
    if len(ends) != 1:
        die("取り込む担い手を 1 人に決めてください（--member <名>）")
    e = ends[0]
    if e.get("exit") != 0 or not e.get("report"):
        die("終了 exit=0 と報告が揃った成果だけ取り込めます")
    wt = Path(e["worktree"]) if e.get("worktree") else loop() / "work" / f"{a.id}-{e['member']}"
    if not wt.exists():
        die(f"作業木がありません: {wt}")
    branch = subprocess.run(["git", "-C", str(wt), "branch", "--show-current"], capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git", "-C", str(wt), "add", "-A", "--", ".", ":!REPORT.md"], check=True)
    staged = subprocess.run(["git", "-C", str(wt), "diff", "--cached", "--quiet"])
    if staged.returncode == 0:
        die("取り込む変更がありません")
    author = e["member"]
    subprocess.run(["git", "-C", str(wt), "-c", f"user.name={author}", "-c", f"user.email={author}@local.invalid",
                    "commit", "-m", f"{a.id}: {author} の成果"], check=True)
    merged = subprocess.run(["git", "-C", str(ROOT), "merge", "--no-ff", branch])
    if merged.returncode:
        print("衝突しました。merge を止めずに置きます。状態を確認してください。", file=sys.stderr)
    return merged.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="担い手へ仕事を渡す")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("title")
    n.add_argument("--id")
    n.add_argument("--member")
    n.add_argument("--hands", choices=("workspace", "none"), default="workspace")
    n.add_argument("--fanout", type=int, default=1)
    n.add_argument("--minutes", type=int, default=DEFAULT_MINUTES)
    n.add_argument("--independent-of", dest="independent_of")
    r = sub.add_parser("run")
    r.add_argument("id")
    r.add_argument("--member")
    retry = sub.add_parser("retry")
    retry.add_argument("id")
    s = sub.add_parser("status")
    s.add_argument("id", nargs="?")
    team_cmd = sub.add_parser("team")
    team_cmd.add_argument("--probe", action="store_true")
    sub.add_parser("stats")
    evaluate = sub.add_parser("eval")
    evaluate.add_argument("--member", required=True, help="担い手の名前。複数ならコンマ区切り")
    evaluate.add_argument("--task", help="課題名。省略すると全課題")
    adopt = sub.add_parser("adopt")
    adopt.add_argument("id")
    adopt.add_argument("--member")
    a = ap.parse_args(argv)
    return {"new": cmd_new, "run": cmd_run, "retry": cmd_retry, "status": cmd_status, "team": cmd_team,
            "stats": cmd_stats, "eval": cmd_eval, "adopt": cmd_adopt}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
