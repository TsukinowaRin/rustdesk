# <短いタイトル>

plan_id: PLAN-<日付や連番>
基準commit: <git rev-parse --short HEAD の値>
plan_revision: 1

<!-- execplan:original:start -->
<!-- ここから execplan:original:end までが上位計画。実行エージェントは削除・上書きせず、
     訂正が必要なときは承認済み amendment として下の判断ログへ追記する（append-only 規約）。
     自動 loop（agent_loop.py の plan / impl pair）では、この領域を含む plan ファイル全体が
     protect され、run 中の変更は exit 6 で停止する。 -->

## 目的 / 全体像

## 背景と見取り図

## 作業計画

## 予定変更範囲

- 予定変更ファイル:
  - <path>
- 許容する付随変更:
  - <例: 隣接する test の追加・修正、docs の同期、自動生成物（lockfile を除く）>
- 変更禁止範囲:
  - <path / 領域>

## 検証と受け入れ条件

<!-- execplan:original:end -->

## 進捗

- [ ] (YYYY-MM-DD HH:MM TZ)

## 現在の停止点

- 現在位置:
- 未完了:
- 次の一手:
- 次に読む文書:
- 次に実行するコマンド:

## 発見事項

- 観測:
  根拠:

## 逸脱提案

<!-- execplan:deviations -->
<!-- 上位計画と異なる対応が必要になったら、実装せずに1行1件で追記して承認を待つ。
     形式: deviation: DEV-001 | <一行要約> | 対象: <path 等> | 日付: YYYY-MM-DD
     ID はこの文書内で一意。既存行の変更・削除・ID 再利用は禁止（内容が変わる提案は新 ID）。
     承認必須: 予定変更範囲外の変更 / 削除・rename / 新規外部依存（lockfile・submodule・
     外部 download 含む）/ 公開契約・schema・権限の変更。軽微か判断できない場合も提案に留める。
     承認は ID 単位（部分承認は無い）。単一文書運用ではこの節の下に、pair 運用では
     plan ファイルへ、承認者が次の1行を追記する:
     approval: DEV-001 APPROVED <承認者> YYYY-MM-DD <条件があれば一行> -->

## 判断ログ

- 判断:
  理由:
  日付/記録者:

## 成果と振り返り

- 成果:
- 不足:
- 学び:
- 目的との差分:

## 具体手順

## 冪等性と復旧

- 中断後の再開手順:

## 成果物とメモ
