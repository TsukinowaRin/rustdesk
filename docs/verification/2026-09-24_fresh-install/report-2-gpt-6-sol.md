# 報告: T-0924-02-sol6
## 何をした
- `README.md`、次に `docs/HARNESS.md` を読み、書き込みや外部送信を伴わない命令を実行した。
## 検証の結果
### ① 打った命令と結果
| 命令 | 結果 |
|---|---|
| `git ls-files \| wc -l`<br>`python3 harness/check.py` | 文書と違う: 791 本（README は 263 本）。<br>動いた: 終了 0、形 8 項目と試験 8 本が `ok`。 |
| `python3 harness/setup.py status`<br>`python3 harness/delegate.py team`<br>`python3 harness/judgment.py brief` | 動いた: `status` は「まだ」を 3 件表示。ただし `notify off` 等の命令の全形は出ない。<br>動かない: `team` は終了 1、`.loop/team.json` がないと表示。<br>動かない: `brief` は終了 1、`judgment.py init` を先に実行と表示。後 2 件の次の手順は表示から分かる。 |
| `python3 harness/sync_skills.py --check`<br>`python3 harness/check.py --list` | 動いた: 前者はスキル 25 本、ずれ 0。後者は形 8 項目、試験 8 本を表示（HARNESS は「試験 7 本」）。 |
| `python3 harness/guard.py --dialect claude`（stdin に `git push origin feature` の hook 入力） | 動いた: 終了 2。「人がいない担い手なので…報告の『人の判断が要ること』に書いて指示役へ返してください」と表示。送信は実行していない。 |
### ② 分かりにくかった文
| 引用 | 直す案 |
|---|---|
| README「git 管理下のファイルは全部で 263 本です」 | 現在の実測 791 本に更新するか、固定値を削る。 |
| README「`docs/HARNESS.md`（構成の地図）は未着手」 | ファイルが存在するため「未着手」を削る。 |
| HARNESS「試験 7 本」 | `test_notify.py` を含め「8 本」に直す。 |
| `setup.py status`「使わない → notify off」 | `python3 harness/setup.py notify off` のように入力する命令全体を示す。 |
### ③ 最初の 30 分でつまずく所 上位 3 つ
| 順位 | 出力で確認した事実 |
|---|---|
| 1 | README の手順 4 は、編成ファイルがない初期状態では `delegate.py team` が終了 1 になる。 |
| 2 | `judgment.py brief` は判断の置き場がない状態で終了 1 になり、`init` を要求する。 |
| 3 | README の 263 本と HARNESS の試験 7 本は、実測の 791 本と 8 本に一致しない。 |
## 残り
- 編成ファイルの作成、判断の置き場の初期化、外部物の取り込みは、今回の読取範囲や前提に合わず未実行。
## 人の判断が要ること
- 編成・判断の置き場を作るか、push を許すか。guard は push の試行を止め、指示役への報告を求めた。
## 変更したファイル
- `REPORT.md`
