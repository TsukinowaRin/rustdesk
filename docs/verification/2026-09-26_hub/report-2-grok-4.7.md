# 報告: T-0925-85 hub 独立の確認 2 回目
## 合否
差し戻し。通ってしまったものが 4 件。
## 先に書いた対
`EXPECTATIONS.md`（実装の前）。要求ごとの対と抜け道 B1–B16。HEAD `b5a784d3b2a06d002a98c93ea3c4b9a5bcdc5392`。着手時から `M docs/design/IMPROVE.md`（未変更）。
## 通ってしまった
1. 転送: `forward_from` と `forward_origin` は `dropped`（本文なし）。`forward_date` だけ、`forward_sender_name`+`forward_date`、`forward_from_chat`+`forward_date`、`is_automatic_forward` は受信箱に入る。後者の `/run alpha PWND` は指示役が起動し、`hub.log` に本文が残った。
2. `--serve ::ffff:0.0.0.0:0` は `0.0.0.0`（port 43976）で待受し POST が 200。字面の `0.0.0.0` は exit 1。`[::]` と `::` は IPv6 が無く bind 失敗（拒否ではない）。
3. 画面 POST は Origin のホストと `Host` が一致すれば通る。両方 `evil.example` で 303、受信箱に入った。Origin だけ違う・無し・`null`・別ポートは 403。Origin 無しで Referer が一致すると 303。
4. `.loop/dashboard` 自体が外への symlink だと、外のファイル（中身 `TOK-DIR-SYMLINK`）が `sendDocument` まで進む。外の path と、中のファイル symlink は送られない。
## 実測
- 判定 76 件、製品のずれ 14。E16 は差し戻しにしない: `/run nosuch` は今の相手で起動し、返事は `[alpha] 起動しました（作業場 alpha）`（裁定どおり）。
- ほか: 話題表に無い thread は current へ（私信の偽 thread では別作業場へ行かない）。話題への送信は `[名前]` を外し thread id だけ。Discord は `bot: true` を捨て、`webhook_id` で bot フラグが偽・許可 ID なら通す。Slack は `bot_id` を捨て、`subtype=bot_message` だけで `bot_id` が無いと通す。`--once` は橋の例外で後続が止まる。常駐は届き、落ちない。
- 合格: 許可外は `dropped` で本文なし。`/ws` `@` `/dash` `/status`。`/run` は引数のリスト、`shell=False`、`HARNESS_ROLE` 無し、`HARNESS_UNATTENDED=1`。`;` `$(touch)` `|` 改行 制御文字は実行されない。同時 1 本、別作業場は並行、`/stop`、許可外 `/stop` は止まらない。送信の印と再送なし。`eval(` `exec(` `os.system` `shell=True` 無し。設定無しは exit 1、token 無しは 1 行。同じ update_id は 1 回。画面は 4000 字まで、4001 は 413、`../` は 404。429 は 0.01 秒待って再送。1 回目: 文書の直接 path と `/run` 重複は直った。転送は一部。無い名前は裁定どおり。
- 複製を 3 通り壊した（許可を外す、`shell=True`、Origin 検査を外す）→ 3 通りとも対が落ちた。`shell=True` は副作用ファイルができた。
## 何をした
- 期待を書いてから実装を読み、偽の API と偽の CLI で測った。製品は直していない。
## 検証の結果
- `python3 tmp-eval/measure.py` → pass 61 / fail 15（1 件は測り方の漏れ。測り直して `shell=True` を検出）。
- 追加で、転送の `/run` 起動、`::ffff:0.0.0.0` の待受、symlink の中身を確認した。
- 本物の `~/.config/harness` と作業木 `.loop/inbox.jsonl` の mtime は不変。
## 残り
- 常駐の送信中に `hub.json` が無い、という例外が 1 回出た（受信は届いた）。原因は未確定。
## 人の判断が要ること
- 話題送信で `[名前]` を外すのを、仕様違反と見るか。E16 は裁定どおり不合格にしていない。
## 変更したファイル
- `EXPECTATIONS.md` `REPORT.md`（`tmp-eval/` は削除した）
