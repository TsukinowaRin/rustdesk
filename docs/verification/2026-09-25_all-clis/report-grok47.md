# 報告: T-0925-04-grok47
## 何をした
- `evals/grok47/greet.py` を作った。名前1個で挨拶1行、名前なしは stderr に使い方を出して exit 2。
- `evals/grok47/test_greet.py` を作った。上の2経路を subprocess で確かめる（外部ライブラリなし）。
## 検証の結果
- `python3 evals/grok47/greet.py 太郎` → stdout `こんにちは、太郎さん`（1行）、stderr 空、exit 0
- `python3 evals/grok47/greet.py` → stdout 空、stderr `使い方: greet.py <名前>`、exit 2
- `python3 evals/grok47/test_greet.py` → `Ran 2 tests in 0.098s` / `OK`、exit 0
- `git status --short` → `?? evals/`（報告前）。`git status --short -u` → `?? evals/grok47/greet.py` と `?? evals/grok47/test_greet.py` の2件のみ
## 残り
- なし
## 人の判断が要ること
- なし
## 変更したファイル
- evals/grok47/greet.py
- evals/grok47/test_greet.py
