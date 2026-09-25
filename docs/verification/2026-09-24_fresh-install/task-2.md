---
member: sol6
hands: workspace
fanout: 1
minutes: 20
independent_of: 
---
# 新規利用者として README と HARNESS.md の手順を通す

## 目的
このハーネスを今日入れたばかりの人になりきって、文書に書いてある命令を順に打ち、
**動かない・書いてあることと違う・分かりにくい**所を見つける。直さない（直しは指示役が決める）。

## 手順
1. `README.md` を上から読み、そこに書いてある命令を書いてある順に打つ（外へ出す物・秘密に触る物は打たない）。
2. 次に `docs/HARNESS.md` を読み、同じように打つ。
3. `python3 harness/judgment.py brief` と `python3 harness/setup.py status` と `python3 harness/delegate.py team` の出力を読み、初めての人に意味が分かるか判断する。
4. 「聞く」判定の操作を 1 つ、わざと打つ（例: `git push origin feature` — remote が無いので外には出ない）。守りが何を言うか、その言葉で次に何をすればよいか分かるかを見る。

## 受け入れ条件
- `REPORT.md` に次の 3 つの表を書く: ①打った命令と結果（動いた / 動かない / 文書と違う）②分かりにくかった文（引用と、どう直せばよいかの案を 1 行）③初めての人が最初の 30 分でつまずくと思う所、上位 3 つ
- 30 行以内。感想ではなく、命令と出力の事実を書く

## 触ってよい場所
`REPORT.md` だけ。他は読むだけ。
