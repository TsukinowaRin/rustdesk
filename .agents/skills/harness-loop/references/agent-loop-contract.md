# agent_loop.py 実行契約（詳細リファレンス）

`scripts/agent_loop.py` の機械契約の正本。SKILL.md は運用の入口だけを持ち、exit code・流量制御・protect・plan / impl pair の詳細はこのファイルを読む。

## Iteration の契約

- 各 iteration は fresh context の headless 起動。prompt には runner が解決した絶対 workdir が明示される。
- エージェントは `docs/WORKLOG.md` を更新してから `LOOP_STATUS: CONTINUE / DONE / BLOCKED` を宣言する。DONE は gates 全 pass の時だけ受理される。
- 必須ファイル不在・必須コマンドの権限拒否時は、捏造・迂回せず BLOCKED を宣言する。
- 実行ログは `.loop/`（gitignore 済み）。state は docs に書く（docs = working memory）。

## Exit code 契約

| exit | 意味 |
|---|---|
| 0 | DONE + gates 全 pass |
| 2 | BLOCKED または未承認 deviation（人間の承認・判断待ち） |
| 3 | workspace 無変化の stall |
| 4 | CLI 異常（iteration timeout / 非ゼロ終了 + 契約行なし / 契約行の連続欠落） |
| 5 | max_iterations 到達 |
| 6 | 保護対象・deviation 記録の改変検出 |
| 7 | max_runtime の門限到達（未完了でも正常停止。再実行で docs から続き） |

- CLI 異常（4）は同条件の再試行をしない。時間の浪費になるだけなので初回で人間に返す。
- 複数条件が同時成立した場合の検査優先順位は 改変（6）→ 承認待ち（2）→ CLI 異常（4）。改変と承認状態は CLI の生死より優先して人間に見せる。

## 流量制御（rate limit を秒で使い切る事故への蓋）

- profile の `iteration_interval:`（スローモード）: iteration 間の最低秒数。例: 300 なら 1 時間に最大 12 iteration。
- profile の `max_runtime:`（門限モード）: run 全体の実時間上限。超過は exit 7 の正常停止。門限は「次の iteration を始めない」ゲートで、実行中の iteration は中断しない（途中 kill は workspace を壊し得る。1 iteration の上限は `iteration_timeout` が担う）。
- 既定はどちらも 0 = 無効。`--interval` / `--max-runtime` で実行単位に上書きでき、`--max-runtime 0` で profile の門限を外せる。
- rate limit 検知後の自動待機・再開は採用しない（使い切った limit は待っても回復しない）。トークン数ベースの budget も CLI 横断で出力形式が揃わないため採用せず、時間ベースで代替する。
- 曖昧な流量指示（「スローで」「1時間くらいで」）は既定値を選ばず、具体的な秒数を確認してから起動する。推測を外したときの実害（limit 枯渇・早すぎる打ち切り）が大きく、「低リスクな仮定なら前進」の例外とする（ユーザー指示 2026-07-17）。

## Gate 改変防止（protect）

- profile の `protect:` に gates が参照するスクリプト・テストを列挙する。profile と runner 本体は常に保護される。
- runner は開始時に保護対象を snapshot し、loop 中の改変を検出したら exit 6 で即停止する。特定モデルへの対策ではなく、自動 loop の完了判定を守る決定論的な共通ガード。

## 上位計画の保持（plan / impl pair）

- profile に `plan_file:` と `implementation_log:` を両方指定する（片方だけは不可）。上位モデルの計画を protect したまま実行モデルに実装させる。
- 実行モデルは計画の「予定変更ファイル」内だけ変更できる。範囲外は impl へ `deviation: DEV-00X | 要約 | 対象: path | 日付: YYYY-MM-DD` を追記して停止する。
- 承認は人間が loop 停止中に plan へ `approval: <ID> APPROVED|REJECTED <承認者> <日付>` を追記して再実行する。承認の正本は protect された plan 側のみ（impl に何を書いても承認にならない。run 中の承認偽造は機械的に不可能）。
- 未承認 deviation は宣言に関係なく exit 2、deviation 行の消失・変更・重複は exit 6。
- 既知の制約: 実行モデルが逸脱を最初から記録しない経路と、却下済み変更が実装されていないことは runner 単体では検出できない。checkpoint skill の「計画と最終 diff の突き合わせ」と人間の diff レビューを必須の監査点とする。
- 文書規約は `docs/EXECPLAN_TEMPLATE.md` と execplan skill、設計の経緯は `docs/EXECPLAN_2026-07-13_iterative-plan-handoff.md`。

## CLI preset の注意

- 全 preset で native subagent 起動を deny する。auto-approve は hooks / permission の deny が効いたままの水準（例: Claude `acceptEdits`、Codex `--full-auto`）だけを使う。runner は push / merge をしない。
- model 選択: runner は自動選択・自動変更しない。`--model` が無ければ各 CLI の設定に任せる。
- Grok preset: project root の `.grok/config.toml` を必須にし、web search / cross-session memory / subagents を無効にする。iteration の最終 text が空の場合、同一 session へ read-only toolset で status だけを 1 回問い合わせる。gate pass から DONE を推測せず、model の `LOOP_STATUS` と gates の両方を要求する。
- Grok 0.2.112+ は `-p` が single-turn 化して preset が使えないため、ドライバ経由で起動する: `--agent-cmd "python3 scripts/grok_stdio_driver.py --cwd <絶対path>"`（prompt は runner が末尾 argv で渡す）。ドライバの permission 応答は hooks_core を再利用した fail-closed で、bash は既定 deny（`--allow-bash` で opt-in、それでも hooks_core の deny が優先）。subagent / web / memory tool は常に deny。
- 既知の制約: gates / stall 検出は workspace 内しか見ないため、CLI が workspace 外へ書く行為は runner では防げない。この層の防御は各 CLI の sandbox / hooks / permissions の責務（実測記録は `docs/HARNESS_VERIFICATION.md`）。
