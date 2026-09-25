# 報告: T-0925-13（opus55）ハーネス全体の研究と 1 周目の計画
## 何をした
- IMPROVE.md・9 CLI の表・fresh-install・PLAN・delegate/guard のコードを読み、下の命令を流した。守りは JSON を渡して判定だけ見た（命令は実行していない）。他の担い手は起動していない。
## 検証の結果
- `check.py`（初回）→ **NG: tests/test_delegate.py**。直後に同時実行の sol6（T-0925-11）がいた。単独で再実行 → 「点検が通りました」（約 20 秒）。原因: 試験が本物の repo に固定の branch 名 `work/T-1-cheap` を作るため、同じ repo で 2 本同時に流すと `cannot force update the branch ... used by worktree` で落ちる。現在の main 側はすでに `work/test-<hash>-...` で動いている（T-0925-11 の変更と推定。未確認）
- `delegate.py team`（作業木）→ exit 1（team.json 無し）。`stats`（本体の .loop）→ flash 8 件中 成功 8・報告あり 6。dist 側 → kilo 2 件 成功 2・報告あり 1（**報告なしも「成功」に数えている**）。events.jsonl に壊れた行 1 つ（注意が出る）
- `setup.py status` → 「まだ」3 件。`judgment.py brief` → 置き場なしで init を求める（作業木では init していない）
- dist の 9 CLI の log を grep → トークンが出るのは codex の `tokens used 37,733` だけ。`--help` では claude/grok/cursor/agy が `--output-format json`、codex `--json`、opencode/kilo `--format json`、omp `--mode json` を持つ
- 守りを `HARNESS_ROLE=worker` で判定（exit）: 本体の `harness/guard.py` への Write=0、自分の作業木の guard.py への Edit=0、`~/.bashrc` への Write=0、`echo x > ../../../harness/guard.py`=0、`git -C ../../.. checkout -- docs/dashboard/index.html`=0、`git restore`/`git stash drop`/`git branch -D main`/`truncate -s0`=0、`codex exec hi`・`python3 harness/delegate.py run T-1`=0。止まったのは `rm -rf ../../../harness`=2、`git push origin feature`=2、`git reset --hard`=2
## 基準 1〜8 の今（自分で見た範囲）
1 ×（通ったのは 6 本。守りの跡は残らない）/ 2 △（check は単独なら通る。team.json は人の手が要る）/ 3 未測（1 日使っていない）/ 4 ×（codex の log だけ）/ 5 ×（adopt 無し）/ 6 未確認（init 前は brief が止まる）/ 7 ○（AGENTS.md 47 行・4,086 B）/ 8 ×（1・4・5 が無いので手順も無い）
## 直す点（重い順）
1. **守りの穴: 担い手が守り自身と本体の木を書き換えられる。** hook は各作業木の `harness/guard.py` と `.claude/settings.json` を呼ぶので、1 回の Edit で以後の守りが消える。本体の未 commit の変更も `checkout --`/`restore` で消せる（AGENTS.md「未コミット変更を巻き戻さない」に反し、`reset --hard` だけ止める今の形と揃っていない）。直し方: `guard.py` の `evaluate()` に「worker なら書く path（`_PATH_KEYS` と `>`・`tee`・`sed -i`・`cp/mv` の行き先）が `git rev-parse --show-toplevel` の外なら deny、中でも `harness/guard.py`・`guard_bridge.mjs`・hook 設定 6 か所なら deny」を足す。`_git()` に `checkout -- / restore（--staged 無し）/ stash drop|clear / branch -D` を `reset --hard` と同じ deny で足す。確かめ方: 上の 9 例を `tests/guard_cases.tsv` に入れ、**別の会社の担い手で independent-check**
2. **担い手が別の担い手を起こせる。** `codex exec`・`claude -p`・`delegate.py run` が worker でも通る（worker skill は禁止、守りは Agent 道具しか見ない）。直し方: `evaluate_command` で worker のとき、`clis.json` の各 `worker[0]` と `delegate.py run` を deny。確かめ方: 同じく場面を足す
3. **`stats` の「成功」が嘘になる。** `cmd_stats` は exit 0 だけで数え、`cmd_run` は exit 0 かつ報告ありで合格にしている。直し方: `ok = exit==0 and report` の 1 行。確かめ方: dist の stats で kilo が 成功 1 になる
4. **守りの跡（基準 1）。** 直し方: `run_one()` で `env["HARNESS_GUARD_TRACE"]=str(d/f"guard-{tag}.jsonl")`、終わりに行数を `out["guard_calls"]` に入れ、`status`/`stats` に列を足す。0 件なら「守りが呼ばれていない」と出す。確かめ方: 偽 CLI の試験で guard.py を 1 回呼ばせて 1 行
5. **費用（基準 4）。** 直し方: `clis.json` に CLI ごとの `usage`（正規表現 1 本）を足し、`run_one()` が log から拾って `out["tokens"]`。まず codex（text の `tokens used\n数字` がそのまま使える）と claude（`--output-format json` の `total_cost_usd`・`usage`）の 2 本だけ。他は「不明」。確かめ方: 両 CLI で 1 件ずつ流して stats に数字
6. **取り込む 1 手（基準 5）。** 直し方: `delegate.py adopt <依頼ID> [--member]` = 作業木で `git add -A -- . ':!REPORT.md'` → commit → 本流で `git merge --no-ff work/<id>-<tag>`（衝突したら止めて知らせるだけ）。push はしない。確かめ方: 試験で偽 CLI の成果が本流の log に出る
7. **試験が本物の repo を汚す／同時に流すと落ちる。** `tests/test_delegate.py` は ROOT の repo に branch と worktree 登録を作る（今日 `/tmp/tmp…/T-1-cheap` の登録が残っていた）。直し方: 試験の中で `git init` した使い捨て repo を ROOT の代わりに使う（`delegate.py` の `ROOT` を `HARNESS_ROOT` で差し替え可能にする）。確かめ方: 2 本同時に `check.py` を流して両方 ok、`git branch --list 'work/test-*'` が空
8. **使えるかを 1 分で見る命令。** 鍵なし（dsh 32 秒・omp 53 秒）は run で分かるので急がない。やるなら `team --probe` で `worker` の形に「OK とだけ返して」を 60 秒の時間切れで流す。REPORT.md を依頼書の条件に数えるのは `TASK_TEMPLATE` に 1 行足すだけ（小さいので 3 と一緒に）
## 削る物
- `delegate.py` 冒頭の説明と PLAN 設計の軸 5 の「ACP」: 実物は subprocess で argv を渡すだけ。文を実物に合わせて ACP の約束を消す
- PLAN 151 行「`git clean -fdn` も止める」は実物と違う（予行は通す）。消す
- `.agents/skills/` の `meeting-copilot`・`hf-cli`・`mcp-builder`・`pptx` 等はハーネスの仕事に使われていない。配布物から外す候補（skills.json で出どころを見て人が決める）
- Cursor が守りを 2 回呼ぶ（`.cursor/hooks.json` と `.claude/settings.json`）。片方で足りるか実測してから 1 本に
## 次の周でやらないこと
- ダッシュボードの見た目、新しい CLI の追加、ACP への載せ替え、鍵の無い dsh/omp を通すこと（使う人の側）、`stats` 以外の集計画面
## 外の出どころ（データとして読んだ）
- https://code.claude.com/docs/en/headless（`--output-format json` に `total_cost_usd`・usage）/ https://learn.chatgpt.com/docs/non-interactive-mode（`codex exec --json` の `turn.completed.usage`）/ https://code.claude.com/docs/en/hooks（hook は best-effort、固い拒否は permission 側で、という注意）/ https://zylos.ai/research/2026-02-22-git-worktree-parallel-ai-development/（担い手 1 人に作業木 1 つ、後始末を定期で）
## 残り・人の判断が要ること
- 基準 3・6 は未測。1 の守りの直しは「hook は最小限」（軸 2）と引き換えになるので、範囲（worker だけ／path 境界まで入れるか）は人が決める
## 変更したファイル
- `REPORT.md`
