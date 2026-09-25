# 報告（T-0925-03-flash / flash）

## 何をした
`evals/flash/` の下に `greet.py` と `test_greet.py` を新規作成した。greet.py は名前があれば `こんにちは、<名前>さん` を stdout に出して exit 0、なければ `使い方: greet.py <名前>` を stderr に出して exit 2。試験は標準ライブラリ unittest のみで subprocess で実機行を確かめる。

## 検証の結果
1. `python3 evals/flash/greet.py 太郎` → `こんにちは、太郎さん`、exit=0 ✔
2. `python3 evals/flash/greet.py` → `使い方: greet.py <名前>` が stderr、exit=2 ✔
3. `python3 evals/flash/test_greet.py` → `Ran 2 tests ... OK`、exit=0（外部ライブラリ未使用）✔
4. `git status --short --untracked-files=all` → `?? evals/flash/greet.py` と `?? evals/flash/test_greet.py` のみ ✔

## 残り
なし。

## 人の判断が要ること
なし。

## 変更したファイル
- evals/flash/greet.py（新規）
- evals/flash/test_greet.py（新規）

## 止められた操作・分かりにくかった所
- なし。初回試験で相対パス `"greet.py"` を cwd 依存で呼ぶテストが落ちたが、`__file__` からの絶対パス化で解消（その他の不准備なし）。
