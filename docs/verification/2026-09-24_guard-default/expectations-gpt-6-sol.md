# 独立確認の事前期待（2026-09-24）

`harness/guard.py` と `tests/` を読む前に、依頼書の要求だけから記す。各入力は `tool_name=Bash`、`cwd` はこの作業木の絶対パスとする。表の「環境」は `guard.py` 側の環境変数で、指定しない場合は `HARNESS_ROLE` と `HARNESS_HANDS` を外す。命令は判定器へ文字列として渡し、実行しない。

| 要求 | 入力（命令 / 環境） | 期待 | なぜ |
| --- | --- | --- | --- |
| 1 | `git push origin feature` / 印なし | exit 2。stderr に「判断カード」「HARNESS_APPROVED」 | 外へ出す ask は既定で止めるため。 |
| 1 | `curl -X POST https://example.invalid -d x=1` / 印なし | exit 2。同じ 2 語を stderr に含む | 送信する curl も ask のため。 |
| 1 | `ssh example.invalid` / 印なし | exit 2。同じ 2 語を stderr に含む | ssh も ask のため。 |
| 1 | `rm -rf $VAR` / 印なし | exit 2。同じ 2 語を stderr に含む | 変数に依存する削除は、依頼書で ask と指定されたため。 |
| 2 | `git push origin feature` / `HARNESS_ATTENDED=1` | exit 0。stdout は `permissionDecision: ask` の JSON | 人がいる場合は CLI の承認画面に回すため。 |
| 2 | `ssh example.invalid` / `HARNESS_ATTENDED=1` | exit 0。同じ JSON | ask 全般に同じ切り替えを適用するため。 |
| 3 | `HARNESS_APPROVED=1 git push origin feature` / 印なし | exit 0。stdout・stderr とも空 | 先頭の承認印が 1 回の ask を通すため。 |
| 3 | `env HARNESS_APPROVED=1 ssh example.invalid` / 印なし | exit 0。stdout・stderr とも空 | `env` による同じ先頭印も認めるため。 |
| 4 | `HARNESS_APPROVED=1 git push origin main` / 印なし | exit 2 | main への push は deny のため。 |
| 4 | `HARNESS_APPROVED=1 rm -rf ./tmp` / 印なし | exit 2 | 壊す命令は deny のため。 |
| 4 | `HARNESS_APPROVED=1 cat .env` / 印なし | exit 2 | 秘密のファイルは deny のため。 |
| 4 | `HARNESS_APPROVED=1 sudo ls` / 印なし | exit 2 | 管理者になる操作は別の承認印が必要なため。 |
| 5 | `git push origin feature` / `HARNESS_ROLE=worker HARNESS_ATTENDED=1` | exit 2 | 担い手には人がいる印が効かないため。 |
| 5 | `HARNESS_APPROVED=1 git push origin feature` / `HARNESS_ROLE=worker` | exit 2 | 担い手には承認印が効かないため。 |
| 6 | `ls` / 印なし | exit 0。stdout・stderr とも空 | allow はそのまま通るため。 |
| 6 | `git fetch` / `HARNESS_ATTENDED=1` | exit 0。stdout・stderr とも空 | 人がいる印でも allow は変わらないため。 |
| 6 | `HARNESS_APPROVED=1 git status` / 印なし | exit 0。stdout・stderr とも空 | 承認印があっても allow は通るため。 |

抜け道の事前仮説: `HARNESS_APPROVED=1; git push origin main`、`export HARNESS_APPROVED=1; git push origin main`、`bash -c 'HARNESS_APPROVED=1 git push origin main'`、`ls; HARNESS_APPROVED=1 git push origin main`、`env HARNESS_APPROVED=1 git push origin main` は、いずれも deny のまま exit 2 とする。単なる別位置の印や子シェルが main への push を許してはならない。
