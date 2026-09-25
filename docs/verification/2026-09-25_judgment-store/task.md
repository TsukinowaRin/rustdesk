---
member: opus55
hands: workspace
fanout: 1
minutes: 30
independent_of: T-0925-61
---
# 台帳の共有（`judgment.py init --from / sync / brief の pull`）の独立の確認

## 目的
GPT-6 Astra（openai）が作った「台帳を作業場をまたいで共有する」機能を、別の会社（anthropic）のあなたが、実装を読む前に対を書いてから確かめる。**git の操作と秘密の扱い**が要なので、抜け道を探す。**直さない。** 書いてよいのは `EXPECTATIONS.md` と `REPORT.md` だけ。作法は `.agents/skills/independent-check/SKILL.md`。**網に出ない**（remote は使い捨てのローカルの bare repo だけ。本物の `.loop/judgment/` は触らない。`HARNESS_LOOP_DIR` と `HARNESS_JUDGMENT_HOME` で使い捨ての場所を指す）。

## 要求（これだけを元に対を書く。正本は `docs/design/JUDGMENT-STORE.md`）
1. `judgment.py init --new`: 上流の型で作り、`git init` する。`init`（旗なし）も同じ
2. `judgment.py init --from <path か URL>`: clone する（symlink にしない）。型のファイルが足りなければ補う。`config.env` はこの作業場用に作り直す（clone 元の `config.env` は使わない）。`.loop/setup.json` に `judgment_home` と `judgment_remote` が入る
3. `judgment.py sync`: 台帳の repo で pull --rebase → 台帳の一覧のファイルだけ add（`config.env`、`*.env`、`logs/`、それ以外の一覧に無いファイルは**入らない**）→ 変更があれば commit → remote があれば push。**台帳の repo が作業場の repo と同じ toplevel なら断る / remote の URL が作業場の repo の remote と同じなら断る / push は台帳の origin だけ**。衝突したら止めて 1 行
4. `judgment.py brief`: 最初に pull --ff-only（remote があれば。5 秒で切る。失敗しても続く）
5. `setup.py status`: 置き場が無いとき「新規 / 既存」の 2 択が命令つきで出る。`.loop/setup.json` の `judgment_home` が使われ、`HARNESS_JUDGMENT_HOME` があればそちらが優先

## 抜け道の候補（最低 8 つ。実装を読む前に書く）
例: 台帳の一覧に無いファイルを台帳の dir に置いて `sync`（成果物が混ざるか）/ `config.env` に偽の token を書いて `sync`（remote に届くか）/ `.env` という名前のファイル / `logs/` の中身 / 作業場の repo の中に `HARNESS_JUDGMENT_HOME` を指して `sync`（断るか）/ 作業場と同じ remote URL（断るか）/ `--from` に symlink の path / `--from` の clone 元に `config.env` がある（使い回されないか）/ pull で衝突する状態で `sync`（自動で解決しないか）/ remote が無い台帳で `sync`（push しようとしないか）/ 台帳の repo の中で `git push` 以外の remote（`upstream`）を足したとき

## 順番
1. `EXPECTATIONS.md` に対を保存（要求ごとに 2 つ以上 + 抜け道 8 つ以上）
2. 保存してから `harness/judgment.py` と `tests/test_judgment.py` を読む
3. 使い捨ての場所で測る（bare repo を `git init --bare` で作る）
4. `REPORT.md` に合否と証拠。30 行以内。通ってしまった物は最上位に

## 触ってよい場所
`EXPECTATIONS.md` と `REPORT.md` だけ。使い捨ての repo は `/tmp` の下に作る（作業木の外だが読む・作るだけ。書く道具の判定で止まるなら、作業木の中に `tmp-eval/` を作ってそこで）。
