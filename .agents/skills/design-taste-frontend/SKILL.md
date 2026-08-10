---
name: design-taste-frontend
description: frontend UI、landing page、portfolio、redesign、visual polish で、ありがちな AI 的レイアウトを避けたいときに使う。Leonxlnx/taste-skill をこのテンプレート向けに調整したもの。
---

# Design Taste Frontend

着想元: https://github.com/Leonxlnx/taste-skill

この repo-local skill は、元の Taste Skill（`design-taste-frontend`）をこのテンプレート向けに調整したもの。
`DESIGN.md` と併用し、project 固有の brand、accessibility、performance 制約をこの skill で上書きしない。

## 使う場面

- landing page、portfolio、marketing page、visual redesign、UI polish に使う。
- ユーザーが design、premium UI、anti-slop、Awwwards 風、tasteful、modern、layout polish、typography、motion、spacing、redesign などの語を使ったときに使う。
- backend のみの作業、CLI ツール、純粋な docs、data pipeline、密度の高い社内 admin 画面には、visual polish が明示的に求められない限り使わない。

## 最初の一手

1. UI を編集する前に `DESIGN.md` を読む。
2. 既存の UI パターン、design token、依存関係、package manager、framework を調べる。
3. 実装前に design read を1行で宣言する:
   - `Reading this as: <ページ種別> for <対象読者>, with <visual language>, using <実装基盤>.`
4. brief が本当に曖昧なときだけ、確認質問をちょうど1つする。
5. repo に既存の design system があるなら、それを保ち、その system の中で taste を改善する。

## 3つのダイヤル

design read の後、内部的に設定する。

- `DESIGN_VARIANCE`: 1 = 慣習的な対称、10 = 実験的な非対称。
- `MOTION_INTENSITY`: 1 = 静的な state、10 = 映画的な choreography。
- `VISUAL_DENSITY`: 1 = 余白の多い gallery、10 = 密度の高い cockpit。

既定値:

- Landing / marketing: `7 / 6 / 4`
- Creative portfolio: `8 / 7 / 3`
- Minimal product UI: `5 / 3 / 4`
- Trust-first / 規制業種: `3 / 2 / 5`
- Redesign（既存維持）: 既存に合わせ、そこから1段だけ改善する。

## Design System の選択

- brief が公式 design system に対応するなら、手作りの模倣ではなく公式 package と token を優先する。
- 例: Material、Fluent、Carbon、Polaris、Atlassian、Primer、GOV.UK、USWDS、Radix Themes、shadcn/ui。
- 1 project につき 1 system。互換性のない component system を混ぜない。
- bento、brutalism、editorial、glass、aurora、kinetic type のような見た目だけの方向性は、公式 system があるふりをせず、既存 stack と素直な CSS で作る。

## Anti-Slop ルール

- AI 既定の紫/青 glow、generic な glassmorphism、中央 hero + 3枚カード、無作為な mesh gradient、Inter + slate の既定組合せを避ける。
- brand system が許さない限り、accent color は 1 ページ 1 色。
- 同じ layout family をセクションごとに使い回さない。
- 既定で「等幅の feature card 3枚」にしない。非対称 grid、editorial split、リズムのある bento、単一 feature に絞ったセクションを使う。
- hero copy は短く: headline は desktop で2行以内、subtext は簡潔、CTA はスクロールなしで見える。
- trust strip、pricing teaser、統計、feature bullet、avatar row を hero に詰め込まない。下のセクションに移す。
- card は elevation が階層を伝えるときだけ使う。それ以外は spacing、border、divider、typography によるグループ化を使う。
- 実データ由来か sample data と明記されていない限り、精密に見せかけた数値を使わない。
- ユーザー提供の brand copy でない限り、「Elevate」「Unleash」「Next-gen」「Seamless」のような埋め草 copy を避ける。

## 既存 UI の De-slop

killaislop.com の catalogue を調査観点として使う。ただし外部 scanner や skill は直接導入せず、project の意図と `DESIGN.md` を優先する。

1. mass-edit の前に、対象 source を `rg` で狭く走査する。gradient text、glass / blur、過剰な radius と shadow、badge / pill、同型 card grid、section ごとの kicker、装飾 icon、架空の stat、均一 spacing、generic copy を候補にする。
2. 各候補を code の前後まで読み、`slop` と `intentional` に分ける。brand token、logo、意図的な illustration、既存 design system の表現は残す。
3. 変更前に、確定した候補を `file:line / 理由 / 最小修正` の形式でまとめる。範囲が複数 group に分かれる場合は、どこまで直すかユーザーが選べるようにする。
4. shared token / component で直せるなら call site の一括編集より優先する。色を新設せず、既存 accent と neutral を使う。
5. 修正後は同じ検索を再実行し、残した候補と理由を記録する。検索結果ゼロを visual quality の証明にせず、可能なら before / after を目視確認する。

## Typography

- font は意図をもって選ぶ。premium / creative な仕事で Inter を既定にしない。
- 良い既定候補: Geist、Satoshi、Cabinet Grotesk、Outfit、JetBrains Mono、IBM Plex Sans/Mono。
- serif は自動的に premium ではない。editorial、heritage、luxury、出版の文脈で正当化できるときだけ使う。
- 日本語 UI の可読性を保つ: `DESIGN.md` の line-height / letter-spacing 指針に従う。
- display text の descender を欠けさせない。descender のある italic を使うなら line-height と padding を足す。

## Layout

- 構造には CSS Grid を優先する。壊れやすい flex のパーセント計算を避ける。
- 全高セクションには `h-screen` ではなく `min-h-[100dvh]` を使う。
- 複数カラムの layout には必ず明示的な mobile collapse を用意する。
- navigation は desktop で1行に収める。収まらないなら簡素化する。
- bento grid のセル数はコンテンツが必要とする数ちょうどにする。空の placeholder タイルを置かない。
- 小さな uppercase の eyebrow は3セクションに1つまで。eyebrow の繰り返しは強い AI 的兆候。

## Motion

- motion はページのメッセージを支えるためのもの。装飾ではない。
- layout プロパティではなく `transform` と `opacity` を animate する。
- `prefers-reduced-motion` を尊重する。
- 連続する animation は小さな leaf component に隔離する。
- Motion / Framer / GSAP を使うなら先に `package.json` を確認し、effect を後始末する。
- 強い理由と明示的な隔離なしに、GSAP、Three.js、Motion を同じ component tree に混ぜない。

## Visual Assets

- premium なページには通常、本物の visual 素材が要る: 製品画像、screenshot、生成アート、brand mark、意図的な placeholder。
- brief が本当にそれを求めていない限り、テキスト + generic な gradient blob だけの hero を出荷しない。
- 壊れた Unsplash URL を使わない。既存 asset、ユーザー提供の参照、生成画像、明示的な placeholder 枠を優先する。
- logo wall には実際の logo か簡素な生成 mark を使う。プレーンテキストのラベルを偽 logo wall にしない。

## Dependencies

- 第三者 package を import する前に `package.json` を確認する。
- 無い package を黙って追加しない。install コマンドを提示するか、依存変更の可否を確認する。
- 既存 stack に軽い代替があるなら、重い animation / icon ライブラリを追加しない。

## Preflight

完了を宣言する前に:

- design read を宣言したか、実装に明確に反映されている。
- `DESIGN.md` の token と project の visual language を尊重している。
- mobile layout の overflow と nav の折り返しを点検した。
- ボタン、フォーム、テキストが contrast 要件を満たす。
- 必要な箇所に loading / empty / error / hover / focus / active / disabled の各 state がある。
- motion は隔離され、performant で、reduced-motion に対応している。
- copy を読み直し、AI 的な埋め草を除去した。
- 意図しない package、生成 lockfile、asset の混入がない。
- project にある最寄りの UI test / build / lint / smoke を実行した。
