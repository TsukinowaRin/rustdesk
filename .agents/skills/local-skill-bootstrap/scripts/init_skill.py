#!/usr/bin/env python3

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
import textwrap


def _repo_root() -> pathlib.Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return pathlib.Path.cwd()
    return pathlib.Path(result.stdout.strip())


def _normalize_skill_name(raw: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    if not normalized:
        raise ValueError("skill name is empty after normalization")
    if len(normalized) > 64:
        raise ValueError("skill name must be 64 characters or fewer")
    return normalized


def _skill_template(skill_name: str, description: str) -> str:
    return textwrap.dedent(
        f"""\
        ---
        name: {skill_name}
        description: {description}
        ---

        # {skill_name}

        ## Trigger

        - この skill を使う場面:
        - この skill を使わない場面:

        ## Workflow

        1.
        2.
        3.

        ## Validation

        -
        """
    )


def _write_if_missing(path: pathlib.Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sync_claude_skills(repo_root: pathlib.Path) -> None:
    sync_script = repo_root / "scripts" / "sync_shared_skills.py"
    if not sync_script.exists():
        return
    subprocess.run([sys.executable, str(sync_script)], cwd=repo_root, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a repo-local shared skill")
    parser.add_argument("--name", required=True, help="Skill folder name or title")
    parser.add_argument("--description", required=True, help="Skill trigger description")
    parser.add_argument("--with-scripts", action="store_true")
    parser.add_argument("--with-references", action="store_true")
    parser.add_argument("--with-assets", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-sync-claude", action="store_true")
    args = parser.parse_args()

    repo_root = _repo_root()
    skill_name = _normalize_skill_name(args.name)
    skill_dir = repo_root / ".agents" / "skills" / skill_name

    skill_dir.mkdir(parents=True, exist_ok=True)
    _write_if_missing(skill_dir / "SKILL.md", _skill_template(skill_name, args.description), args.force)

    if args.with_scripts:
        (skill_dir / "scripts").mkdir(exist_ok=True)
    if args.with_references:
        (skill_dir / "references").mkdir(exist_ok=True)
    if args.with_assets:
        (skill_dir / "assets").mkdir(exist_ok=True)

    if not args.no_sync_claude:
        _sync_claude_skills(repo_root)

    print(f"Created shared skill scaffold: {skill_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
