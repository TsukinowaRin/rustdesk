#!/usr/bin/env python3

from __future__ import annotations

import argparse
import filecmp
import pathlib
import shutil
import time
from contextlib import contextmanager


# v2 では mirror は Claude Code 用の 1 本だけにする。Codex / Antigravity / Cursor /
# opencode / Kilo Code は `.agents/skills/` を native に読むため（出典は
# docs/SOURCES.md）、mirror を増やすと drift リスクと保守コストだけが増える。
# Claude Code が AGENTS.md / .agents/skills を native 対応したら、この script ごと
# 廃止してよい。
MIRROR_ROOTS = (".claude/skills",)


@contextmanager
def skill_sync_lock(repo_root: pathlib.Path):
    lock_dir = repo_root / "tmp" / ".skill-sync.lock"
    lock_dir.parent.mkdir(exist_ok=True)

    # Mirror sync deletes and recreates target directories. If smoke and a
    # manual sync run at the same time, one process can observe a half-written
    # mirror and fail. A directory lock keeps the operation portable and avoids
    # adding an external dependency.
    for _ in range(600):
        try:
            lock_dir.mkdir()
            break
        except FileExistsError:
            try:
                if time.time() - lock_dir.stat().st_mtime > 600:
                    lock_dir.rmdir()
                    continue
            except OSError:
                pass
            time.sleep(0.1)
    else:
        raise TimeoutError(f"timed out waiting for skill sync lock: {lock_dir}")

    try:
        yield
    finally:
        try:
            lock_dir.rmdir()
        except OSError:
            pass


def sync_tree(source_root: pathlib.Path, target_root: pathlib.Path) -> None:
    # `.agents/skills` stays the only hand-edited source so agents do not drift
    # by CLI. WSL + Windows ドライブ (drvfs) では symlink が壊れやすいため、
    # 参照ではなくコピー同期にしている。
    source_names = set()

    for source_dir in sorted(source_root.iterdir()):
        if not source_dir.is_dir():
            continue
        if not (source_dir / "SKILL.md").exists():
            continue
        skill_name = source_dir.name
        source_names.add(skill_name)
        target_dir = target_root / skill_name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(source_dir, target_dir)

    if target_root.exists():
        for target_dir in sorted(target_root.iterdir()):
            if not target_dir.is_dir():
                continue
            if target_dir.name in source_names:
                continue
            shutil.rmtree(target_dir)


def compare_trees(left: pathlib.Path, right: pathlib.Path, relative: pathlib.Path) -> list[str]:
    """copy mirrorのfile set、type、bytesの差を再帰的に返す。"""
    problems = []
    left_entries = {path.name: path for path in left.iterdir()}
    right_entries = {path.name: path for path in right.iterdir()}

    for name in sorted(left_entries.keys() - right_entries.keys()):
        problems.append(f"mirror missing: {relative / name}")
    for name in sorted(right_entries.keys() - left_entries.keys()):
        problems.append(f"mirror extra: {relative / name}")

    for name in sorted(left_entries.keys() & right_entries.keys()):
        source = left_entries[name]
        target = right_entries[name]
        path = relative / name
        if source.is_symlink() or target.is_symlink():
            problems.append(f"mirror symlink unsupported: {path}")
        elif source.is_dir() != target.is_dir():
            problems.append(f"mirror type mismatch: {path}")
        elif source.is_dir():
            problems.extend(compare_trees(source, target, path))
        elif not filecmp.cmp(source, target, shallow=False):
            problems.append(f"mirror content differs: {path}")

    return problems


def mirror_problems(source_root: pathlib.Path, target_root: pathlib.Path) -> list[str]:
    """sync_treeが生成するべきskill集合と現在のmirrorを比較する。"""
    source_names = {
        path.name
        for path in source_root.iterdir()
        if not path.is_symlink() and path.is_dir() and (path / "SKILL.md").is_file()
    }
    if not target_root.is_dir():
        return [f"mirror root missing: {target_root}"]

    problems = []
    target_entries = {path.name: path for path in target_root.iterdir()}
    target_names = set(target_entries)
    for name in sorted(source_names - target_names):
        problems.append(f"mirror missing: {name}")
    for name in sorted(target_names - source_names):
        problems.append(f"mirror extra: {name}")
    for name in sorted(source_names & target_names):
        target = target_entries[name]
        if target.is_symlink() or not target.is_dir():
            problems.append(f"mirror type mismatch: {name}")
            continue
        problems.extend(compare_trees(source_root / name, target, pathlib.Path(name)))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="repo-local skillsをClaude mirrorへ同期する")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fileを変更せず、正本とmirrorのdriftがあればexit 1",
    )
    args = parser.parse_args()

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    source_root = repo_root / ".agents" / "skills"

    with skill_sync_lock(repo_root):
        if args.check:
            problems = []
            for mirror in MIRROR_ROOTS:
                problems.extend(mirror_problems(source_root, repo_root / mirror))
            if problems:
                print("skill mirror drift:")
                for problem in problems:
                    print(f"- {problem}")
                print("正本を確認し、必要なら python3 scripts/sync_shared_skills.py で再生成する。")
                return 1
            print("Skill mirrors match: " + ", ".join(MIRROR_ROOTS))
            return 0

        for mirror in MIRROR_ROOTS:
            sync_tree(source_root, repo_root / mirror)

    print("Synced shared skills into " + ", ".join(MIRROR_ROOTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
