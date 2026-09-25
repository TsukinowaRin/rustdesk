# 独立の確認: hub（harness/hub.py）

正本は `docs/design/HUB.md` と依頼書の要求 1〜6。実装を読む前に書いた。測定は偽の Telegram API と偽の CLI。本物の `~/.config` と `.loop/` は触らない（`HARNESS_CONFIG_HOME` と `HARNESS_LOOP_DIR` で使い捨て）。

固定: `git rev-parse HEAD` = `039e5973ee847518c014f20ee823502511a28015`。`git status --short` は空。

---

## 要求 1: 許可 chat ID だけ受け付ける

### 通す
- 入力: `TELEGRAM_CHAT_IDS` に入っている chat ID から `/ws`（または普通の文）。
  期待: 処理する。受信箱か送信箱の合図に入る。`hub.log` に振り分け先が残る。
  なぜ: 正本「受け付けるのは許可した chat ID の人だけ」。
- 入力: 許可 chat から `/run <名前> <文>`。
  期待: 捨てない。作業場の leader 起動、または「実行中」などの正当な返事。
  なぜ: 許可した人の `/run` は 2 段目の入口。

### 止める
- 入力: `TELEGRAM_CHAT_IDS` に無い chat ID から `/run harness 何か`（本文に秘密めいた長い文）。
  期待: 仕事を始めない。受信箱に書かない。leader を起動しない。Telegram へ返事を送らない。`hub.log` に `dropped` だけ。本文は `hub.log` に残さない。
  なぜ: 依頼「許可外の文は捨てて `hub.log` に `dropped` だけ残す（本文は残さない）」。正本は本文を先頭 80 字残すとあるが、許可外は依頼の方が厳しいので本文なし。
- 入力: 許可外 chat から普通の文・`/ws`・`/dash`・`/status`・`@名前 文`。
  期待: いずれも捨てる。受信箱・`current`・送信箱に触れない。`hub.log` は `dropped` のみ（本文なし）。
  なぜ: 許可は命令の種類で分けない。入口そのものを閉じる。

---

## 要求 2: 振り分け（`/ws` `/ws <名前>` `@<名前> <文>` 普通の文 `/dash` `/status`）

前提の作業場: hub.json に `harness` と `demo` の 2 つ。`current` は `harness`。各作業場に `.loop/`。

### 通す
- 入力: 許可 chat から `/ws`。
  期待: 登録名の一覧と「今の相手」が Telegram へ返る。受信箱には書かない。
  なぜ: 正本「`/ws` → 作業場の一覧と今の相手」。
- 入力: `/ws demo`。続けて普通の文 `hello`。
  期待: hub.json の `current` が `demo` になる。`hello` は `demo` の `.loop/inbox.jsonl` に 1 行。`harness` の受信箱は空のまま。
  なぜ: 正本「`/ws <名前>` → 今の相手を切り替える。普通の文 → 今の相手の受信箱」。
- 入力: `current=harness` のまま `@demo ping`。
  期待: `demo` の受信箱に `ping`。`current` は `harness` のまま。`harness` の受信箱は空。
  なぜ: 正本「`@<名前> 文` → 切り替えずにその作業場へ 1 通」。
- 入力: `@demo /dash` および今の相手への `/dash` `/status`。
  期待: 宛先作業場の送信箱の合図（見張りが書く入口）に入る。別作業場の送信箱・受信箱は触らない。
  なぜ: 正本「`/dash` `/status` → 今の相手の物。`@<名前> /dash` も可。見張りが送信箱に書き hub が送る」。

### 止める
- 入力: `/ws ghost` または `@ghost 文`（hub.json に無い名前）。
  期待: Telegram へ「知らない作業場」と返す。どの受信箱にも書かない。`current` は変わらない。
  なぜ: 依頼「知らない名前は『知らない作業場』と返す」。
- 入力: `@../etc/passwd 文` や `@harness/../demo 文` のような path まがいの名前。
  期待: 知らない作業場として返す。hub.json の `path` の外のファイルを開かない。受信箱を作業場の外に作らない。
  なぜ: 名前は登録キーであり、ファイル path ではない。

---

## 要求 3: `/run` と `/stop`

前提: 偽の leader CLI を `clis.json` の `leader` に指す。本物の CLI は起動しない。

### 通す
- 入力: `/run demo 仕事して`（または `/run 仕事して` で今の相手）。
  期待: その作業場の `leader` を **argv のリスト**で起動する（`subprocess` に `shell=True` が無い）。文は argv の 1 要素か stdin のどちらでもよいが、シェルに渡さない。環境に `HARNESS_ROLE` が無い。`HARNESS_UNATTENDED=1` がある。偽 CLI が終了したら要点が送信箱（または Telegram へ `[demo]` 付き）に入る。
  なぜ: 正本「指示役を headless で起動。`HARNESS_ROLE` を付けない。`HARNESS_UNATTENDED` 相当。終わったら要点を `[<名前>]` 付きで送る」。依頼「argv のリスト。文は argv の 1 要素か stdin」。
- 入力: 同じ作業場で `/run` が走っているあいだにもう一度 `/run`。別作業場への `/run` は空いている。
  期待: 同じ作業場は「実行中」と返して 2 本目を起動しない。別作業場は起動してよい。走っているあいだに `/stop`（または `/stop <名前>`）で止まり、以降その作業場はまた `/run` できる。
  なぜ: 正本「同じ作業場で同時 1 本まで。`/stop <名前>` で止める」。

### 止める
- 入力: `/run demo 'touch /tmp/pwned; echo hi'` および `/run demo '$(touch /tmp/pwned)'` および `/run demo 'echo a | tee /tmp/pwned'`。
  期待: 偽 CLI の argv または stdin に文字列として渡るだけ。シェルが `;` `$(…)` `|` を解釈しない。`/tmp/pwned` は作られない。`os.system` や `shell=True` で文を渡さない。
  なぜ: 依頼「`;` `$(…)` `|` などを含んでいても実行されない」。正本「hub が shell で実行することは無い」。
- 入力: `/run ghost 文`（hub.json に無い名前）。
  期待: 起動しない。「知らない作業場」と返す。
  なぜ: 抜け道候補「`/run` の名前に hub.json に無い作業場」。知らない先でプロセスを起こさない。

---

## 要求 4: 送信箱は `[<名前>]` 付きで一度だけ送る

### 通す
- 入力: `demo` の `.loop/outbox.jsonl` に未送信の行が 1 本ある状態で hub の送信処理を 1 回回す。
  期待: Telegram へ送る本文の先頭が `[demo]`。送った行に印が付く（再読しても送らない）。
  なぜ: 正本「各作業場からの要点は `[<名前>]` を頭に付けて届く。hub が読んで送り、送った行に印を付ける」。
- 入力: 同じ未送信行がある状態で送信処理を 2 回回す。
  期待: Telegram への送信は 1 回だけ。2 回目は送らない。
  なぜ: 依頼「送った物に印が付く（二重に送らない）」。

### 止める
- 入力: 送信箱の行の `path`（または本文がファイル path を指す形）が作業場の外（例: 偽 config の外にある秘密ファイル）を指す。
  期待: そのファイルの中身を読んで Telegram へ送らない。送るなら作業場内の送信箱の行の本文だけ。
  なぜ: 抜け道候補「送信箱の `path` に作業場の外のファイル（秘密）を書いたら送られるか」。hub は中継であり、任意 path の読み出し器ではない。
- 入力: 印付きの行だけが送信箱にある。
  期待: 何も送らない。
  なぜ: 二重送信の禁止の裏側。

---

## 要求 5: hub は文を評価・実行しない。`/run` の文で設定を書き換えない

### 通す
- 入力: ソース上、`eval` `exec` `os.system` が無い。`subprocess` は leader の固定 argv（`clis.json` の `leader`）だけ。ユーザー文は argv の 1 要素か stdin。
  期待: `harness/hub.py` を読んで、ユーザー文を `eval`/`exec`/`os.system`/`shell=True` に渡す箇所が 0。
  なぜ: 依頼「`hub.py` が文を評価・実行する所が無い」。
- 入力: `/run demo` の文に JSON や path を混ぜたもの（例: `{"path":"/tmp/evil","leader":{...}}` や `../../.config/harness/hub.json`）。
  期待: hub.json の `path` も `leader` も変わらない。作業場の root も変わらない。起動 cwd は登録済み `path`。
  なぜ: 依頼「`/run` の文が hub.json の `path` や `leader` を変えられない」。

### 止める
- 入力: `leader.cli` が `clis.json` に無い名前。
  期待: 起動しない。不明なバイナリを `argv[0]` にしない。エラーを返す。
  なぜ: 抜け道候補「`leader` の cli が clis.json に無い」。許可した CLI 以外を起こさない。
- 入力: ユーザー文を `python -c` や `bash -c` の次の引数にする、または `shlex.split` して argv を増やす。
  期待: そのような組み立てが無い。文は常に 1 要素（または stdin のバイト列）。
  なぜ: 1 要素でなければ `;` や改行で argv を分裂させられる。

---

## 要求 6: 設定が無いときの止まり方

### 通す
- 入力: `HARNESS_CONFIG_HOME` の下に hub.json が無い状態で `python3 harness/hub.py` を起動。
  期待: 案内（hub.json の書き方に触れる文）を標準エラーか標準出力に出して、終了コード 1。プロセスはループに入らない。
  なぜ: 依頼「hub.json が無いときは案内を出して終了 1」。
- 入力: hub.json はあるが token が無い（`telegram.env` 無し、環境変数の token も無し）。
  期待: 1 行で止まり、終了コードは 0 以外。getUpdates を呼ばない。
  なぜ: 依頼「token が無いときも 1 行で止まる」。

### 止める
- 入力: hub.json が壊れている（JSON でない、`workspaces` が無い、`path` が空）。
  期待: 作業を始めない。終了コード 0 以外。勝手に作業場を作らない。
  なぜ: 入口の設定が読めないのに受信を始めると、振り分け先が不定になる。
- 入力: token が空文字 `TELEGRAM_BOT_TOKEN=`。
  期待: token 無しと同じ。1 行で止まる。
  なぜ: 空文字は「ある」と数えない。

---

## 抜け道の候補（8 つ以上。実装を読む前）

1. `/run` の文に `\n` や制御文字（NUL、ANSI CSI）。argv が割れる、ログや Telegram で別命令に見える、偽 CLI の引数が増える。
2. `@名前` に `../` や絶対 path。受信箱を作業場の外に書く。
3. `/ws` に存在しない名前。`current` が壊れる、または空の作業場ができる。
4. 許可 chat からの転送メッセージ（forward）。中の from.id は許可外でも、外側の chat.id が許可なら通るか。転送元の本文で `/run` されると、許可していない人の文が入口になる。
5. 同じ `update_id` の再配送。受信箱へ二重に書く、`/run` を二重起動する。
6. 送信箱の `path` に作業場の外のファイル（秘密）を書く。hub が読んで Telegram へ送る。
7. `/run` の名前に hub.json に無い作業場。知らない path でプロセスを起こす。
8. `leader` の cli が `clis.json` に無い。任意コマンドが argv[0] になる。
9. `/run` の文で hub.json の `path`/`leader`/`current` を上書きしようとする（要求 5 と重なる）。
10. 許可外 chat の本文が `hub.log` に残る（先頭 80 字でも残ると秘密がログに出る）。正本は許可した文の 80 字、依頼は許可外は本文なし。
11. `TELEGRAM_CHAT_IDS` を空または未設定のまま起動。全員許可になるか、誰も許可しないか。前者なら入口が開く。
12. 作業場名の大文字小文字・前後空白・ゼロ幅文字。登録名と別物なのに受信箱 path がずれる。

各候補の期待: 仕事を始めないか、登録済み作業場の中だけで扱う。秘密ファイルを読まない。同じ update を二重に実行しない。許可外の本文をログに残さない。
