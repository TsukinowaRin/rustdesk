#!/usr/bin/env python3
"""判断の輪の試験。使い捨ての置き場と、作り物の会話ログで、上流の道具ごと通す（実物の .loop/judgment は触らない）。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
bad: list[str] = []
count = 0

CARD = """## Q-2026-01-02-01 🔴
- 種別: 公開
- 宛先: GitHub の利用者
- 内容: v3.1.0 を release する
- 前提: 9/17 に作り直しを始め、点検が通った
- 現物: gh release create v3.1.0
- 根拠: docs/PLAN.md
- 取り消し可能性: 一部可
- エージェントの迷い: zip の中身を人が見ていない
- 推奨: 保留。人が zip を 1 回開いてから
- 無回答時: 保留
- [ ] 承認  / [ ] 修正して承認  / [ ] 却下（理由:            ）
"""


def check(name: str, cond: bool, detail: str = "") -> None:
    global count
    count += 1
    if not cond:
        bad.append(f"{name} :: {detail[-300:]}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        home, logs = Path(tmp) / "home", Path(tmp) / "logs"
        logs.mkdir()
        env = dict(os.environ, HARNESS_JUDGMENT_HOME=str(home), HARNESS_LOG_DIR=str(logs),
                   HARNESS_LOOP_DIR=str(Path(tmp) / "loop"))

        def run(*args: str) -> tuple[int, str]:
            r = subprocess.run([sys.executable, "-B", str(ROOT / "harness" / "judgment.py"), *args], capture_output=True, text=True, env=env)
            return r.returncode, r.stdout + r.stderr

        code, out = run("brief")
        check("init の前は止まる", code == 1 and "init" in out, out)
        code, out = run("init")
        kit = ROOT / "vendor" / "kagemusha" / "templates"
        check("上流の型が 1 文字も変えずに写る", all((home / n).read_bytes() == (kit / s).read_bytes() for s, n in
              [("approval_queue.md", "approval_queue.md"), ("decisions_journal.md", "decisions_journal.md"), ("judgment_model.md", "judgment_model.md")]), out)
        cfg = (home / "config.env").read_text(encoding="utf-8")
        check("通知は既定で切、上流の見本の題目を使わない", "NTFY_ENABLED=0" in cfg and "change-me" not in cfg, cfg)
        check("蒸留に権限を外す旗を渡さない", 'DISTILL_AGENT_FLAGS=""' in cfg and "dangerously" not in cfg, cfg)
        (home / "judgment_model.md").write_text("人の原則", encoding="utf-8")
        run("init")
        check("2 度目の init は人のファイルを上書きしない", (home / "judgment_model.md").read_text(encoding="utf-8") == "人の原則")
        code, out = run("brief")
        check("原則が道具の外で変わったら知らせ、中身を出さない", "変わっています" in out and "人の原則" not in out, out)
        (home / "judgment_model.md").write_bytes((kit / "judgment_model.md").read_bytes())
        run("seal")
        code, out = run("brief")
        check("seal のあとは原則を出す", "変わっています" not in out and "判断原則" in out, out)

        # カード: 欄は上流の型から読む
        sys.path.insert(0, str(ROOT / "harness"))
        import judgment
        check("カードの欄を上流の型から読む", judgment.card_fields() == ["種別", "宛先", "内容", "前提", "現物", "根拠", "取り消し可能性", "エージェントの迷い", "推奨", "無回答時"], str(judgment.card_fields()))
        q = home / "approval_queue.md"
        base = q.read_text(encoding="utf-8")
        q.write_text(base.replace("## 未処理\n", "## 未処理\n\n" + CARD, 1), encoding="utf-8")
        code, out = run("check")
        check("型どおりのカードは通る", code == 0 and "未処理 1 枚" in out, out)
        q.write_text(base.replace("## 未処理\n", "## 未処理\n\n" + CARD.replace("- 現物: gh release create v3.1.0\n", "- 現物: \n").replace(" 🔴", ""), 1), encoding="utf-8")
        code, out = run("check")
        check("現物が空・重みが無いカードは落ちる", code == 1 and "現物" in out and "重み" in out, out)
        four = "".join(CARD.replace("-01 🔴", f"-0{i} 🟡") for i in range(1, 5))
        q.write_text(base.replace("## 未処理\n", "## 未処理\n\n" + four, 1), encoding="utf-8")
        code, out = run("check")
        check("4 枚あれば 3 枚までと知らせる", "3 枚まで" in out, out)

        # 採取: 語彙が空なら動かない。人の言葉は拾い、子エージェントへの文は拾わない
        code, out = run("harvest")
        check("語彙が空なら採取せず、育て方を言う", code == 1 and "pattern" in out, out)
        code, out = run("pattern", "違う|(そうじゃな", "--heard", "違う")
        check("壊れた正規表現は語彙に入れない（上流の採取を止めないため）", code == 1 and "読めません" in out, out)
        code, out = run("pattern", "x*")
        check("何にでも当たる語彙は入れない", code == 1, out)
        code, out = run("pattern", "やめて", "--heard", "違う、勝手に全部書き直さないで")
        check("実際に言われた言葉に当たらない語彙は入れない", code == 1 and "当たりません" in out, out)
        code, out = run("pattern", "違う|そうじゃな|勝手に", "--heard", "違う、勝手に全部書き直さないで")
        check("言われた言葉に当たる語彙は入る", code == 0 and "1 個" in out, out)
        code, out = run("pattern", "違う|そうじゃな|勝手に")
        check("同じ語彙は 2 度入らない", "もうあります" in out, out)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        rows = [
            {"type": "assistant", "sessionId": "s1", "timestamp": ts, "isSidechain": False, "message": {"role": "assistant", "content": [{"type": "text", "text": "README を全部書き直しました。"}]}},
            {"type": "user", "sessionId": "s1", "timestamp": ts, "isSidechain": False, "message": {"role": "user", "content": "違う、勝手に全部書き直さないで。頼んだのは誤字だけ。"}},
            {"type": "user", "sessionId": "s1", "timestamp": ts, "isSidechain": True, "message": {"role": "user", "content": "違う、これは子エージェントへの依頼文"}},
        ]
        (logs / "s1.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        code, out = run("harvest")
        mat = (home / "correction_material.md").read_text(encoding="utf-8") if (home / "correction_material.md").exists() else ""
        check("人の訂正を拾う", code == 0 and "new_events=1" in out and "頼んだのは誤字だけ" in mat, out)
        check("子エージェントへの文は拾わない", "子エージェントへの依頼文" not in mat, mat)
        check("直された物（直前の AI の発言）も一緒に残る", "全部書き直しました" in mat, mat)
        code, out = run("harvest")
        check("2 度打っても同じ訂正は増えない", "new_events=0" in out, out)
        code, out = run("brief")
        check("brief が数を出す", "未処理のカード 4 枚" in out and "蒸留待ちの訂正 1 件" in out and "語彙 1 個" in out, out)
        code, out = run("distill", "--dry-run")
        check("しきい値（5 件）未満ではモデルを呼ばない", code == 0 and "SKIPPED" in out and "threshold 5" in out, out)

        # 写しが上流のままか
        sums = (ROOT / "vendor" / "kagemusha" / "SHA256SUMS").read_text(encoding="utf-8")
        files = [l for l in (ROOT / "vendor" / "kagemusha" / "FILES.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
        r = subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=ROOT / "vendor" / "kagemusha", capture_output=True, text=True)
        check("vendor/kagemusha の全ファイルが記録した hash と一致し、一覧と同じ本数", r.returncode == 0 and len(sums.splitlines()) == len(files), r.stdout + r.stderr)
    shared_store()
    for b in bad:
        print("NG  " + b)
    print(f"判断の輪の試験: {count} 場面、ずれ {len(bad)}")
    return 1 if bad else 0


def shared_store() -> None:
    # 実際の clone/pull/push をローカルだけで通す。宛先・秘密・履歴の検査が消えると失敗する。
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.invalid",
                   GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.invalid",
                   GIT_ALLOW_PROTOCOL="file", HARNESS_LOOP_DIR=str(base / "loop"))

        def git(where, *args, ok=True):
            r = subprocess.run(["git", "-C", str(where), *args], env=env, capture_output=True, text=True)
            if ok and r.returncode:
                raise RuntimeError(r.stderr)
            return r.stdout.strip()

        project, remote, seed, home = (base / n for n in ("workspace", "remote.git", "seed", "home"))
        project.mkdir()
        git(project, "init", "-b", "main")
        git(base, "init", "--bare", "--initial-branch=main", str(remote))
        git(base, "clone", str(remote), str(seed))
        (seed / "decisions_journal.md").write_text("共有の台帳\n", encoding="utf-8")
        git(seed, "add", "decisions_journal.md")
        git(seed, "commit", "-m", "seed")
        git(seed, "push", "origin", "main")

        def run(*args, target=home, workspace=project, extra=None):
            e = dict(env, HARNESS_JUDGMENT_HOME=str(target), **(extra or {}))
            script = ("import sys; from pathlib import Path; "
                      f"sys.path.insert(0, {str(ROOT / 'harness')!r}); "
                      "import judgment; judgment.ROOT=Path(sys.argv[1]); "
                      "raise SystemExit(judgment.main(sys.argv[2:]))")
            r = subprocess.run([sys.executable, "-B", "-c", script, str(workspace), *args],
                               env=e, capture_output=True, text=True)
            return r.returncode, r.stdout + r.stderr

        code, out = run("init", "--from", str(remote))
        check("既存の台帳を path から clone する", code == 0 and (home / ".git").is_dir() and not home.is_symlink(), out)
        if code:
            return
        check("clone で足りない型を補い config をこの作業場用に作る",
              (home / "approval_queue.md").exists() and str(project) in (home / "config.env").read_text(), out)
        saved = json.loads((base / "loop/setup.json").read_text())
        check("置き場と origin を保存する", saved["judgment_home"] == str(home) and saved["judgment_remote"] == str(remote))
        code, out = run("init", "--from", str(remote))
        check("既存の置き場を clone で上書きしない", code != 0 and (home / "decisions_journal.md").read_text() == "共有の台帳\n", out)
        # 上流の更新を brief で取得する。upstream 設定がなくても origin の同じ branch を読む。
        (seed / "decisions_journal.md").write_text("共有の台帳\n別の作業場の判断\n", encoding="utf-8")
        git(seed, "commit", "-am", "remote update")
        git(seed, "push", "origin", "main")
        git(home, "branch", "--unset-upstream")
        code, out = run("brief")
        check("brief が最新を読む（追跡 branch 未設定）", code == 0 and "別の作業場の判断" in (home / "decisions_journal.md").read_text(), out)
        with (home / "decisions_journal.md").open("a") as f:
            f.write("topic: team 共有する指示\n")
        excluded = ["private.env", "logs/chat.txt", "journal_archive/id_rsa", "journal_archive/local.env", "artifact.txt", "correction_material.md.key"]
        for name in excluded:
            p = home / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("test-only value\n")
        (home / "journal_archive/2026-09.md").write_text("過去の判断\n")
        (home / "correction_material.md.1").write_text("訂正\n")
        code, out = run("sync")
        check("journal の追記を sync で送る", code == 0 and "共有する指示" in git(remote, "show", "main:decisions_journal.md"), out)
        tracked = git(remote, "ls-tree", "-r", "--name-only", "main").splitlines()
        check("config.env・env・logs・鍵・成果物を送らない", "config.env" not in tracked and not set(excluded) & set(tracked), str(tracked))
        check("台帳の archive と材料の世代ファイルを送る", "journal_archive/2026-09.md" in tracked and "correction_material.md.1" in tracked)
        check("秘密の ignore を作る", all(x in (home / ".gitignore").read_text().splitlines() for x in ("config.env", "*.env", "logs/")))
        check("commit に日付と作業場名を記す", git(remote, "log", "-1", "--format=%s") == f"judgment: {datetime.now().astimezone():%Y-%m-%d} workspace")
        other = base / "other"
        code, out = run("init", "--from", str(remote), target=other)
        check("別の場所の clone に同じ判断が届く", code == 0 and "共有する指示" in (other / "decisions_journal.md").read_text(), out)
        before = git(remote, "rev-parse", "main")
        code, out = run("sync")
        check("変更なしでは commit を増やさない", code == 0 and git(remote, "rev-parse", "main") == before, out)

        # stage 済み・履歴内の秘密も送らない。単なる git add の絞り込みでは防げない。
        git(home, "add", "-f", "config.env")
        code, out = run("sync")
        check("stage 済み秘密があれば拒否し送らない", code == 1 and "一覧外" in out and git(remote, "rev-parse", "main") == before, out)
        git(home, "reset", "--", "config.env")
        git(home, "add", "artifact.txt")
        git(home, "commit", "-m", "unrelated content")
        git(home, "rm", "artifact.txt")
        git(home, "commit", "-m", "remove unrelated content")
        code, out = run("sync")
        check("削除済みでも未送信履歴に一覧外があれば拒否する", code == 1 and "一覧外" in out and git(remote, "rev-parse", "main") == before, out)

        code, out = run("init", "--new", target=project)
        code, out = run("sync", target=project)
        check("安全条件1: 作業場と台帳の toplevel が同じなら拒否", code == 1 and "作業場" in out and "同じ" in out, out)
        git(project, "remote", "add", "origin", str(remote))
        code, out = run("sync", target=other)
        check("安全条件2: 作業場と remote URL が同じなら拒否", code == 1 and "remote" in out and "同じ" in out, out)
        spare = base / "spare.git"
        git(base, "init", "--bare", "--initial-branch=main", str(spare))
        git(project, "remote", "set-url", "origin", str(spare))
        git(other, "remote", "set-url", "--push", "origin", str(spare))
        code, out = run("sync", target=other)
        check("安全条件2: pushurl が作業場と同じでも拒否", code == 1 and "remote" in out and "同じ" in out and not git(spare, "show-ref", ok=False), out)
        git(other, "config", "--unset-all", "remote.origin.pushurl")
        # 同じ repo を指す書き方違い。作業場の remote が空だと pull で止まらないので、照合だけが頼り。
        for mine, theirs in [(str(spare), str(spare) + "/"), (str(spare), "file://" + str(spare)),
                             ("git@GitHub.com:u/r.git", "https://github.com/u/r/"),
                             ("ssh://git@github.com/u/r", "git@github.com:u/r.git")]:
            git(project, "remote", "set-url", "origin", mine)
            git(other, "remote", "set-url", "origin", theirs)
            code, out = run("sync", target=other)
            check(f"安全条件2: 書き方違いでも同じ repo なら拒否（{theirs}）",
                  code == 1 and "同じ" in out and not git(spare, "show-ref", ok=False), out)
        git(other, "remote", "set-url", "origin", str(remote))
        git(project, "remote", "remove", "origin")
        git(other, "remote", "add", "elsewhere", str(spare))
        git(other, "config", "remote.pushDefault", "elsewhere")
        git(other, "config", "remote.origin.push", "HEAD:refs/heads/wrong")
        (other / "decisions_journal.md").write_text("origin の main だけに送る\n")
        code, out = run("sync", target=other)
        check("安全条件3: origin の現在の branch だけに push", code == 0 and not git(spare, "show-ref", ok=False)
              and not git(remote, "show-ref", "refs/heads/wrong", ok=False)
              and git(remote, "show", "main:decisions_journal.md") == "origin の main だけに送る", out)
        git(other, "remote", "set-url", "--push", "origin", str(spare))
        (other / "decisions_journal.md").write_text("第三の repo へは送らない\n")
        code, out = run("sync", target=other)
        check("pushurl があれば知らせて送らない", code == 1 and "pushurl" in out and len(out.splitlines()) == 1
              and not git(spare, "show-ref", ok=False), out)
        git(other, "config", "--unset-all", "remote.origin.pushurl")
        # ローカルの未 commit 追記と、remote の同じ行の編集が衝突する。
        git(seed, "pull", "--ff-only")
        (seed / "decisions_journal.md").write_text("remote の判断\n")
        git(seed, "commit", "-am", "conflicting update")
        git(seed, "push", "origin", "main")
        before = git(remote, "rev-parse", "main")
        (other / "decisions_journal.md").write_text("local の判断\n")
        code, out = run("sync", target=other)
        check("衝突時は1行で停止し送信しない", code == 1 and len(out.splitlines()) == 1 and git(remote, "rev-parse", "main") == before, out)
        code, out = run("brief", target=other)
        check("brief は pull に失敗しても件数を出す", code == 0 and "取得" in out and "未処理のカード" in out, out)

        fresh = base / "fresh"
        code, out = run("init", "--new", target=fresh)
        check("--new が独立した repo を作る", code == 0 and git(fresh, "rev-parse", "--show-toplevel") == str(fresh), out)
        code, out = run("sync", target=fresh)
        check("remote がなくても台帳を commit する", code == 0 and bool(git(fresh, "rev-parse", "HEAD", ok=False)), out)
        git(fresh, "remote", "add", "origin", str(spare))
        code, out = run("sync", target=fresh)
        check("新規の台帳を空の remote に初めて送れる", code == 0 and bool(git(spare, "show-ref", ok=False)), out)

        (seed / "config.env").write_text("PROJECT_ROOT=/old-workspace\n")
        git(seed, "add", "-f", "config.env")
        git(seed, "commit", "-m", "old config")
        imported = base / "imported"
        code, out = run("init", "--from", str(seed), target=imported)
        check("clone 元の config を作業場用に作り直す", code == 0 and "/old-workspace" not in (imported / "config.env").read_text()
              and str(project) in (imported / "config.env").read_text(), out)

        # clone 元が一覧外を追跡していたら、init の時点で外し方を案内する。sync も同じ案内で断る。
        check("clone 元の一覧外を init で知らせる", "git rm --cached" in out, out)
        code, out = run("sync", target=imported)
        check("一覧外があれば sync は断り、外し方を案内する", code == 1 and "git rm --cached" in out, out)

        # 認証情報入りの URL で clone しても setup.json に残さない（insteadOf で手元の repo へ向ける）。
        login = "https://someone:test-only-password@example.invalid/ledger.git"
        code, out = run("init", "--from", login, target=base / "withlogin",
                        extra={"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.{remote}.insteadOf", "GIT_CONFIG_VALUE_0": login})
        saved = (base / "loop/setup.json").read_text()
        check("認証情報を setup.json に残さない", code == 0 and "test-only-password" not in saved and "someone" not in saved
              and json.loads(saved)["judgment_remote"] == "https://example.invalid/ledger.git", out + saved)

        legacy = project / "legacy"
        legacy.mkdir()
        for name in ("config.env", "approval_queue.md", "judgment_model.md", "harness_state.json", "correction_patterns.txt"):
            (legacy / name).write_bytes((home / name).read_bytes())
        git(project, "remote", "add", "origin", str(remote))
        code, out = run("brief", target=legacy)
        check("旧形式の台帳から親 repo を pull しない", code == 0 and not (project / ".git/FETCH_HEAD").exists() and "取得に失敗" not in out, out)

        import judgment
        real_run, limits, output = subprocess.run, [], StringIO()

        def timeout_pull(args, **kwargs):
            if args[0] == "git" and "pull" in args:
                limits.append(kwargs.get("timeout"))
                raise subprocess.TimeoutExpired(args, kwargs.get("timeout"))
            return real_run(args, **kwargs)

        with patch.dict(os.environ, dict(env, HARNESS_JUDGMENT_HOME=str(home)), clear=True), \
                patch.object(judgment, "ROOT", project), patch("subprocess.run", side_effect=timeout_pull), \
                redirect_stdout(output), redirect_stderr(output):
            result = judgment.cmd_brief(None)
        check("brief の取得は5秒で切り手元の件数を出す", result == 0 and limits == [5]
              and "取得に失敗" in output.getvalue() and "未処理のカード" in output.getvalue(), output.getvalue())


if __name__ == "__main__":
    raise SystemExit(main())
