---
name: harness-loop
description: Harness / loop engineering を使い、長いAIエージェント作業を状態、制約、品質ゲート、停止条件つきの反復に分解するときに使う。「続けて」なしで goal 達成まで自己ループさせる runner（scripts/agent_loop.py）の使い方を含む。複数エージェント、長時間実行、定期運用、失敗回復が必要な作業向け。exit code / 流量制御 / protect / plan-impl pair の機械契約は references/agent-loop-contract.md を読む。
---

# Harness Loop

## 使う場面

- medium / deep task が複数セッション、複数エージェント、または長時間実行にまたがる。
- 同じ作業を定期的に回したいが、毎回の手作業プロンプトに依存したくない。
- 「作った」ではなく、検証、レビュー、停止条件、handoff まで含めて閉じたい。

小さい単発修正では使わない。まず `start-task` と `AGENTS.md` の作業原則を優先する。

## Loop Contract

作業前に、以下を `docs/REQS.md` または `docs/EXECPLAN_*.md` に明示する。

1. State: 進行状態を置くファイル。例: `docs/WORKLOG.md`、対象 ExecPlan。
2. Constraints: 触ってよい範囲、禁止コマンド、secret、予算、時間上限。
3. Inputs: 最初に読む docs / code / issue / spec。
4. Actions: 1 loop で実行する最小手順。例: 調査 -> 小変更 -> 最小検証。
5. Gates: loop ごとに必ず通す test / lint / smoke / review。
6. Stop: 成功、失敗、確認待ち、予算切れの条件。
7. Handoff: 次のエージェントが読む文書と最初のコマンド。

## 推奨 Loop

1. 要求を 1 文の goal と受け入れ条件に圧縮する。
2. 作業を 15-30 分以内の chunk に切る。
3. chunk ごとに、変更前の前提、変更内容、実行した検証を state に残す。
4. 実装 agent と review / verification agent を分けられる場合は分ける。
5. 失敗が 2 回続いたら、同じ試行を繰り返さず、原因仮説と次の検証を state に書く。
6. 成功後は `checkpoint` を使い、diff、検証、残リスク、Go/No-Go をまとめる。

## 自己ループ runner（scripts/agent_loop.py）

「続けて」と毎回入力する代わりに、headless CLI を goal 達成まで自動で再起動する。
Loop Contract の実行形で、state は docs（WORKLOG / REQS）、gates と停止条件は profile に置く。

```bash
# profile 駆動で回す（CLI preset: claude / codex / agy / opencode / kilo / cursor / grok）
python3 scripts/agent_loop.py --profile .agent-shared/loops/security-review.md --cli codex

# ユーザーが model を明示する場合だけ、実行単位でその値を渡す
python3 scripts/agent_loop.py --profile <p> --cli codex --model <model-id>

# 起動コマンドを自由指定する場合（prompt は末尾 argv で渡される）
python3 scripts/agent_loop.py --profile <p> --agent-cmd "kilo run -m kilo/kilo-auto/free"

# CLI を起動せず構成だけ検証
python3 scripts/agent_loop.py --profile <p> --dry-run
```

- profile は `.agent-shared/loops/` に置く。新しい loop は `TEMPLATE.md` をコピーして作る。gates（機械実行できる完了判定）は必須で、空にできない。
- 停止・承認・改変検出の機械契約（exit code 表、`iteration_interval` / `max_runtime` の流量制御、`protect:`、plan / impl pair の deviation / approval 手順、CLI preset の注意）は `references/agent-loop-contract.md` が正本。loop を起動・監視・再開する前に必ず読む。
- 曖昧な流量指示（「スローで」「1時間くらいで」）は既定値を選ばず、具体的な秒数を確認してから起動する。
- 安全策: hooks / permission の deny は headless でも効いたまま。全 CLI preset で native subagent 起動を無効化し、必要な分担は mailbox へ分ける。runner は push / merge をしない。

## 下請け用 mailbox dispatch

native subagent へ仕事を任せる時は、通常の自己ループ内で待たない。`agent-mailbox` skill（`.agents/skills/agent-mailbox/`）の手順で、model 外の dispatcher に配送・起動を任せる。`agent_loop.py` は通常作業 chunk 用であり、iteration 内で subagent を起動して待つ用途には使わない。

## 役割分担（マルチエージェント / マルチ CLI）

- 標準形: 計画（高性能モデル、`execplan` で pair 作成）→ 実装（安価モデル、`.agent-shared/loops/implement-from-plan.md` をコピーして pair loop）→ レビュー（実装と**別の CLI / モデル**、`.agent-shared/loops/review-against-plan.md` をコピー）。
- 指揮官は前線に出ない: 実装を別モデルに任せる構成では、指揮官役（計画・承認・レビュー担当）は計画作成、deviation の承認判断、checkpoint レビューだけに徹する。指揮官が自分でも実装や探索を始めると高性能モデルの token を二重に消費し、分担による節約が消える。指揮官の出番は loop 停止中（exit 2 の承認待ちなど）に限る。
- pipeline は shell の `&&` / `case` で繋ぐ（exit code 契約があるため orchestrator は不要）。運用形は `docs/HARNESS.md`「マルチエージェント運用」。
- レビュー成果物は `docs/<plan_id>_review-NNN.md`（試行ごとに別ファイル、FAIL を上書きしない）。判定行 `review: PASS|FAIL | 理由` はちょうど1行。FAIL は `LOOP_STATUS: BLOCKED` で人間へ返し、自動差し戻しはしない。レビュー loop では plan / impl / 変更対象コードを `protect:` に列挙する。
- 並列は plan を独立 pair に分割し `git worktree` で分離する（同一 workspace の並列 loop は非対応）。統合担当を1名に固定し、merge 順・競合解決・全体 gates を担わせる。

## Quality Gates

- Deterministic gate を優先する。例: unit test、lint、type-check、smoke、schema validation。
- prompt だけで守れない制約は hook、permission、script、CI、MCP server など外側で止める。
- subagent review は「仕様適合」と「コード品質」を分ける。
- 自動 loop では auto-merge を既定にしない。release / push は明示条件を満たした時だけ行う。

## Anti-patterns

- 状態を chat 履歴だけに置く。
- 成功条件を「良い感じ」など検証不能な言葉にする。
- 毎回 docs 全読を強制して token を浪費する。
- 失敗時に同じ command / prompt を根拠なく再実行する。
- 長い process を always-on instructions に貼り付ける。
