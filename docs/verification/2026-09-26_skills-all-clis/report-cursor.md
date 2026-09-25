# 報告: スキルが見えて使えるか（担い手 cursor）

## 何をした
- Cursor 起動時の `available_skills` で見えた skill 名を列挙（ワークスペース 25＋ユーザ系多数）
- `ls .agents/skills` は 27 本。差は `handoff` / `i-have-adhd`（両方 `disable-model-invocation: true` のためモデル提示から除外）
- `consulting-pptx-skill` で `evals/cursor/deck.html` を生成・文言差し替え・`check_deck.py` 実行
- `test-audit` の Authoring gate 4 問を `harness/evals/greet/check.py` に当てて回答

## 検証の結果
- CLI 提示（ワークスペース由来）: 25 / `.agents/skills`: 27 / 差: 2（上記。ユーザ・同期 skill は別枠で約 24 本も提示）
- `python3 .../new_deck.py --parts b01,b02,b10 ... -o evals/cursor/deck.html` → 3 slides
- `python3 .../check_deck.py evals/cursor/deck.html` → **0 FAIL / 3 WARN**（表紙・裏表紙タイトル空＋`.sub`）
- Authoring gate（greet/`check.py`）:
  1. 守る契約: `greet(name)=="Hello, {name}!"` と `test_hello.py` が通ること
  2. 壊れる回帰: 戻り値形式変更・`hello.py`/`test_hello.py` 欠落・試験が非ゼロ終了
  3. 既存との差: この eval の唯一の合否境界（他に所有者なし）
  4. 試験専用 seam: 不要（本番ファイルを `runpy`/`subprocess` で直接実行）

## 残り
- なし（独立の確認は別担い手）

## 人の判断が要ること
- なし

## 変更したファイル
- `evals/cursor/deck.html`
- `REPORT.md`
