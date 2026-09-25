# 中継（hub）: 1 つのアプリから複数の作業場に指示する（9/25 夜、ユーザーの指示）

ユーザーの言葉: 「外部からメッセージ送信して指示できるの、体験として非常に良かったから、複数種類のワークスペースをアプリから指示できるようにしたい」「複数種類のワークスペースを一つのアプリから管理したい」「すぐに始めて。タイムリミットは明日の午前 7 時。少なくともこれを使って開発が始められる状態にして」

## 形（作業場ではなく、この機械に 1 つ）

Telegram は 1 つの bot の受信を同時に 1 か所でしか受け取れない。だから **受け取るのは hub だけ**。各作業場の見張りは、hub があるときは受信せず、送る物を自分の送信箱に書く。hub がそれを bot へ送り、bot からの文を宛先の作業場の受信箱へ振り分ける。作業場側の受信箱・`brief`・ダッシュボードは今のまま。

```
Telegram bot ──受信── hub（この機械に 1 本。~/.config/harness/hub.json）──振り分け──▶ 作業場 A の .loop/inbox.jsonl
             ◀─送信──          ◀── 作業場 A の .loop/outbox.jsonl ◀── 見張り（要点・/dash の返事）
                                ──/run──▶ 作業場 A の指示役を headless で起動（2 段目）
```

| 物 | 置き場 | 何 |
|---|---|---|
| `harness/hub.py` | 配布物 | `python3 harness/hub.py [--hours 8]` で 1 本だけ動く。token は全体の置き場（`~/.config/harness/telegram.env`）。作業場の一覧は `~/.config/harness/hub.json`（`{"workspaces": {"harness": {"path": "/mnt/d/.../multiagent-best-template", "leader": {"cli": "claude", "model": "claude-opus-5-5"}}, ...}, "current": "harness"}`） |
| 送信箱 | 各作業場の `.loop/outbox.jsonl` | 見張りが書く（要点 / `/dash` の返事 = ファイルの path / `/status`）。hub が読んで送り、送った行に印を付ける |
| 受信箱 | 各作業場の `.loop/inbox.jsonl` | hub が `inbox.append` で書く（今と同じ形） |
| 記録 | `~/.config/harness/hub.log` | 受けた命令と振り分け先を 1 行ずつ（本文は先頭 80 字） |

## Telegram からの書き方（1 段目）

- `/ws` → 作業場の一覧と「今の相手」。`/ws <名前>` → 今の相手を切り替える（hub.json の `current` に保存）
- 普通の文 → 今の相手の受信箱へ。`@<名前> 文` → 切り替えずにその作業場へ 1 通
- `/dash` `/status` → 今の相手の物（`@<名前> /dash` も可）。作業場の見張りが送信箱に書き、hub が送る
- 各作業場からの要点は `[<名前>]` を頭に付けて届く

## `/run`（2 段目: 外から仕事を始める）

- `/run <名前> <依頼の文>`（名前を省くと今の相手）→ hub がその作業場で **指示役を headless で起動**する。起動の形は `harness/clis.json` の各 CLI の `leader`（新設。`worker` と同じ形で、`HARNESS_ROLE` を付けない）。依頼の文は前置き（「あなたは指示役。AGENTS.md と leader skill に従う。担い手へ回し、終わったら要点を 10 行以内で出す」）を付けて渡す
- 指示役は `HARNESS_UNATTENDED` 相当（既定で「聞く」は止まって判断カード）。終わったら hub が最後の出力の要点を `[<名前>]` 付きで送る。途中の担い手の終了は、見張りの要点として届く
- 同じ作業場で `/run` は同時に 1 本まで（走っていれば「実行中」と返す）。`/stop <名前>` で止める
- **受け付けるのは許可した chat ID の人だけ。** 文は指示役への依頼として渡すだけで、hub が shell で実行することは無い。全部 `hub.log` に残す

## 基準（Fable 5.1 が判定）

1. 2 つの作業場（この repo と `dist/test-project`）を hub.json に登録し、Telegram から `/ws`・切り替え・`@名前 文`・`/dash`・`/status` が両方で通る（本物）
2. 作業場の見張りは hub があるとき Telegram に触らない（`getUpdates` の衝突が無い）。hub が無ければ今までどおり自分で送受信する
3. `/run harness <文>` で指示役が起動し、担い手に回って、要点が Telegram に返る（本物で 1 件）
4. 許可外の chat ID からの `/run` は捨てて記録だけ残る。`/run` の文が shell に渡る道が無い（独立の確認）
5. `python3 harness/check.py` が通る。試験は偽の API と偽の CLI
6. `docs/HARNESS.md` に使い方（hub.json の書き方、起動、Telegram の書き方）

## 3 段目（9/25 夜、Telegram からのユーザーの言葉で方向を直す）

「作業場 2 つじゃなくて、作業場が何個になってもこのチャット欄で会話できるようにしたい。どのワークスペースの AI に送ろうかとか考えなくていいようにしたい。会話が勝手に分岐するとか、会話欄が複数あって、受信箱から選んで受けられるとか。Telegram に限らず、どの通信手段でもできるように。HTML ダッシュボードを改良してこれができるようにするのはどうか。送信先がひとつだけだと、受信側も混乱する。」

決めた形（2 本立て。どちらも hub の同じ受信箱・送信箱の上に載る）:

1. **Telegram は「話題（forum topics）」で作業場ごとに会話欄を分ける。** 人が Telegram で「グループ」を作り、設定で「トピック」を有効にし、bot を管理者（トピックの管理を許可）で入れる。hub は作業場ごとに話題を自動で作り（`createForumTopic`、名前は作業場名）、届いた文は `message_thread_id` でどの作業場か決まる（`/ws` も `@名前` も要らない）。作業場からの要点・返事・`/run` の結果はその話題に返す。`hub.json` に `chat_id`（グループ）と `topics`（作業場名 → thread id）を保存。話題の無いチャット（今の私信）は今までどおり `/ws` で動く（後方互換）。**作業場が増えたら話題が増えるだけ。**
2. **HTML の hub 画面（どの通信手段でも同じ）。** `hub.py --serve <host>:<port>` で、作業場の一覧 → 作業場ごとの会話（受信箱と送信箱を時系列で 1 本に）→ 返事を書く欄（POST。同じ私設の網の中だけ）。返事は hub が受信箱に入れる（Telegram から来た物と同じ扱い）。`/run` も画面の欄から送れる。これが「通信手段に依らない 1 つの受信箱」。Telegram / Slack / Discord は、この画面の写しを各アプリの会話欄に映す物、という位置づけ。

基準に足す: 7. 話題つきグループで、作業場 3 つ（もう 1 つは使い捨て）の会話欄が自動で分かれ、`/ws` を打たずに各作業場と往復できる（本物）。8. hub 画面で作業場の会話を読み、返事を書くと受信箱に入り、`brief` に出る。

## 通信手段を足す形（9/25 夜、ユーザー:「Discord とか Slack とか言ってたと思うけど。一通り実装して欲しい」）

橋は `harness/bridge/<name>.py` で、同じ 3 つの関数を持つ: `configured()` / `send(text, *, target, thread=None)` と `send_document(path, caption, *, target, thread=None)` / `poll() -> list[dict]`（届いた文を `{"text", "chat_id"（送り主の ID）, "target"（チャンネルなど）, "thread", "update_id"（重複除け）}` で返す）。token は `~/.config/harness/<name>.env`（守りの秘密。`discord.env` `slack.env` を一覧に足した）。**公開 URL は使わない**（Discord は REST を数秒ごとに読む。Slack は Web API を数秒ごとに読む。WebSocket も要らない = 標準ライブラリだけ）。
hub は `hub.json` の `transports`（`{"telegram": {...}, "discord": {"guild_id": ..., "channels": {作業場: channel_id}}, "slack": {"channels": {作業場: channel_id}}}`）を見て、有効な橋を全部、同じ受信箱・送信箱につなぐ。作業場ごとの会話欄は、Telegram = 話題、Discord = テキストチャンネル（bot が作る）、Slack = チャンネル（bot が作る。無理なら 1 チャンネルに `[名前]`）。人向けの手順（token の取り方）は `docs/HARNESS.md`。
