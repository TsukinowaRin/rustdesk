# DESIGN.md

このファイルは、AI エージェントが UI を実装するときに読む design source of truth です。
`AGENTS.md` は「どう作業するか」、`DESIGN.md` は「どう見えるべきか」を定義します。

このテンプレートは、Google Stitch 系の DESIGN.md 形式と、`awesome-design-md` / `awesome-design-md-jp` の構成を参考にした汎用版です。
新しいプロジェクトでは、下の値を実プロダクトのブランド、ユーザー、情報密度に合わせて置き換えてください。

premium frontend / redesign 作業では `.agents/skills/design-taste-frontend/` も読む。`DESIGN.md` が source of truth で、skill は layout、typography、motion、copy の AI っぽさを減らす補助として使う。

---

## 1. Visual Theme & Atmosphere

- デザイン方針: 日本語 UI で読みやすい、技術文書にも業務アプリにも転用できる、静かで精度の高い interface。
- 雰囲気: calm, precise, durable, structured, craft。
- 密度: 情報密度は中から高。余白で高級感を出すより、見出し、罫線、surface、状態色で構造を明確にする。
- 避ける雰囲気: 量産型の白地に紫グラデーション、意味のない glassmorphism、過剰な blur、説明不能な装飾。
- 画面の主役: ユーザーの作業内容、データ、文章、操作の次の一手。背景装飾は補助に留める。

---

## 2. Color Palette & Roles

### Brand

- Primary `#2563eb`: 主要 CTA、focus ring、選択状態。青は信頼と操作可能性の signal として使う。
- Primary Hover `#1d4ed8`: Primary の hover / pressed。
- Accent `#f59e0b`: 注意を引く補助 accent。多用せず、重要な注釈、更新、強調に限定する。

### Neutral

- Canvas `#f7f5ef`: ページ背景。純白ではなく、長時間読んでも疲れにくい紙寄りの下地。
- Surface `#ffffff`: card、modal、table header、form block。
- Surface Muted `#f1eee7`: 入れ子 surface、code block、subtle section。
- Border `#d8d2c4`: 罫線、input border、区切り。
- Border Strong `#b8ad9b`: focus 以外の強い区切り。

### Text

- Text Primary `#1f2933`: 本文、見出し。
- Text Secondary `#52606d`: 補足、説明、meta。
- Text Muted `#7b8794`: disabled、caption、placeholder。
- Text Inverse `#ffffff`: dark surface 上の文字。

### Semantic

- Success `#0f766e`: 成功、完了、安全。
- Warning `#b45309`: 注意、要確認。
- Danger `#b91c1c`: 削除、破壊的操作、失敗。
- Info `#2563eb`: 情報、リンク、進行中。

### Usage Rules

- Primary は「次に押すべき操作」だけに使う。
- Danger は destructive action と validation error だけに使う。
- Warning と Accent を混同しない。Warning はユーザー判断が必要な状態、Accent は視線誘導。
- 本文に純黒 `#000000` は使わない。背景に純白だけを敷き詰めない。

---

## 3. Typography Rules

### Japanese First

- 和文: `"Noto Sans JP"`, `"Yu Gothic"`, `"Hiragino Sans"`, sans-serif。
- 欧文: `"Geist"`, `"Inter"`, `"Segoe UI"`, sans-serif。
- 等幅: `"JetBrains Mono"`, `"SFMono-Regular"`, `"Consolas"`, monospace。

```css
:root {
  --font-sans: "Noto Sans JP", "Geist", "Inter", "Yu Gothic", "Hiragino Sans", sans-serif;
  --font-mono: "JetBrains Mono", "SFMono-Regular", "Consolas", monospace;
}
```

### Hierarchy

| Role | Size | Weight | Line Height | Letter Spacing | Use |
|---|---:|---:|---:|---:|---|
| Display | 48px | 700 | 1.18 | -0.02em | landing hero |
| Heading 1 | 36px | 700 | 1.25 | -0.01em | page title |
| Heading 2 | 28px | 700 | 1.35 | 0 | section title |
| Heading 3 | 20px | 700 | 1.45 | 0 | card title |
| Body | 16px | 400 | 1.75 | 0.04em | main Japanese body |
| Body Small | 14px | 400 | 1.7 | 0.02em | table, card body |
| Caption | 12px | 500 | 1.55 | 0.04em | labels, metadata |
| Mono | 13px | 400 | 1.6 | 0 | code, command |

### Japanese Typesetting

- 日本語本文は `line-height: 1.7` 前後を標準にする。
- 日本語本文の字間は `letter-spacing: 0.04em` を標準にする。表、caption、密度の高い管理画面では `0.02em` まで詰めてもよい。
- 見出しは詰めすぎない。和文見出しで過度な negative tracking を使わない。
- 長い URL や code token が混ざる領域は `overflow-wrap: anywhere` を許可する。
- 本文には `font-feature-settings: "palt" 1` を乱用しない。見出し、nav、button label だけで検討する。
- 禁則処理は可能なら `line-break: strict` を指定する。

---

## 4. Layout Principles

### Spacing Scale

| Token | Value |
|---|---:|
| XS | 4px |
| S | 8px |
| M | 16px |
| L | 24px |
| XL | 32px |
| XXL | 48px |
| Section | 80px |

### Containers

- Content max width: 1120px。
- Reading max width: 760px。
- Page padding: mobile 16px、tablet 24px、desktop 32px。
- Grid gap: 16px から 24px を標準にする。

### Rhythm

- 画面は「header / content / action / feedback」の順で読む。
- Primary action は1画面に原則1つ。
- table や form は余白より alignment を優先する。
- dashboard は card を増やす前に、見出し、grouping、empty state を整理する。

---

## 5. Component Stylings

### Buttons

- Primary: background Primary、text Text Inverse、radius 10px、padding 10px 16px、weight 700。
- Secondary: background Surface、text Text Primary、border Border、radius 10px。
- Ghost: background transparent、text Text Secondary、hover Surface Muted。
- Danger: background Danger、text Text Inverse。確認 dialog や irreversible action だけに使う。
- Touch target: 最小 44px。

### Inputs

- Height: 40px から 44px。
- Background: Surface。
- Border: Border。Focus は Primary の 2px ring。
- Error: Border と helper text に Danger。
- Placeholder は Text Muted。本文と同じ濃さにしない。

### Cards

- Background: Surface。
- Border: 1px solid Border。
- Radius: 14px。
- Padding: 16px から 24px。
- Shadow は控えめにし、階層は border と surface で作る。

### Tables

- Header: Surface Muted、Caption typography。
- Row height: 44px 以上。
- Numeric column は右寄せ。
- Long text は truncation だけにせず、必要なら detail view を用意する。

### Navigation

- Top nav は 56px から 64px。
- Active state は Primary の line、pill、または surface shift で示す。
- Breadcrumb は complex workflow で優先する。

---

## 6. Depth & Elevation

| Level | Treatment | Use |
|---|---|---|
| 0 | Canvas only | page background |
| 1 | Surface + Border | card, table, form |
| 2 | Surface + Border Strong + subtle shadow | dropdown, popover |
| 3 | Surface + stronger shadow | modal, command palette |
| Focus | 2px Primary ring | keyboard focus |

- shadow は装飾ではなく、重なり順を示すために使う。
- dark overlay は modal と destructive confirmation に限定する。

---

## 7. Motion

- Motion は状態理解のために使う。飾りのために常時動かさない。
- Duration: 120ms から 180ms を標準にする。
- Easing: `cubic-bezier(0.2, 0, 0, 1)`。
- Page load は軽い stagger まで。無限 loop animation は必要な場合だけ。
- `prefers-reduced-motion` を尊重する。

---

## 8. Responsive Behavior

| Name | Width | Rule |
|---|---:|---|
| Mobile | <= 640px | 1 column、bottom actions、16px padding |
| Tablet | <= 1024px | 2 column まで、side nav は collapse |
| Desktop | > 1024px | 12 column grid、sidebar / split view を許可 |

- Mobile では hover 依存の UI を作らない。
- Form は mobile で縦積みにする。
- Table は mobile で card list または priority columns に変換する。

---

## 9. Accessibility

- Contrast は WCAG AA 以上を目標にする。
- Focus visible を消さない。
- Icon-only button には accessible name を付ける。
- Error は色だけで伝えない。text と icon を併用する。
- Loading、empty、error、success の4状態を component 設計に含める。

---

## 10. Do's and Don'ts

### Do

- `DESIGN.md` の tokens を先に CSS variables / theme tokens へ写す。
- 日本語本文の line-height を広めに取り、読みやすさを優先する。
- UI 実装前に、目的、情報密度、主要 action、empty state を決める。
- 既存 design system がある場合は、このファイルより既存 system を優先し、差分だけここに追記する。

### Don't

- 紫 gradient、glass card、過剰 shadow を default にしない。
- 全画面を card だらけにしない。
- component の state を default だけで終わらせない。
- Tailwind / CSS framework の default spacing だけで見た目を決めない。
- ブランド未定のまま logo、illustration、写真素材を作り込まない。

---

## 11. Agent Prompt Guide

### Quick Reference

```text
Design source: DESIGN.md
Tone: calm, precise, durable, structured
Primary: #2563eb
Canvas: #f7f5ef
Surface: #ffffff
Text: #1f2933
Japanese body: 16px / line-height 1.75
Radius: 10px buttons, 14px cards
Spacing: 4, 8, 16, 24, 32, 48, 80
```

### Prompt Pattern

```text
DESIGN.md に従って UI を作ってください。
最初に visual direction、主要 tokens、component states、responsive behavior を短く確認してください。
実装後は desktop / mobile、empty / loading / error / success state を確認してください。
```

### When Requirements Conflict

- ユーザー指定のブランド、既存 product UI、既存 component library がある場合は、それを優先する。
- `DESIGN.md` と実装済み design system が矛盾する場合は、差分を説明してから最小変更する。
- デザイン判断に迷う場合は、平均的な無難案ではなく、目的に合う明確な visual direction を1つ選ぶ。
