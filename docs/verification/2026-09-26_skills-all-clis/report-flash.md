# 報告: スキルが見えて使えるか（担い手 flash）

## 何をした
- 起動時に CLI が提示した skill 一覧（available_skills）を列挙: **32 本**。別に `ls .agents/skills` では **27 本**。
- 差: リポジトリの skill 27 本は**すべて** CLI から見えた（欠け 0）。CLI が 5 本多い（agmsg, customize-opencode, docs, import-memory, morning）。この 5 本は木の外（~/.config/opencode/skills、~/.claude/skills/synced）に置かれた物で、置き場 `.agents/skills/` とは別物。この CLI（opencode）は追加設定なしで両方を読めた。写しや kilo.jsonc の設定は不要だった。
- `consulting-pptx-skill` で 3 枚のデッキを実際に作った（b01 表紙 / b02 全体マップ / b10 裏表紙）。プレースホルダー（Text N・ラベル N・会社名・連絡先）を skill 確認の実物に差し替えた。
- `test-audit` の SKILL.md を読み、Authoring gate の 4 問を `harness/evals/greet/` の試験に当てはめた（下記 4 行）。

## 検証の結果
- `python3 .agents/skills/consulting-pptx-skill/scripts/new_deck.py --parts b01,b02,b10 --title "スキルの確認" -o evals/flash/deck.html` → `wrote evals/flash/deck.html: 3 slides（番号付き 1 ページ）`
- `python3 .agents/skills/consulting-pptx-skill/scripts/check_deck.py evals/flash/deck.html` → **`0 FAIL / 3 WARN`**。WARN は p1・p3「タイトル空（表紙/扉なら可）」×2 と `.sub` ×2 の注記 1 行で、すべて表紙・裏表紙まわり。依頼書の許容内。
- 「見えない・読めない・使えなかった」は無し。CLI 固有の理由で詰まった箇所は無し。

## Authoring gate 4 問（greet の試験に当てはめる）
1. 保つ振る舞い: `hello.py` の `greet("Ada")` が「Hello, Ada!」を返すという、呼び手が頼る契約。
2. 信頼できる Regression: 文面の変え忘れ・返り値の取り替え・引数の意味替えで挨拶が外れる壊れ方。試験が落ちる。
3. 既存の coverage で足りない理由: この課題は新規で coverage がまだ無く、`test_hello.py` が契約の保有者 1 本。`check.py` は別担い手の独立の合否であり、同じ契約の二重化ではない。
4. 試験専用の生産口（seam）: 不要。`greet(name)` がもともとの公開先で、試験のための輸出・旗・包みは足す箇所が無い。

## 残り
- greet の `hello.py`・`test_hello.py` は作っていない（この依頼は skill の確認であり、評価課題の実装は別の担い手）。

## 人の判断が要ること
- なし（止められた操作は無し。git commit / push もしていない）。

## 変更したファイル
- evals/flash/deck.html
- REPORT.md（この報告）
