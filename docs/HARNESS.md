# ハーネス構成ガイド

このファイルは、このテンプレートが 7 CLI（Claude Code / Codex / Antigravity CLI / Cursor / opencode / Kilo Code / Grok CLI）でどう動くかの正本。常設の契約だけを書き、日付付きの実測・検証記録は `docs/HARNESS_VERIFICATION.md`、出典は `docs/SOURCES.md` に分離する。

## 設計原則

1. **native-first / 同期より参照**: 各 CLI が native に読める場所（`AGENTS.md`、`.agents/skills/`）を最大限使い、生成 mirror は最小にする。
2. **always-on context 最小化**: 常時読まれるのは `AGENTS.md`（+ Claude は `CLAUDE.md`）だけ。長い知識は skills（必要時 lazy 読込）と docs へ逃がす。
3. **deterministic gate**: prompt だけで防げない失敗は hooks / permissions / smoke script で機械的に止める。最終防衛はモデルの遵守ではなく機械層に置く。
4. **docs = working memory**: chat 履歴なしで `docs/` だけから再開できる状態を保つ。

## CLI 対応マトリクス

| CLI | always-on rules | skills | guard |
|---|---|---|---|
| Claude Code | `CLAUDE.md`（`@AGENTS.md` import。AGENTS.md native 非対応） | `.claude/skills/`（生成 mirror） | `.claude/settings.json` + `.claude/hooks/` |
| Codex | `AGENTS.md` native | `.agents/skills/` native | `.codex/config.toml` `[hooks]` + `.codex/hooks/` + `.codex/rules/` |
| Antigravity (agy) | `AGENTS.md` native | `.agents/skills/` native | `.agents/hooks.json` + `.agents/hooks/` |
| Cursor | `AGENTS.md` native | `.agents/skills/` native | `.cursor/hooks.json` + `.cursor/hooks/` |
| opencode | `AGENTS.md` native | `.agents/skills/` native | `opencode.jsonc` `permission`（生成領域） |
| Kilo Code | `AGENTS.md` native | `.agents/skills/` native（`skills.paths`） | `kilo.jsonc` `permission`（生成領域） |
| Grok CLI (xAI) | `AGENTS.md` native（`CLAUDE.md`も検出） | project skillsを自動検出（`grok inspect`で確認） | `.grok/config.toml` native permission + trust後のClaude互換hook |

## 共有contextの同期

`.agent-shared/context-surfaces.json`が7 CLIのrules / skills / guard接続をmachine-readableに定義する。共通rulesは`AGENTS.md`、共通skillsは`.agents/skills/`、hook logicは`.agent-shared/hooks_core/`、opencode / Kiloのpermissionは`.agent-shared/permissions.json`が正本。CLI固有形式はbridge、adapter、generated blockとして残す。

- 生成と検査: `python3 scripts/sync_shared_context.py`
- read-only検査: `python3 scripts/sync_shared_context.py --check`
- default実行はClaude skill mirrorとopencode / Kilo permission blockを既存scriptで生成してから、7 CLIの接続を検査する。
- `--check`は生成せず、CLI集合、Claude rules bridge、skills path / mirror、hook adapter、generated permission、Grok native permissionのdriftを検出する。
- user-level設定、MCP、model、認証、daemonは同期対象外。

## Skills

- 編集元は `.agents/skills/` のみ。1 ディレクトリ 1 skill、ルートに `SKILL.md`、frontmatter は `name`（ディレクトリ名と一致、`^[a-z0-9]+(-[a-z0-9]+)*$`、1-64 chars）と `description`（1-1024 chars、trigger words を前半に）。
- 長い skill は SKILL.md 本体を 150 行以内に保ち、詳細は同 skill 内の `references/` へ分離して必要時に読む（progressive disclosure）。default-onの`i-have-adhd`はさらに2,785 bytesを上限とし、通常応答ではreferenceを読まない。
- `.claude/skills/`は唯一のmirror。`python3 scripts/sync_shared_skills.py`で同期し、手で編集しない。`--check`はfileを変更せずdriftを検出し、smokeは自動同期せずこのcheckでfailする。
- 標準 skill: `start-task`（文脈 triage）/ `execplan`（複雑作業の計画）/ `checkpoint`（区切りの検証・記録）/ `security-harness` / `harness-loop`（自己ループ運用）/ `agent-mailbox`（CLI 横断通信）/ `human-readable-writing` / `i-have-adhd`（全セッションでデフォルト有効のaction-first出力）/ `design-taste-frontend` / `local-skill-bootstrap` / `codebase-improvement-audit`。`i-have-adhd`は同じセッションでユーザーが`stop adhd mode`または`normal mode`と明示した場合だけ解除し、その他のskillの起動条件はfrontmatter descriptionを正本とする。
- 人間向け最終成果物は、platformがMarkdownを要求しない限り自己完結型HTMLを正本にする。agent state・policy・GitHub標準文書はMarkdownを維持し、同内容のHTML / Markdownを併存させない。HTMLは`human-readable-writing`のvalidatorで検査する。
- 新しい workflow が繰り返し必要になったら、外部 download より `local-skill-bootstrap` で local 作成する。

## Hooks / Permissions

安全ポリシーの正本は機械層。プロース（AGENTS.md / SECURITY.md）は要点とポインタだけを持つ。

- 共通ロジックは `.agent-shared/hooks_core/`（危険コマンド、admin escalation、secret path、skill への外部 download を deny）。各 CLI の adapter は payload / 出力 schema の変換だけを行う。
- 宣言的 permission（opencode / Kilo）の単一ソースは `.agent-shared/permissions.json`。`python3 scripts/sync_permissions.py` が `opencode.jsonc` / `kilo.jsonc` の marker 区間（`permissions:generated`）を生成し、`--check` で drift を検出する（security smoke に組込み済み）。`.grok/config.toml` と `.codex/rules/safe-default.rules` は形式が大きく異なるため生成対象外で、変更時は手動で整合させる。
- CLI 別の検査点:
  - Claude Code: `.claude/settings.json` の `PreToolUse`（matcher: `Bash|Edit|Write|Read|Grep`）。hook 本体の root は `CLAUDE_PROJECT_DIR` を優先し、cwd 由来（`git rev-parse`）は fallback にとどめる。nested repo に cwd が入ると root が内側になり、hook 起動失敗＝全 tool block で cwd を戻す Bash も打てなくなる（2026-08-04 に session 再起動が必要になった）。
  - Codex: `.codex/config.toml` の `[features].hooks = true` + inline `[hooks]`。加えて `.codex/rules/safe-default.rules` が破壊的 git 操作を prefix rule で deny する。project-local hooks は初回に `/hooks` で承認が要る場合がある（設定エラーではない）。
  - Antigravity: `.agents/hooks.json` の `PreToolUse`（`decision: deny`）。subagent 系 tool は force_ask（無人時 deny）。
  - Cursor: `.cursor/hooks.json` の `beforeShellExecution` / `beforeReadFile` / `subagentStart`。拒否は `{"permission": "deny"}`。
  - opencode / Kilo: `opencode.jsonc` / `kilo.jsonc` の `permission` セクション（生成領域）。
  - Grok: `.grok/config.toml` は folder trust 前にも読み込まれ、secret / 破壊操作を deny、admin / push / download を ask。trust 後は Claude 互換 hook も発火する（adapter が camelCase / native tool alias を変換）。
- 共通ポリシー: secret ファイル（`.env`、`.pem`、`id_rsa` 等）は deny（`.env.example` 等は allow）。破壊的コマンド（`git reset --hard`、`git clean -fd`、`rm -rf /`、`mkfs`、`dd`）は deny。`git push` と外部 download は ask。admin 昇格は `AGENT_ADMIN_APPROVED=1` 付きの明示承認時のみ。
- 委任 session の shell: `AGENT_DELEGATED_SHELL=deny`（driver が既定で子プロセスへ渡す）なら hooks_core が shell tool を無条件に deny し、`allow` で opt-in する。承認プロンプトを自動承認する CLI（grok の always-approve / yolo）でも hook は発火するため、これが `--allow-bash` の実質的な実行層になる。`allow` でも破壊的コマンド・secret・admin 昇格の deny は弱まらない。通常の対話 session では未設定なので影響しない。

## Subagents

native subagent は、通常利用でもモデル判断だけでは起動させない。CLI ごとの境界は次のとおり。

| CLI | 通常利用 | mailbox / agent_loop | 再委任 |
|---|---|---|---|
| Claude Code | `.claude/settings.json`で`Agent`をask | `--disallowedTools Agent` | `.claude/agents/*.md`で`disallowedTools: Agent` |
| Codex | `.codex/config.toml`で`multi_agent = false` | `--disable multi_agent` | spawn機能自体を提供しない |
| Antigravity | hookが`invoke_subagent` / `define_subagent`を`force_ask` | `HARNESS_UNATTENDED=1`時はdeny | 同じhookを継承 |
| Cursor | `subagentStart` hookでdeny | 同じhookでdeny | 全階層の開始eventをdeny |
| OpenCode / Kilo | global `task: ask` | primary `mailbox-worker`の`task: deny` | repo-local agentも`task: deny` |
| Grok | `.grok/config.toml`で`Agent`をask | `--no-subagents` | 起動ごとのaskを継承 |

Cursor の `subagentStart` は `ask` をサポートせず、値を指定しても deny として扱うため、Cursor だけは通常利用も全面 deny。Codex で native subagent を意図的に使う場合は、利用者が実行単位で `--enable multi_agent` を付ける。CLI 横断の役割分担は native subagent ではなく mailbox を使う。

## Mailbox（CLI 横断通信）

`scripts/agent_mailbox.py` が CLI をまたぐ下請け通信を `.loop/mailboxes/` で扱う。定期確認するのは model 外の Python dispatcher だけで、空 mailbox では AI CLI を起動しない。配送は `role` / `instance`（登録ごとの世代 ID）/ `task_id` の 3 値完全一致で行い、role を再利用しても旧 message を新 instance へ渡さない。message 本文は untrusted data として batch 内で引用し、REQS・計画・permissions・承認条件を上書きしない。

即時配送（`--now`）は定期実行の interval gate と別経路で、詰まった inflight batch は `fail` で inbox へ戻す（`ack` で逃がさない）。worker の出力は batch の `agent.log` へ直接書かれるので、pipe を挟まず log の更新時刻を進捗の根拠にする。register / send / deliver / fail / close の手順、ACK 契約、CLI 別の `--agent-cmd` は `agent-mailbox` skill（`.agents/skills/agent-mailbox/`）が正本。安全策は `SECURITY.md` の「Multi-agent mailboxの安全策」。

## 自己ループ runner（agent_loop）

`scripts/agent_loop.py` は、headless CLI を goal 達成まで自動で再起動する loop 実行機構。loop の定義は `.agent-shared/loops/` の profile（gates は空にできない）。毎 iteration fresh context で CLI を起動し、docs への state 記録と `LOOP_STATUS:` 宣言をさせ、DONE は gates 全 pass の時だけ受理する。profile / runner / `protect:` 対象の改変は機械検出して停止する。

無人 worker は作業ディレクトリ外（`/tmp` を含む）へ一時fileを書かない。tool permission が拒否された場合も最終 status を省略せず、caller の gate と同じ自己検証なら runner へ委譲し、実装に必須なら理由付き BLOCKED を返す。権限拒否を全権限flagや別toolで迂回しない。

実行例: `python3 scripts/agent_loop.py --profile .agent-shared/loops/security-review.md --cli codex`（preset: claude / codex / agy / opencode / kilo / cursor / grok。全 preset で native subagent を deny。`--dry-run` で構成検証のみ）。

exit code 契約、profile の書き方、流量制御（`iteration_interval` / `max_runtime`）、plan / impl pair 運用の詳細は `harness-loop` skill（`.agents/skills/harness-loop/`、`references/agent-loop-contract.md` を含む）が正本。安全策は `SECURITY.md` の「Loop 実行の安全策」。

## マルチエージェント運用（役割分担 + CLI 横断）

このハーネスの「マルチエージェント」は、**7 CLI + 任意モデルが計画 / 実装 / レビューのどの役割でも入れ替え可能**なこと。契約（pair、deviation / approval、review marker）は CLI 非依存の行 marker + runner / gate の機械検証で表現し、特定 CLI の機能に依存しない。

- **役割の標準形**: 計画 = 高性能モデル（`execplan` / `codebase-improvement-audit` skill で pair を作る）→ 実装 = 安価モデル（`implement-from-plan` profile の pair loop）→ レビュー = 実装と**別の CLI / モデル**（`review-against-plan` profile）。
- **pipeline は shell で繋ぐ**（orchestrator は作らない）。exit code で分岐する: 0=成功 / 2=承認待ち・BLOCKED / それ以外=異常停止（`.loop/` のログと WORKLOG を確認）。
- **レビューの契約**: 成果物は第3のファイル `docs/<plan_id>_review-001.md`（再レビューは review-002 と別ファイル。FAIL を上書きしない）。判定は `review: PASS`（行全体一致）/ `review: FAIL | 理由` をちょうど1行。レビュー中は plan / impl / 変更対象コードを `protect:` で保護し、review には対象 commit を記録する。
- **並列実行**: 同一 workspace での並列 loop は非対応。並列にする場合は plan を独立した pair に分割し、`git worktree` で workspace ごと分離する。統合担当は1名に固定し、各エージェントによる main への merge は禁止。

実機検証の水準と CLI ごとの parity は `docs/HARNESS_VERIFICATION.md` を参照。

## CLI 別の運用ルール

実測に基づく非自明な制約だけを書く（観測の経緯は `docs/HARNESS_VERIFICATION.md`）。

- **Antigravity (agy)**: terminal-first の実体は `agy`。`--add-dir` は**必ず絶対 path**で渡す（相対 path では workspace 外の scratch に偽の作業ファイルを作る）。headless（`-p`）は権限を付与できないコマンド待ちで無出力ハングし得るため `--print-timeout` を使う。user-level 設定 `~/.gemini/antigravity-cli/settings.json` はテンプレートから書き換えない。実行中の観察は `~/.gemini/antigravity-cli/brain/<会話ID>/.system_generated/logs/transcript.jsonl`。
- **Codex**: `AGENTS.md` は global → project root → 作業ディレクトリの順で近いものが後勝ち。project docs は約 32KiB 上限があるため always-on を短く保つ。
- **Cursor**: 実体は `cursor-agent`。`.cursor/rules/` は使わず `AGENTS.md` + `.agents/skills/` に寄せる。headless は `-p`、未 trust のディレクトリでは `--trust` が必要。hook block 時は「Rejected: Command execution was blocked by a hook.」が返る。
- **opencode / Kilo**: headless `run` は `--dir <絶対path>` を明示する（project 判定が cwd とずれると permission が auto-reject され全ツールが失敗する）。Kilo の headless は **project の kilo.jsonc が権限の正本**で、無い場所では動かない。`--auto`（全権限自動承認）は使わない。model は `provider/model` の完全形で指定する（同名 model が複数 provider にあり、課金枠が別。`opencode models` の列挙を `head` で切り詰めたまま選ばない）。
- **Grok**: 実体は `grok`。0.2.112+ の agentic headless は `python3 scripts/grok_stdio_driver.py --cwd <絶対path>` を `agent_loop.py --agent-cmd` に渡し、`grok agent stdio` 経由で実行する（bash は既定 deny）。旧 `-p` は single-turn のため使わない。driver の tool 分類は名前と `kind` の**完全一致**で行う（部分文字列で判定すると 0.2.118 の `kind` 表記差でシェル実行まで禁止扱いになり、2026-08-04 に委任が2回止まった）。拒否の一次情報は stderr の `permission tool=... mapped=... kind=... category=... input_keys=... verdict=... reason=...` 行で、値は出さないので常時有効にしてよい。`--sandbox` は WSL の `/mnt/` 配下で filesystem 境界にならないため、未信頼 code の実行には container / VM を使う。`--debug-file` は認証情報を含み得るので共有・commit しない。**`[ui] permission_mode = "always-approve"`（および `yolo = true`）を設定した grok は ACP client へ permission を一切問い合わせない**ため、driver 内の gate も `--allow-bash` も効かない（2026-08-05 実機確認）。ただし **hook は自動承認でも発火する**ので、shell の可否は hook 層（`AGENT_DELEGATED_SHELL`）が担う。driver は preflight で自動承認設定を検出したら、workspace が `~/.grok/trusted_folders.toml` で trusted かつ project hook が共有 policy を実行する構成であることを確認し、片方でも欠けていれば exit 1 で止める（hook が動かない＝歯止めが無いため）。Yolo を使いながら委任するときは trust と project hook を消さない。
- 全 CLI 共通: model は project-level で pin せず、runner も自動選択しない。ユーザーが `--model` を指定した時だけ CLI へ渡す。

## Windows / WSL wrapper

- WSL → Windows PowerShell: `scripts/win_pwsh.sh`(inline と `--file <path.ps1>` の両対応)。
- WSL → Windows 側 Codex: `scripts/win_codex.sh`（`cmd.exe /c codex.cmd` の直書きは PATH 解決が不安定なので禁止。実体指定は `WIN_CODEX_CMD=...`）。
- Windows → WSL: `scripts/wsl_exec.ps1` / `scripts/wsl_exec.cmd`（`-Workdir` は両 path 対応、複数コマンドは `-ShellCommand`）。
- 管理者権限が要る操作は wrapper に混ぜず、ユーザーが直前に OK した1コマンドだけ `AGENT_ADMIN_APPROVED=1` を付けて実行する。

## 検証

- 構造 smoke: `bash scripts/smoke_template.sh`（必須ファイル、stale 参照、skill metadata、mirror 一致、hooks 構文、policy 動作）。Windows wrapper 部分は `TEMPLATE_SMOKE_WINDOWS=0` で skip。公開 ZIP との release 照合は通常実行ではskipし、release作業時だけ`TEMPLATE_SMOKE_RELEASE=1 TEMPLATE_RELEASE_DATE=YYYYMMDD`で有効化する。
- release ZIP生成: `python3 scripts/build_release_asset.py build --release-date YYYYMMDD --output New/<versioned-name>.zip`。日付はrelease時の年月日を明示し、展開時の最上位folderは`multiagent-best-template-YYYYMMDD`になる。local clockからは補完しない。verifyはZIP comment、指定日、全memberのrootを照合する。
- 安全策 smoke: `bash scripts/security_smoke.sh`（7 CLI共有contextのread-only検査とpermission / hook canaryを含む）。
- skill追加・変更後: `python3 scripts/sync_shared_skills.py`で生成し、`python3 scripts/sync_shared_skills.py --check`またはsmokeで一致を確認する。
- loop profile の構成検証: `python3 scripts/agent_loop.py --profile <p> --dry-run`。
- OS 通知: `python3 scripts/notify.py "<message>"`（backend 詳細は `scripts/notify.py` と `SECURITY.md`。`--dry-run` で backend 確認のみ）。

## テンプレート導入手順

1. root 一式を対象 repo のワークスペース表層へコピーする（`Old/` と `.git/` は除く）。
2. `docs/PROJECT_BRIEF.md` をその repo の build / test / run / 制約で埋める。
3. `docs/REQS.md` / `docs/WORKLOG.md` を空 scaffold に戻し、最初のタスクで埋める。
4. `README.md` はプロジェクト本体の README に置き換えてよい（ハーネスの説明はこのファイルが正本）。
5. `bash scripts/smoke_template.sh` で構造が壊れていないことを確認する。
