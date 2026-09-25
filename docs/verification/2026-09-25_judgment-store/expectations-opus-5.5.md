# 期待（T-0925-60。実装を読む前に書いた。後から書き換えない）

対象: HEAD 0d6c938（`harness/judgment.py` は 658742e で入った物）。status は clean。
測る場所: `/tmp` の使い捨て（`HARNESS_LOOP_DIR` / `HARNESS_JUDGMENT_HOME` で指す）。remote は `git init --bare` のローカル repo だけ。

## 要求ごとの対（入力 → 期待 → なぜ）

### 1. init --new / init
- 通す N1: 空の置き場で `init --new` → 型のファイル（decisions_journal.md ほか）ができ、`.git/` がある、remote は無い → 設計の表どおり
- 通す N2: 空の置き場で `init`（旗なし）→ N1 と同じ結果 → 要求 1
- 止める N3: 既に台帳がある置き場で `init --new` → 既存の記録を上書きしない（中身が変わらない）→ 台帳の記録は戻せない

### 2. init --from
- 通す F1: bare repo の path を `--from` → 置き場は clone（`.git/` がある実 dir、symlink でない）、`origin` が clone 元 → 要求 2
- 通す F2: clone 元に型のファイルが欠けている → 足りない型が補われる → 要求 2
- 止める F3: clone 元（の履歴）に `config.env`（中に偽 token）がある → 置き場の `config.env` は作り直され、偽 token を含まない → 置き場ごとに違う
- 通す F4: `.loop/setup.json` に `judgment_home` と `judgment_remote` が入る → 要求 2
- 止める F5: `--from` に symlink の path → 置き場が symlink にならない（clone か断る）→ 要求 2「symlink にしない」

### 3. sync
- 通す S1: 台帳の記録を 1 行足して `sync` → bare に commit が届く、中身は一覧のファイルだけ → 要求 3
- 止める S2: 一覧に無いファイル（`artifact.py`）を置いて `sync` → bare に入らない
- 止める S3: `config.env` に偽 token を書いて `sync` → bare のどの commit にも入らない
- 止める S4: `.env` / `x.env` → 入らない
- 止める S5: `logs/a.txt` → 入らない
- 止める S6: 置き場が作業場の repo と同じ toplevel → 断る（非 0、push しない）
- 止める S7: 台帳の origin の URL が作業場の repo の remote と同じ → 断る
- 止める S8: pull で衝突 → 止めて 1 行、非 0、自動で解決しない（衝突の印を commit しない）
- 通す S9: remote が無い台帳で `sync` → commit だけして成功、push しようとしない
- 通す S10: 変更が無い → commit を作らない

### 4. brief の pull
- 通す B1: remote に新しい commit → brief の後で置き場に取り込まれている
- 通す B2: remote が届かない path → brief は 1 行知らせて最後まで出る（終了 0）
- 通す B3: remote が無い → pull しない、brief は普通に出る

### 5. setup.py status
- 通す T1: 置き場が無い → `init --new` と `init --from` の両方が命令つきで出る
- 通す T2: `.loop/setup.json` の `judgment_home` が指す場所が使われる
- 通す T3: `HARNESS_JUDGMENT_HOME` があれば setup.json より優先

## 抜け道の候補（止まるべき）
1. 一覧に無い成果物を置き場に置いて sync → 混ざらない（S2）
2. `config.env` に偽 token → remote に届かない（S3）
3. `.env` という名前 → 入らない（S4）
4. `logs/` の中身 → 入らない（S5）
5. `HARNESS_JUDGMENT_HOME` を作業場の repo の中（サブ dir、自前の .git 無し）に向けて sync → 断る（S6）
6. 台帳の origin を作業場の remote と同じ URL にして sync → 断る（S7）
7. `--from` に symlink の path → symlink にならない（F5）
8. clone 元の `config.env` が使い回されない（F3）
9. 衝突 → 自動で解決しない（S8）
10. remote 無しで push しない（S9）
11. 台帳に `upstream` を足し、branch の上流を upstream にする → push は origin だけ（upstream の bare に何も届かない）
12. 一覧のファイル名で git に既に追跡されている `config.env`（clone 元の履歴にある）→ sync で更新が push されない
13. `.gitignore` を消す・書き換えてから sync → それでも秘密が入らない（一覧だけ add するなら .gitignore に頼らない）
14. `journal_archive/` の下に `secret.env` → 入らない
15. URL の書き方違い（末尾 `/`、`.git` 付き）で作業場と同じ remote → 断るのが望ましい（届かなければ「ずれ」ではなく注意）
