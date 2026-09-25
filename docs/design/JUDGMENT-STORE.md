# 台帳（判断の置き場）を作業場をまたいで共有する（9/25、ユーザーの指示）

「Kagemusha の台帳は、ワークスペースが変わっても、共通の台帳を取得できるようにすることと、Git にコミットしてプッシュして最新を保つこと、既存の Kagemusha 台帳を読み込めるようにすること。このテンプレートを使ってワークスペースをセットアップするとき、台帳を新規に作るか、既存の台帳を読み込むか、選ぶ。GitHub とかから落としてきて、規則が変わったり記録が追加されたらコミットしてプッシュする。Kagemusha 以外の内容は台帳リポジトリにプッシュしない（そのワークスペースで完成した成果物等はそのワークスペースのリポジトリに上げる）」

## 形

| 命令 | 何をする |
|---|---|
| `python3 harness/judgment.py init --new` | 今までどおり `.loop/judgment/` に上流の型で作る。`git init` して台帳の repo にする（remote は人が後で足す） |
| `python3 harness/judgment.py init --from <git の URL か path>` | 既存の台帳を `.loop/judgment/` に clone（path なら symlink ではなく clone）。型のファイルが足りなければ上流の型で補う。`config.env` は**この作業場用に作り直す**（置き場ごとに違う。台帳には入れない） |
| `python3 harness/judgment.py sync` | 台帳の repo で `git pull --rebase` → 変更があれば commit（`judgment: <日付> <作業場の名前>`）→ remote があれば push。**台帳の repo 以外へは絶対に push しない。** 秘密（`config.env`、`*.env`、`logs/`）は `.gitignore` で除く。衝突したら止めて知らせるだけ |
| `python3 harness/judgment.py brief` | 最初に `git pull --ff-only`（remote があれば。5 秒で切る。失敗は 1 行で知らせて続ける） |
| `python3 harness/setup.py status` | 判断の置き場が無いとき「新規に作る: `init --new` / 既存を読み込む: `init --from <URL か path>`」の 2 択を出す |

- 置き場と remote は `.loop/setup.json` の `judgment_home` / `judgment_remote` に記録（`HARNESS_JUDGMENT_HOME` があればそれが優先）。
- 台帳に入る物: `decisions_journal.md` `approval_queue.md` `judgment_model.md` `promotion_queue.md` `correction_patterns.txt` `correction_material.md*` `distill_state.json` `harness_state.json` と `journal_archive/`。入らない物: `config.env`（作業場ごと）、`logs/`（会話ログの採取結果は作業場の物）、`*.env`。
- 守りとの関係: `sync` の中の push は、人がこの指示で許可した操作。`sync` は台帳の repo の remote にしか push しない（コードで縛る。作業場の repo の中に台帳があって remote が同じなら断る）。指示役が `git push` を直接打つのは今までどおり「聞く」。
- 人の指示（どのモデルをどう使うか）は台帳に `topic: team` で書くので、別の作業場で `init --from` すれば `brief` の原則と台帳に出る。
