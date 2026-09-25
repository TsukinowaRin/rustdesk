# 報告: T-0926-90
# 確認: 中継 hub の宛先（4 回目）
## 合否
合格。通った 0（攻撃側の chat・話題・チャンネル・未登録の橋・偽の作業場へは届いていない）。
## 何をした
- 実装の前に `EXPECTATIONS.md`（止める 6、通す 3）を保存。HEAD `dbd98da`（保存の前も後も同じ）。
- その後 `harness/hub.py` の `_outbox_destination` と `tests/test_hub.py` を読み、偽 API で測った。測ったあと `tmp-eval/probe.py` は消した。
## 検証の結果
- `python3 tmp-eval/probe.py` → 対 9、hits 0。`hub.json` は全対で送信前と同じ。
- A は `-100` の話題 `11` へ `out-A`（`99999` も話題 `102` も 0、ログ `ignored-destination`）。B は `POST /channels/111alpha/messages`、本文 `[alpha] out-B`（`999attack` は 0）。C は `matrix` と `evil.example` が 0 で話題 `11`。D の文書も話題 `11`（`note.html`）。E の作業場名 `beta` は無視。F の `out-F` と `out-F2` も話題 `11`。返信先は増えない。
- 期待との差（通ったにしない）: 話題への送信は先頭の `[alpha]` を外す。宛先欄の無い行は最初の橋（telegram）だけなので P2 の `111alpha` と P3 の `Salpha` には届かない。行の `transport=discord` は有効な橋の `111alpha` を選ぶ。
## 残り
- 送信箱の行だけでは再現しない。`hub.json` に先に返信先 `thread=999attack` があると、行の `chat_id=99999` だけで Discord の `/channels/999attack/messages` に出た。Discord の受信は `thread` を保存しない。
## 人の判断が要ること
- なし
## 変更したファイル
- `EXPECTATIONS.md`
- `REPORT.md`
閉じてよい
