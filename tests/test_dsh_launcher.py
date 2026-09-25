#!/usr/bin/env python3
"""dsh の起動口の試験。偽の dsh を PATH に置き、渡る引数と置き場を見る（本物は起動しない。外へ出ない）。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

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
        fake = Path(tmp) / "bin"
        fake.mkdir()
        (fake / "dsh").write_text('#!/usr/bin/env bash\npython3 -c \'import json,os,sys; print(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(), "home": os.environ.get("DSH_HOME")}))\' "$@"\n', encoding="utf-8")
        (fake / "dsh").chmod(0o755)

        def run(*args: str, **env: str) -> tuple[int, str]:
            e = {k: v for k, v in os.environ.items() if k != "DSH_HOME"}
            e.update(env, PATH=f"{fake}:{e['PATH']}")
            r = subprocess.run(["bash", str(ROOT / "harness" / "dsh.sh"), *args], capture_output=True, text=True, env=e, cwd=tmp)
            return r.returncode, r.stdout + r.stderr

        code, out = run("--profile", "headless", "依頼")
        got = json.loads(out)
        check("守りの追加設定を必ず付ける", got["argv"][:2] == ["--patch", str(ROOT / ".dsh" / "guard.patch.yml")], out)
        check("依頼の引数はそのまま渡る", got["argv"][-3:] == ["--profile", "headless", "依頼"], out)
        check("repo の根で起動する（hook の設定が起動した場所から読まれるため）", got["cwd"] == str(ROOT), out)
        check("認証情報の置き場（DSH_HOME）に触らない = dsh 本体のグローバルな置き場が使われる", got["home"] is None, out)
        code, out = run("web")
        check("web は --profile web に直して渡す", json.loads(out)["argv"][-2:] == ["--profile", "web"], out)
        home = ROOT / ".loop" / f"dsh-home-{Path(tmp).name}"
        code, out = run("--profile", "acp", DSH_HOME=str(home))
        check("repo の中を指す DSH_HOME は断る（認証情報を repo に置かない）", code == 2 and "repo の中" in out, out)
        home.rmdir()
        outside = Path(tmp) / "elsewhere"
        code, out = run("--profile", "acp", DSH_HOME=str(outside))
        check("repo の外を指す DSH_HOME は人の選択なので通す", code == 0 and json.loads(out)["home"] == str(outside), out)
        local = ROOT / ".dsh" / f"zz-test-{Path(tmp).name}.local.patch.yml"
        local.write_text("# test\n", encoding="utf-8")
        try:
            code, out = run("--profile", "headless")
            check("人ごとの設定（*.local.patch.yml）を付ける", str(local) in json.loads(out)["argv"], out)
        finally:
            local.unlink()
        r = subprocess.run(["git", "check-ignore", "-q", ".dsh/providers.local.patch.yml"], cwd=ROOT)
        check("人ごとの設定は git に入らない", r.returncode == 0)
        patch = (ROOT / ".dsh" / "guard.patch.yml").read_text(encoding="utf-8")
        check("守りは Claude Code と同じ hook 設定を共用する", "configPath: ./.claude/settings.json" in patch)
        for tool in ("tool-subagent", "tool-subagent-fork", "tool-subagent-control", "tool-subagent-list-agents", "tool-ralph", "tool-workflow"):
            check(f"標準の子エージェント系 {tool} を止める", f"- id: {tool}\n  disabled: true" in patch)
        for f in (".dsh/guard.patch.yml", ".dsh/providers.example.yml"):
            text = (ROOT / f).read_text(encoding="utf-8")
            check(f"{f} に鍵そのものを書かない", "sk-" not in text and "tk_" not in text and "Bearer" not in text)
    for b in bad:
        print("NG  " + b)
    print(f"dsh の起動口の試験: {count} 場面、ずれ {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
