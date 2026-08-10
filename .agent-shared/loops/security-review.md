---
name: security-review
max_iterations: 8
stall_limit: 2
gates_every_iteration: true
gates:
  - bash scripts/security_smoke.sh
  - git diff --check
protect:
  - scripts/security_smoke.sh
---
# セキュリティ反復レビュー

`SECURITY.md` と `.agents/skills/security-harness/` の基準で repo を監査し、
見つかった問題を重大度順に修正して、gates が安定して pass する状態まで持っていく。

## 進め方

1. 初回 iteration では監査だけを行い、findings を重大度（high / medium / low）付きで
   `docs/REQS.md` の受け入れ条件として列挙する。修正はまだしない。
2. 以降の iteration では high から順に 1〜2 件ずつ修正し、修正ごとに最小の検証を回す。
3. 修正した finding は受け入れ条件のチェックを埋め、`docs/WORKLOG.md` に何をどう直したかを残す。

## 監査観点

- hard-coded secrets: ソース・設定・履歴に残る token、API key、パスワード、接続文字列。
- secret ファイルの扱い: `.env` 系・鍵・証明書が gitignore されているか。example ファイルに実値が入っていないか。
- 外部入力: ユーザー入力・外部 API 応答・ファイル内容を、検証やエスケープなしに
  shell / SQL / eval / パス結合 / テンプレートへ渡していないか。
- 危険なコマンドと権限: スクリプト内の破壊的コマンド、不要な sudo、過剰な権限要求。
- 依存関係: 出所不明の依存、`curl | sh` 型のインストール、pin されていない危険な依存。
- AI エージェント経路: hooks / permission 設定の穴、prompt injection を運ぶ外部テキストの無検証利用。

## してはいけないこと

- secret の実値を出力・ログ・docs に書くこと（場所と種類だけを記録する）。
- 挙動を変える「ついで修正」。セキュリティと無関係なリファクタリングはしない。
- 確認できない脆弱性を直したことにすること。再現・確認できないものは BLOCKED で人間に返す。

## 完了条件

- `docs/REQS.md` に列挙した findings が全て「修正済み」または「リスク受容として理由記載済み」になっている。
- gates が全て pass している。
