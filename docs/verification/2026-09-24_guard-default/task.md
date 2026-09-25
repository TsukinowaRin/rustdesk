---
member: sol6
hands: workspace
fanout: 1
minutes: 25
independent_of: 
---
# 守り（harness/guard.py）の今日の変更の独立の確認

## 目的
今日（2026-09-24）、守りの「聞く」の既定を変えた。作った本人（Claude）の試験は検収に数えない。
**別の会社のモデルであるあなた**が、実装を見る前に「止める形 / 通る形」を自分で書き、実物を確かめて合否と証拠を返す。
作法は `.agents/skills/independent-check/SKILL.md`。**直さない**（直しは差し戻す）。

## 変更の要求（これだけを元に対を書く。実装は後で読む）
1. 「聞く（ask）」判定の操作（`git push origin feature`、書き込む `gh`、`curl` の送信、`ssh`、`rm -rf $VAR`）は、**印が無い既定では承認画面に回さず止まる**（exit 2、stderr に「判断カード」と「HARNESS_APPROVED」の語）。
2. 環境変数 `HARNESS_ATTENDED=1` があるときだけ、ask は CLI の承認画面に回る（exit 0 で `permissionDecision: ask` の JSON）。
3. 命令の先頭に `HARNESS_APPROVED=1` を付けると、ask の操作が 1 回だけ通る（exit 0、無出力）。`env HARNESS_APPROVED=1 ...` も同じ。
4. `HARNESS_APPROVED=1` があっても、deny は止まる: main / master への push、壊す命令、秘密のファイル、管理者になる操作（`sudo`。これは `AGENT_ADMIN_APPROVED=1` の担当）。
5. `HARNESS_ROLE=worker`（担い手）では、`HARNESS_ATTENDED=1` も `HARNESS_APPROVED=1` も効かず、ask は止まる。
6. allow の操作（`ls`、`git fetch`、`git status` など）は、どの印があっても通る。

## 順番
1. `EXPECTATIONS.md` を作業木の根に書いて保存する。要求 1〜6 それぞれについて「入力（命令と環境変数）→ 期待 → なぜ」を最低 2 つずつ。自分で考える。
2. 保存してから `harness/guard.py` と `tests/` を読む。
3. 自分で測る。**あなた自身は担い手として動いていて `HARNESS_ROLE=worker` が付いている**ので、素の判定を見るときは `env -u HARNESS_ROLE -u HARNESS_HANDS` を先頭に付ける。形:
   `echo '{"tool_name":"Bash","tool_input":{"command":"<命令>"},"cwd":"<作業木の絶対 path>"}' | env -u HARNESS_ROLE -u HARNESS_HANDS [HARNESS_ATTENDED=1] python3 harness/guard.py --dialect claude; echo exit=$?`
4. 抜け道を探す: `HARNESS_APPROVED=1` を別の位置や別の書き方（`HARNESS_APPROVED=1;`、`export`、`bash -c`、`;` でつないだ 2 つ目の命令、など）で置いたとき、deny が通ってしまう形が無いか、最低 5 通り試す。
5. 合否と証拠（打った命令と exit と出力の要点）を `REPORT.md` に書く。30 行以内。

## 触ってよい場所
`EXPECTATIONS.md` と `REPORT.md` だけ。`harness/` と `tests/` は読むだけ。
