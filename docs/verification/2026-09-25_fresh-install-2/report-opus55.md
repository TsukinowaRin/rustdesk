# 報告: T-0925-22（配布物を新規展開して、文書だけで最初の依頼まで）
## 何をした（zip 展開した `fresh/` で HARNESS.md の手順を 1 から順に。6 の run は打たず）
| 手順 | 打った命令 | 結果 | 初めての人が迷う点 |
|---|---|---|---|
| 1 | `python3 --version`(3.12.3) / `git --version`(2.43.0) | 動いた | 3.11 では未確認。「担い手の CLI」がどれか、この時点では分からない（編成は手順 4） |
| 2 | `git init` / `git add -A` / `git commit -m init` | 動いた | branch が `master` になり hint が出る。user.name/email 未設定の機械では commit が失敗するが文書に無い（この機械は全体設定済みで再現できず） |
| 3 | `check.py`（26 秒, 全 ok「点検が通りました。」）/ `setup.py status`（まだ 3 件）/ `notify skip` / `judgment.py init` | 動いた | 「編成」の「まだ」には命令が無く「人と決める」だけ。手順 4 と同じ事と気づきにくい。済むと「まだ」が消えるだけで「全部済み」の一言が無い |
| 4 | `cp harness/team.example.json .loop/team.json` / `delegate.py team` | 動いた（4 人の表） | 表は CLI が入っているかを見ない。dsh はこの機械に無いが deepseek がそのまま並ぶ |
| 5 | `delegate.py new "README の誤字を直す" --member flash` → task.md を記入 | 動いた（T-0925-01。次の命令も表示） | 頭の `guard:` `minutes:` が HARNESS.md の「ギア 4 つ」に無い。`delegate.py --help` の各副命令に説明が無い |
| 6 | 打たず（依頼書どおり） | 未確認 | — |

## 検証の結果（済ませた後、`fresh/` で）
- `python3 harness/check.py` → 全 ok（守り 122+28・配線 41・判断 24・setup 17・dsh 18・delegate 37・管理 29・通知 16・dashboard 3 本）、rc=0
- `python3 harness/setup.py status` → 通知: skip / 文書の道具: そろっている。「まだ」0 件
- `python3 harness/delegate.py team` → flash(opencode)・deepseek(dsh)・sol(codex)・opus(claude, claude-opus-5)
- `python3 harness/judgment.py brief` → 原則なし・カード 0・訂正 0・語彙 0 と、次にやること 1 行。rc=0。`.loop/` は `git status` に出ない
## 判断
- 基準 2: **合格**（展開 → 点検通過 → 「まだ」0 → 依頼書まで作れた）。ただし run〜adopt は未確認。
- 基準 8: **条件付き**。手順は docs にあるが、同じ機械（git 全体設定・CLI 導入済み）での確認だけ。git の名前設定と CLI の入れ方が抜けており、他の機械では手順 2・6 で詰まりうる。
## 直すべき文（案）
1. 手順 2「`git commit -m init`」→ 前に「名前が未設定なら `git config user.name …` / `user.email …`」を足す。
2. 手順 3「書いてある命令で 1 つずつ済ませる」→「編成の『まだ』は手順 4 で済む。『まだ』が出なくなれば完了」。
3. 手順 4「写して直し」→「使わない CLI の人を消す（入っているかは `command -v <CLI>` で見る）」。
4. 手順 5 の後に「頭の欄の意味は ③ のギアの表」＋表に `guard` `minutes` を足す。
5. 手順 1「サインインしておく」→ 担い手に使う CLI の一覧（`team.example.json` の cli 欄）を指す。
## 残り: 手順 6（run・adopt）、Python 3.11、別の機械での再現は未確認。
## 人の判断が要ること
- 守りが止めた 2 件（回避はしていない）: ①`… >/dev/null` を「作業木の外へ書く」と判定。②`fresh/` で `git init` 後、作業場所が `fresh/` に移り、指定の `REPORT.md` への Write が「作業木の外」と判定（作業場所が戻った後の同じ Write は通った）。誤検知かの判断を。
## 変更したファイル
- `fresh/`（展開先。中で git init・`.loop/` 作成・`.loop/tasks/T-0925-01/task.md` 記入）、`fresh.zip`（手順 1 の産物、依頼書の許可外だが手順どおり）、`REPORT.md`
