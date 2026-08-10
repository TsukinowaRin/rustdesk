#!/usr/bin/env python3
"""opencode.jsonc / kilo.jsonc の permission block を単一ソースから生成する。

背景: 両ファイルの permission block はバイト一致の内容を手書きで二重管理しており、
片方だけ直して片方が古いまま、という permission drift はセキュリティ事故になる。
skills の sync_shared_skills.py と同じ「単一ソース + 生成 + smoke 検証」方式に揃える。

- 編集元: .agent-shared/permissions.json（strict JSON。コメントは "_comment" キー）
- 生成先: 各 jsonc の marker 行に挟まれた区間だけを置換する
    // permissions:generated:start ...
    "permission": { ... }
    // permissions:generated:end
  marker 行自体は保持する。marker の外（$schema、skills.paths 等）は触らない。
- --check: 生成結果と現状を比較し、drift があれば非ゼロで終了する（security_smoke.sh が呼ぶ）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / ".agent-shared" / "permissions.json"
TARGETS = (REPO_ROOT / "opencode.jsonc", REPO_ROOT / "kilo.jsonc")

START_MARKER = "// permissions:generated:start"
END_MARKER = "// permissions:generated:end"


def render_permission_block(permission: dict) -> list[str]:
    """marker 区間へ入れる行のリストを返す（末尾カンマなし = 区間は object の最終メンバに置く）。"""
    dumped = json.dumps({"permission": permission}, indent=2, ensure_ascii=False)
    # json.dumps のトップレベル {} を剥がすと、メンバ行は既に 2-space indent になっている
    return dumped.splitlines()[1:-1]


def rebuild(text: str, block_lines: list[str], path: Path) -> str:
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if START_MARKER in l)
        end = next(i for i, l in enumerate(lines) if END_MARKER in l)
    except StopIteration:
        sys.exit(f"error: {path.name} に marker（{START_MARKER} / {END_MARKER}）が無い。"
                 " 生成対象区間を特定できないため中断する。")
    if end <= start:
        sys.exit(f"error: {path.name} の marker 順序が不正。")
    new_lines = lines[: start + 1] + block_lines + lines[end:]
    return "\n".join(new_lines) + "\n"


def validate_jsonc(text: str, path: Path) -> None:
    """行頭 // コメントだけ剥がして JSON として parse できることを確認する。"""
    stripped = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    try:
        json.loads(stripped)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: 生成後の {path.name} が JSON として不正: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="書き込まず drift の有無だけ検査する（drift ありは exit 1）")
    args = parser.parse_args()

    permission = json.loads(SOURCE.read_text(encoding="utf-8"))["permission"]
    block_lines = render_permission_block(permission)

    drift = []
    for target in TARGETS:
        current = target.read_text(encoding="utf-8")
        rebuilt = rebuild(current, block_lines, target)
        validate_jsonc(rebuilt, target)
        if rebuilt != current:
            drift.append(target)
            if not args.check:
                target.write_text(rebuilt, encoding="utf-8")

    if args.check:
        if drift:
            names = ", ".join(p.name for p in drift)
            print(f"permission drift: {names} が .agent-shared/permissions.json と一致しない。"
                  " python3 scripts/sync_permissions.py で再生成する。")
            return 1
        print("permissions: opencode.jsonc / kilo.jsonc は単一ソースと一致")
        return 0

    if drift:
        print("regenerated: " + ", ".join(p.name for p in drift))
    else:
        print("permissions: 変更なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
