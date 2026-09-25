# 担い手の書く範囲・担い手の起動を縛る守り（9/25）の独立の確認

作った側: GPT-6 Sol（T-0925-14）。確認: GPT-6 Astra（high、T-0925-17、449 秒、83,914 トークン）。実装を読む前に 88 対を保存してから測った。
注意: 作った側と同じ会社（openai）の別モデル。ユーザーの指示で Astra を使ったが、独立の原則（別の会社）からは弱い。直したあとの再確認は Grok 4.7（xai）で行う。

結果: **差し戻し。** 107 判定のうち不一致 21。うち抜け道 11（下）、設計の限界 3（`python3 -c` / `dd of=` / `ln -sf`。SECURITY.md の限界に書く）、期待の解釈違い 6（承認印の置き方 5、報告の shell 1。不具合ではない）、要求の狭さ 1（`git restore --staged --worktree` が通る）。壊した 3 通りは事前の対で 3/3 検出。

| # | 通ってしまった形 | 何が抜けているか |
|---|---|---|
| 1 | `env -u HARNESS_ROLE codex` | 印を外して別の担い手を起こせる |
| 2 | `bash ./harness/dsh.sh` | path の書き方の違い |
| 3 | `python3 -B harness/delegate.py run` | script の前の旗 |
| 4 | `cp /tmp/guard.py harness/`、`mv` 同 | 行き先が directory のとき、写した後の名前を見ていない |
| 5 | `cp -t ../outside-dir README.md` | `-t` の行き先 |
| 6 | `cd .. && echo x > outside.txt` | `cd` で作業木を出てからの書き込み |
| 7 | `sed -i.bak s/x/y/ ../outside.txt`、`sed -i s/x/y/ ../outside.txt notes.txt` | `-i` の接尾辞、複数ファイル |
| 8 | `echo x &> ../outside.txt`、`>\|` | 見ていないリダイレクトの記号 |
| 9 | `git restore --staged --worktree README.md` | `--worktree` は作業内容を消す |

直しは GPT-6 Sol（T-0925-20、依頼書の `guard: edit` で守りを書く例外を開ける）。

## 2 回目（Grok 4.7、xai。T-0925-23、923 秒）

Sol の直し（T-0925-20、`3e87936`）のあと、別の会社で再確認。実装を見る前に 138 対を保存（要求 82、Astra の 11 の言い直し、新規 45）。

結果: **差し戻し（2 回目）。** Astra の 11 件は全部塞がった。新しく通った 7 件と、止め過ぎ 2 件。

| 種類 | 形 | 指示役の裁定 |
|---|---|---|
| 起動の path の綴り | `./harness/dsh.sh`、`harness/dsh.sh`、`source harness/dsh.sh`、`. harness/dsh.sh`、`bash -c './harness/dsh.sh'` / `python3 harness/./delegate.py run`、`python3 harness/foo/../delegate.py run` | 塞ぐ（path を正規化して basename と親で見る） |
| 別の命令を経由 | `find . -exec cp {} ../outside-dir/ \;`、`printf ../f \| xargs truncate -s 0`、`busybox cp README.md ../outside.txt`、`exec -a x codex` | 塞ぐ（find -exec の `{}` を元と見る / 担い手の xargs は書く命令（cp mv tee truncate sed -i）を deny / busybox と exec の前置きを外す） |
| 列挙外の書く命令 | `rsync -a README.md ../outside.txt`、`install README.md ../outside.txt`、`perl -pi -e s/x/y/ ../outside.txt` | 塞ぐ（行き先を見る。perl の `-pi`/`-i` は sed と同じ） |
| 止め過ぎ | `cd .. && ls`（書かないのに外への cd で止まる）、`git restore -S README.md`（`--staged` の短旗） | 直す（cd は cwd を追って以後の書き込みだけ見る。`-S` を `--staged` と同じに） |
| 設計の限界 | `python3 -c`、`dd of=`、`ln -sf` | 塞がない（SECURITY.md に記載済み） |

直しは Sol（T-0925-25、`guard: edit`）。3 回目の確認は Grok。

## 3 回目の直し（Opus 5.5、T-0925-37、1,144 秒。Sol の途中の patch を引き継ぎ）

Grok の 7 件 + 止め過ぎ 2 件を全部直し、加えて元から通っていた 3 つ（`cd harness && bash dsh.sh`、`cd -P .. && echo x > f`、`cd - && echo x > f`）も塞いだ。対を 18 組足し、直す前の守りに向けると 37 件ずれる（対が穴を捕まえている証拠）。取り込み `ef56ee1`。
指示役の裁定: `cd harness && echo x > ../notes.txt`（中から中へ）が止まる止め過ぎは安全側として受け入れる。`\;` の読み方の直しが指示役にも効く（`find . -exec true \; -delete` が止まる）のは正しい動きなので採る。
Opus が見つけて直していない元からの抜け 3 つ（`;` の直前の `\\`、`timeout -s KILL`、`pushd`）は 3 回目の確認（Grok、T-0925-58）の対象に入れた。

## 3 回目の確認（Grok 4.7、T-0925-58、645 秒）→ **閉じる**

115 対（要求 81、前回の 19、元からの抜け 3、新規 12）。要求と前回の 7+2 は全部一致。Grok の判断「閉じてよい」。指示役も閉じる。

残っている抜け（**既知の限界として `docs/SECURITY.md` に書く。次の周で塞ぐ候補**）:

| 形 | 種類 |
|---|---|
| `echo a\; codex`（`;` の直前の `\`）、`timeout -s KILL 5 codex`（`--signal=KILL` は止まる）、`pushd .. && echo x > f` | 元からの抜け 3 |
| `env -C .. cp a b`、`tar -C .. -xf x.tar`、`git -C .. apply p.diff`、`patch -d .. < p.diff`、`python3 -m pip install -t .. x` | 列挙外 5（`-C` `-d` `-t` で作業場所を変える命令） |
| `cd harness && cd .. && echo x > f`（作業木の根の `f` なのに止まる） | 止め過ぎ 1（安全側） |

経緯のまとめ: Sol が作る（11 件の穴）→ Astra が見つける → Sol が塞ぐ → Grok が 7+2 を見つける → Opus が塞ぐ（Sol の途中を引き継ぎ）→ Grok が閉じる。3 社 4 モデルで 3 往復。
