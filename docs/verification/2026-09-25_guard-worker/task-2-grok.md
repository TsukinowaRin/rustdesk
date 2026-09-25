---
member: grok47
hands: workspace
fanout: 1
minutes: 30
independent_of: T-0925-20
---
# 守りの直し（担い手の書く範囲・起動・巻き戻し）の再確認

## 目的
GPT-6 Sol（openai）が守りに足した決まりを、GPT-6 Astra（同じ openai）が確かめて抜け道 11 件を見つけ、Sol が塞いだ。あなた（xai）は**別の会社**として、塞がったか・新しい抜け道が無いかを確かめる。**直さない。** 書いてよいのは `EXPECTATIONS.md` と `REPORT.md` だけ。作法は `.agents/skills/independent-check/SKILL.md`。

## 要求（これだけを元に対を書く。実装は後で読む）
1. 担い手（`HARNESS_ROLE=worker`）は自分の作業木（`git rev-parse --show-toplevel`）の外に書けない: Write / Edit の path、shell の `>` `>>` `&>` `>|` `tee` `sed -i`（接尾辞つき・複数ファイル）`cp` `mv`（`-t`、行き先が directory）`truncate`、`cd <外> && ...` の後の書き込み
2. 担い手は作業木の中でも守りのファイル（`harness/guard.py` `harness/guard_bridge.mjs` と hook の設定 9 つ）を書けない。`cp /tmp/x harness/` のように行き先が directory でも同じ。例外は環境変数 `HARNESS_GUARD_EDIT=1`（指示役が依頼書で付ける）のときだけ
3. 担い手は別の担い手を起こせない: `claude` `codex` `agy` `cursor-agent` `opencode` `kilo` `grok` `omp`、`bash harness/dsh.sh`（path の書き方を変えても）、`python3 [旗] harness/delegate.py run`。`env -u HARNESS_ROLE ...`・`HARNESS_ROLE= ...`・`unset HARNESS_ROLE` で印を外す形も deny
4. 変更や履歴を消す git は担い手 deny・指示役 ask: `git checkout -- <path>`、`git restore`（`--staged` だけの物は通る。`--worktree` があれば deny）、`git stash drop|clear`、`git branch -D`
5. 指示役（印なし）には 1〜3 は効かない。担い手でも、作業木の中の普通のファイルへの書き込み、`cp a b`、`sed -i s/x/y/ notes.txt`、`cd harness && ls`、`git restore --staged README.md`、`ls`、`git status` は通る
6. 設計の限界として塞がない物: `python3 -c` の中の書き込み、`dd of=`、`ln -sf`。`docs/SECURITY.md` にその旨がある

## 順番
1. `EXPECTATIONS.md` に、要求ごとに最低 2 対 + **Astra が見つけた 11 件を自分の言葉で書き直した物** + 新しい抜け道の候補を 8 つ以上（Astra の物と違う形。例: `cp --target-directory=`、`tee -a`、`sed -i -- expr file`、`git -C ../.. restore`、`bash -c 'echo x > ../f'`、`sh -c`、`xargs`、`find -exec`、`rsync`、`install`、`python3 harness/delegate.py  run`（空白 2 つ）、`./harness/dsh.sh`、`command codex`、`exec codex`）
2. 保存してから `harness/guard.py` と `tests/test_guard.py` を読む
3. 測る（形は前回と同じ。担い手はそのまま、指示役は `env -u HARNESS_ROLE -u HARNESS_HANDS`）
4. `REPORT.md` に合否と証拠。30 行以内。**通ってしまった物は最上位に**。塞ぐ価値が低い物（設計の限界）は分けて書く

## 触ってよい場所
`EXPECTATIONS.md` と `REPORT.md` だけ。
