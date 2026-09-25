# 報告: T-0925-71-astra
## 何をした
- 起動時の Available skills 提示を列挙した（一覧コマンド未使用）。全体 51 エントリー／同名重複除外 49 名、ハーネス 25 本／ディスク 27 本。
- CLI 提示（作業木 .agents/skills（起動時提示））: brainstorming, consulting-pptx-skill, diagnosing-bugs, docx, frontend-design, hf-cli, independent-check, japanese-tech-writing, leader, mcp-builder, meeting-copilot, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx
- CLI 提示（システム /home/muro/.codex/skills/.system）: imagegen, openai-docs, plugin-creator, skill-creator, skill-installer
- CLI 提示（個人 /home/muro/.agents/skills）: agmsg, skill-creator
- CLI 提示（プラグイン app-6a330a7730c081919892632d5baaec58）: app-6a330a7730c081919892632d5baaec58:build-checklist, app-6a330a7730c081919892632d5baaec58:build-onboard, app-6a330a7730c081919892632d5baaec58:build-prd, app-6a330a7730c081919892632d5baaec58:build-project, app-6a330a7730c081919892632d5baaec58:build-scope, app-6a330a7730c081919892632d5baaec58:build-spec, app-6a330a7730c081919892632d5baaec58:find-hackathon, app-6a330a7730c081919892632d5baaec58:hackathon-map, app-6a330a7730c081919892632d5baaec58:prepare-submission, app-6a330a7730c081919892632d5baaec58:resources, app-6a330a7730c081919892632d5baaec58:review-hackathon-rules, app-6a330a7730c081919892632d5baaec58:start-hackathon, app-6a330a7730c081919892632d5baaec58:submit-project
- CLI 提示（プラグイン google-drive）: google-drive:google-docs, google-drive:google-drive, google-drive:google-drive-comments, google-drive:google-sheets, google-drive:google-slides
- CLI 提示（プラグイン plugin-management）: plugin-management:plugin-management
- `ls .agents/skills`（27 本）: brainstorming, consulting-pptx-skill, diagnosing-bugs, docx, frontend-design, handoff, hf-cli, i-have-adhd, independent-check, japanese-tech-writing, leader, mcp-builder, meeting-copilot, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx
- 差は未提示の `handoff`, `i-have-adhd` の2本。双方に `disable-model-invocation: true` と `policy.allow_implicit_invocation: false` がある。27本とも本文は読めた。内部原因の断定・明示呼び出しは未検証。
- consulting-pptx-skill で指定の3枚を生成し、見本文字・架空のページ参照を実物に置換。test-audit の Authoring gate を既存試験に適用した。
## 検証の結果
- `python3 .agents/skills/consulting-pptx-skill/scripts/new_deck.py --parts b01,b02,b10 --title "スキルの確認" -o evals/astra/deck.html` → 3 slides。初回は出力先不在で FileNotFoundError、`mkdir -p evals/astra` 後に成功。CLI 固有の問題ではない。
- `python3 .agents/skills/consulting-pptx-skill/scripts/check_deck.py evals/astra/deck.html` → 終了0、0 FAIL / 2 WARN。WARN は p1・p3 のタイトル空のみ（許容対象）。
- `PYTHONDONTWRITEBYTECODE=1 python3 harness/check.py` → 終了0、「点検が通りました。」。出力は evals/astra/harness-check.txt。
- 問1（守る動作）: `harness/evals/greet/check.py` は報告・試験ファイルの存在、`greet("Ada") == "Hello, Ada!"`、試験の15秒以内の正常終了を確認する。
- 問2（失敗させる退行）: 挨拶の綴り・空白・句読点の誤り、greet の欠落、報告・試験ファイルの欠落、試験の異常終了・時間超過で失敗する。Ada 以外への固定値返却は見逃し得る。
- 問3（既存試験との差）: `tests/test_delegate.py` は偽 CLI の正しい成果物で評価経路を確認する。実際の担い手の成果物は本 check.py が直接検査する。生成された test_hello.py との同一入力の重複はあり得るため、新規の同内容試験は追加しない。
- 問4（試験専用の仕掛け）: 不要。依頼された hello.py の greet を直接呼び、test_hello.py を別プロセスで実行しており、本番コードに試験専用の公開関数・フラグは求めていない。
## 残り
- 独立の検収は別の担い手へ委ねる。本報告は実行事実のみ。依頼は HTML の機械チェックまでのため、PDF化・描画確認は未実施。全27本の実行可能性は未検証。
## 人の判断が要ること
- なし。skill の中身・設定は変更していない。
## 変更したファイル
- `evals/astra/deck.html`, `evals/astra/skills.md`, `evals/astra/check_deck.txt`, `evals/astra/harness-check.txt`, `REPORT.md`（明示された報告先）。
