# 報告: T-0925-58
## 合否
要求と前回の 7+2 は一致。先に固定した規則では閉じてよい。通った物は直下。
## 通ったもの
- 元からの抜け（期待どおり exit 0）: `echo a\; codex`、`timeout -s KILL 5 codex`、`pushd .. && echo x > f`
- 列挙外（期待 deny、実際 exit 0。閉じの不合格にしないと `EXPECTATIONS.md` に先に書いた）: `env -C .. cp a b`、`tar -C .. -xf x.tar`、`git -C .. apply p.diff`、`patch -d .. < p.diff`、`python3 -m pip install -t .. x`
## 何をした
- 実装を読む前に `EXPECTATIONS.md` へ 115 対（要求 1〜6 が 81、前回 19、抜け 3、新規 12）。sha256 `9b8b9e6ac4e57302dade045de4887b45b6ab0eb888da4b952331d2cdee20d5ef`。あとから変えていない
- 固定 `576745b9b2e1a7ce036689f6282aa0fef7800c1a`。測る前後で同じ。書く前の `git status --short` は空
## 検証の結果
- `python3 harness/guard.py --dialect claude` に 115 件。一致 108、不一致 7。要求の行と前回の 7+2（兄弟 10 を含む 19）の不一致は 0
- 前回 7 件は exit 2。`cd .. && ls` と `git restore -S README.md` は exit 0
- 新規で列挙内は exit 2: `bash -c "cd .. && echo x > f"`、同じ `sh -c`、`cp --no-clobber README.md ../b`、heredoc の `> ../f`、`cd` を 3 回
- 不一致の内訳: `cd harness && cd .. && echo x > f` は exit 2（期待 allow。`f` を外と見た）。`timeout --signal=KILL 5 codex` は exit 2（短い `-s` は exit 0）
- 指示役は `env -u HARNESS_ROLE -u HARNESS_HANDS`。`git checkout -- README.md` は exit 2（判断カード）。`HARNESS_ATTENDED=1` では exit 0、`permissionDecision` ask
## 残り
- 隔離した複製で試験を壊す手順はしていない。書いてよいのはこの 2 ファイルだけ
## 人の判断が要ること
- 元からの抜け 3 と列挙外 5 を塞ぐか。`cd harness && cd ..` のあと作業木の中の `f` が止まるのを許すか
## 変更したファイル
- `EXPECTATIONS.md`、`REPORT.md`

閉じてよい
