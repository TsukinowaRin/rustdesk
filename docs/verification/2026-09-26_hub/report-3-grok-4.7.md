# 報告: T-0925-88
# 確認: T-0925-88
## 合否
差し戻し。送信箱の行が送る先を書き換えられる（下の「通った」）。
## 通った
- alpha の行 `chat_id=99999` `thread_id=102` → グループ -100 の話題 102 へ `out-N3`（`[alpha]` なし）。99999 へは送っていない。
- 同じ関数で `transport=discord` `target=999attack` → `POST /channels/999attack/messages`（`[alpha] out-N3-discord`）。
## 先に書いた対
`EXPECTATIONS.md`（実装の前）。要求の対 + R1〜R6 + N1〜N7。HEAD `4db812641bd2c462141ef211a5c2b72ffe33193a`。
## 何をした
対を保存してから hub を読み、偽 API と使い捨ての配置で再測と新しい抜け道だけ測った。複製を 2 通り壊して対が落ちることを見た。測ったあとに `tmp-eval/` は消した。
## 検証の結果
- `python3 tmp-eval/probe.py` → 16 判定、FAIL は N3 のみ。転送 8 種は `dropped`（本文なし）。普通の文と引用の外側だけ受信箱。`::ffff:0.0.0.0:0` と `:::0` は終了 1。`[::]:0` は名前解決失敗で終了 1（待受なし）。Origin/Host 偽・印なし・印違い・4001 字 = 403/403/403/403/413。正しい印は 303 で受信箱。symlink の dashboard は送信 0。`webhook_id` と `bot_message` は捨て、人の文だけ入る。対応外チャンネルは未参照。`--once` の例外は `discord 受信失敗: bridge broke` の 1 行。Traceback なし。終了 0。本文は出ない。
- 壊した複製: `MUTATION_R1 FELL`（転送を受け入れた）。`MUTATION_R3 FELL`（悪意の Origin が 303）。
## 実測
危険なずれは N3 の 1 件（中身 2 通り）。R6 の終了コードだけ対と違う（0）。実行も漏えいも無いので穴に数えない。
## 差し戻す点
- `harness/hub.py` `_outbox_destination`。宛先は hub.json の chat・話題・チャンネルだけ。行の `thread_id` / `target` / `transport` では変えない。`tests/test_hub.py` は `thread_id: 777` を送る形なので、試験も直す対象。
## 残り
なし。要求 1〜6 の対は、依頼どおり今回は流していない。
## 人の判断が要ること
なし
## 変更したファイル
- `EXPECTATIONS.md`
- `REPORT.md`
