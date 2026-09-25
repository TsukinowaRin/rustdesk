# 報告: スキルが見えるか（Kilo、一覧だけ）
## 何をした
- Kilo 起動時に提示された skill 一覧を書き出し、`ls .agents/skills` と比べ、test-audit/SKILL.md の先頭見出しを確認した
## 検証の結果
- 1. Kilo に見える skill（32 件）: agmsg, brainstorming, consulting-pptx-skill, diagnosing-bugs, docs, docx, frontend-design, handoff, hf-cli, i-have-adhd, import-memory, independent-check, japanese-tech-writing, kilo-config, leader, mcp-builder, meeting-copilot, morning, pdf, ponytail, pptx, receiving-code-review, research, skill-creator, test-audit, test-driven-development, verification-before-completion, webapp-testing, worker, writing-for-agents, writing-plans, xlsx
- 2. 差: `.agents/skills` に 27 件。Kilo が示す 32 件から 5 件は他のパスから来ている。`agmsg`(~/.agents/skills)、`docs`(~/.claude/skills/synced)、`import-memory`(~/.claude/skills/synced)、`kilo-config`(builtin)、`morning`(~/.claude/skills/synced)。`.agents/skills` の 27 件すべてが Kilo に表示されている
- 3. `test-audit/SKILL.md` 先頭 `#` 見出し: `# Test Audit`
## 残り
- なし
## 人の判断が要ること
- なし
## 変更したファイル
- .loop/work/T-0925-72-kilo/REPORT.md
