# 確認: T-0925-78
## 合否
差し戻し
## 通ってしまった物
- 送信箱 `kind=document` の `path` が作業場の外の秘密ファイルでも `sendDocument` に渡る（偽 API にその path が届いた）。
- 同じ `update_id` の `/run` は、offset を戻して再配送すると二度起動する（普通の文の受信箱は 1 通のまま）。
- 許可 chat からの転送（`forward_from`）は普通の文として受信箱へ入る。
- `/run ghost 文`（hub.json に無い名前）は「知らない作業場」にならず、今の相手で `action=run`。
## 何をした
- 実装を読む前に `EXPECTATIONS.md` を書いた。固定 HEAD `039e5973ee847518c014f20ee823502511a28015`（当時 `git status --short` は空）。
- 偽 Telegram API・偽 CLI、`HARNESS_CONFIG_HOME` と `HARNESS_LOOP_DIR` の使いで対を流した。網には出ていない。本物の `~/.config` と `.loop/` は触っていない。
- 隔離複製で `hub.py` を 3 通り壊し、対が落ちることを見た。作業木の実装は変えていない。
## 先に書いた対
- `EXPECTATIONS.md`（要求 1〜6 を各 2 対以上、抜け道 12）
## 実測
- 58 件中 ずれ 4。わざと壊した 3 通り（許可判定削除 / dropped に本文 / `shell=True`）→ 検出 3。
- 命令: `HARNESS_TESTING=1 python3 tmp-eval/eval_hub.py` → passed 54 failed 4。
- AST: `eval`/`exec`/`os.system`/`shell=True` は 0。`/run` の `; $(touch …) |` はファイルを作らず argv か stdin の 1 要素。子の環境は `HARNESS_ROLE` 無し・`HARNESS_UNATTENDED=1`。同時 1 本と `/stop`、許可外は `dropped` のみ（本文なし）、`[名前]` 付き送信と二重送信なし、hub.json/token 無しは終了 1、未登録 CLI は `unsupported`。
## 差し戻す点
- `flush_outbox` が `row["path"]` を作業場内に制限しない。作業場の外なら送らず、失敗の印だけ付ける。
- `/run` も受信箱と同じく `update_id` で一度だけにする。
## 残り
- なし（対は流した。直していない）。
## 人の判断が要ること
- 転送メッセージを捨てるか（正本は「許可した chat ID の人」としか書いていない）。
- `/run` の第 1 語が未登録のとき、今の相手への依頼文とみなす設計でよいか。
## 変更したファイル
- `EXPECTATIONS.md` `REPORT.md`
