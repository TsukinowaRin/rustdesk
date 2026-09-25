# 報告: スキルが見えて使えるか（担い手 omp）
## 何をした
- CLI に skill 一覧コマンドは提示されていないため、起動時に提示された skills を「見える物」とした。
- CLI 提示 26: agmsg, brainstorming, consulting-pptx-skill, diagnosing-bugs, docx, frontend-design, hf-cli, independent-check, japanese-tech-writing, leader, mcp-builder, meeting-copilot, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx。
- `.agents/skills/` 27: brainstorming, consulting-pptx-skill, diagnosing-bugs, docx, frontend-design, handoff, hf-cli, i-have-adhd, independent-check, japanese-tech-writing, leader, mcp-builder, meeting-copilot, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx。
- 差: 共通 25、CLI 提示にない handoff・i-have-adhd の 2 本、CLI にだけある agmsg の 1 本。CLI から skill://consulting-pptx-skill と skill://test-audit を読めた。
- 指定の b01,b02,b10 を使い、実物の文言に置き換えた 3 枚の HTML デッキを作った。
## 検証の結果
- `python3 .agents/skills/consulting-pptx-skill/scripts/new_deck.py --parts b01,b02,b10 --title "スキルの確認" -o evals/omp/deck.html` → `3 slides（番号付き 1 ページ）`。
- `python3 .agents/skills/consulting-pptx-skill/scripts/check_deck.py evals/omp/deck.html` → `0 FAIL / 3 WARN`。WARN は表紙・裏表紙のタイトル空 2 件と、その両ページの `.sub` 2 箇所をまとめた 1 件。
- Authoring gate ① 守る動作: `test_hello.py` は `greet("Ada") == "Hello, Ada!"` という外から見える返り値を守る（`task.md` の受け入れ条件）。
- Authoring gate ② 起こりうる退行: 挨拶の句読点、空白、名前の連結を誤れば、その返り値の比較が失敗する。
- Authoring gate ③ 既存試験との重複: `harness/evals/greet/check.py` の 9 行目も同じ返り値を直接検査する。`test_hello.py` は課題で必須だが、契約の独立した追加リスクはない。
- Authoring gate ④ 専用口: 通常の `greet(name)` だけを呼べばよく、試験だけの export・flag・wrapper は要らない。
## 残り
- CLI の skill 登録状況を表示する専用コマンドは提示されず、起動時一覧と実際の読込成功以外の確認はしていない。欠落 2 本が CLI 設定や写しの不足によるかは未確定。
## 人の判断が要ること
- CLI 起動時一覧を `.agents/skills/` と揃えるか（handoff・i-have-adhd を登録するか）確認が必要。設定・写しは触っていない。
## 変更したファイル
- `evals/omp/deck.html`
- `REPORT.md`
