# 報告: T-0925-05-opus55
## 何をした
- `evals/opus55/greet.py` を作った（引数がちょうど 1 つなら `こんにちは、<名前>さん` を出す。それ以外は使い方を stderr に出して exit 2）
- `evals/opus55/test_greet.py` を作った（標準の unittest と subprocess だけ。正常時と名前なしの 2 件）
## 検証の結果
- 条件1: `python3 evals/opus55/greet.py 太郎; echo $?` → `こんにちは、太郎さん` の 1 行、exit=0
- 条件2: `python3 evals/opus55/greet.py; echo $?` → stderr に `使い方: greet.py <名前>`、exit=2。`2>/dev/null | wc -c` → 0（stdout は空）
- 条件3: `python3 evals/opus55/test_greet.py` → `Ran 2 tests ... OK`、exit=0
- 条件4: `git status --short -uall` → `?? evals/opus55/greet.py` と `?? evals/opus55/test_greet.py` の 2 件だけ（この REPORT.md を書く前に確認。`__pycache__` はできていない）
## 残り
- なし
## 人の判断が要ること
- なし（止められた操作なし）
- 分かりにくかった所: 報告 `REPORT.md` を作業木の直下に書くよう言われたため、書いた後は `git status` に `?? REPORT.md` も出る。条件4 の「2 ファイル以外の変更が無い」とぶつかるので、確かめる側は REPORT.md を除いて見る必要がある
- 分かりにくかった所: 引数が 2 つ以上のときの扱いは依頼書に無い。使い方を出して exit 2 にした（前提）
## 変更したファイル
- evals/opus55/greet.py（新規）
- evals/opus55/test_greet.py（新規）
- REPORT.md（報告）
