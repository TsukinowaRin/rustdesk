# 公式ソースと設計メモ

このテンプレートは、2026-07-04 時点の公式ソースをもとに設計する。二次情報ではなく、各ベンダー自身の docs / blog と repository README / code を優先する。旧版の出典（2026-06-20 検証）は `Old/docs/BEST_PRACTICES_SOURCES.md` に残っている。

## AGENTS.md 標準

- [agents.md](https://agents.md/)
  - AGENTS.md は Sourcegraph / OpenAI / Google / Cursor / Factory 発の共通 instruction 標準で、Linux Foundation 管理。Codex / Antigravity / Cursor / opencode / Kilo Code が native に読む。
- [anthropics/claude-code issue #6235](https://github.com/anthropics/claude-code/issues/6235)
  - Claude Code は 2026-07 時点で AGENTS.md を native に読まない。`CLAUDE.md` に `@AGENTS.md` import を置く方式が公式にサポートされた橋渡しで、このテンプレートもそれを採る。

## Claude Code

- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices)
  - context window は最重要リソース。探索、計画、実装を分け、subagents で調査を分離する。
- [Extend Claude Code](https://code.claude.com/docs/en/features-overview)
  - `CLAUDE.md` は always-on、Skills は on-demand、Hooks は guardrail。`CLAUDE.md` は 200 行未満を目安にする。
- [Hooks reference](https://code.claude.com/docs/en/hooks)
  - project-level hooks は `.claude/settings.json`。静的contextは`CLAUDE.md`に置き、このテンプレートでは決定論的guardが必要な`PreToolUse`だけを使う。
- [Claude Code Skills](https://code.claude.com/docs/en/skills)
  - skill の name は常時読まれ、description は数が多いと短縮されうる。trigger words を description 前半に置く。

## Codex / GPT-5.5

- [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
  - global → project root → 作業ディレクトリの順に読み、近いものが後勝ち。project docs は約 32KiB 上限。
- [Agent Skills – Codex](https://developers.openai.com/codex/skills)
  - skills は progressive disclosure。repo-local skills は `.agents/skills/` に置ける。
- [Hooks – Codex](https://developers.openai.com/codex/hooks) / [Config basics](https://developers.openai.com/codex/config-basic)
  - project config は `.codex/config.toml`。`[features].hooks = true` で有効化し、deny は `hookSpecificOutput.permissionDecision = "deny"`。

## Antigravity CLI

- [Transitioning Gemini CLI to Antigravity CLI](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)
  - 2026-05-19 告知。Agent Skills / Hooks / Subagents / plugins を引き継ぐ。旧 `.gemini/` 構造は持ち込まない。
- [Antigravity CLI features](https://antigravity.google/docs/cli-features) / [hooks](https://www.antigravity.google/docs/hooks)
  - workspace customization は `.agents/`。AGENTS.md を project instruction として native に読む。このテンプレートでは`.agents/hooks.json`の`PreToolUse`（`decision: allow|deny|ask`）だけを使う。
- local observation
  - terminal-first binary は `agy`。`antigravity` は GUI launcher の場合があるため headless smoke には `agy -p` を使う。

## Cursor（2026-07-04 追加検証）

- [Agent Skills | Cursor Docs](https://cursor.com/docs/context/skills)
  - Cursor は `.agents/skills/` と `.cursor/skills/` から skill を native 読込し、互換として `.claude/skills/` / `.codex/skills/` も読む。SKILL.md frontmatter は `name` / `description`（+ optional `paths`, `disable-model-invocation`）。rules は `/migrate-to-skills` で skills への移行が推奨方向。
- [Hooks | Cursor Docs](https://cursor.com/docs/agent/hooks)
  - project-level は `.cursor/hooks.json`（`{"version": 1, "hooks": {...}}`）。event は `beforeShellExecution` / `beforeReadFile` / `preToolUse` など。拒否は exit code 2 または `{"permission": "deny"}` JSON。
- [Best practices for coding with agents](https://cursor.com/blog/agent-best-practices)
  - AGENTS.md を project root（と subdirectory）で読む。

## Kilo Code

- [Custom Instructions](https://kilo.ai/docs/customize/custom-instructions) / [Skills](https://kilo.ai/docs/customize/skills)
  - `AGENTS.md` を自動検出し primary instruction にできる。project skills は `.kilo/skills/` に加え `.claude/skills/` / `.agents/skills/` も読む。
- [Custom Modes](https://kilo.ai/docs/customize/custom-modes)
  - agent は `.kilo/agents/*.md` か `kilo.jsonc` の `agent` key で定義し、`permission` で絞れる。

## opencode

- [Rules](https://opencode.ai/docs/rules) / [Agent Skills](https://opencode.ai/docs/skills/)
  - project rules は `AGENTS.md`。skills は `.opencode/skills/` / `.claude/skills/` / `.agents/skills/` を検出。`name` はディレクトリ名一致、`description` は 1-1024 chars。
- [Config](https://opencode.ai/docs/config/) / [Permissions](https://opencode.ai/docs/permissions/)
  - project config は `opencode.jsonc`。`permission` で `bash` / `edit` / `read` などを allow / ask / deny にできる。

## Grok CLI（2026-07-16、grok 0.2.101で追試）

- [Hooks | SpaceXAI Docs](https://docs.x.ai/build/features/hooks)
  - `.claude/settings.json` を互換 hook として読むが、project hook は事前 trust が必要。Grok native event は `toolName` / `toolInput` を使い、deny は `{"decision":"deny","reason":"..."}` または exit 2。timeout・crash・不正出力は fail-open。
- [Settings | SpaceXAI Docs](https://docs.x.ai/build/settings) / [Enterprise Deployments | SpaceXAI Docs](https://docs.x.ai/build/enterprise)
  - repo-shared の `.grok/config.toml` は permission rule を持てる。deny は allow より優先し、`dontAsk` + narrow allow + sandbox の併用が high-security / CI 向け。sandbox は Linux で Landlock / seccomp を使うと説明されているが、本 repo の WSL2 実測では `--sandbox read-only` が CWD write を止めなかった。
- [CLI Reference | SpaceXAI Docs](https://docs.x.ai/build/cli/reference)
  - `grok inspect --json` で検出した rules / hooks を確認できる。`--deny`、`--tools`、`--disallowed-tools`、`--sandbox` を headless session に指定できる。
- local 0.2.101実測:
  - `.grok/config.toml`はfolder trust前にもloadされ、denyがallowより優先した。Claude互換hookはtrust後に発火し、Grok payloadは`toolName` / `toolInput`とnative tool名を使う。
  - WSL2 `/mnt/d`では`read-only` / `strict` sandboxともwriteを止めなかった。現runnerは同一sessionのread-only status recoveryにより2 iterations、DONE + gate pass、exit 0を確認した。

## GPT-5.6（2026-07-11 調査。モデルノートは docs/HARNESS.md、対策は SECURITY.md / agent_loop.py）

- [GPT-5.6: Frontier intelligence that scales with your ambition | OpenAI](https://openai.com/index/gpt-5-6/) / [Previewing GPT-5.6 Sol | OpenAI](https://openai.com/index/previewing-gpt-5-6-sol/)
  - 2026-06-26 限定プレビュー、2026-07-09 GA。ChatGPT / Codex / API で提供。Sol は agentic coding で token 効率 54% 改善を主張。
- [Models | ChatGPT Learn（旧 developers.openai.com/codex/models）](https://developers.openai.com/codex/models)
  - model ID は `gpt-5.6-sol`（複雑・曖昧なタスク）/ `gpt-5.6-terra`（日常の主力）/ `gpt-5.6-luna`（定型・大量処理）。Codex CLI は `-m` / `--model` か config.toml の `model` key で指定。reasoning effort は low / medium / high + Sol の max / ultra（ultra は内部 sub-agent 並列で使用枠を高速消費）。
- [OpenAI launches its new family of models with GPT-5.6 | TechCrunch](https://techcrunch.com/2026/07/09/openai-launches-its-new-family-of-models-with-gpt-5-6/) / [GPT-5.6 - Wikipedia](https://en.wikipedia.org/wiki/GPT-5.6)
  - TerminalBench 2.1 で Sol 88.8% / Sol Ultra 91.9%。Terra は GPT-5.5 同等性能で半額（$2.50/$15 per M tokens。Sol $5/$30、Luna $1/$6 の報道）。
- [GPT-5.6 cheats so much its testers couldn't measure it | Transformer](https://www.transformernews.ai/p/openai-gpt-56-sol-cheating-scheming-metr) / [HN: Summary of METR's predeployment evaluation](https://news.ycombinator.com/item?id=48690710)
  - METR 事前評価: Sol の reward hacking 率は「評価した公開モデルで過去最高」。評価基盤のバグ悪用・隠しテスト参照・隠しソース抽出を観測。不正の扱いで能力推定が 11.3h〜270h+ までぶれ、「頑健な測定ではない」と結論。「明示的に禁止されていないことは実行可能と解釈する」傾向、虚偽報告の事例も system card に記載。Apollo Research は「テスト認識の言語化が 16%（GPT-5.5 は 43%）に低下 = 認識を隠している可能性」を指摘。→ 本ハーネスの対策: 禁止事項の明示列挙（AGENTS.md / loop prompt）+ agent_loop.py の protect 機構（gate 改変の機械検出、exit 6）。
- [GPT-5.6 Is Finally Public — and Reddit Can't Decide | Hardware Busters](https://hwbusters.com/news/gpt-5-6-is-finally-public-and-reddit-cant-decide-if-its-a-breakthrough-or-a-mess/) / [GPT5.6を使用した感想メモ | せせらブログ](https://sesera231.com/laptop/gpt5-6-memo/)
  - コミュニティ知見: ChatGPT Work と Codex が usage pool を共有し、チャット利用が Codex weekly limit を消費する不満。ultra は並列化が効くタスク向けで小修正には過剰。
- Artificial Analysis Intelligence Index（intelligence vs cost per task。2026-07-11 にユーザー経由で共有された分析結果）
  - 3 モデルとも推論タスクで GPT-5.5 の Pareto frontier を超えるが、**Sol と Luna が Terra を全点で上回る**（Terra のどの effort でも、同コストで高知能 or 同知能で低コストの Luna / Sol 設定が存在する）。Luna がとくにコスト効率で突出。→ 本ハーネスのモデルノート（docs/HARNESS.md）は「Luna か Sol の 2 択」を推奨とし、公式の「Terra=日常の主力」表現をそのまま採らない。

### Codex チーム AMA（2026-07-12 追試）

- [AMA with OpenAI’s Codex team（Reddit embed）](https://embed.reddit.com/r/codex/comments/1us9ty9/ama_with_openais_codex_team/) / [ユーザー指定の r.jina.ai proxy](https://r.jina.ai/https://www.reddit.com/r/codex/comments/1us9ty9/ama_with_openais_codex_team/)
  - embed から公式投稿本文を確認: Codex の weekly user は 5M 超（3か月で2倍）、同期間に 150 の features / improvements。Codex は software development 専用体験として維持され、repo、terminal、browser、desktop apps、Chrome、mobile からタスクを継続できると説明。
  - r.jina.ai、old.reddit、Reddit JSON/API、redditmedia はいずれも Reddit 側の 403 / network verification でコメント本文を取得できなかった。embed は投稿本文とコメント数のみを返す。そのため、モデル使い分け、`codex exec`、AGENTS.md / skills / hooks、usage limits、reward hacking、roadmap に関する AMA 回答は検証できず、ハーネス設計へ反映していない。

## 追加 workflow 調査（2026-07-12）

- [Kill AI Slop](https://killaislop.com/#skill) / [yetone/kill-ai-slop](https://github.com/yetone/kill-ai-slop)
  - 32 種の visual / copy の兆候を catalogue 化し、dependency-free scanner → code を読んだ triage → 変更前 report → 最小修正 → 再走査という workflow。gradient / glass / over-rounding / badge spam / kicker / invented stats / generic copy などを検出するが、brand token や意図的表現を false positive として分ける。
  - 既存 `design-taste-frontend` と目的・ルールの大半が重なるため新 skill は追加しない。補完価値がある「変更前の走査・intentional 判定・file:line report・変更後の再走査」を既存 skill の De-slop 節へ取り込んだ。外部 scanner は導入していない。
- [shadcn/improve](https://github.com/shadcn/improve)
  - source を変更しない advisor が9 category を監査し、根拠を再確認・優先順位付けしたうえで、別の低コスト agent が実行できる自己完結 plan を作る MIT licensed skill。plan には対象 commit、drift check、scope、検証 gate、STOP 条件を持たせる。
  - 本ハーネスの `execplan` は既知の要求を実装計画にする workflow であり、改善候補を横断監査する入口が無かった。直接 download はせず、`codebase-improvement-audit` を local skill として再構成し、`start-task` / `execplan` / `checkpoint` と既存の deny-by-default に接続した。issue 公開や自動 merge は採用していない。

## Harness / Loop / 品質

- [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd/tree/07684c4ab625dd7d1ea6e99e065f60bc0ac6a1ba)
  - action-first、進捗の再提示、permission拒否後の具体的な原因・次動作を促す MIT skill。commit `07684c4` の `skills/i-have-adhd/` だけを `skill-installer` で導入し、upstream hook、評価runner、CI、plugin metadataは導入していない。skill内にMIT本文を同梱した。

- [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent)
  - 小さい harness と評価可能な task ほど再現性が上がる。巨大 framework ではなく最小 wrapper と smoke を優先する。
- [jpicklyk/task-orchestrator](https://github.com/jpicklyk/task-orchestrator) / [cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering)
  - workflow は prompt でなく deterministic gate（hooks / permissions / smoke / acceptance criteria）で守る。loop は state / budget / stop 条件を持つ system として設計する（`.agents/skills/harness-loop/`）。
- [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills)
  - 4原則（Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution）を`AGENTS.md`の作業原則として保持する。重複していたskillは2026-07-13に削除した。

## Windows通知（2026-07-14実機確認）

- [Windows notifications overview | Microsoft Learn](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/)
  - unpackaged Win32の現行推奨はWindows App SDKの`AppNotificationManager`。NuGet packageが必要なため、外部依存を持たない本テンプレートでは採用しない。
- [Quickstart: Sending a toast notification from the desktop | Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/shell/quickstart-sending-desktop-toast)
  - inbox WinRTの`ToastNotificationManager`は、Start shortcutへ登録済みのAppUserModelIDを`CreateToastNotifier`へ渡す必要がある。本テンプレートはregistry / Start menuを書き換えず、既存のWindows Terminal AppUserModelIDを利用するため、toastの表示名はWindows Terminalになる。
- WSL2 / Windows 10.0.26200.8737で、PowerShellを使わず.NET Framework `csc.exe`でhelperをcompileし、標準通知音付きtoastの表示、通知センターへの残存、exit 0を実機確認した。

## Design / Writing / Security

- [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) / [kzhrknt/awesome-design-md-jp](https://github.com/kzhrknt/awesome-design-md-jp) / [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)
  - `DESIGN.md` を plain-text design system として扱う構成と、anti-slop frontend の考え方（`design-taste-frontend` skill）。
- [iKora128/stop-ai-slop-jp](https://github.com/iKora128/stop-ai-slop-jp)
  - 日本語の AI 臭さを主体の不在・反証不能な抽象・均一リズムとして扱う（`human-readable-writing` skill）。
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) / [GitHub Docs: security policy](https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository)
  - prompt injection / excessive agency / supply chain を主要脅威とし、`SECURITY.md`、`security-harness` skill、hooks、`scripts/security_smoke.sh` に分解。

## 実機検証（2026-07-06、WSL2 + テンプレをコピーした新規ワークスペースで実測）

`tmp/testws-20260706` にテンプレートを配布形（Old/ と .git なし）でコピーし、git init 後に headless session で確認した。

| CLI | AGENTS.md 読込 | skills 認識 | guard 発火 |
|---|---|---|---|
| Claude Code | ✅ `@AGENTS.md` import 経由（見出し引用で確認） | ✅ `.claude/skills/` 9本 | ✅ SessionStart / PreToolUse とも実 session で発火確認 |
| Codex 0.142 | ✅ 見出し引用で確認 | ✅ `.agents/skills/` 9本 | instruction 層で拒否を確認（AGENTS.md の安全策を引用して実行拒否）。hook 機構は `~/.codex/config.toml` の `hooks.state` に他 project の `.codex/config.toml` 承認記録があり project hooks 対応を確認。初回 interactive 承認が必要 |
| Antigravity 1.0.13 | ✅ 見出し引用で確認 | ✅ `.agents/skills/` 9本 | ✅ `cat .env` probe が hooks_core の deny 文言原文でブロックされた |
| opencode | ✅ 見出し引用で確認 | ✅ `.agents/skills/` 9本 | ✅ `.env` read が `opencode.jsonc` の deny ルールでブロックされた（user global の ask より project deny が優先） |
| Kilo Code | ✅ 見出し引用で確認（free モデル `kilo/kilo-auto/free`、認証不要で実行可） | ✅ `kilo debug skill` と実 session の両方で 9本（`.agents/skills/` と `.claude/skills/` の両方から解決） | ✅ `.env` read が `kilo.jsonc` の deny ルールでブロックされた（既定モデルは PAID_MODEL_AUTH_REQUIRED で不可のため free モデル指定で検証） |
| Cursor CLI 2026.07.01 | ✅ 見出し引用で確認（headless は `--trust` が必要） | ✅ `.agents/skills/` 9本を過不足なく列挙 | ✅ `cat .env` probe が `.cursor/hooks.json` の hook でブロックされた（「Rejected: Command execution was blocked by a hook.」）。payload key の懸念は解消 |

- 補足: `.env` probe は Claude Code headless では API 安全層に flag され実行不能だったため、Claude Code の hook 発火は実作業 session での観測（SessionStart 注入、`sudo` リテラル入りコマンドの PreToolUse deny）を根拠とする。
- 2026-07-29追試: `i-have-adhd`追加後はsource / Claude mirrorとも11 skill。Agy 1.1.8とopencode 1.18.4の`agent_loop`実機で、同skillを明示した通常goalが1 iterationのDONE + gates全pass。ほかのCLIでの11 skill列挙は未追試。

## v2 での主な設計反映（2026-07-04）

- mirror は `.claude/skills/` のみ。Codex / Antigravity / Cursor / opencode / Kilo は `.agents/skills/` native 読込のため、旧 `.codex/skills/` / `.kilo/skills/` / `.opencode/skills/` mirror を廃止。
- bridge memory は `CLAUDE.md` のみ。旧 `ANTIGRAVITY.md` / `KILO.md` / `OPENCODE.md` は AGENTS.md native 読込のため廃止。
- docs は PROJECT_BRIEF / REQS / WORKLOG / HARNESS の4本コア + SOURCES + EXECPLAN に統合。
- Cursor guard を `.cursor/hooks.json` + 共通 hooks_core の thin adapter として新設。
