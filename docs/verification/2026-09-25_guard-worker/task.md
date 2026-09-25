---
member: astra
hands: workspace
fanout: 1
minutes: 30
independent_of: T-0925-14
---
# 守り（harness/guard.py）の今日の変更の独立の確認

## 目的
GPT-6 Sol（openai）が今日、守りに 3 つの決まりを足した。作った側の試験は検収に数えない。あなたは同じ会社（openai）だが別のモデルで、実装を読む前に対を書いてから確かめる。**直さない。** 書いてよいのは `EXPECTATIONS.md` と `REPORT.md` だけ。作法は `.agents/skills/independent-check/SKILL.md`。

## 変更の要求（これだけを元に対を書く）
1. **担い手（`HARNESS_ROLE=worker`）は、自分の作業木の外に書けない。** 書く道具（Write / Edit など）の path、shell の `>` `>>` `tee` `sed -i` `cp` `mv` `truncate` の行き先が、`git rev-parse --show-toplevel`（cwd で解いた物）の外なら deny。変数（`$`）や backtick を含む行き先も deny
2. **担い手は、作業木の中でも守りのファイルを書けない**: `harness/guard.py` `harness/guard_bridge.mjs` と hook の設定 9 つ（`.claude/settings.json` `.codex/config.toml` `.agents/hooks.json` `.cursor/hooks.json` `.grok/hooks/guard.json` `.omp/extensions/guard.ts` `.opencode/plugins/guard.js` `.kilo/plugins/guard.js` `.dsh/guard.patch.yml`）
3. **担い手は別の担い手を起こせない**: `claude` `codex` `agy` `cursor-agent` `opencode` `kilo` `grok` `omp` の実行、`bash harness/dsh.sh`、`python3 harness/delegate.py run` は deny
4. **変更や履歴を消す git は、担い手は deny・指示役は ask**: `git checkout -- <path>`、`git restore`（`--staged` 無し）、`git stash drop|clear`、`git branch -D`。指示役の ask は既定で止まり（判断カード）、`HARNESS_APPROVED=1` で 1 回通る
5. **指示役（印なし）には 1〜3 は効かない**（hook は最小限）。担い手でも、作業木の中の普通のファイルへの書き込み・`ls`・`git status`・試験の実行は通る
6. 担い手の報告（`HARNESS_REPORT` で指した `REPORT.md`）は、`hands: none` でも書ける（前からの決まり。壊れていないこと）

## 順番
1. `EXPECTATIONS.md` に、要求 1〜6 それぞれ最低 2 つずつ「入力（道具・命令・環境変数・cwd）→ 期待 → なぜ」を書いて保存。**抜け道の候補**も 6 つ以上（例: `cp -r`、`sed --in-place=.bak`、`python3 -c` での書き込み、`ln -sf`、`git -C ../.. checkout -- x`、`env -u HARNESS_ROLE ...`、作業木の中に symlink を置いて外を指す、`dd of=`）
2. 保存してから `harness/guard.py` と `tests/test_guard.py` を読む
3. 測る。あなた自身は担い手なので、担い手の判定はそのまま（`HARNESS_ROLE=worker`）、指示役の判定は `env -u HARNESS_ROLE -u HARNESS_HANDS` を付ける。形:
   `echo '{"tool_name":"Bash","tool_input":{"command":"<命令>"},"cwd":"<作業木の絶対 path>"}' | python3 harness/guard.py --dialect claude; echo exit=$?`
   Write 道具は `{"tool_name":"Write","tool_input":{"file_path":"<path>","content":"x"},"cwd":...}`
4. 合否と証拠を `REPORT.md` に。30 行以内。**通ってしまった抜け道は最上位に。** 守りが止められない物（`python3 -c` の中身など）は「設計の限界」として分けて書く

## 触ってよい場所
`EXPECTATIONS.md` と `REPORT.md` だけ。
