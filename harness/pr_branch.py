#!/usr/bin/env python3
"""PR に出す branch を作る。作業 branch から「harness:」で始まる commit を抜き、本家の上に積み直す。

  python3 harness/pr_branch.py <作業branch> [--upstream upstream/master] [--name <PR用branch>] [--force]

- 作業 branch と本家の分かれ目（merge-base）の上に、harness 以外の commit だけを cherry-pick する（merge commit は飛ばす）。
- 出来た branch に、ハーネスの commit が触ったファイルや、ハーネスが足した置き場のファイルが残っていれば失敗にする（混入の点検）。
- push はしない（外へ出す操作は人が決める）。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "harness:"


def git(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        die(f"git {' '.join(args)} が失敗しました: {r.stderr.strip()}")
    return r.stdout.strip()


def die(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("branch")
    ap.add_argument("--upstream", default="upstream/master")
    ap.add_argument("--name")
    ap.add_argument("--force", action="store_true", help="同名の PR 用 branch があれば作り直す")
    a = ap.parse_args(argv)
    name = a.name or f"{a.branch}-pr"

    base = git("merge-base", a.branch, a.upstream)
    # delegate.py adopt の merge commit は飛ばし、中の commit だけを積む（merge で衝突を解いた分は積み直しで衝突として出る）
    commits = git("rev-list", "--reverse", "--no-merges", f"{base}..{a.branch}").split()
    harness, keep = [], []
    for c in commits:
        (harness if git("log", "-1", "--format=%s", c).startswith(PREFIX) else keep).append(c)
    if not keep:
        die("ハーネス以外の commit がありません")
    touched = set()
    for c in harness:
        touched |= set(git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split("\n")) - {""}

    if git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False):
        if not a.force:
            die(f"{name} は既にあります。作り直すなら --force")
        git("branch", "-D", name)
    with tempfile.TemporaryDirectory(prefix="pr-branch-") as tmp:
        wt = Path(tmp) / "wt"
        git("worktree", "add", "-b", name, str(wt), base)
        try:
            for c in keep:
                r = subprocess.run(["git", "-C", str(wt), "cherry-pick", c], capture_output=True, text=True)
                if r.returncode != 0:
                    subprocess.run(["git", "-C", str(wt), "cherry-pick", "--abort"], capture_output=True)
                    git("branch", "-D", name, check=False)
                    die(f"{c[:9]} の cherry-pick が衝突しました（ハーネスの commit に依存している可能性）。{name} は作りませんでした:\n{r.stdout}{r.stderr}")
        finally:
            subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(wt)], capture_output=True)

    changed = set(git("diff", "--name-only", f"{base}..{name}").split("\n")) - {""}
    # ハーネスが丸ごと足した置き場（harness/・.agents/ など）は、後から足したファイルも混入として数える
    in_base = set(git("ls-tree", "--name-only", base).split("\n"))
    owned = {p.split("/")[0] for p in touched} - in_base
    leaked = sorted(p for p in changed if p in touched or p.split("/")[0] in owned)
    if leaked:
        die(f"{name} にハーネスのファイルが残っています: {leaked[:10]}。push せずに中身を確かめてください")
    print(f"{name} を作りました（{base[:9]} の上に {len(keep)} 件。抜いた harness commit {len(harness)} 件）。")
    print(f"本家との差分: {len(changed)} ファイル。ハーネスの混入なし。push は人が決めてから。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
