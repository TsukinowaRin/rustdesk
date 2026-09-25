# 報告: スキルが見えて使えるか（担い手 sol6）
## 何をした
- Codex の起動時に提示された利用可能スキルは51件（同名の `skill-creator` 3件を区別すると49名）。専用の一覧命令は提示されていないため、起動時の一覧を数えた。
- 起動時一覧 r1（5件）: imagegen, openai-docs, plugin-creator, skill-creator, skill-installer。
- 起動時一覧 r5（25件）: brainstorming, consulting-pptx-skill, diagnosing-bugs, docx, frontend-design, hf-cli, independent-check, japanese-tech-writing, leader, mcp-builder, meeting-copilot, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx。
- 起動時一覧 r0（2件）: agmsg, skill-creator。
- 起動時一覧 r2（13件）: app-6a330a7730c081919892632d5baaec58:build-checklist, :build-onboard, :build-prd, :build-project, :build-scope, :build-spec, :find-hackathon, :hackathon-map, :prepare-submission, :resources, :review-hackathon-rules, :start-hackathon, :submit-project（後続の `:` 名は同じ接頭辞）。
- 起動時一覧 r3（5件）: google-drive:google-docs, google-drive:google-drive, google-drive:google-drive-comments, google-drive:google-sheets, google-drive:google-slides。
- 起動時一覧 r4（1件）: plugin-management:plugin-management。
- `.agents/skills`（27本）: brainstorming, consulting-pptx-skill, diagnosing-bugs, docx, frontend-design, handoff, hf-cli, i-have-adhd, independent-check, japanese-tech-writing, leader, mcp-builder, meeting-copilot, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx。
- 差: ローカル27名のうち25名が起動時一覧にあり、`handoff` と `i-have-adhd` の2名は無い。起動時一覧にはローカル以外の24名もある（49名−27名＝22名の差）。
- `consulting-pptx-skill` を読み、指定の b01,b02,b10 で3枚の HTML デッキを作り、見本の文言を実物に差し替えた。
- `test-audit` Authoring gate ① 守る契約: `greet("Ada")` が `Hello, Ada!` を返すという外から見える動作。
- ② 落ちる退行: 名前の差し込み、句読点、感嘆符が変わると期待値と一致しない。
- ③ 既存試験との差: `harness/evals/greet/check.py` も同じ戻り値を直接確認するため、`test_hello.py` に別の動作上のリスクは無い。課題は同ファイルの作成と実行を別途要求する。
- ④ 試験専用の口: 不要。公開関数 `greet(name)` を直接呼べる。
## 検証の結果
- `ls .agents/skills` → 上記の27名を確認。
- `python3 .agents/skills/consulting-pptx-skill/scripts/new_deck.py --parts b01,b02,b10 --title "スキルの確認" -o evals/sol6/deck.html` → 初回は出力先未作成で失敗。`mkdir -p evals/sol6` 後に再実行し、`3 slides（番号付き 1 ページ）`。
- `python3 .agents/skills/consulting-pptx-skill/scripts/check_deck.py evals/sol6/deck.html` → `0 FAIL / 2 WARN`。WARN は p1・p3 の「タイトルが空」で、表紙・裏表紙に当たる。
- `rg -n 'Text [0-9]|ラベル[ 0-9]|YYYY|Source [0-9]|→ P\\.' evals/sol6/deck.html` → 該当なし。
## 残り
- なし。
## 人の判断が要ること
- `handoff` と `i-have-adhd` が Codex 起動時のスキル一覧に提示されなかった理由は、この作業で見えた情報からは特定できない。配置は確認済みで、設定・起動時の読み込み範囲の確認が必要。
## 変更したファイル
- `evals/sol6/deck.html`
- `REPORT.md`（依頼書で指定された報告先）
