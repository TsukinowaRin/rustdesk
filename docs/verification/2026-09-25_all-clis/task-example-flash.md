---
member: flash
hands: workspace
fanout: 1
minutes: 15
independent_of: 
---
# 一通り試す: 挨拶の道具と試験（担い手 flash）

## 目的
この機械にある CLI を 1 本ずつ担い手にして、同じ小さな仕事を通す。仕事: `evals/flash/greet.py` と試験 `evals/flash/test_greet.py` を作る。

## 受け入れ条件（機械で確かめる）
1. `python3 evals/flash/greet.py 太郎` が `こんにちは、太郎さん` と 1 行だけ出して exit 0
2. `python3 evals/flash/greet.py` のように名前が無いときは `使い方: greet.py <名前>` を stderr に出して exit 2
3. `python3 evals/flash/test_greet.py` が上の 2 つを確かめて通る（外部ライブラリは使わない）
4. `git status --short` に `evals/flash/` の 2 ファイル以外の変更が無い

## 触ってよい場所
`evals/flash/` の下だけ。

## 報告に必ず書くこと
- 受け入れ条件 1〜4 の実行結果（打った命令と出力の要点）
- 止められた操作・分かりにくかった所があれば 1 行ずつ
