---
name: implement-grok-stdio
max_iterations: 8
stall_limit: 2
iteration_timeout: 1800
gate_timeout: 600
gates_every_iteration: false
max_runtime: 7200
plan_file: docs/EXECPLAN_2026-07-29_grok-stdio-driver.md
implementation_log: docs/EXECPLAN_2026-07-29_grok-stdio-driver_impl.md
gates:
  - python3 scripts/grok_stdio_driver.py --selftest
  - bash scripts/security_smoke.sh
  - git diff --check
protect:
  - scripts/security_smoke.sh
  - scripts/smoke_template.sh
  - scripts/sync_permissions.py
  - .agent-shared/hooks_core/common.py
  - .agent-shared/hooks_core/runtime.py
  - .agent-shared/permissions.json
---
# scripts/grok_stdio_driver.py の selftest が pass し、plan の受け入れ条件をすべて満たす

`docs/EXECPLAN_2026-07-29_grok-stdio-driver.md` の上位計画を実装する loop。

## 進め方

1. plan の `execplan:original` 領域（目的・作業計画・予定変更範囲・受け入れ条件）を読む。
2. 「予定変更ファイル」の範囲で 1 chunk 実装し、最小の検証を添える。
3. 実装メモ・プロトコル発見の記録・検証結果は implementation_log へ追記する（plan は編集しない）。
4. 予定変更範囲の外に出る必要が生じたら、実装せず implementation_log へ `deviation:` 行を追記して BLOCKED を宣言する。

## してはいけないこと

- plan_file / protect 対象の編集（runner が exit 6 で停止する）。
- 承認されていない deviation の実装（runner が exit 2 で停止する）。
- gates・検証スクリプトの弱体化。外部 download。
