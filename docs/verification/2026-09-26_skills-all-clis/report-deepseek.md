# 報告: T-0925-74-deepseek
## 何をした
- CLI 起動時の `<available_skills>` に提示された 26 本を記録した：agmsg, brainstorming, consulting-pptx-skill, diagnosing-bugs, docx, frontend-design, hf-cli, independent-check, japanese-tech-writing, leader, mcp-builder, meeting-copilot, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx。
- `ls .agents/skills` に表示された 27 本：brainstorming, consulting-pptx-skill, diagnosing-bugs, docx, frontend-design, handoff, hf-cli, i-have-adhd, independent-check, japanese-tech-writing, leader, mcp-builder, meeting-copilot, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx。
- 差：CLI にのみある `agmsg` が 1 本、ディスクにのみある `handoff` と `i-have-adhd` が 2 本。数の差は CLI が 1 本少ない（26 対 27）。
- `consulting-pptx-skill` の規約を読み、指定の3枚を生成してプレースホルダーを短い実文に変更した。
- `test-audit` の Authoring gate を `harness/evals/greet/task.md` と `check.py` に当てた：
- 問1：`greet("Ada")` が `Hello, Ada!` を返す、利用者から観測できる挨拶を守る。
- 問2：挨拶の句読点・空白・名前の差し込みを誤る変更で失敗する。
- 問3：既存の `check.py` は Ada の戻り値と `test_hello.py` 実行を確認するため、Ada の同じ試験は重複する。別のリスクが無ければ新規追加しない。
- 問4：試験専用の本番側 export・flag・wrapper は不要。公開境界の `greet(name)` を直接呼ぶ。
## 検証の結果
- `ls .agents/skills` → 27 名（上記）。CLI の skill 提示は 26 名（上記）。
- `python3 .agents/skills/consulting-pptx-skill/scripts/new_deck.py --parts b01,b02,b10 --title "スキルの確認" -o evals/deepseek/deck.html` → `3 slides（番号付き 1 ページ）`。
- `python3 .agents/skills/consulting-pptx-skill/scripts/check_deck.py evals/deepseek/deck.html` → `0 FAIL / 2 WARN`。WARN は p1・p3 の表紙と裏表紙のタイトル空のみ。
## 残り
- 別の担い手による独立の検収は未実施。指定の点検出力だけ記録した。
## 人の判断が要ること
- CLI の提示一覧には `handoff`・`i-have-adhd` が無く、ディスクには `agmsg` が無い。CLI 固有の一覧生成・注入の理由や設定要否はこのセッションからは特定できない。`consulting-pptx-skill`・`test-audit` は CLI の skill ツールで読めた。
## 変更したファイル
- `evals/deepseek/deck.html`
- `REPORT.md`（指定された報告先）
