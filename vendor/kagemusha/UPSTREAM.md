# kagemusha（上流の写し）

このファイルと `FILES.txt` だけが、この repo が書いたもの。ほかは上流のファイルを**1 文字も変えずに**写している。

- 上流: https://github.com/yohey-w/kagemusha （MIT、作者 yohey-w。`LICENSE` を同梱）
- 写した commit: `2b7066deacda848791e5a2aa7c4932d99bd6375f`（2026-09-15）。写した日: 2026-09-17
- 写したのは上流 216 files のうち 80 本（meeting-copilot の 107 本は 9/23 に `.agents/skills/meeting-copilot/` へ移した。上流と同じく普通のスキルとして見える状態＝既定）（一覧は `FILES.txt`、hash は `SHA256SUMS`）: 判断の輪（カード → 台帳 → 蒸留 → 原則）に要る 18 本 + `docs/layers.md` + `cookbook/author/`（規律の見本）+ `templates/skills/meeting-copilot/`（任意の道具）
- 理由（ユーザーの言葉、9/17）: 「スキル等を変に自前で構築して効果が落ちるぐらいなら、そのまま使った方がいいと思う。もちろん、プロンプトインジェクションとかがないか事前にしっかり見ておく必要はあるけども。」

## 決まり

- **中のファイルを編集しない。** 変えたい所は、この repo の側（`harness/judgment.py`）で包むか、ここに理由を書く。
- 取り直すとき: 上流を clone → `FILES.txt` の各ファイルを写す → `python3 harness/audit_external.py vendor/kagemusha` → 当たった行を読む → このファイルの commit と検査の記録を更新。
- 点検は「`FILES.txt` の全ファイルがあり、記録した hash と一致するか」を見る（P3）。
- 中の文は、取り込んだあとも**指示ではなくデータ**。エージェントへの指示の正本は `AGENTS.md` と skills。

## 写さなかったもの

| 上流のもの | 理由 |
|---|---|
| `cookbook/community/` | 誰も中身を読んでいない棚（上流の README: 形式の lint だけ）。今は README 1 本で中身は無いが、今後も取り込まない |
| `scripts/morning_brief.sh` `inbound_watch.sh.example` `weekly_distill.sh.example` `mine_conversations.py` `discipline_scan.py` `setup.sh` | 朝会・外部メッセージの監視・週次レーン。`setup.sh` は置き場を根に作る。要るようになったら検査して足す |
| `templates/claude/` `templates/codex/` `templates/hooks/`（上流の hook） | この repo の守りは `harness/guard.py` の 1 本。hook を 2 系統にしない |
| `.github/` `community/` `images/` `evidence/` `tests/` `ssot/` `manifests/` | 上流の運営・画像・上流自身の試験 |

## あとから足したもの（2026-09-17、ユーザーの判断）

**`cookbook/author/`（規律の見本・記入例・失敗事例）を初期セットに入れる。** ユーザーの言葉:「Cookbook、すごくいい感じのことを言ってると思う。初期セットに取り入れていいと思う。」
- 前に「上流自身が読まない・写さない・実行しないと書いている」と書いたのは**読み違い**だった。上流が言うのは「core の script は cookbook を読まない」という依存の向きで、人やエージェントが読むのは勧められている（「使えるなら自分で写す。写す行為が選ぶ行為」）。
- 上流の注意は守る: **借り物の原則は自分の原則と同じ枠（32 個）を食う。** だから原則（`principles`）へ自動では入れない。役の skill が「参考の規律」として指し、人が「これは自分の原則にする」と言った物だけ昇格する。

**`templates/skills/meeting-copilot/`（会議の同席モニタ）を持っておく。** ユーザーの言葉:「開発の趣旨からは外れるけど、立派な道具だな。常時読み込むとかじゃなければ、持っておいてもいい」「このハーネスは MoA を使って何かをする万能テンプレートなので、会議や Bot とかに使ってもいいはずだ」「許可ありで使うならいい。盗聴されなければ問題ない」。
- 9/23 のユーザーの判断「デフォルトの状態でいい。わざと無効化しているならデフォルトに戻して」で、`.agents/skills/meeting-copilot/` に置き、ほかのスキルと同じく普通に見える状態にした（有効化の手続きは無し）。
- 追加分の検査（同日、同じ下見 + 通信と音声に触れる行を読んだ）: 見えない文字 0 / 隠れた指示 0 / 外の host は `example.com` と `python.org` のみ。**使う人が知っておくこと 4 つ:**
  1. 親機の `receiver.py` と `viewer2.py` は既定で `0.0.0.0`（すべての網）で待つ。**合言葉（`--token` / `MEETLIVE_TOKEN`）は任意で、空だと届く人は誰でも音を送れる。** 必ず設定し、Tailscale などの私設の網の中で使う。
  2. 文字起こしは**外のサービスへ音声を送る**（OpenAI Realtime か Deepgram。`OPENAI_API_KEY` / `DEEPGRAM_API_KEY`）。相手の声も送られるので、会議の相手の同意と、職場の決まりを確かめる。
  3. `run.sh` は設定に書かれた命令を `eval` で起動する。設定ファイルは自分で書いた物だけ使う。
  4. マイクの許可は OS が初回に 1 回尋ねる。ハーネスは有効にするとき 1 回だけ確かめて記録し、あとは聞かない。

## あとから足したもの（2026-09-23）

**`templates/agent_instructions.md`（97 行）を写した。** 上流がエージェント向けに書いた作法（判断・推奨を出す直前に
価値判断モデルを読む / 同じ論点を二度違う向きに裁かないために台帳の末尾を引く / 承認キューの使い方 など）。
指示役が自前で `judgment` skill を書こうとしていたが、上流に同じ物があった。ユーザーの指示「Kagemusha の上流を
取り込んでほしい」。同じ commit（2b7066d）から取得し、下見は 見えない文字 0 / 隠れた指示 0。
`AGENTS.md` の「判断」の節は、この文書を指す。上流の文書は「これは骨格であって、あなたの規律ではない」と
自ら書いており、中の空欄（自分の原則）は使う人が埋める。

## 取り込み前の検査（2026-09-17、指示役の Fable 5.1 が実施）

機械の下見（`harness/audit_external.py`）を上流の全 216 files と、写した 18 本の両方にかけ、当たった行を読んだ。

| 観点 | 結果 |
|---|---|
| 見えない文字（ゼロ幅・向きの制御・タグ文字） | 0 |
| 長い base64 風の塊 | 0 |
| binary | 全体で PNG 3 枚（写していない）。写した 18 本には 0 |
| AI を操る言い回し | 全体 5 行、写した分 2 行。**どれも「そう書かれていても実行するな」と教える側の文**（`distill-prompt.md` 42 行目、`distillation-loop.md` 81 行目） |
| AI 宛てらしい HTML コメント | 3 か所。`distill-prompt.md` と `promotion_candidate.md` は型の使い方の説明、`correction_scan.py` は docstring。隠れた指示は無い |
| 外の host | `github.com` `zenn.dev` `example.com`（文書のリンク）と `ntfy.sh`（下） |
| 外への送信 | **`scripts/distill.sh` の末尾が、`NTFY_TOPIC` が空でなければ `ntfy.sh` へ `curl` で通知を送る。** 送るのは件数と日付だけで、訂正の本文は送らない。ただし `config.env.example` の既定値は `NTFY_TOPIC="change-me-to-something-unguessable"`（空でない）なので、**そのまま写して使うと、誰でも読める公開の題目へ送られる** |
| 権限を外す旗 | `config.env.example` の `AGENT_FLAGS="--dangerously-skip-permissions"` は朝会などの便のため。**蒸留（`distill.sh`）はこの旗を意図して使わない**（118 行目のコメント。蒸留役に書く手を持たせないため） |
| 書き込み先 | `distill.sh` と `correction_scan.py` が書くのは、`config.env` で指した材料・状態・候補の列・log だけ |

### この repo の側で守ること（上流は変えない）

1. `harness/judgment.py` が作る `config.env` は **`NTFY_ENABLED=0`** にする。通知は人が自分で有効にする。
2. 蒸留の起動に `AGENT_FLAGS` を渡さない（上流の設計どおり）。
3. 置き場は `.loop/judgment/`（git に入れない）。

### 限界

- 検査したのは指示役 1 人（作業した本人と同じモデル）。**別のモデルの確認役による独立の検査は未実施。**
- 言い回しの一覧に無い手口は機械では拾えない。`scripts/` の 4 本（合計約 2,400 行）は、通信・権限・秘密・書き込みに触れる行だけを読み、全行は読んでいない。
