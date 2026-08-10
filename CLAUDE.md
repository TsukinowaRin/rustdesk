@AGENTS.md

# Claude Code 向け補足

- Claude Code は AGENTS.md を native に読まないため、このファイルが import で橋渡しする。ここには Claude 固有の差分だけを書く。
- skills の編集元は `.agents/skills/`。`.claude/skills/` は生成 mirror なので直接編集せず、`python3 scripts/sync_shared_skills.py` で同期する。
- 役割特化の subagent は `.claude/agents/`（code-reviewer / docs-maintainer / test-debugger）を使う。
- project hooks は `.claude/settings.json` に定義されている。ブロックされた操作を別の書き方で回避しない。
- model は pin しない。必要なときだけ `/model` や `--model` で切り替える。
