# 中継 hub（`harness/hub.py`）の独立の確認

作った側: Opus 5.5（1 段目）と GPT-6 Sol（2 段目 `/run`）。確認: Grok 4.7（xai、T-0925-78、474 秒）。実装を見る前に要求 6 × 2 対以上 + 抜け道 12 を保存してから測った（58 件、ずれ 4）。壊した 3 通りは全部検出。`eval` / `exec` / `os.system` / `shell=True` は 0。`/run` の文は argv か stdin の 1 要素で、`; $(touch …)` は実行されない。

結果: **差し戻し（4 件）。** 指示役の裁定:

| # | 通ってしまった形 | 裁定 |
|---|---|---|
| 1 | 送信箱の `kind=document` の `path` が作業場の外の秘密でも `sendDocument` に渡る | 塞ぐ。作業場の `.loop/dashboard/` の下だけ送る。外なら失敗の印だけ |
| 2 | 同じ `update_id` の `/run` が再配送で二度起動する | 塞ぐ。受信箱と同じく `update_id` で一度だけ |
| 3 | 許可 chat からの転送（`forward_from`）が普通の文として入る | 塞ぐ。転送は捨てる（許可した人が自分で打った物だけ） |
| 4 | `/run ghost 文`（無い名前）が今の相手への依頼になる | 設計どおり残す（第 1 語が作業場名のときだけ宛先。返事に作業場名を出す）。文書に書く |

直しは Opus 5.5（話題対応の統合と一緒に）。再確認は Grok。

## 2 回目（Grok 4.7、T-0925-85、1,487 秒）: 話題・画面・Discord・Slack・`/run` を含む

76 判定、ずれ 14（うち製品の穴 4、裁定どおりの物 1、その他は測り方や仕様の解釈）。壊した 3 通りは全部検出。1 回目の 4 件のうち文書の path と `/run` の重複は直り、転送は一部だけ。

| # | 通ってしまった形 | 裁定 |
|---|---|---|
| 1 | 転送の判定が `forward_from` / `forward_origin` だけ。`forward_date` だけ・`forward_sender_name`・`forward_from_chat`・`is_automatic_forward` は通り、`/run` まで起動した | 塞ぐ。`forward_` で始まる欄か `is_automatic_forward` があれば全部捨てる |
| 2 | `--serve ::ffff:0.0.0.0:0` が `0.0.0.0` で待ち受ける（字面の `0.0.0.0` だけ断っていた） | 塞ぐ。bind する前に住所を解いて、未指定（`0.0.0.0` / `::` / IPv4-mapped）なら断る |
| 3 | 画面の POST は `Origin` の host が `Host` 見出しと一致すれば通る（両方 `evil.example` なら通る） | 塞ぐ。比べる相手は要求の `Host` ではなく **`--serve` で指定した host:port**。加えて画面に乱数の印（CSRF token）を埋め、POST で照合 |
| 4 | `.loop/dashboard` 自体が外への symlink だと外のファイルが送られる | 塞ぐ。`dashboard` の dir も `resolve()` し、作業場の中でなければ送らない |
| — | Discord: `webhook_id` があって `bot` が偽なら許可 ID で通る / Slack: `subtype=bot_message` で `bot_id` が無ければ通る | 塞ぐ（両方 bot として捨てる） |
| — | `--once` は橋の例外で後続が止まる | 直す（橋ごとに try） |

直しは Opus 5.5（T-0925-86、382 秒）: 6 行とも直し、偽 API で 6 件 + 2 件を実測、直しを 1 つずつ戻すと 8 通りとも試験が落ちた。取り込み済み（`b4b7716`）。3 回目の確認は Grok（T-0925-87）。

## 3 回目（Grok 4.7、T-0925-88、986 秒。1 回目の 30 分版は時間切れ）

2 回目の 4+2 件は全部直っていた（転送 8 種・`::ffff:0.0.0.0`・Origin/Host の偽装と印・symlink・bot の判定・`--once`）。壊した 2 通りも検出。
新しく 1 件: **送信箱の行の `thread_id` / `target` / `transport` で送る先を書き換えられる**（作業場の送信箱に細工した行を書けば、別の話題や別のチャンネルへ送れる）。裁定: 塞ぐ。宛先は hub.json（作業場 → 話題 / チャンネル）だけから決め、行の欄では変えない。直しは Opus 5.5（T-0926-89、377 秒）: 宛先を hub.json だけで決める形に書き直し、行の `thread_id` / `target` / `thread` は無視して `hub.log` に `ignored-destination`。Grok の 2 通り + hub.json に無い橋の 1 通りを偽 API で実測、旧 hub.py に戻すと試験が落ちる。取り込み済み（`dbd98da`）。

## 4 回目（Grok 4.7、宛先の再測だけ。25 分）

T-0926-90、658 秒。合格、**閉じてよい**。止める 6 通り（Grok の 2 通り + hub.json に無い橋 / 文書の行に `target` / 作業場名の偽り / 返信先の保存を汚す）と通す 3 通りで、攻撃側の chat・話題・チャンネルへ届いた物 0。`hub.json` は送信の前後で同じ。

残りの 1 件（送信箱の行だけでは再現しない）: `~/.config/harness/hub.json` の返信先に先に `thread=999attack` が書かれていると、行の `chat_id` だけで Discord のその thread へ出る。hub.json は作業場の外（担い手は書けない。守りが作業木の外への書き込みを止める）にある設定なので、**既知の穴として記録し、直さない**。Discord の受信は `thread` を保存しないので、受信箱から入れる道は無い。
