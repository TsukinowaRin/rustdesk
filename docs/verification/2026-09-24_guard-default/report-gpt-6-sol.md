# 報告: T-0924-08-sol6
## 何をした
- 実装を見る前に `EXPECTATIONS.md` へ要求 1〜6 の対を 17 件保存した（SHA-256: `0d16de781e3490951cdb4519c130c917527ed2cc864e26084db12276769be992`）。
- 保存後に `harness/guard.py`、`tests/test_guard.py`、`tests/guard_cases.tsv` を読んだ。実装と試験は変更していない。
- 判定対象の命令は JSON の文字列として `guard.py` に渡し、実行していない。
## 合否
- 判定保留。事前の対 17 件中 1 件が不一致。作業木内の削除を deny とした期待が、既存試験の allow と衝突する。
## 検証の結果
- `python3 -B - <<'PY'`（各件を `subprocess.run([sys.executable,'-B','harness/guard.py','--dialect','claude'], input=JSON, env=...)` で測定）→ 事前の対 17 件中、一致 16 件・不一致 1 件。追加 7 件は期待どおり。
- 印なしの `git push origin feature`、送信 `curl`、`ssh`、`rm -rf $VAR`、書き込む `gh` → 各 exit 2、stderr に「判断カード」「HARNESS_APPROVED」。
- `HARNESS_ATTENDED=1` で `git push origin feature` と `ssh` → 各 exit 0、`permissionDecision: ask` の JSON。
- 先頭の `HARNESS_APPROVED=1 git push origin feature` と `env HARNESS_APPROVED=1 ssh example.invalid` → 各 exit 0、無出力。
- 承認印つき `git push origin main`、`cat .env`、`sudo ls` → 各 exit 2。`HARNESS_ROLE=worker` では出席印と承認印の各 ask が exit 2。
- `ls`、出席印つき `git fetch`、承認印つき `git status` → 各 exit 0、無出力。
- 抜け道 5 通り（`HARNESS_APPROVED=1;`、`export`、`bash -c`、`ls;`、`env` と main への push）→ 全 5 件 exit 2。承認印を付けた ask の後に印なし ask をつないだ命令も exit 2。
- `HARNESS_APPROVED=1 rm -rf ./tmp` → 予想 exit 2 に対し実測 exit 0、無出力。`tests/guard_cases.tsv:14-15` は作業木内の再帰削除を allow としている。
- 明確な破壊命令 `HARNESS_APPROVED=1 rm -rf /`、`git reset --hard HEAD~1`、`git clean -fdx` → 各 exit 2。
- メモリ上だけで `unattended()`、deny の承認、worker の承認を 1 箇所ずつ壊した 3 通り → 各 exit 0 となり、事前の exit 2 の点検で 3 通りとも検出した。ファイルは変更していない。
## 残り
- `rm -rf ./tmp` の分類が確定するまで、事前の対の不一致 1 件を採否に換算できない。
## 人の判断が要ること
- 要求 4 の「壊す命令」に作業木内の `rm -rf ./tmp` を含めるか。既存試験は allow とし、事前に保存した期待は deny とした。期待は書き換えていない。
## 変更したファイル
- `EXPECTATIONS.md`
- `REPORT.md`
