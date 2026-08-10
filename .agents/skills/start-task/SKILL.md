---
name: start-task
description: repo変更、複数段階の構造化調査、またはhandoff再開の入口で使う。task sizeを分類し、必要最小限の文脈だけ読んでdocs/REQS.mdを更新する。短いQ&A、説明、状態確認、限定的なread-only探索には使わない。
---

# Start Task

## 使う場面

- repoのcode、docs、configを変更する。
- 複数段階の調査・監査で、要求、判断、停止点をdocsへ残す必要がある。
- handoffまたは中断した作業を再開する。

## 使わない場面

- 短いQ&A、概念説明、状態確認。
- 1〜2ファイルを見れば答えられる限定的なread-only探索。
- REQSやWORKLOGへstateを残す価値がない単発の確認。

## 手順

1. task size を分類する。
   - small: 単一ファイル変更、限定的なdocs修正
   - medium: 複数ファイルだが局所的、軽い検証あり
   - deep: 複数モジュール横断、履歴依存、handoff 再開、高リスク
2. 現在の user request と関係する project artifact を一次情報として扱い、`docs/REQS.md` を先に更新する。stale な REQS を source of truth として扱わない。
3. small: `AGENTS.md`、`docs/PROJECT_BRIEF.md`、更新済み `docs/REQS.md` だけ読んで始める。`docs/PROJECT_BRIEF.md` が scaffold / stale なら repo 実態に合わせて最小限埋める。
4. medium: 上記に加えて、task に直結する docs / コードを 1-2 個だけ `rg` / 部分読みで狭く読む。
5. deep / handoff 再開: `docs/WORKLOG.md` と active な `docs/EXECPLAN_*.md` を読む。計画が無ければ `execplan` skill で作る。自動 loop の plan / impl pair で中断した作業は、`plan_id` が一致する両ファイルを pair として読み、逸脱提案と `approval:` の状態を確認してから再開する。
6. 選んだ path、意図的にまだ読んでいない文書、最初の具体的な一手を短く明示する。
7. 文脈不足で判断を誤りそうになったら、その時点で deep へ昇格し、理由を明記する。

## 完了条件

- `docs/REQS.md` が現在の依頼を反映し、読む文脈と最初の一手が明示されている。
