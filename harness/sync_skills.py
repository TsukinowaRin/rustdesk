#!/usr/bin/env python3
"""スキルを全 CLI から読める状態にする。編集元は .agents/skills/（Agent Skills 標準）の 1 か所だけ。

  python3 harness/sync_skills.py           写しと設定を作り直す
  python3 harness/sync_skills.py --check   ずれていないか見るだけ（点検が使う）

CLI ごとの読み方は harness/clis.json の skills_mode:
  native = .agents/skills/ を直接読む（8 本）      mirror = 専用の写しが要る（Claude Code）
  config = 設定ファイルで置き場を指す（Kilo）
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / ".agents" / "skills"
CLIS = json.loads((ROOT / "harness" / "clis.json").read_text(encoding="utf-8"))["clis"]


def skills() -> list[Path]:
    return sorted(d for d in SRC.iterdir() if d.is_dir() and (d / "SKILL.md").exists()) if SRC.exists() else []


def mirror(dst: Path, check: bool) -> list[str]:
    bad, names = [], set()
    for s in skills():
        names.add(s.name)
        d = dst / s.name
        same = d.exists() and all(
            (d / p.relative_to(s)).exists() and (d / p.relative_to(s)).read_bytes() == p.read_bytes()
            for p in s.rglob("*") if p.is_file())
        if same:
            continue
        if check:
            bad.append(f"{d} が編集元と違います")
        else:
            shutil.rmtree(d, ignore_errors=True)
            shutil.copytree(s, d)
            print(f"写した {dst.name}/{s.name}")
    if dst.exists():
        for d in sorted(dst.iterdir()):
            if d.is_dir() and d.name not in names:
                if check:
                    bad.append(f"{d} は編集元にありません")
                else:
                    shutil.rmtree(d)
                    print(f"消した {dst.name}/{d.name}")
    return bad


def config_points(path: Path, check: bool) -> list[str]:
    if path.exists() and ".agents/skills" in path.read_text(encoding="utf-8"):
        return []
    return [f"{path} が .agents/skills を指していません"]


def main(argv: list[str]) -> int:
    check = "--check" in argv
    if not skills():
        print("スキルがありません（.agents/skills/）")
        return 0
    bad: list[str] = []
    for name, c in CLIS.items():
        mode = c.get("skills_mode")
        if mode == "mirror":
            bad += mirror(ROOT / c["skills_path"], check)
        elif mode == "config":
            bad += config_points(ROOT / c["skills_config"], check)
    for b in bad:
        print("NG  " + b)
    modes = {}
    for name, c in CLIS.items():
        modes.setdefault(c.get("skills_mode", "?"), []).append(name)
    print(f"スキル {len(skills())} 本 / 直接読む {len(modes.get('native', []))} CLI ・ "
          f"写し {len(modes.get('mirror', []))} ・ 設定で指す {len(modes.get('config', []))}"
          + ("（ずれ 0）" if not bad else f"（ずれ {len(bad)} 件。直すには --check を外して実行）"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
