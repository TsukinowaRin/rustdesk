# 期待（実装を読む前）

対象: 中継 hub の送信先。依頼は T-0926-90。固定: `HEAD dbd98da8c4382b76397e42062b0ed634232f271f`、`git status --short` は空（このファイルを書く前）。

裁定（前回の残り 1 件）: 宛先は `hub.json` だけから決める。送信箱の行の欄は無視し、`hub.log` に `ignored-destination` と残す。

## 測る世界（期待側で決めた配置）

- 作業場 `alpha` と `beta`。送信箱は、特に書かない限り `alpha` の `.loop/outbox.jsonl`。
- Telegram: グループ `chat_id=-100`。話題は `alpha=11`、`beta=22`。
- Discord: `alpha` のチャンネル `111alpha`、`beta` は `222beta`。
- Slack: `alpha` は `Salpha`、`beta` は `Sbeta`。
- 攻撃側の値: `chat_id=99999`、`thread_id=102`、`target=999attack`、橋の名前 `matrix`、部屋 `evil-room`。これらは `hub.json` に無い。

## 数え方（先に固定）

- **通った**: 本文が、攻撃側の chat / 話題 / チャンネル / `hub.json` に無い橋 / 偽った作業場の宛先へ届く。または、送ったあと `hub.json` の `chat_id`・話題・チャンネル・`current` が攻撃側の値に変わる。または、接頭が別の作業場名（`[beta]`）になる。
- **合格**: 届く先は、その送信箱の作業場について `hub.json` に書いてある先だけ。行の欄では変わらない。
- `ignored-destination` がログに無いのは記録のずれ。届く先が上の合格なら、通ったには数えない。閉じる判定は「通ったが 0」。

## 止める（再測 2）

### A 再測: `chat_id=99999` と `thread_id=102`

- 入力: `alpha` の行。本文 `out-A`。`chat_id=99999`。`thread_id=102`。
- 期待: `99999` へは 0 通。話題 `102` へは 0 通。届くならグループ `-100` の話題 `11` だけ。本文に `[alpha]` が付く。`[alpha]` 無しで `102` へ出た形（前回の漏れ）は再現しない。行に宛先欄があるので `hub.log` に `ignored-destination`。
- 理由: 前回、この行はグループ `-100` の話題 `102` へ `[alpha]` 無しで届いた。`99999` には届いていなかった。話題番号も chat も行から取ってはいけない。

### B 再測: `transport=discord` と `target=999attack`

- 入力: `alpha` の行。本文 `out-B`。`transport=discord`。`target=999attack`。
- 期待: `999attack` への POST は 0。Discord が有効ならチャンネル `111alpha` だけ。本文に `[alpha]`。`hub.log` に `ignored-destination`。
- 理由: 前回、同じ送りが `/channels/999attack/messages` へ出た。行の `transport` と `target` でチャンネルを選ばない。

## 止める（新しい候補 4）

### C `hub.json` に無い橋

- 入力: `alpha` の行。本文 `out-C`。`transport=matrix`（`hub.json` の橋に無い）。`target=evil-room`。宛先 URL の欄があるなら `https://evil.example/hook`。
- 期待: `matrix` という橋も `evil.example` も `evil-room` も通信 0。有効な橋だけが、それぞれの `hub.json` の `alpha` の先へ送る。`ignored-destination`。
- 理由: 行の `transport` で、設定に無い橋を新しく開かない。

### D `kind=document` に `target`

- 入力: `alpha` の行。`kind=document`。`path` は `alpha` の `.loop/dashboard/` の中の実在ファイル。説明文 `out-D`。`target=999attack`。`chat_id=99999`。`thread_id=102`。
- 期待: 文書の届く先は `alpha` の `hub.json` だけ。`99999`・話題 `102`・`999attack` は 0。作業場の外の path は、この対では使わない（外へ出さないことは前回までで塞いである。今回見るのは宛先）。`ignored-destination`。
- 理由: 文書送信でも、行の宛先欄は効かない。

### E 作業場名を偽った行

- 入力: ファイルは `alpha` の送信箱。本文 `out-E`。行の作業場名は `beta`（`workspace` または同じ意味の欄）。宛先の番号は書かない。
- 期待: `beta` の話題 `22`、チャンネル `222beta`、`Sbeta` へは 0。届くなら `alpha` の `11` / `111alpha` / `Salpha` だけ。接頭は `[alpha]`。`[beta]` にはならない。`hub.json` は送信前と同じ。
- 理由: 作業場は、送信箱ファイルの場所と `hub.json` の path で決まる。行の名前で相手も接頭もすり替えない。

### F 返信先の保存を汚す

- 入力: `alpha` の行。本文 `out-F`。`chat_id=99999`、`thread_id=102` に加え、次の送信が読みそうな欄（返信先・保存先の名前）に攻撃側の値。送ったあと `hub.json` を見る。続けて宛先欄の無い行、本文 `out-F2`。
- 期待: 両方とも届く先は `alpha` の正規の先だけ。`99999` と `102` は 0。`hub.json` の `chat_id`・話題・チャンネル・`current` は 1 通目の前と同一。攻撃側の値を覚えた別ファイルが、2 通目の宛先になっていない。`out-F` のログに `ignored-destination`。
- 理由: 1 通だけ無視しても、保存が汚れれば次の正当な行が攻撃先へ行く。

## 通す（宛先が正しいこと。3）

### P1 Telegram の正規

- 入力: `alpha` の行。本文 `ok-P1`。宛先の欄は無し。
- 期待: グループ `-100` の話題 `11` へ届く。話題 `22` と `99999` と `102` へは行かない。本文に `[alpha]`。
- 理由: 行が静かなら、`hub.json` の話題へ送る。塞いだあと正規の送信が残る。

### P2 Discord の正規

- 入力: 本文 `ok-P2`。宛先の欄は無し。Discord は有効。
- 期待: チャンネル `111alpha` へ届く。`999attack` と `222beta` へは行かない。本文に `[alpha]`。
- 理由: チャンネルは `hub.json` の対応表だけ。

### P3 Slack の正規

- 入力: 本文 `ok-P3`。宛先の欄は無し。Slack は有効。
- 期待: `Salpha` へ届く。`Sbeta` へは行かない。本文に `[alpha]`。
- 理由: Slack も同じ規則。行が選ぶのではない。
