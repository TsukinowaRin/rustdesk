---
name: implement-from-plan
max_iterations: 8
stall_limit: 2
iteration_timeout: 1800
gate_timeout: 600
gates_every_iteration: false
# 使い方: このファイルをコピーして <topic>.md を作り、下2行の # を外して実際の
# pair ファイル（execplan skill「上位計画の保持と逸脱」の規約で作った plan / impl）を指す。
# plan_file は runner が自動で protect し、未承認 deviation は exit 2 で停止する。
# plan_file: docs/EXECPLAN_<topic>.md
# implementation_log: docs/EXECPLAN_<topic>_impl.md
gates:
  - git diff --check
---
# <plan の受け入れ条件を1文で書く>

上位モデルが作成した計画（plan_file）を実装する loop の scaffold。**直接実行用ではなく、
コピーして path / gates / goal を埋めてから使う。**

## 進め方

1. plan の `execplan:original` 領域（目的・作業計画・予定変更範囲・受け入れ条件）を読む。
2. 「予定変更ファイル」の範囲で 1 chunk 実装し、最小の検証を添える。
3. 実装メモ・検証結果・発見は implementation_log へ追記する（plan は編集しない）。
4. 予定変更範囲の外に出る必要が生じたら、実装せず implementation_log へ
   `deviation:` 行を追記して BLOCKED を宣言する（形式は prompt の pair 契約に従う）。

## してはいけないこと

- plan_file の編集（runner が exit 6 で停止する）。
- 承認されていない deviation の実装（runner が exit 2 で停止する）。
- gates・検証スクリプトの弱体化。

## 完了条件

- plan の受け入れ条件をすべて満たし、gates が pass する。
