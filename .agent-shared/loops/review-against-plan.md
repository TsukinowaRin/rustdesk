---
name: review-against-plan
max_iterations: 3
stall_limit: 2
iteration_timeout: 1800
gate_timeout: 600
gates_every_iteration: false
# 使い方: コピーして <topic>-review.md を作り、protect と gates の path を実タスクの
# ファイルに置き換える。レビュー loop では pair キー（plan_file / implementation_log）を
# 使わない: pair prompt は「impl は常に追記可」を実装者へ約束するもので、レビュー中は
# 逆に plan / impl / 変更対象コードすべてを protect してレビュアーの改変を機械的に防ぐ。
protect:
  - docs/EXECPLAN_<topic>.md
  - docs/EXECPLAN_<topic>_impl.md
  # - <plan の「予定変更ファイル」をすべて列挙する>
gates:
  # 成功条件は「review marker がちょうど1行、かつ PASS 行が完全一致」。FAIL・重複・
  # `review: PASSFAIL` のような prefix 偽装は gate が落ちる（Sol round 6 監査で強化）。
  # 2本目は review が正しい plan に紐付くことの機械照合。<plan_id> は実値に置き換える。
  - test "$(grep -Ec '^review: (PASS|FAIL)([ \t|]|$)' docs/<plan_id>_review-001.md)" -eq 1 && grep -Eq '^review: PASS[ \t]*$' docs/<plan_id>_review-001.md
  - grep -q '^plan_id: <plan_id>$' docs/<plan_id>_review-001.md
---
# <レビュー対象 plan の受け入れ条件を1文で書く>

実装完了後に**別のエージェント / CLI**が「計画と実装の突き合わせ」を行う loop の scaffold。
実装者と同じモデル・CLI を使わないこと（自己レビューは checkpoint の代替にならない）。

## 進め方

1. plan の `execplan:original` 領域と implementation_log、`git diff <基準commit>` を読む。
2. 次を突き合わせる:
   - 受け入れ条件 ↔ 実装差分 ↔ 検証記録（証拠のない「済み」を信用しない）
   - 承認済み deviation ↔ 実際の変更（承認なしの範囲外変更、却下済みの実装を探す）
   - 「変更禁止範囲」への接触が無いこと
3. レビュー結果は新しいファイル `docs/<plan_id>_review-001.md` に書く（再レビューは
   review-002 のように**別ファイル**。過去の FAIL を上書きしない）。必ず含める:
   - `plan_id:`（plan と同じ値。gate が機械照合する）
   - 対象 commit（`git rev-parse HEAD`）または diff の範囲
     （これは監査証跡としての記録であり、gate は照合しない。違う差分をレビューする
     事故の最終防止は人間の確認に残る）
   - 指摘一覧（severity 順、根拠 file:line 付き）
   - 判定行をちょうど1行: `review: PASS`（行末まで一致）または `review: FAIL | <一行理由>`
4. PASS なら `LOOP_STATUS: DONE`。FAIL なら `LOOP_STATUS: BLOCKED: review failed` を
   宣言する（自動差し戻し・自動修正はしない。差し戻し判断は人間または上位モデル）。

## してはいけないこと

- コード・plan・implementation_log の変更（protect が exit 6 で停止する）。
- FAIL の握りつぶし（判定行なしの DONE は gate が落ちる）。

## 完了条件

- review ファイルに判定行がちょうど1行あり、PASS で gates が pass する。
