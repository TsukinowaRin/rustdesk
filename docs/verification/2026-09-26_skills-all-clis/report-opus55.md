# 報告: T-0925-65-opus55（スキルが見えて使えるか / Claude Code・Opus 5.5）
## 何をした
- 1 見える物: Claude Code は起動時に skill 一覧を model へ渡す（Skill 道具の一覧）。その中にこのハーネスの skill は **25 本**: brainstorming, consulting-pptx-skill, diagnosing-bugs, docx, frontend-design, hf-cli, independent-check, japanese-tech-writing, leader, mcp-builder, meeting-copilot, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx（ほかに利用者側の agmsg や plugin の skill も並ぶが、ハーネスの物ではない）
- `ls .agents/skills` → **27 本**（上の 25 本 + handoff, i-have-adhd）。`.claude/skills` も 27 本で、`diff -r` の差は 0
- 差 2 本の理由: handoff と i-have-adhd は SKILL.md に `disable-model-invocation: true` があり、Claude Code は model 向け一覧に出さない（人が `/handoff` `/i-have-adhd` と打てば動く設計）。写しや設定の不足ではない
- 2 `new_deck.py --parts b01,b02,b10` で 3 枚を作り、プレースホルダー（Text N / ラベル N / Source 1 / 会社名 / 連絡先 / パーツ名の日付欄）を実物に差し替えた。全体マップの存在しない参照「→ P.3〜P.6」は消した
- 3 test-audit「Authoring gate」を `harness/evals/greet/check.py` に当てはめた（下の 4 行）
## 検証の結果
- `grep -nE 'Text [0-9]|ラベル [0-9]|YYYY|Source [0-9]' evals/opus55/deck.html` → 該当なし
- `python3 .agents/skills/consulting-pptx-skill/scripts/check_deck.py evals/opus55/deck.html` → **0 FAIL / 3 WARN**（p1・p3 タイトル空＝表紙・裏表紙で許容。`.sub` ×2 も表紙・裏表紙の物）
- 手順 7（check_layout.mjs）・9（PDF 化の目視）は依頼外なので打っていない
- test-audit の 4 問の答え:
  1. 守る物: 受け入れ条件どおり `greet("Ada")` が `Hello, Ada!` を返し、`test_hello.py` が通り、報告があること（外から見える結果）
  2. 落ちる退行: 文字列の違い（`Hello, Ada` の「!」抜け等）、関数名違い、`test_hello.py` の欠落や失敗、REPORT.md の欠落
  3. 既存で足りない理由: `test_hello.py` は担い手自身が書くので独立の証拠にならず、評価側の持ち主は check.py だけ。ただし `test_hello.py` の実行は中身を問わず、assert の無い試験でも通る（junk pattern の「assertion-free」に近い弱さ）
  4. 本番に無い継ぎ目（seam）: 要らない。`runpy` で hello.py を実際に読み、公開の `greet` を呼ぶだけ
## 残り
- なし（見えない・読めない・使えない skill は無かった）
## 人の判断が要ること
- なし。補足: 最初の一覧の命令で `tee /tmp/...` を使い、守り（guard.py）に「作業木の外」で止められた。回避せず tee を外して打ち直した
## 変更したファイル
- evals/opus55/deck.html（新規）、REPORT.md（新規）
