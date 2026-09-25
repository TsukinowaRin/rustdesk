---
member: grok47
hands: workspace
fanout: 1
minutes: 30
independent_of: T-0925-77
---
# 中継 hub（`harness/hub.py`）の独立の確認

## 目的
Opus 5.5（1 段目）と GPT-6 Sol（2 段目 `/run`）が作った hub を、別の会社（xai）のあなたが、実装を読む前に対を書いてから確かめる。**外から届く文が仕事を始める入口**なので、守りが要。**直さない。** 書いてよいのは `EXPECTATIONS.md` と `REPORT.md` だけ。作法は `.agents/skills/independent-check/SKILL.md`。**網に出ない**（Telegram の API は偽の物に差し替える。`tests/test_hub.py` の偽の API の作りを参考に。本物の `~/.config` と `.loop/` は触らず、`HARNESS_CONFIG_HOME` と `HARNESS_LOOP_DIR` で使い捨ての場所を指す）。

## 要求（正本 `docs/design/HUB.md`。これだけを元に対を書く）
1. 受け付けるのは許可した chat ID（`TELEGRAM_CHAT_IDS`）の人だけ。許可外の文は捨てて `hub.log` に `dropped` だけ残す（本文は残さない）
2. `/ws` `/ws <名前>` `@<名前> <文>` 普通の文 `/dash` `/status` が、正しい作業場の受信箱（`<path>/.loop/inbox.jsonl`）か送信箱の合図に入る。知らない名前は「知らない作業場」と返す
3. `/run [<名前>] <文>`: その作業場の `leader`（`hub.json`）の CLI を **argv のリストで** 起動する（`shell=True` は無い）。文は argv の 1 要素か stdin として渡り、`;` `$(…)` `|` などを含んでいても実行されない。環境は `HARNESS_ROLE` 無し、`HARNESS_UNATTENDED=1`。同じ作業場で同時 1 本まで。`/stop` で止まる。終了で要点が送信箱に入る
4. 送信箱の行は `[<名前>]` 付きで送られ、送った物に印が付く（二重に送らない）
5. `hub.py` が文を評価・実行する所（`eval` `exec` `os.system` `subprocess` に文を渡す所）が無い。`/run` の文が hub.json の `path` や `leader` を変えられない
6. hub.json が無いときは案内を出して終了 1。token が無いときも 1 行で止まる

## 順番
1. `EXPECTATIONS.md`（要求ごとに 2 対以上 + 抜け道の候補 8 つ以上。例: `/run` の文に `\n` や制御文字 / `@名前` に `../` / `/ws` に存在しない名前 / 許可 chat からの転送メッセージ / 同じ update_id の再配送 / 送信箱の `path` に作業場の外のファイル（秘密）を書いたら送られるか / `/run` の名前に hub.json に無い作業場 / `leader` の cli が clis.json に無い）
2. 保存してから `harness/hub.py` と `tests/test_hub.py` を読む
3. 偽の API と偽の CLI で測る（`tests/test_hub.py` の作りを流用してよいが、自分の対で）
4. `REPORT.md` に合否と証拠。30 行以内。通ってしまった物は最上位に

## 触ってよい場所
`EXPECTATIONS.md` と `REPORT.md` だけ（測定用の一時ファイルは作業木の中の `tmp-eval/` に作り、終わったら消す）。
