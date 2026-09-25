# 報告: スキルが見えて使えるか（grok47）

## 何をした
- 起動時に提示されたスキル（手順書）を全部書き、`ls .agents/skills` の 27 本と比べた。
- consulting-pptx-skill で 3 枚を作り、プレースホルダーを短い実文に替えた。
- test-audit の Authoring gate（試験を足す前の 4 問）を `harness/evals/greet/check.py` に当てた。

## 検証の結果
- `ls -1 .agents/skills` と `ls -1d .agents/skills/*/ | wc -l` → 27。
- 一覧を出す CLI 命令は無い。起動時の提示は 45 本。差は、外から 20 本足され、置き場の 2 本が欠ける。
- 見えた 45: brainstorming, consulting-pptx-skill, diagnosing-bugs, docx, frontend-design, hf-cli, independent-check, japanese-tech-writing, leader, mcp-builder, meeting-copilot, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx, agmsg, docs, import-memory, morning, build-with-ai, create-skill, create-workflow, design, execute-plan, game-assets, imagine, learn, long-running-background-tasks, resume-claude, resume-codex, resume-cursor, review, skill-design-principles, statusline, threejs-frame-conventions
- 置き場 27: brainstorming, consulting-pptx-skill, diagnosing-bugs, docx, frontend-design, handoff, hf-cli, i-have-adhd, independent-check, japanese-tech-writing, leader, mcp-builder, meeting-copilot, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx
- 差: 置き場だけ handoff と i-have-adhd。どちらも `disable-model-invocation: true` で、Grok は起動時の使える一覧に出さない。中身は読めた。見えた側だけの 20 本は作業木の外（`~/.grok/skills` の agmsg、`~/.claude` の docs / import-memory / morning、`~/.grok/bundled/skills` の 16 本）。workflows の deep-research と learn-traces はスキルではないので数に入れていない。
- `python3 .agents/skills/consulting-pptx-skill/scripts/new_deck.py --parts b01,b02,b10 --title "スキルの確認" -o evals/grok47/deck.html` → wrote evals/grok47/deck.html: 3 slides（番号付き 1 ページ）。
- `python3 .agents/skills/consulting-pptx-skill/scripts/check_deck.py evals/grok47/deck.html` → 終了コード 0。0 FAIL / 3 WARN。WARN は `.sub` ×2（表紙の副題なら可）、p1 と p3 のタイトル空（表紙・裏表紙）。
- Authoring gate の 4 行:
  1. 守るものは、`greet("Ada")` が `Hello, Ada!` を返すこと、`test_hello.py` が終了コード 0 であること、`REPORT.md` がファイルであることです。
  2. 戻り値が違う、`hello.py` に `greet` が無い、試験が失敗するかファイルが無い、報告が無い、のどれかで落ちます。
  3. 同じ場所に、これより強い既存の試験はありません。直接の呼び出しは戻り値、`test_hello.py` の実行は提出した試験が通ることを、別々に見ます。
  4. 本番の呼び出し手に要らない出口は要りません。`runpy` で `hello.py` の `greet` を呼ぶだけです。

## 残り
- `check_layout.mjs`、PDF 化、別の人による読み直しはしていない。依頼の確認は `check_deck.py` の FAIL 0 までで、担い手は他の担い手を起動できない。

## 人の判断が要ること
- `command -v grok` を含む命令は「担い手は担い手を起こさない」で止まった。一覧は起動時の提示で足りたので、別の書き方では打ち直していない。続きの判断は不要。

## 変更したファイル
- evals/grok47/deck.html
- REPORT.md
