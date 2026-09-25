---
member: sol6
hands: workspace
fanout: 1
minutes: 10
independent_of: 
---
# はじめての依頼: 挨拶の道具と試験

## 目的
このハーネスを入れたばかりの空の project で、担い手が普通に仕事をして報告を返せるかを見る。
仕事そのものは小さい: `hello/greet.py` と、その試験 `hello/test_greet.py` を作る。

## 受け入れ条件（機械で確かめる）
1. `python3 hello/greet.py 太郎` が `こんにちは、太郎さん` と 1 行だけ出して exit 0
2. `python3 hello/greet.py` のように名前が無いときは `使い方: greet.py <名前>` を stderr に出して exit 2
3. `python3 hello/test_greet.py` が上の 2 つを確かめて通る（外部ライブラリは使わない）
4. `python3 harness/check.py` が通ったまま

## 触ってよい場所
`hello/` の下だけ。`harness/`・`AGENTS.md`・`docs/` は読むだけで変えない。

## 報告に必ず書くこと
- 打った命令と出力の要点（受け入れ条件 1〜3 の実行結果）
- このハーネスを「入れたばかりの人」として使って、分かりにくかった所・止められた所があれば 1 行ずつ
