# 報告: T-0925-08-cursor（挨拶の道具と試験）

## 何をした
- `evals/cursor/greet.py` を作成（名前あり→挨拶、無し→stderr 使い方・exit 2）
- `evals/cursor/test_greet.py` を作成（標準ライブラリのみで上の 2 挙動を試験）
- 本報告を `REPORT.md` に記載（起動指示どおり）

## 検証の結果
- 条件1: `python3 evals/cursor/greet.py 太郎` → stdout `こんにちは、太郎さん`、exit 0
- 条件2: `python3 evals/cursor/greet.py` → stderr `使い方: greet.py <名前>`、exit 2
- 条件3: `python3 evals/cursor/test_greet.py` → `Ran 2 tests` / `OK`、exit 0
- 条件4: `git status --short` → `?? REPORT.md` と `?? evals/`（中身は greet.py / test_greet.py のみ）。依頼どおりの 2 ファイル以外に起動指示の REPORT.md が未追跡で出る

## 残り
- なし

## 人の判断が要ること
- なし（REPORT.md の扱いが条件4とぶつかるが、起動指示で書くよう指定されたため実行した）

## 変更したファイル
- `evals/cursor/greet.py`
- `evals/cursor/test_greet.py`
- `REPORT.md`（報告。触ってよい場所外だが起動指示）
