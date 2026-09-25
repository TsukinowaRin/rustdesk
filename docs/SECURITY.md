# Security Policy

## Reporting a Vulnerability

We value security for the project very highly. We encourage all users to report any vulnerabilities they discover to us.
If you find a security vulnerability in the RustDesk project, please report it responsibly by sending an email to info@rustdesk.com.

At this juncture, we don't have a bug bounty program. We are a small team trying to solve a big problem. We urge you to report any vulnerabilities responsibly
so that we can continue building a secure application for the entire community.

---

<!-- 以下はハーネス（multiagent-harness v3.1.0）の守りの説明。PR 用 branch には入らない -->

# SECURITY.md — このハーネスの守り

エージェントが危ない命令を打つ前に、`harness/guard.py`（判定の本体）が止めたり、人に聞いたりします。この文書は、**何を止めて、何を聞いて、何をそのまま通すか**、そして**守りの限界**をまとめたものです。基準は「戻せるか」: 取り返しがつく操作は通し、つかない操作だけ止めます。

## ① 止めるもの（deny）

hook が操作の直前に `harness/guard.py` を呼び、次の 5 つは止まります。

1. **壊す命令** — 作業場の外や木ごとの削除（`rm -rf /`、`git reset --hard`、`git clean -fdx`、絞り込みの無い `find -delete`）、ディスクを消す操作（`mkfs`、`dd of=/dev/...` など）。
2. **秘密のファイル** — `.env`、鍵（`id_ed25519` など）、証明書、token、OS の認証情報（`/etc/shadow`）、CLI の認証情報の置き場（`.aws`、`.ssh`、`.claude/.credentials.json` など）。読む・書く・検索する先、どれでも止まります。
3. **管理者になる操作** — `sudo`、`doas`、`su` など。人が直前に OK した 1 回だけ、命令の先頭に `AGENT_ADMIN_APPROVED=1` を付けて通ります。OK があっても、壊す命令と秘密のファイルは止まります。
4. **各 CLI 標準の子エージェントの起動** — `agent`、`task`、`subagent_fork` などの名前の道具。他の担い手へ渡す道は `python3 harness/delegate.py` だけです（AGENTS.md の決まり）。
5. **main・master への直接 push** — `git push origin main` など。branch を切って PR にします。

この 5 つとは別の理由で止まるものが 3 つあります。

- **読めない命令** — 引用符や heredoc が閉じていない / 入れ子が深すぎる / `cat a | xargs rm -rf` のように引数が実行前に決まらない形。読めないものは判定できないため、止める側に倒します。
- **手なしの担い手の書く道具** — 依頼書に `hands: none`（読むだけ）と書かれた担い手は、書く道具と shell が使えません。例外は報告 1 本（`HARNESS_REPORT` で指されたファイル）だけです。
- **担い手の決まり**（`HARNESS_ROLE=worker` の側だけ。2026-09-25）:
  - **書く範囲** — 書けるのは自分の作業木（`HARNESS_WORKTREE`）の中だけです。書く道具の path に加え、`>` `>>` `tee` `sed -i` `cp` `mv` `truncate` の書き先も見ます。作業木の外への `cd` も止まります。
  - **守りのファイル** — 作業木の中でも、`harness/guard.py`・`harness/guard_bridge.mjs`・各 CLI の守りの設定 9 枚は書けません。**例外**: 指示役が依頼書に `guard: edit` と書いた依頼だけ、`delegate.py` が `HARNESS_GUARD_EDIT=1` を付け、作業木の中の守りのファイルを書けます（作業木の外は書けないまま）。
  - **担い手の起動** — 担い手の CLI（`harness/clis.json` の `worker` の先頭の命令）・`harness/dsh.sh`・`python3 harness/delegate.py run` を起動できません。担い手の印（`HARNESS_ROLE` `HARNESS_HANDS` `HARNESS_WORKTREE` `HARNESS_GUARD_EDIT`）を付け替える・外すことも止まります。
  - **git の巻き戻し** — `git checkout -- <path>`、`git restore`（`--staged` だけの物を除く）、`git stash drop` / `clear`、`git branch -D` は止まります（指示役には「聞く」）。

## ② 聞くもの（ask）

危ないと決まったわけではないが、実行してよいか人が決めるべき操作です。hook は「聞く」と答えますが、**既定では承認画面を出さずに止まります**（人が目の前にいる `HARNESS_ATTENDED=1` のときだけ CLI が確認を出す。⑤ 参照）。

- **外へ出す操作** — `git push`（main / master 以外への）、書く `gh`（`gh pr create` など）、`curl` で送る（`-d`、`-X POST` など）、`ssh` / `rsync` での遠隔操作、`npm publish` などの公開。
- **消す場所が変数で決まらない削除** — `rm -rf "$TARGET"` のように、消す場所が実行時まで確定しない削除。危ないとは限らないので「聞く」に緩めました（2026-09-23）。
- **変更や履歴を消しうる git** — `git checkout -- <path>`、`git restore`（`--staged` だけの物を除く）、`git stash drop` / `clear`、`git branch -D`。担い手には「止める」です（①）。

## ③ 通すもの（allow）

上以外は通ります。外向きでも**見るだけ**の操作は止めません。

- 予行の `git clean -fdn`（`-n` / `--dry-run` は何も消さない）
- 作業場の中の、絞り込み付きの `find . -name '*.log' -mtime +7 -delete`（git があるので戻せる）
- 見るだけの `curl https://example.com/x.json`、`git fetch`、`git clone`
- 本文に「rm -rf /」という禁止語が入っているだけの `git commit -m "..."`（書く中身は見ないため。後述）
- `cat .env.example`、公開鍵（`.pub`）、検索語に `.env` とあるだけの `grep`

## ④ 見るもの・見ないもの

守りが判定に使うのは **「実行する命令の文字列」と「触る場所（path）」だけ**です。

- **見る**: 命令の文字列、リダイレクト先、道具に渡される `file_path` などの path。
- **見ない**: 書き込む・コミットする中身（ファイルの本文、patch の本文）。`docs/SECURITY.md` に「rm -rf / は止める」と書けるのは、この決まりがあるためです。中身まで見ると、この一覧を説明する文書すら書けなくなります。

コードの中身（`python3 -c '...'` など）は実行前に読めませんが、**引用符で囲まれた文字列のうち秘密の path らしい名前だけ**は見ます。`python3 -c 'open(".env")'` を止めるためです（2026-09-23 の独立の確認で見つかった穴）。

## ⑤ 人がいないとき

「聞く」は、聞く相手がいるときだけ意味があります。承認の設定が Never の CLI では黙って通り得ますし、承認画面が出る CLI では人が気づくまで作業が止まります。そこで、**既定では「聞く」を実行せずに止めます**（書き置きを残す。2026-09-24、ユーザーの判断:「デフォルトで Hook の承認で勝手にストップしないようにして」）。

- 指示役: 人が目の前にいる印 `HARNESS_ATTENDED=1` を付けたときだけ、CLI の承認画面に回ります
- 担い手（`HARNESS_ROLE=worker` の側。`delegate.py` が起動した CLI）: 印があっても止めます
- 人が OK したら、その 1 回だけ命令の先頭に `HARNESS_APPROVED=1` を付けて打ちます（管理者の操作の `AGENT_ADMIN_APPROVED=1` と同じ形）。OK があっても deny（壊す命令・秘密・main への push）は止まります。これは印であって鍵ではありません（エージェントが勝手に付けられます）。守りは「うっかり」を止める物で、「わざと」は台帳と人の目で見ます

このときの振る舞い:

- **指示役**は、実行せず判断カードを 1 枚書いて次の仕事へ移ります。
- **担い手**は、実行せず、報告の「人の判断が要ること」に書いて指示役へ返します。

外からの `/run` は、許可した chat ID の人の依頼として指示役に渡します。
hub は依頼の文を shell で実行せず、CLI の引数または標準入力として渡します。
指示役には守りが効き、人が離れているときの「聞く」は判断カードになります。

hub が送る先（Telegram の話題・Discord / Slack のチャンネル）は `~/.config/harness/hub.json` だけから決めます。作業場の送信箱の行に `thread_id` や `target` が書かれていても無視して `hub.log` に残します（Grok の独立の確認 4 回で確かめ、記録は `docs/verification/2026-09-26_hub/`）。残っている 1 つ: `hub.json` の返信先そのものが細工されていると、その thread へ出ます。`hub.json` は作業場の外にあり、担い手は書けないので、直さず記録だけにしています。

## ⑥ CLI ごとの「効かない条件」

hook（守りの掛け金）は 9 本の CLI それぞれに配線してありますが、**配線が生きる条件**が CLI ごとに違います。`harness/clis.json` の notes から 1 行ずつ:

| CLI | 効かない条件 |
|---|---|
| claude | 対話で 1 回「信頼する」に答えるまで、allow の一覧は無視される（hook 自体は信頼の前から効く） |
| codex | 展開した直後は Codex の中で `/hooks` を 1 回承認するまで hook が動かない（黙って素通り）。無人で動かす前に必ず承認する |
| agy | `--add-dir` に repo の絶対 path を渡さないと、hook も AGENTS.md も読まれない（9/17 実測: loaded 0 hooks.json） |
| cursor | failClosed: true。無料の契約では `--model auto` が要る |
| opencode | plugin の tool.execute.before で判定。「聞く」は出せないので止める側へ倒す |
| kilo | opencode と同じ作りの plugin |
| grok | folder を信頼するまで project の hook は 0 本。command の中に未設定の `$VAR` があると hook を起動せず素通りにするので、変数は既定値つきの 1 つだけ |
| omp | 拡張は自動で読み込まれる。「聞く」は ctx.ui.confirm、出せない場では止める |
| dsh | プロジェクトの設定を自動では読まない。必ず `harness/dsh.sh` から起動する（hook の設定は Claude Code と共用） |

特に codex・agy・grok・dsh は、**条件を満たさないと守りが黙って素通りします**。CLI を使う前に上の条件を満たしているか確かめてください。配線が生きているかは `python3 harness/check.py` が確かめます。

## ⑦ 画面操作と管理者の操作

### 画面操作（computer use）

画面のクリックは、命令の文字列として判定できません（守りの外）。対策は、**ハーネスで判定する代わりに、使い捨ての仮想環境と操作の記録で守る**ことです（`harness/computer-use.json`）:

- 画面操作の MCP サーバーは、エージェントが動く場所ではなく、**使い捨ての仮想環境**（Windows Sandbox、Docker コンテナなど）で動かす。閉じたら消えます
- 起動時の環境変数で、触ってよいアプリ・消す前に承認が要ること・操作の記録先（`.loop/computer-use/<依頼ID>.jsonl`）を決める。サーバー側が持っている守りを使い、ハーネスは自前で作りません
- パスワード管理・鍵の管理画面は触らせません

### 管理者の操作（`harness/admin_window.py`）

`sudo` は hook でも止めますが、どうしても管理者の権限が要るときは**窓**を通します:

- 命令をエージェントが渡し、資格（パスワード）の確認は OS に任せる。**パスワードも同意もエージェントを通りません**。エージェントが受け取るのは、出力と終了値だけ
- 受け取るのは命令 1 つだけ。`;` `&&` `|` `$` などの記号があれば断り、shell を管理者で起動する命令も断ります
- 認証は保存しません（`sudo -k`）。何を実行したかは `.loop/admin-window.jsonl` に残ります

## ⑧ 分かっている限界

正直に書きます。次の形は**止まりません**:

- **命令の文字列に中身が無い形** — `make`、`bash file.sh`、`npm run`、`curl | sh`、`webapp-testing` の `with_server.py`。実行する中身が命令の文字列に書かれていないため、判定できません。
- **書き込む中身は見ない** — コミットやファイルへの書き込みの中身は判定対象ではありません。
- **コードの中身は読めない** — `python3 -c '...'` の中で秘密の名前を引用符で囲んでいなければ、コードが何をするかは読めません（引用符で囲まれた秘密の名前だけは見ます）。
- `python3 -c "open('../outside.txt','w').write('x')"` のような任意の Python コードがどこへ書くかは判定できません。
- `dd of=../outside.txt` の書き先は判定できません（`dd of=/dev/...` は止めます）。
- `ln -sf /tmp/outside.txt notes.txt` のようなリンクの操作は、リンク先と書き先の関係を判定できません。
- 上の 3 つ（`python3 -c` の書き先 / `dd of=` / `ln -sf`）は、担い手の書く範囲（①）の抜け道でもあります。2026-09-25 の独立の確認で「設計の限界として塞がない」と決めました（`docs/verification/2026-09-25_guard-worker/README.md`）。
- **OS の sandbox の代わりにはならない** — これは文字列を見る掛け金です。VM やコンテナの分離は別に用意してください。
- **hook は完璧ではない** — 止めすぎると回避が常態化するため、取り返しのつかない物だけを止め、それ以外は「聞く」か「通す」に倒しています。そのため、上に書いた形の一部は通ります。

## ⑨ 守りを直すときの決まり

守りを変えるときは、この順で通します:

1. **試験** — `tests/guard_cases.tsv` に、止める形と通す形の対を 1 行足す（そこにある物は実測で確かめられている）。
2. **点検** — `python3 harness/check.py` を通す。落ちたら最後の行に直し方が出ます。
3. **独立の確認** — 作った人とは別の会社のモデルで独立の確認（`independent-check` skill）。実装を見る前に「止める形 / 通す形」を書いてから確かめます。

この 3 つを通してから採用します。点検や試験を、通すために弱めないこと。点検が間違っていると思ったら、変えずに人へ理由を書きます。

### 担い手の書く範囲の、分かっている抜け（9/25 の 3 回の独立の確認で残った物）

守りは「うっかり」を止める物で、「わざと」は台帳と人の目で見ます。次の形は今は通ります（次の周で塞ぐ候補）: `;` の直前に `\` がある命令の区切り / `timeout -s KILL 5 <CLI>`（`--signal=` は止まる）/ `pushd` で出てからの書き込み / `env -C` `tar -C` `git -C` `patch -d` `pip install -t` のように旗で作業場所を変える命令。記録は `docs/verification/2026-09-25_guard-worker/`。
