# 対（実装を読む前に書いた）

正本は `docs/design/HUB.md` と依頼書の要求だけ。実装は未読。
測るのは 3 回目の範囲（2 回目の 6 件の再測 + 新しい抜け道 7 件）。要求 1〜6 の対は基準として残す。

用語: 「許可 chat」は `TELEGRAM_CHAT_IDS` に入っている chat ID。「捨てる」は受信箱に書かず、CLI を起動せず、`hub.log` に `dropped` だけ残し本文を残さない。

## 要求 1 — 許可した chat だけ

### 止める 1-S1
- 入力: 許可外の chat から `/run alpha id` と普通の文 `secret-body-1s1`
- 期待: どの作業場の受信箱にも残らない。CLI は起動しない。`hub.log` に `dropped` があり、`secret-body-1s1` と `id` は無い
- 理由: 許可外は捨て、記録に本文を残さない

### 止める 1-S2
- 入力: `from.id` は許可リストに見えるが、届いた場の `chat.id` は許可外
- 期待: 1-S1 と同じ（捨てる）
- 理由: 見るのは届いた場の chat ID。送り主の ID だけでは通さない

### 通す 1-P1
- 入力: 許可 chat から普通の文 `hello-1p1`（今の相手は alpha）
- 期待: `alpha` の `<path>/.loop/inbox.jsonl` にその文が入る。beta には入らない
- 理由: 許可した人の普通の文は、今の相手の受信箱へ

### 通す 1-P2
- 入力: 許可 chat から `/status`
- 期待: 今の相手の受信箱か、その作業場の送信箱の合図にだけ入る
- 理由: `/status` は今の相手の物

## 要求 2 — 振り分け

### 通す 2-P1
- 入力: `/ws`
- 期待: 返事に登録した作業場の名前と、今の相手が出る。受信箱は増えない
- 理由: 一覧と今の相手を返す命令

### 通す 2-P2
- 入力: `/ws beta`（今は alpha）
- 期待: `hub.json` の `current` が `beta` になる。返事はその切り替え。alpha の受信箱は増えない
- 理由: 名前を指定した切り替えは現在の相手を保存する

### 通す 2-P3
- 入力: `@beta only-beta`（current は alpha のままにする操作の後）
- 期待: beta の受信箱に `only-beta`。alpha には入らない。`current` は alpha のまま
- 理由: `@名前` は切り替えずに 1 通だけ

### 通す 2-P4
- 入力: `@beta /dash`
- 期待: beta 側の受信箱か送信箱の合図に `/dash` が入る。alpha には入らない
- 理由: `@名前 /dash` はその作業場の物

### 止める 2-S1
- 入力: `/ws nosuch`
- 期待: 返事に「知らない作業場」と `nosuch` がある。`current` は変わらない。どの受信箱も増えない
- 理由: 知らない名前。裁定は「設計どおり残す。返事に作業場名」

### 止める 2-S2
- 入力: `@nosuch hello-2s2`
- 期待: 返事に「知らない作業場」。`hello-2s2` はどの受信箱にも無い
- 理由: 知らない宛先に文を置かない

## 要求 3 — `/run`

### 通す 3-P1
- 入力: 許可 chat から `/run beta please-work`
- 期待: `hub.json` の beta の `leader` の CLI が起動する。`shell=True` は無い（argv のリスト）。文は argv の 1 要素か stdin。環境に `HARNESS_ROLE` は無く、`HARNESS_UNATTENDED=1` がある。作業場は beta の `path`
- 理由: 指示役を headless で起動する。文はデータとして渡す

### 止める 3-S1
- 入力: `/run beta x; echo PWNED $(touch /tmp/hub-pwn) | cat`
- 期待: `echo` も `touch` も `cat` も実行されない。文字列はそのまま argv の 1 要素か stdin。`/tmp/hub-pwn` はできない
- 理由: shell に渡る道が無い

### 止める 3-S2
- 入力: beta で `/run` が走っているあいだ、もう一度 `/run beta second`
- 期待: 返事は「実行中」。プロセスは 1 本のまま
- 理由: 同じ作業場で同時 1 本

### 通す 3-P2
- 入力: 走っている beta に `/stop` または `/stop beta`
- 期待: そのプロセスが止まる。2 本目は残らない
- 理由: `/stop` で止める

### 通す 3-P3
- 入力: `/run` したプロセスが終了コード 0 で終わる
- 期待: その作業場の送信箱に要点の行が入る（あとで `[beta]` 付きで送れる形）
- 理由: 終了で要点が送信箱に入る

### 止める 3-S3
- 入力: `/run nosuch anything`
- 期待: 「知らない作業場」。CLI は起動しない
- 理由: 名前が `hub.json` に無い

## 要求 4 — 送信箱

### 通す 4-P1
- 入力: alpha の送信箱に未送信の 1 行 `note-4p1`
- 期待: 許可 chat へ送る文が `[alpha]` で始まるか、`[alpha]` を含む。本文 `note-4p1` を含む。送った行に印が付く
- 理由: 名前を付けて送り、印を付ける

### 止める 4-S1
- 入力: 4-P1 のあと、同じ送信箱でもう一度送る処理
- 期待: `note-4p1` は 2 回目は送られない
- 理由: 二重に送らない

### 通す 4-P2
- 入力: alpha と beta の両方に未送信行
- 期待: それぞれ `[alpha]` と `[beta]`。取り違えない
- 理由: 作業場ごとに名前を付ける

## 要求 5 — 文を評価・実行しない

### 止める 5-S1
- 入力: `hub.py` のソース（測定時に読む）
- 期待: 届いた文を `eval` / `exec` / `os.system` に渡す所が無い。`subprocess` に文を shell 文字列として渡す所が無い。`shell=True` が無い
- 理由: hub は文を実行しない

### 止める 5-S2
- 入力: `/run alpha ` の文が `{"path":"/tmp/elsewhere","leader":{"cli":"bash","model":"x"}}` の形で、hub.json の書き換えを頼む
- 期待: 実行後も alpha の `path` と `leader` は測定前と同じ。`/tmp/elsewhere` は起動されない
- 理由: `/run` の文は `path` も `leader` も変えられない

### 止める 5-S3
- 入力: `leader.cli` が `clis.json` に無い名前
- 期待: その CLI は起動しない。shell にも落ちない
- 理由: 起動してよいのは登録済み CLI の argv だけ

## 要求 6 — 設定が無いとき

### 止める 6-S1
- 入力: `hub.json` が無い（使い捨ての配置先）
- 期待: 終了コード 1。案内の文が出る（何を置くかが読める）。受信は始まらない
- 理由: 一覧が無ければ案内して終了 1

### 止める 6-S2
- 入力: `hub.json` はある。token が無い
- 期待: 1 行で止まる（2 行以上の traceback ではない）。終了コードは 0 以外
- 理由: token が無いときは 1 行で止まる

### 通す 6-P1
- 入力: `hub.json` と token がある。`--once` で空の更新
- 期待: 6-S1 の案内では終わらない
- 理由: 設定が揃っていれば受信の処理に入る

## 2 回目の再測（直ったと期待する）

### R1 転送の全種（止める）
許可 chat から、本文 `fwd-secret-R1` を含む `/run alpha fwd-secret-R1`。次のどれが付いていても捨てる。
1. `forward_origin.type=user`
2. `forward_origin.type=hidden_user`
3. `forward_origin.type=chat`
4. `forward_origin.type=channel`
5. 古い `forward_from`
6. 古い `forward_from_chat`
7. `forward_sender_name`
8. `is_automatic_forward: true`
- 期待: 受信箱に入らない。CLI は起動しない。`hub.log` に `dropped`。`fwd-secret-R1` はログに無い
- 理由: 転送は本人がその場で打った文ではない。全種を落とすのが 2 回目の直し

### R1b 転送ではない文（通す）
- 入力: 同じ許可 chat、転送の印が無い `plain-R1b`
- 期待: 今の相手の受信箱に入る
- 理由: 通常の文まで捨てない

### R2 `::ffff:0.0.0.0`（止める）
- 入力: `--serve [::ffff:0.0.0.0]:<空きポート>` または `::ffff:0.0.0.0:<port>`
- 期待: 待受を始めない。終了コードは 0 以外。全インターフェースでは開かない
- 理由: `0.0.0.0` と同じ「全公開」を、IPv4 射影の書き方で通さない

### R2b ループバック（通す）
- 入力: `--serve 127.0.0.1:<port>`
- 期待: 待受が始まる（接続できるか、起動メッセージのあとプロセスが残る）
- 理由: 自分の機械だけは許可

### R3 Origin と Host の偽装（止める）
画面は `127.0.0.1:<port>`。CSRF の印（token）が要る前提。
1. `Origin: http://evil.example` かつ `Host: 127.0.0.1:<port>`、印なし → 403。受信箱は増えない
2. `Origin: http://evil.example` かつ `Host: evil.example`、印なし → 403
3. `Origin` は正しいが印が違う、または印が無い → 403
4. 正しい `Origin` と正しい印、本文 4001 字 → 413。受信箱は増えない
- 理由: Origin 不一致は 403。2 回目で CSRF の印が入った。4000 字超は 413。本文は shell に渡さない

### R3b 正しい画面の返事（通す）
- 入力: `Origin: http://127.0.0.1:<port>`、正しい印、本文 `screen-ok-R3b`（4000 字以内）
- 期待: 403 でも 413 でもない。その作業場の受信箱に `screen-ok-R3b` が入る。shell のプロセスは増えない
- 理由: 同じ私設の網からの返事は受信箱へ。`/run` を画面から送るのは設計どおり（この対の本文は普通の文）

### R4 `dashboard` ディレクトリが symlink（止める）
- 入力: 画面用の `dashboard` ディレクトリを、作業場の外のディレクトリへの symlink にする。中に `secret-R4.txt`（中身 `secret-body-R4`）を置く。`GET /` と、そのファイルに届く URL
- 期待: `secret-body-R4` は返らない。待受を拒否するか、そのファイルは 404
- 理由: 画面のディレクトリを差し替えて、外のファイルを配らない

### R5 Discord `webhook_id` と Slack `bot_message`（止める）
- 入力: 許可した人の ID に見える Discord メッセージに `webhook_id` がある。本文 `disc-wh-R5`
- 期待: 受信箱に入らない
- 入力: Slack の `subtype=bot_message`。本文 `slack-bot-R5`。ユーザー欄は許可 ID
- 期待: 受信箱に入らない
- 理由: bot 自身と、bot に見える投稿は捨てる。webhook と bot_message はその穴

### R5b 人の発言（通す）
- 入力: Discord は許可 ID、`webhook_id` なし、チャンネルは対応表にある、本文 `disc-ok-R5b`。bot 自身の ID ではない
- 期待: そのチャンネルの作業場の受信箱に入る
- 入力: Slack は許可 ID、`subtype` なし、対応チャンネル、本文 `slack-ok-R5b`
- 期待: 同様に入る
- 理由: 許可した人の、対応する会話欄の文は通す

### R6 `--once` の例外（止める）
- 入力: `--once` で、橋が例外を出す更新、または本文が文字列でない更新。近くに危険な文字列 `once-secret-R6` と `$(touch /tmp/hub-once-R6)` を置く
- 期待: 未捕捉の Traceback で本文を出さない。受信箱に入らない。CLI は起動しない。`/tmp/hub-once-R6` はできない。終了コードは 0 以外か、例外を捕まえて 1 で終わる
- 理由: 例外が、落としたはずの文の実行や、本文の漏えいにつながらない

## 3 回目の新しい抜け道（前回と別の形）

### N1 `X-Forwarded-Host` で Origin を合わせる（止める）
- 入力: 待受は `127.0.0.1`。`POST /ws/alpha/reply`。`Origin: http://evil.example`。`X-Forwarded-Host: evil.example`。`Forwarded: host=evil.example`。印は無い、または転送ヘッダに合わせた印。本文 `xfh-secret-N1`
- 期待: 403。受信箱に `xfh-secret-N1` は無い
- 理由: クライアントが付ける転送ヘッダで、許可する Origin を広げない

### N2 対応表に無いチャンネル（止める）
- 入力: Discord。許可した人。チャンネル ID は `channels` に無い。本文 `unmap-disc-N2`。`current` は alpha
- 期待: alpha にも他の作業場にも受信箱へ入らない
- 入力: Slack で同じ。本文 `unmap-slack-N2`
- 期待: 同じ
- 理由: 作業場はチャンネルで決まる。決まらなければ `current` に落とさない

### N3 送信箱の行が宛先を上書き（止める）
- 入力: alpha の送信箱の行に、本文 `out-N3` に加えて、別の `chat_id` と別の `thread`（beta の話題 ID や許可外 chat）を書く
- 期待: 送る先は alpha 用に設定した chat と話題だけ。許可外 chat にも beta の話題にも送らない。本文は `[alpha]` 付き
- 理由: 送信箱の中の宛先フィールドで、他の会話欄や外部へ出さない

### N4 画面の path に `..`（止める）
- 入力: 正しい Origin と正しい印で `POST /ws/..%2fbeta/reply` と `POST /ws/alpha%2f..%2fbeta/reply`。本文 `trav-N4`
- 期待: beta の受信箱に `trav-N4` は無い。作業場の外のパスにも書かない。404 か 400 か 403
- 理由: 名前の符号化で、別の作業場や外へ書かない

### N5 送り主がいない（止める）
- 入力: 許可 chat。`from` が無い。`sender_chat` だけがある。本文 `/run alpha nosender-N5`
- 期待: 捨てる。CLI は起動しない。ログに `nosender-N5` は無い
- 理由: 人の ID が取れない投稿は許可した人の文ではない

### N6 引用の中だけが命令（止める）
- 入力: 許可 chat。本文は `just-hi-N6`。`reply_to_message.text` が `/run alpha quoted-N6`
- 期待: 起動しない。受信箱に入るなら `just-hi-N6` だけ。`quoted-N6` は命令にしない
- 理由: 見るのはその投稿の本文。引用を命令にしない

### N7 未指定アドレスの別表記（止める）
- 入力: `--serve [::]:<port>` と `--serve :::<port>`（IPv6 の未指定）
- 期待: R2 と同じ。待受しない。終了コードは 0 以外
- 理由: `0.0.0.0` と同じ全公開を、`::` では通さない

## 測らない（時間のため依頼書が外した）

要求 1〜6 の対は基準。3 回目の実測は R1〜R6 と N1〜N7 だけ。
