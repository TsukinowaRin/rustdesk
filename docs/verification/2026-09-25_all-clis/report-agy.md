# 報告: T-0925-07-agy
## 何をした
- `evals/agy/greet.py` を新規作成（引数ありで挨拶、なしで stderr に使い方を出し exit 2）
- `evals/agy/test_greet.py` を新規作成（subprocess で上記 2 パターンを検証。外部ライブラリなし）

## 検証の結果
- `python3 evals/agy/greet.py 太郎` → stdout `こんにちは、太郎さん`、exit 0（条件 1 OK）
- `python3 evals/agy/greet.py` → stderr `使い方: greet.py <名前>`、exit 2（条件 2 OK）
- `python3 evals/agy/test_greet.py` → `全試験 OK (2/2)`、exit 0（条件 3 OK）
- `git status --short` → `?? evals/` のみ（evals/agy/ 以外の変更なし。条件 4 OK）

## 残り
- なし

## 人の判断が要ること
- なし

## 変更したファイル
- `evals/agy/greet.py`（新規）
- `evals/agy/test_greet.py`（新規）
