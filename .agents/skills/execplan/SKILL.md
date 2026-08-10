---
name: execplan
description: 複雑、高リスク、複数モジュール横断、または複数チェックポイントにまたがる作業で使う。要求を docs/REQS.md に正規化し、docs/EXECPLAN_*.md を作成または更新してから、その計画に沿って進める。小さな単一ファイル修正や単純なQ&Aには使わない。
---

1. `docs/REQS.md` と関連する `docs/EXECPLAN_*.md` を読む。
2. `docs/REQS.md` が無い、または古い場合は、要求、制約、受け入れ条件、仮定が明確になるよう更新する。
3. active な ExecPlan が無ければ、`docs/EXECPLAN_TEMPLATE.md` を元に `docs/EXECPLAN_<date>_<topic>.md` を作る。
4. ExecPlan は自己完結に保ち、目的、設計判断、具体手順、検証、復旧、停止点ログを含める。
5. 高リスクな曖昧さで止まらない限り、逐次確認より計画に沿った前進を優先する。
6. 発見により方針が変わったら、コード変更の前後で `docs/REQS.md` と ExecPlan を更新する。
7. 最後に、実施した検証と残リスクを記録する。

## 上位計画の保持と逸脱

上位モデルが計画し、別の実行エージェントが実装する運用のための規約
（設計の経緯は `docs/EXECPLAN_2026-07-13_iterative-plan-handoff.md`）。

- template の `execplan:original` marker で囲まれた上位計画は **append-only 規約**:
  削除・上書きせず、訂正は承認済み amendment として判断ログへ追記する。
  進捗・停止点・発見事項は実行エージェント管轄で、通常どおり更新してよい。
- 逸脱は二段階で判定する。「許容する付随変更」の範囲内は発見事項へ記録して続行。
  **承認必須**は、予定変更範囲外の変更 / 削除・rename / 新規外部依存（lockfile・
  submodule・外部 download 含む）/ 公開契約・schema・権限の変更。軽微か重要か
  判断できない場合も実装せず「逸脱提案」に留める。
- 提案は `deviation: DEV-001 | 一行要約 | 対象: path | 日付: YYYY-MM-DD` の1行。
  ID は文書内で一意、既存行の変更・削除・ID 再利用は禁止（変わる提案は新 ID）。
- 承認は ID 単位の `approval:` 行の追記で行う（部分承認は無い）。単一文書運用では
  逸脱提案節の下へ、自動 loop の pair 運用では protect された plan ファイル側が正本。
- 作業ログ（impl 側）への追記は、この規約のどの条件下でも常に許可されている。
- 単一文書 + git diff レビューは監査手段であって強制ではない。機械的な強制が必要な
  作業は `agent_loop.py` の plan / impl pair 運用を使う（harness-loop skill 参照）。
- 行頭の `plan_id:` / `deviation:` / `approval:` は runner が走査する予約 marker。
  本文中で例示するときは行頭に置かず、インデントまたは引用で書く（fenced code 内でも
  行頭にあると実 marker として検出される）。

### pair 運用の最小 scaffold

plan 側は `docs/EXECPLAN_TEMPLATE.md` から作る。impl 側（作業ログ）の最小形は次の2行
+ 追記本文で、`plan_id:` は plan と同値をちょうど1行:

    plan_id: PLAN-<plan と同じ ID>
    # 作業ログ（実行エージェントが追記する）

loop profile には次の2キーを両方書く（`.agent-shared/loops/implement-from-plan.md` 参照）:

    plan_file: docs/EXECPLAN_<topic>.md
    implementation_log: docs/EXECPLAN_<topic>_impl.md
