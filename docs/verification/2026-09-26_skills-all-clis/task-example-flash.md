---
member: flash
hands: workspace
fanout: 1
minutes: 20
independent_of: 
---
# スキルが見えて使えるか（担い手 flash）

## 目的
このハーネスの skill 27 本が、あなたの CLI から見えて、実際に使えるかを確かめる。skill の置き場は `.agents/skills/`（Claude Code は `.claude/skills/` の写し、Kilo は `kilo.jsonc` で指す）。

## やること
1. **見える物を列挙する**: あなたの CLI が skill を認識する仕組みで見えている skill の名前を全部書く（CLI に skill の一覧を出す命令や表示があればそれを使う。無ければ、起動時に読み込まれた・提示された skill があるかを正直に書く）。別に `ls .agents/skills` の名前一覧も書き、CLI の仕組みで見えた数と比べる
2. **1 本を実際に使う**: `consulting-pptx-skill` を使って、3 枚のデッキを作る。`python3 .agents/skills/consulting-pptx-skill/scripts/new_deck.py --parts b01,b02,b10 --title "スキルの確認" -o evals/flash/deck.html` → プレースホルダー（`Text N` / `ラベル N` / `YYYY` など）を短い実物に差し替える → `python3 .agents/skills/consulting-pptx-skill/scripts/check_deck.py evals/flash/deck.html` で **FAIL 0**（表紙・裏表紙の「タイトル空」WARN は許容）
3. **もう 1 本**: `test-audit` skill の「Authoring gate」の 4 つの問いを、`harness/evals/greet/` の試験に当てはめて 4 行で答える（skill の中身を読んで使えるか）

## 報告に必ず書くこと
- 1 の一覧（CLI の仕組みで見えた数 / `.agents/skills` の数）と、両者の差
- 2 の `check_deck.py` の出力の要点（FAIL と WARN の数）
- 3 の 4 行
- skill が「見えない」「読めない」「使えなかった」ことがあれば、その CLI 固有の理由（設定が要る、写しが要る、など）

## 触ってよい場所
`evals/flash/` の下だけ。skill の中は読むだけで変えない。
