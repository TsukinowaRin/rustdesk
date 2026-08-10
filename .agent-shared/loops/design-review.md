---
name: design-review
max_iterations: 8
stall_limit: 2
gates:
  - git diff --check
---
# デザイン反復レビュー

`DESIGN.md`（source of truth）と `.agents/skills/design-taste-frontend/` の基準で
UI コードを点検し、一通り良くなるまで反復改善する。

注意: gates の `git diff --check` は最低限の placeholder。対象プロジェクトに
lint / build / visual test があるなら、この profile をコピーして gates に追加してから回すこと
（例: `npm run lint`、`npm run build`）。gates が参照する設定・テストファイル
（例: `.eslintrc`、visual test の snapshot）は frontmatter の `protect:` にも列挙し、
「lint 設定を緩めて pass させる」型の改変を runner に検出させる。

## 進め方

1. 初回 iteration では点検だけを行い、下の観点ごとの違反を画面 / component 単位で
   `docs/REQS.md` の受け入れ条件として列挙する。修正はまだしない。
2. 以降の iteration では影響の大きい画面から 1〜2 件ずつ直し、`docs/WORKLOG.md` に
   何をどの基準に合わせたかを残す。

## 点検観点（DESIGN.md の章に対応）

- tokens: 色・spacing・radius・typography が DESIGN.md の値を使っているか。
  ハードコードされた任意の色や px 値が散らばっていないか。
- 和文組版: 本文 line-height 1.7 前後、letter-spacing、禁則。見出しの過剰な詰め。
- 状態設計: loading / empty / error / success の4状態が component にあるか。
  disabled と placeholder が本文と同じ濃さになっていないか。
- 階層と余白: primary action が1画面に1つか。card の乱造や意味のない装飾
  （紫グラデーション、過剰 shadow、glassmorphism）がないか。
- responsive: mobile で hover 依存 UI・横スクロールが出ないか。table の mobile 変換。
- accessibility: contrast AA、focus visible、icon-only button の accessible name、
  色だけに頼らないエラー表示。

## してはいけないこと

- DESIGN.md と無関係な機能変更・リファクタリング。見た目の修正に限定する。
- 既存プロダクトに design system が既にある場合の全面置換。差分を説明して最小変更にする
  （DESIGN.md「When Requirements Conflict」参照）。
- スクリーンショット等で確認できない「直したつもり」。確認手段が無い項目は BLOCKED で返す。

## 完了条件

- `docs/REQS.md` に列挙した違反が全て「修正済み」または「対象外として理由記載済み」になっている。
- gates が全て pass している。
