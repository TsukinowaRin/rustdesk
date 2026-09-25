---
member: opus55
hands: workspace
fanout: 1
minutes: 30
independent_of: 
---
# 配布物を新規展開して、文書だけで最初の依頼まで進む（基準 2・8 の確かめ）

## 目的
`docs/HARNESS.md` の冒頭「入れてから最初の 1 件まで」（今日書いた）が、**それだけを読んで**本当に進めるかを確かめる。直さない。つまずいた所を報告する。

## やり方（全部あなたの作業木の中で。外には書けない）
1. あなたの作業木で `git archive --format=zip --prefix=fresh/ -o fresh.zip HEAD` → `python3 -c "import zipfile; zipfile.ZipFile('fresh.zip').extractall('.')"` → `fresh/` が配布物の展開先
2. `fresh/` に `cd` して、`docs/HARNESS.md` の「入れてから最初の 1 件まで」を **1 から順に**打つ。ただし:
   - 手順 6 の `delegate.py run` は打たない（担い手は担い手を起こせない決まり）。`new` で依頼書を作り、目的・受け入れ条件・触ってよい場所を書いた所まで
   - `setup.py` の「まだ」のうち、通知は `notify skip`、判断の置き場は `init`、編成は `team.example.json` を写す（モデル名は変えない）
   - 外へ出す操作・秘密に触る操作はしない
3. 各手順で「書いてあるとおりに動いたか / 出力は初めての人に分かるか / 文書と違う所」を記録する
4. `fresh/` で `python3 harness/check.py` と `python3 harness/setup.py status`（済ませた後）と `python3 harness/delegate.py team` と `python3 harness/judgment.py brief` の出力を要約する

## 報告に書くこと（`REPORT.md`、30 行以内）
- 手順 1〜6 の表: 打った命令 / 動いた・動かない・文書と違う / 初めての人が迷う点
- 基準 2（展開して点検が通り、「まだ」を済ませると依頼書まで作れる）と基準 8（他の人の機械でも再現できる手順が docs にある）の合否、あなたの判断
- 直すべき文（引用と案）を最大 5 つ

## 触ってよい場所
作業木の中の `fresh/`（展開先）と `REPORT.md` だけ。本体の `docs/` や `harness/` は読むだけ。
