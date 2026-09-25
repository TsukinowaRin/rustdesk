# HARNESS.md — 構成の地図

ハーネスを直す人のための 1 枚。どこに何があり、なぜその形か、直すときの決まりを書く。
使い方の説明は、下の「入れてから最初の 1 件まで」だけ。正本は `docs/PLAN.md`（設計と計画）と `harness/clis.json`（CLI の接続一覧）。ここに書くのは実物にあることだけ。

## 入れてから最初の 1 件まで

展開したら CLI を開いて、普通に依頼を言うだけでよい。準備（`git init` と最初の commit・担い手の編成 `.loop/team.json`・`.loop/tasks/`）は `python3 harness/setup.py auto` が CLI の開始 hook から自動で走る（Claude Code / Codex / Cursor / opencode / Kilo / omp / dsh。実測は Claude Code / Codex / Cursor で合格、`docs/verification/2026-09-26_first-run/`）。Claude Code は最初に出る「このフォルダを信頼しますか」で信頼を選ぶ（選ぶまで `.claude/settings.json` の hook は読まれない）。開始 hook が無い CLI（Antigravity / Grok）では、指示役が依頼の前に `auto` を 1 回打つ（AGENTS.md）。手順 2〜4 は、その中身の説明。

1. 要る物: Python 3.11 以上と git。担い手に使う CLI（`harness/team.example.json` の `cli` 欄）にはサインインしておく。
2. 展開先で `git init` → `git add -A` → `git commit -m init`（担い手の作業木は HEAD から作るので、最初の commit が要る）。名前が未設定なら commit の前に `git config user.name "名前"` / `git config user.email "メールアドレス"`。
3. `python3 harness/check.py` を通す。`python3 harness/setup.py status` の「まだ」を、書いてある命令で 1 つずつ済ませる。編成の「まだ」は手順 4 で済む。「まだ」が出なくなれば完了。
4. `cp harness/team.example.json .loop/team.json` で写し、使わない CLI の人は消す（入っているかは `command -v <CLI>`）。`python3 harness/delegate.py team` で確かめる。
5. `python3 harness/delegate.py new <題名> --member <名>` → できた `.loop/tasks/<依頼ID>/task.md` に目的・受け入れ条件・触ってよい場所を書く。
依頼書の頭の欄の意味は ③ のギアの表を見る。
6. `python3 harness/delegate.py run <依頼ID>` → 報告（`.loop/tasks/<依頼ID>/` に写る）を読む → よければ `python3 harness/delegate.py adopt <依頼ID>`。

## ① 置き場の表

| 場所 | 中身 | 直すときの注意 |
|---|---|---|
| `AGENTS.md` | 全 CLI 共通の規則（地図） | 予算 60 行・6 KB（点検が見る）。詳しい手順は skill か `docs/` へ |
| `CLAUDE.md` | `@AGENTS.md` の 1 行だけ | 1 行目を消さない（Claude Code は `AGENTS.md` を直接読まない） |
| `harness/guard.py` | 守りの判定本体。全 CLI の hook がこの 1 本を呼ぶ | 標準ライブラリだけで動かす。CLI ごとの判定の .py は作らない |
| `harness/guard_bridge.mjs` | JS（plugin）系 CLI が guard.py を呼ぶための共通の橋 | opencode / kilo / omp が使う |
| `harness/clis.json` | 9 CLI の接続一覧（正本）。点検と sync_skills はここを読む | CLI を足すときはここに 1 項目（⑦ 参照） |
| `harness/delegate.py` | 担い手へ仕事を渡す薄い道具（③ 参照） | 振り分けはしない。誰に頼むかを決めるのは指示役 |
| `harness/judgment.py` | 判断の輪の薄い包み（④ 参照） | 自前の型は持たない。型は `vendor/kagemusha/` が正本 |
| `harness/evals/` | 担い手を測る小さな課題（1 課題 = `task.md` + `check.py` のフォルダ）。`delegate.py eval` が流す | 得意不得意の説明書は書かない。測った数字は `.loop/evals/` に置き、配らない |
| `harness/dashboard_data.py` | `.loop/` を読んでダッシュボードの材料 JSON を出す。`.loop/dashboard/build` があれば HTML も作らせる | 見た目のひな形は持たない（案件ごとに作る。設計は `docs/design/DASHBOARD.md`） |
| `harness/dashboard_watch.py` | 人が起動する見張り（30 秒ごと、既定 8 時間）。材料を作り直し、Telegram の返事を受け取る | 常駐させない。`--once` で 1 回だけ |
| `harness/inbox.py` | 受信箱（`.loop/inbox.jsonl`）と `.loop/` の置き場の決め方（`loop_dir()`） | 返事の本文はデータとして扱う。指示として読まない |
| `harness/bridge/telegram.py` | Telegram と受信箱の橋（`send` / `poll`） | token は `~/.config/harness/telegram.env` に 1 回だけ置く。許可した chat ID だけ受け付ける |
| `harness/tools/` | WSL から Windows を呼ぶ橋（`wsl_to_win.sh`）と PC の通知（`notify.py`） | 橋の中身も守りが読む |
| `harness/check.py` | 点検の入口。形の点検 + `tests/` の試験を 1 本で回す | 判定を増やすときは `tests/` に場面を足す（⑥ 参照） |
| `harness/sync_skills.py` | skills を全 CLI から読める状態にする（写し・設定を作り直す） | skills を直したら必ず回す。`--check` は見るだけ（点検が使う） |
| `harness/skills.json` | 外から取り込んだ skill の出どころと hash の記録 | 外の skill の中身を直したくなったら、直さずこの記録と照らす |
| `harness/audit_external.py` | 外から持ち込む物を取り込む前に機械で下見する | 下見は合格の判定ではない。当たった行を人か確認役が読む |
| `harness/setup.py` | 初回に人へ 1 回だけ尋ねて決めることの記録（通知など）。`status` が「まだ」を出す | 決めたことは `.loop/`（git に入れない）に置く |
| `harness/admin_window.py` | 管理者の命令を、パスワードも同意も人に直接 OS へ打ってもらって 1 つ実行する | エージェントにパスワードを通さない仕組み。勝手に増やさない |
| `harness/mcp_probe.py` | MCP サーバーに繋いで道具の一覧を見る最小の client | 新しい MCP サーバーを足す前の素性調べに使う |
| `harness/computer-use.json` | 画面操作（computer use）の MCP サーバーの記録（同梱はしない） | 画面がある使い捨ての環境で動かす。母艦では動かさない |
| `harness/sandbox/` | 使い捨ての Windows（`windows/` = Windows Sandbox、`hyperv/` = Hyper-V）の台本と検査の記録 | 閉じると消える環境。恒久の物を置かない |
| `harness/dsh.sh` | dsh の起動口。守りの patch を必ず付ける | 認証情報は dsh 本体の置き場（`~/.dsh/`）。ここでは設定しない |
| `harness/team.example.json` | 編成（担い手の一覧）のひな形 | 実際の編成は `.loop/team.json`（この機械だけ）に置く |
| `tests/` | 表で書いた試験（止める形 / 通す形）と試験（一覧は `python3 harness/check.py --list`） | 場面を 1 行足すのが基本。点検の本体をここに太らせる |
| `.agents/skills/` | skills の編集元（Agent Skills 標準）1 か所 | 直したら `python3 harness/sync_skills.py`。外の物は編集しない |
| `.claude/skills/` | Claude Code 用の写し（生成物） | 手で直さない。sync_skills.py が作り直す |
| 各 CLI の設定 1 枚 | `.claude/settings.json` `.codex/config.toml` `.agents/hooks.json` `.cursor/hooks.json` `.grok/hooks/guard.json` `.omp/extensions/guard.ts` `.opencode/plugins/guard.js` `.kilo/plugins/guard.js` `.dsh/guard.patch.yml` | 中身は「guard.py を正しい dialect で呼ぶ」こと。判定を書かない |
| `kilo.jsonc` | Kilo に skills の置き場を指す設定 | Kilo だけ `.agents/skills` を自動で読まないため |
| `vendor/kagemusha/` | 上流 kagemusha の型と蒸留の道具（無編集の写し、MIT） | 中は 1 文字も編集しない。出どころと検査は `vendor/kagemusha/UPSTREAM.md` |
| `docs/PLAN.md` | 今の依頼と進み、設計の正本 | 作業が進むたびに更新する |
| `docs/SECURITY.md` | 守りの説明と限界（担い手が書いた） | 守りを変えたら限界の欄も直す |
| `docs/verification/` | 独立の確認の記録 | 作った本人の試験は検収に数えない（⑤ 参照） |
| `docs/design/` | DESIGN のひな形（`DESIGN.ja.md` / `DESIGN.intl.md`）と、設計の記録（`DASHBOARD.md` = ダッシュボード、`IMPROVE.md` = 改善の輪） | ひな形は写して使う。設計の記録は決めたことを追記する |
| `docs/dashboard/` | この repo（ハーネスの開発）用のダッシュボード 1 枚（`build.py`） | 配布物のひな形ではない |
| `docs/reports/` | 人向けの報告（HTML） | 機械が読む物は置かない |
| `.loop/` | 人ごとの設定（編成・判断・依頼・events）。git に入れない | この repo は配布物を作る場所。配る物に 1 つも入れてはいけない |

## ② 9 CLI の接続

正本は `harness/clis.json`。CLI ごとの違いは設定 1 枚に閉じ込め、判定の本体は `harness/guard.py` の 1 本だけ（JS 拡張の 3 本は `guard_bridge.mjs` を経由）。CLI ごとの判定の .py は無い。

| CLI | 規則の読み方 | skills_mode | 守りの設定 | dialect | 担い手としての起動 |
|---|---|---|---|---|---|
| Claude Code | `CLAUDE.md`（`@AGENTS.md` を取り込む） | mirror（`.claude/skills` へ写す） | `.claude/settings.json` | claude | `claude -p --model … --disallowedTools Agent --permission-mode bypassPermissions`（依頼文は stdin） |
| Codex | `AGENTS.md` | native | `.codex/config.toml` | claude | `codex exec --dangerously-bypass-approvals-and-sandbox …` |
| Antigravity（agy） | `AGENTS.md` | native | `.agents/hooks.json` | agy | `agy --add-dir <作業木> --dangerously-skip-permissions --print-timeout …` |
| Cursor | `AGENTS.md` | native | `.cursor/hooks.json` | cursor | `cursor-agent -p --trust --force …`（9/25 に担い手として 1 件合格。画面なしの shell は日によって固まる） |
| opencode | `AGENTS.md` | native | `.opencode/plugins/guard.js` | plain | `opencode run --dir <作業木> …` |
| Kilo | `AGENTS.md` | config（`kilo.jsonc` で指す） | `.kilo/plugins/guard.js` | plain | `kilo run --dir <作業木> --dangerously-skip-permissions …`（無いと bash の許可を自分で断って報告が書けない。守りは plugin が呼ぶので外れない） |
| Grok Build | `AGENTS.md` | native | `.grok/hooks/guard.json` | claude | `grok -p "<依頼文>"` |
| oh-my-pi（omp） | `AGENTS.md` | native | `.omp/extensions/guard.ts` | plain | `omp -p --auto-approve …` |
| DeepSeek Harness（dsh） | `AGENTS.md` | native（`.dsh/skills` も） | `.dsh/guard.patch.yml`（hook は Claude Code と共用） | claude | `bash harness/dsh.sh --profile headless "<依頼文>"`（必ずこの起動口から） |

skills_mode の意味: native = `.agents/skills/` を直接読む。mirror = 専用の写しが要る（`sync_skills.py` が作る）。config = 設定ファイルで置き場を指す。

各 CLI の `notes` に書いてある「黙って素通り」の型は、使う人が知っておくべき注意（例: Codex は `/hooks` を承認するまで hook が動かない。agy は `--add-dir` が無いと hook も規則も読まれない。Grok は folder の信頼まで hook が 0 本）。守りの限界の全体は `docs/SECURITY.md`。

## ③ 担い手へ渡す流れ

```
依頼書（.loop/tasks/<依頼ID>/task.md）
  → delegate.py run（作業木 git worktree を 1 つ作る）
    → 担い手 1 人を、編成の「worker」の形で 1 回だけ起動（HARNESS_ROLE=worker を付ける）
      → 報告（作業木の中の REPORT.md。終わると task フォルダへ写る）
        → events.jsonl に起動・終了・合否を 1 行ずつ（指示役は sleep で待たずこれを見張る）
```

- 待ち方: 指示役は `delegate.py run` を裏で起動し、`.loop/events.jsonl` に `end` が書かれるのを CLI の見張りで受ける（Claude Code なら Monitor。見張りが無い CLI なら、応答を終えず `run` を前で待つ）。`sleep` の輪で待たない。
- 枠切れの印が出た担い手は 1 時間休ませ、期限後に `delegate.py retry <依頼ID>` で同じ依頼を 1 回だけ再試行する。
- `delegate.py team --probe` は各担い手を 60 秒以内で試し、状態と秒数を表示する（結果は `.loop/` に書かない）。
- トークンが取れる CLI の一覧は `harness/clis.json` の `usage` を見る。空欄の CLI は「不明」。

- 正本はファイル（`.loop/tasks/<依頼ID>/`）。会話で指示を渡さない。
- 担い手を別の作業木（git worktree）で動かす理由は 2 つ: 同じ場所を 2 人が書き換えない。訂正の採取（④）が「作業場所」で会話を見分けるので、指示役の依頼文を「人の訂正」として拾わせない。

評価を流す: `python3 harness/delegate.py eval --member <名>[,<名>...] [--task greet|read|fix]`。
評価を見る: `python3 harness/delegate.py stats` の「評価」列で、合格数・平均秒・平均トークンを確かめる。
結果は `.loop/evals/<日付>.jsonl` に置き、配布物には入れない。

### ギア 4 つ（依頼書の先頭に書く。delegate.py が読む）

| ギア | 欄 | 意味 |
|---|---|---|
| 費用 | `member` | 誰に頼むか。指示役が `.loop/team.json` の編成を見て選ぶ。道具は選ばない |
| 独立 | `independent_of` | その依頼の確認を別の担い手にする。同じ会社（`vendor`）の担い手を選ぶと delegate.py が注意を出す |
| 手 | `hands` | `workspace`（普通）か `none`（読むだけ。guard が書く道具と shell を止める。報告 1 本だけ例外） |
| 並べる | `fanout` | 同じ依頼を N 人に並行で出す。担い手の `max_parallel` を超えると止まる |
| 補助 | `guard` | 守りを直す依頼だけ `edit` を書く。空欄なら守りの本体は書けない |
| 補助 | `minutes` | 担い手を動かす上限時間（分） |

環境変数の意味（delegate.py が起動時に付ける。guard.py と worker skill が読む）:

| 変数 | 意味 |
|---|---|
| `HARNESS_ROLE=worker` | 付けられた側は担い手。guard は「聞く」を「止める」に倒し、作業木の外と守りのファイルへの書き込み・別の担い手の起動・担い手の印（この表の `HARNESS_ROLE` `HARNESS_HANDS` `HARNESS_WORKTREE` `HARNESS_GUARD_EDIT`）の書き換えを止める |
| `HARNESS_HANDS=none` | その担い手は書く手が無い。書く道具と shell が止まる |
| `HARNESS_REPORT` | 報告を書く場所（作業木の中の `REPORT.md`） |
| `HARNESS_WORKTREE` | 担い手の作業木。guard は担い手の書き先がこの中かを見る |
| `HARNESS_GUARD_EDIT=1` | 依頼書に `guard: edit` があるときだけ付く。担い手が作業木の中の守りのファイルを書ける（作業木の外は書けないまま） |
| `HARNESS_TASK` / `HARNESS_MEMBER` | 依頼 ID と担い手の名前（記録用。guard は読まない） |
| `HARNESS_GUARD_TRACE` | guard が呼ばれるたびに 1 行残すファイル（命令の中身は残さない）。`stats` の `guard_calls` の元 |
| `HARNESS_ATTENDED=1` | 人が目の前にいる印。付けたときだけ guard の「聞く」が CLI の承認画面に回る。**既定（印なし）は承認画面を出さず止める**（2026-09-24、承認待ちで気づかず止まるのを防ぐため） |
| `HARNESS_LOOP_DIR` | `.loop/` の置き場を指す。無ければ、作業木（`.loop/work/<名>`）の中では本体の `.loop/`、それ以外は repo の `.loop/`。`delegate.py`・`judgment.py brief`・`setup.py` が同じ決め方（`harness/inbox.py` の `loop_dir()`）を使う |
| `HARNESS_APPROVED=1` | 命令の先頭に付けると、人が OK した「聞く」操作を 1 回だけ通す（`HARNESS_APPROVED=1 git push origin feature`）。deny と管理者の操作には効かない。担い手には効かない |

担い手だけに渡す環境変数は、git に入らない `.loop/worker.env` に `KEY=VALUE` で置く。指示役の環境は変わらない。
例: `CLIPROXY_API_KEY=...`（値は人が直接書く。空行と `#` で始まる注記は読み飛ばし、値の外側の引用符は外す）。

ほかに人が付ける変数: `HARNESS_JUDGMENT_HOME`（判断の置き場を別の非公開 repo に。④）、`HARNESS_LOG_DIR`（訂正の採取で読む会話ログの場所）。`HARNESS_ROOT` `HARNESS_CLIS` `HARNESS_TESTING` `HARNESS_SETUP_STDIN` は試験用。

ダッシュボードの見張りは人が `python3 harness/dashboard_watch.py` で起動する（既定 8 時間、Ctrl-C で終了）。1 回だけ作り直すなら `python3 harness/dashboard_watch.py --once`。
スマホから見る道は 2 つある。
Telegram: bot を作り、`~/.config/harness/telegram.env`（`HARNESS_CONFIG_HOME` を使う場合はその下）に token と許可する chat ID を 1 回だけ書くと、どの作業場でも見張りが変化の要点を送る（`--digest-minutes 0` で停止）。作業場ごとに変える場合は `.loop/telegram.env` が優先される。
Telegram: bot に `/dash` と送ると最新の HTML が届き、`/status` では要点だけが届く。
注意: 1 つの bot を同時に受信できるのは 1 つの見張りだけ。2 つの作業場を同時に動かすなら bot を分ける。
私設の網: 見張りを `--serve 100.x.y.z:8765` で起動し、同じ網のスマホから `http://100.x.y.z:8765/` を開く。

複数の作業場を 1 つのアプリから（hub。設計は `docs/design/HUB.md`）: 受け取るのは hub だけで、各作業場の見張りは `.loop/outbox.jsonl` に書く。
hub.json: `~/.config/harness/hub.json` に `{"workspaces": {"harness": {"path": "/abs/path/repo"}, "test": {"path": "/abs/path/test-project"}}, "current": "harness"}`。token は `~/.config/harness/telegram.env`（`HARNESS_CONFIG_HOME` があればその下）。
話題で分ける: Telegram のグループでトピックを有効にし、bot を「トピックの管理」ができる管理者として追加する。
グループで `/start` を送り、`python3 harness/hub.py whoami` で `chat_id` を確認し、`hub.json` に `"chat_id": <番号>` を足す。
次の hub 起動時に作業場ごとの話題を作り、`topics`（作業場名 → `message_thread_id`）へ保存する。作業場を増やした後も次の起動で作る。
話題の文と返事はその作業場へ届く。General と、`chat_id` が無いときの私信は今の相手へ届く。
起動: `python3 harness/hub.py`（既定 8 時間、`--once` で 1 回）。各作業場の見張りも起動しておく（hub.json に載っていれば Telegram に触らない）。
書き方: `/ws` で一覧、`/ws <名前>` で相手を切り替え、普通の文は今の相手の受信箱へ、`@<名前> 文` は 1 通だけその作業場へ。`/dash` `/status`（`@<名前> /dash` も可）は見張りが応える。
届く文の頭には `[<名前>]` が付く。記録は `~/.config/harness/hub.log`（本文は先頭 80 字）。許可外の chat ID は捨てて記録だけ。
`/run [<名前>] <依頼の文>` は、`hub.json` の作業場に `"leader": {"cli": "claude", "model": "claude-opus-5-5"}` を設定し、指示役をその作業場で起動する。名前を省くと今の相手。
第 1 語が `hub.json` に無い名前なら、それも依頼の文の一部として今の相手で起動する（打ち間違いは返事の「起動しました（作業場 <名前>）」で気づく）。同じ `update_id` の再配送では二度起動しない。
同じ作業場では同時に 1 件まで。`/stop [<名前>]` で実行中の指示役に停止を求める。
終了すると要点が `[<名前>]` 付きで届く。claude と codex に対応し、ほかの CLI は未対応と返す。
hub 画面: `python3 harness/hub.py --serve 100.x.y.z:8765`（`0.0.0.0` は断る。Telegram の設定が無ければ画面だけで動く）。`/` は作業場の一覧（未読の数・`/run` 実行中か）、`/ws/<名前>` はその作業場の会話（受信箱と送信箱を時刻順に 1 本、15 秒ごとに描き直し）。
返事の欄に書くと、Telegram から来た文と同じ道（`hub.receive`）で受信箱に入る（`chat_id` は `"web"`）。`/run` `/stop` `/dash` `/status` も同じ欄から送れ、その返事は画面にだけ出る。
POST は同じ host の画面から（`Origin` か `Referer` が一致）だけ受け、本文は 4,000 字まで。鍵は無いので、私設の網（Tailscale など）の外に出さない。

Discord ①: [Developer Portal](https://discord.com/developers/applications) で Application を作り、Bot の token をコピーする。
Discord ②: Bot → Privileged Gateway Intents → MESSAGE CONTENT INTENT を ON にする。
Discord ③: OAuth2 URL Generator の scope を bot、権限を Manage Channels / Send Messages / Read Message History / Attach Files にして、生成した URL からサーバーに招待する（対象チャンネルの View Channel も許可する）。
Discord ④: Discord の設定 → 詳細設定 → 開発者モードを ON にし、自分を右クリック → ID をコピー、サーバーも右クリック → サーバー ID をコピーする。
Discord ⑤: `harness/discord.env.example` を `~/.config/harness/discord.env` に写し、`DISCORD_BOT_TOKEN`・`DISCORD_USER_IDS`（複数はコンマ区切り）・`DISCORD_GUILD_ID` を入れる（`HARNESS_CONFIG_HOME` があればその下）。
Discord ⑥: `hub.json` に `"transports": {"discord": {"guild_id": "サーバーID"}}` を足して hub を起動すると作業場ごとのチャンネルができ、文・`/run 依頼`・`/dash`・`/status` をそこで送れる（3 秒ごとに受信、`python3 harness/hub.py whoami` で bot と発言者の ID を確認、Telegram も使うなら `transports` に `"telegram": {}` を足す）。

Slack ①: [api.slack.com/apps](https://api.slack.com/apps) でアプリを作る。
Slack ②: OAuth & Permissions → Bot Token Scopes に `channels:manage channels:history channels:read channels:join chat:write files:write users:read` を追加する。
Slack ③: アプリをワークスペースにインストールする。
Slack ④: Bot User OAuth Token（`xoxb-`）をコピーする。
Slack ⑤: `harness/slack.env.example` を `~/.config/harness/slack.env` に写し、`SLACK_BOT_TOKEN` と `SLACK_USER_IDS`（プロフィール → ⋯ → メンバー ID をコピー）を入れる。
Slack ⑥: `hub.json` の `transports.slack` を `{}` で有効にして hub を起動する。作業場ごとのチャンネルを作り、3 秒ごとに読む。`python3 harness/hub.py whoami` で bot と発言者の ID を確認できる。文書は私設の網の HTML から開く。

依頼書の書き方と報告の形は `.agents/skills/leader/SKILL.md` と `.agents/skills/worker/SKILL.md`。受け入れ条件は機械で確かめられる形で書き、報告は 30 行以内。独立の確認の手順は `.agents/skills/independent-check/SKILL.md`（実装を読む前に「止める形 / 通す形」の対を書く）。

## ④ 判断の輪（カード → 台帳 → 蒸留 → 原則）

**型は上流のまま、道具は機械の仕事だけ。** 型と蒸留の道具は `vendor/kagemusha/`（無編集の写し）が正本で、`harness/judgment.py` は自前の型を持たない。ここが包むのは機械の仕事だけ:

| すること | 誰が | 何で |
|---|---|---|
| `brief` 原則と、たまっている物の数を最初に読む | 指示役 | `judgment.py brief`（副作用: ダッシュボードの材料の JSON と HTML を作り直す。`.loop/telegram.env` があれば 1 回受信する） |
| ① 判断カードを書く | 指示役が上流の型どおり `.loop/judgment/` へ直接 | 型は `vendor/kagemusha/templates/`。作法は `vendor/kagemusha/templates/agent_instructions.md`（「これは骨格であって、あなたの規律ではない」ので、中の空欄は使う人が埋める） |
| ② 台帳に書く | 指示役。人に直された・却下された・裁定されたら、そのターンのうちに | `judgment.py check` が上流の型の欄を機械で点検する |
| ③ 蒸留 | 書く手の無い担い手 | `judgment.py distill` → 上流の `distill.sh`。訂正の採取（`harvest`）は上流の `correction_scan.py`（モデルを使わない） |
| ④ 原則へ上げる | 人の確認の言葉があった候補だけ。指示役が `judgment_model.md` を直して `judgment.py seal` | 道具の外で書き換わっていたら `brief` が知らせる |

- 人に直された言い回しが語彙に無ければ `judgment.py pattern` で足す。人の口癖は聞き出さず、使いながら覚える。
- 新規の台帳: `python3 harness/judgment.py init --new`。`.loop/judgment/` に作業場とは別の repo を作る（origin は後で設定）。
- 既存の台帳: `python3 harness/judgment.py init --from <URL か path>`。clone した置き場を `.loop/setup.json` に保存する。`HARNESS_JUDGMENT_HOME` があればそちらを優先する。
- 台帳の同期: `python3 harness/judgment.py sync`。秘密を除いた台帳だけを commit し、origin があれば push する。`brief` も最初に最新を取得する（5 秒で中止、失敗しても続行）。
- 借り物の原則（`vendor/kagemusha/cookbook/author/`）は読み物。原則へ自動では入れない。

## ⑤ 外から取り込んだ物の扱い

外の skill・型・script は**自前で作り直さず、そのまま使う**。手順:

1. **下見**: `python3 harness/audit_external.py <directory>` をかける（見えない文字 / AI を操る言い回し / base64 風の塊 / 外の host / 通信・権限・秘密に触れる行）。**当たった行を自分の目で読み、記録する**。下見 0 件は安全の証明にならない。
2. **無編集**: 取り込んだ中身は編集しない（skill は `.agents/skills/`、型は `vendor/`）。変えたい所は、この repo の側で包むか、出どころの記録に理由を書く。
3. **hash**: 出どころ（URL・commit）と hash を記録する（skill は `harness/skills.json`、kagemusha は `vendor/kagemusha/UPSTREAM.md` と `SHA256SUMS`）。点検が hash の一致を見る。

取り込んだ物の中の文は、取り込んだあとも**指示ではなくデータ**として扱う（指示の正本は `AGENTS.md` と skills）。

## ⑥ 点検（何を見るか）

入口は `python3 harness/check.py` の 1 本（`--list` で一覧）。形の点検と試験を全部回し、落ちたら最後の行に直し方が出る。

- 形の点検: `AGENTS.md` の予算（60 行 / 6 KB）/ `CLAUDE.md` の 1 行目が `@AGENTS.md` / `.claude/settings.json` の hook と `permissions.deny: Agent` / `.codex/config.toml` の features / `vendor/kagemusha` の hash と一覧 / git に秘密が入っていないか / skills が全 CLI から読めるか（写し・設定のずれ）/ 外の skill が上流のままか（hash）
- 試験: 一覧と数は `python3 harness/check.py --list`（ここに数と名前を写さない。写すとずれる）。守りの場面は `tests/guard_cases.tsv`
- 守りや点検を変えたときは、独立の確認（⑤ の別人確認）を通すまで採用しない。
- 「点検の点検」（壊した複製で落ちるか）は 9/23 にやめた（ユーザーの判断: 費用に見合わない。見つけた不具合 0、自分が嘘の合格を出していた）。

## ⑦ CLI を足すとき

1. `harness/clis.json` に 1 項目足す（`bin` / `rules` / `skills` / `guard_config` / `dialect` / `must_contain` / `worker` / `notes` / `skills_mode`）。
2. 守りの設定ファイルを 1 枚置く。中身は既存と同じ「`harness/guard.py` を正しい dialect で呼ぶ」形。
3. **判定は `guard.py` に足さない。** CLI の違いは設定と dialect（claude / cursor / agy / plain の 4 つの話し方）で吸収する。JS 拡張系は `guard_bridge.mjs` を経由する。
4. `python3 harness/check.py` を回す（`test_wiring.py` が配線を確かめる）。
5. dialect は guard.py が知る 4 つ（claude / cursor / agy / plain）。新しい CLI は、この 4 つのどれかが使えないかを先に探す。どうしても要るときだけ guard.py に dialect を足す。

## ⑧ 太らせないための決まり

- `AGENTS.md` の予算は 60 行 / 6 KB。点検が毎回見る。手順・規範・型は skill か `docs/` に置き、必要になったときだけ読ませる。
- **足すなら消す。** 新しい仕組みを足すときは、代わりに消すものを同じ変更で示す（旧版の反省。hook と adapter が膨らんで破綻した）。
- **役を足さない。** 役は指示役と担い手の 2 つだけ。「調査」「文書」「確認」は役ではなく、依頼書の書き方とギア（③ の 4 つ）で表す。
- **外の物は作り直さない。** 実績のある skill や型はそのまま使う（⑤）。自前の包みは機械の仕事まで（`judgment.py` が見本）。
