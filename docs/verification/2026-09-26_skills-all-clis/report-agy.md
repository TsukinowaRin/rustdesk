# 報告: スキルが見えて使えるか（担い手 agy）

## 何をした
- CLIのシステムプロンプトで見えるスキルを列挙し、`ls .agents/skills/` と比較した
- `consulting-pptx-skill` で `new_deck.py --parts b01,b02,b10` を実行し3枚のデッキ `evals/agy/deck.html` を生成、プレースホルダーを実物に差し替え、`check_deck.py` で検証した
- `test-audit` skill の Authoring gate 4問を `harness/evals/greet/` の試験（`test_hello.py`）に当てはめた

## 検証の結果
- **1. スキル一覧**: CLI の仕組み（Available skills）で 28 本が見えた。`.agents/skills/` には 27 本ある
  - CLI にあるが `.agents/skills/` にない 3 本: `agmsg`（グローバル）、`agy-customizations`（ビルトイン）、`antigravity-guide`（ビルトイン）。いずれも Antigravity CLI 自体のスキル
  - `.agents/skills/` にあるが CLI に見えない 2 本: `handoff`、`i-have-adhd`。両方とも `SKILL.md` に `disable-model-invocation: true` があり、モデルの自動呼び出し対象から除外されている（ファイルは読める）
  - `.agents/skills/` 内の 27 本のうち 25 本が CLI に見え、残り 2 本は意図的な除外
- **2. check_deck.py の出力**: `0 FAIL / 3 WARN`（p1: タイトル空=表紙、p3: タイトル空=裏表紙、`.sub` ×2=表紙サブタイトル）。すべて表紙・裏表紙の許容範囲
- **3. test-audit Authoring gate（greet の test_hello.py に当てはめ）**:
  1. `greet("Ada")` が `"Hello, Ada!"` を返す公開関数の入出力契約を守る
  2. 関数の返り値が変わったら（例: フォーマット変更）テストが落ちる
  3. この関数にはほかのテストが無く、check.py は検収用であり単体テストではない
  4. 本番にテスト専用の継ぎ目は不要。greet は通常の公開関数であり、テストのための特別なエクスポートや注入はない

## 残り
- なし

## 人の判断が要ること
- なし

## 変更したファイル
- `evals/agy/deck.html`（新規作成・プレースホルダー差し替え済み）
