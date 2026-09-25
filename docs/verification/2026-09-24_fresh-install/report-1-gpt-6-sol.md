# 報告: T-0924-01-sol6
## 何をした
- `hello/greet.py` と `hello/test_greet.py` を作成した。試験は実装前に実行し、2 件の失敗を確認した。
- 分かりにくかった所: なし。
- 止められた所: なし。
## 検証の結果
- `python3 hello/test_greet.py`（実装前）→ 2 件失敗。`greet.py` が無いことによる失敗。
- `python3 hello/greet.py 太郎` → stdout に `こんにちは、太郎さん` を 1 行、exit 0。
- `python3 hello/greet.py` → stderr に `使い方: greet.py <名前>` を 1 行、exit 2。
- `python3 hello/test_greet.py`（実装後）→ 2 件実行、`OK`、exit 0。
- `python3 harness/check.py` → exit 1。守りの試験は 119 場面 + 入出力 28、ずれ 2。`guard_cases.tsv:60` と `:61` で期待 `allow` / 実際 `ask`。
## 残り
- `harness/check.py` のずれ 2 件。依頼書の編集範囲外のため未修正。
## 人の判断が要ること
- 着手時から変更されていた `tests/guard_cases.tsv` と `tests/test_guard.py` は触っていない。守りの試験失敗をどう扱うか判断が必要。
## 変更したファイル
- `hello/greet.py`
- `hello/test_greet.py`
- `REPORT.md`
