# 展開直後に「普通に使うだけで準備される」かの実測（2026-09-26 06:10〜07:00）

人の言葉: 「Zip を展開して即使うとかはできないの？Python スクリプトを必ず走らせないと行けないのはめんどくさい」「展開した後に普通に AI エージェントを使ったら準備とかいい感じにされるようにして欲しい」。

## 方法
`git archive` で HEAD を repo の外の新しい folder に展開（`.git` 無し・`.loop` 無し）→ 指示役 `claude -p --model claude-opus-5-5` に普通の質問（「guard.py が何を止めるか 5 行で」）→ 終わったあと `.git` と `.loop/team.json` があるか。

| 回 | 仕込み | 結果 | 費用 |
|---|---|---|---|
| 1 | `leader` skill に「初回」の手順（AGENTS.md から「最初に読む」と指す） | **準備されず**。答えだけ返した（2 turn）。skill を読まない | $0.24 |
| 2 | 加えて AGENTS.md に「`.loop/team.json` が無ければ `setup.py auto` を打つ」の 1 行 | **準備されず**（3 turn）。毎回読む 1 枚に書いても、一発実行の指示役は飛ばす | $0.26 |
| 3 | 加えて `.claude/settings.json` の `SessionStart` から `setup.py auto`（作業場を信頼済みにして） | **準備された**。`git log` = `init`、`.loop/team.json` と `tasks/` あり。指示役は何も打っていない | $0.31 |

## 分かったこと
- 文書（skill・AGENTS.md）に書くだけでは、指示役が飛ばすことがある。**機械の入口（開始 hook）から打つ**のが確実。
- Claude Code は、その folder を「信頼する」まで `.claude/settings.json` の hook を読まない（`-p` の試験では `~/.claude.json` の `projects.<path>.hasTrustDialogAccepted` を立てて再現）。人が対話で開けば最初に聞かれる。
- `setup.py auto` は 2 回目は無言・終了 0（T-0926-91 の試験と、repo の外での手打ちで確認）。

## 配線（T-0926-92、Sol、指示役が 2 点直した）
| CLI | 開始 hook | 配線 |
|---|---|---|
| Claude Code | `SessionStart` | あり |
| Codex | `SessionStart`（config.toml） | あり（指示役が guard.py と同じ探し方に直した）。**実測 07:00 ごろ: 合格**（`codex exec -m gpt-6-sol "1+1 は？"` → `hook: SessionStart Completed`、`git log` = `init`、`team.json` あり） |
| Cursor | `sessionStart` | あり（指示役が failClosed を外し、同じ探し方に直した）。**実測 07:00 ごろ: 合格**（`cursor-agent -p --trust --force --model auto "1+1 は？"` → `git log` = `init`、`team.json` あり） |
| opencode / Kilo | plugin の `session.created` | あり |
| omp | 拡張の `session_start` | あり |
| dsh | `.claude/settings.json` 共用 | あり（変換 plugin が `SessionStart` を渡す。実機は未測） |
| Antigravity / Grok | 無し | 指示役が `auto` を打つ（AGENTS.md） |

実測したのは Claude Code / Codex / Cursor の 3 本（すべて合格）。opencode / Kilo / omp / dsh の開始 hook は形の点検（`harness/check.py`）まで。
