---
name: human-readable-writing
description: 人間が直接読む日本語の最終レポート、比較結果、説明資料、手順書、README、release note、onboardingを書く・直すときに使う。AI-slopを除き、platformがMarkdownを要求しないhuman deliverableは自己完結型HTMLにする。
---

# Human Readable Writing

## 使う場面

- README、onboarding docs、release note、公開文書など、人間が直接読むことを想定した日本語文章に使う。
- 「AIっぽさを消したい」「generic すぎる」「もっと自然に」「もっと具体的・実務的に」と依頼されたときに使う。
- `docs/REQS.md` のような machine 向け state、生ログ、生成出力、厳密な config コメントには、その文章を人間が読む予定がない限り使わない。

## 出力形式

- 人間が読む最終レポート、比較結果、説明資料、手順書は、platformがMarkdownを要求しない限り`.html`を標準にする。
- README、AGENTS、SECURITY、SKILLと、REQS、WORKLOG、HARNESS、ExecPlanなどagent state・policy・platform指定文書はMarkdownを維持する。
- 同内容のHTMLとMarkdownを併存させない。人間向け正本はHTML、agentの状態と根拠dataは既存のmachine-readable artifactへ分けてlinkする。
- 見た目の設計が必要なHTMLでは`design-taste-frontend` skillを併用し、先に`DESIGN.md`を読む。

## HTML契約

- `<!doctype html>`、`<html lang="ja">`、UTF-8、viewport、内容を表す`<title>`を置く。
- header / nav / main / section / table / footerなどsemantic HTMLを使い、見出し階層を飛ばさない。
- CSSを埋め込んだ単一fileにし、外部CDN、外部font、JavaScript、新規dependencyを既定で使わない。
- mobileで横幅を壊さず、tableは意味を保ったscroll containerまたはpriority表示にする。`@media print`も用意する。
- WCAG AA相当のcontrast、`:focus-visible`、skip link、意味のあるlink textを用意し、色だけで状態を伝えない。
- 結論、重要な数値、比較、制約、次のactionを視覚階層で区別する。装飾cardを増やさず、spacing、border、typographyを優先する。

## 出典

- `https://github.com/iKora128/stop-ai-slop-jp` の公開アイデアをこの repo 向けに調整したもの。
- 元 repo を丸写ししない。主語、立場、具体性、リズム、語彙、AI 的な残骸を点検するチェックリストとして使う。

## 手順

1. 読者が誰で、読んだ直後に何をする人かを特定する。
2. 言い回しを磨く前に主張を決める。誰も反対しようがない文は、たぶん曖昧すぎる。
3. 主語を見えるように保つ。「課題が浮き彫りになる」型の言い回しを、誰が見た・変えた・選んだ・失敗したに置き換える。
4. 広い形容詞より、具体的な名詞、ファイル名、コマンド、日付、結果、限界を優先する。
5. 人間向けの説明とエージェントの working memory を分ける。運用 state は正本 docs に移してリンクする。
6. 見出しは短く実用的に保つ。スローガン型・論文タイトル型の見出しを避ける。
7. リズムを変える。全段落を同じ長さ・同じ調子・同じ結び方にしない。
8. 締めは装飾的なまとめではなく、読者の次の実務的アクションで終える。

## 書き換えルール

- 根拠のない「簡単に」「シームレスに」「強力な」「包括的な」「堅牢な」「最適化された」のような一般的な賛辞・埋め草を置き換える。
- 具体的な結果を名指ししない「これにより...」の連鎖を避ける。
- 「以下に説明します」「本記事では」のような自明な構造宣言を避ける。
- 全 bullet が同じリズムで整いすぎたリストを避ける。
- 「AではなくB」「単なるAではなくB」は、B を直接言えるなら避ける。
- 「本質」「解像度」「思想」「営み」「手触り」「熱量」のような膨らんだ語は、本当に必要なときだけ使う。
- 根拠のない「現代社会において」「多くの人は」のような偽の精密さや広い社会的主張を避ける。
- 装飾の残骸を消す: 全角ダッシュ、普通の形容詞を囲む引用符、絵文字の繰り返し、迷子の `**`。
- 本文は日本語を既定にする。コマンド名、file path、config key、製品名は原文のまま正確に保つ。

## 人間向け文書チェックリスト

- 最初の段落で、誰が読むべき文書か、読んだ後に何ができるかが分かる。
- 「人間が読む部分」と「エージェント専用の working memory」が区別されている。
- 重要な主張それぞれに、具体的な主語、例、file path、コマンド、日付、観測可能な結果のどれかが付いている。
- 読者が重複テキストではなく正本文書にたどり着ける。
- コマンドはそのままコピーして使え、この repo に scope されている。
- 陳腐化しやすい主張には日付、出典、検証コマンドのどれかが付いている。
- そのツールについての節でない限り、Obsidian、plugin、特定の AI CLI を前提にしない。

## 検証

- 声に出して読むか、ゆっくり読み直して、繰り返しのリズム、膨らんだ語、主語の欠落に気づく。
- 読者の次のアクションを変えない段落は削る。
- リンクを追加したなら local link の生死を確認する。
- HTMLは`python3 .agents/skills/human-readable-writing/scripts/validate_html.py <file.html>`で、構造、内部link、外部resource、script不使用、responsive / print / focusを検査する。
- workflow が変わる文書なら、必要に応じて `docs/HARNESS.md` や `README.md` も更新する。
