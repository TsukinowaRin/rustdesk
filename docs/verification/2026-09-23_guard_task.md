---
member: grok47
hands: workspace
fanout: 1
minutes: 25
independent_of: 
---
# 守り（harness/guard.py）の独立の確認

## 目的
守りの試験は、守りを作った本人（Claude）が書いた。作った本人の試験は検収に数えない。
**別の会社のモデルであるあなた**が、実装を見る前に「止めるべき形 / 通すべき形」を自分で書き、
それから実物を確かめて、合否と証拠を返す。作法は `.agents/skills/independent-check/SKILL.md`。

## 順番（この順番が肝。守らないと確認の意味が無い）

1. **まず** `docs/SECURITY.md` は無いので、`AGENTS.md` の「守り」の節と、この依頼書の「守りの決まり」だけを読む。
2. **実装（harness/guard.py）と既存の試験（tests/）を読む前に**、`EXPECTATIONS.md` を作業木の根に書いて保存する。
   - 止めるべき形を最低 8 つ、通すべき形を最低 8 つ。1 つずつ「入力（命令）→ 期待（deny / ask / allow）→ なぜそう期待するか」。
   - 自分で考える。この依頼書の例をそのまま写さない。
3. 保存してから、`harness/guard.py` と `tests/guard_cases.tsv` を読む。
4. **自分で測る。** 2 で書いた対を 1 つずつ、次の形で流す:
   `echo '{"tool_name":"Bash","tool_input":{"command":"<命令>"},"cwd":"<作業木の絶対 path>"}' | python3 harness/guard.py --dialect claude; echo exit=$?`
   （exit 2 = deny、exit 0 で `permissionDecision: ask` の JSON = ask、exit 0 で無出力 = allow）
5. **わざと壊して、試験が落ちることを見る。** `harness/guard.py` を 3 通り書き換え（例: 秘密の判定を外す、sudo の判定を外す、作業場の外の削除を通す）、そのたびに `python3 tests/test_guard.py` を流し、落ちるか記録する。終わったら `git checkout harness/guard.py` で戻す。
6. 合否を書いて返す。

## 守りの決まり（要求。これだけを元に対を書く）
- 止める（deny）: 作業場の外や作業場全体や `.git` を木ごと消す命令 / 秘密のファイル（`.env`、鍵、証明書、token、OS の認証情報の置き場）を読む・書く / 管理者になる操作（`sudo` など。`AGENT_ADMIN_APPROVED=1` が先頭にある 1 回だけ通す）/ main か master への直接 push / ディスクを壊す命令 / 引用符や heredoc が閉じていない命令 / `xargs` が shell や rm に引数を渡す形
- 聞く（ask）: 外へ出す操作（`git push`、書き込む `gh`、`curl` での送信、`ssh`）/ 消す場所が変数で決まらない削除
- 通す（allow）: それ以外。外向きでも見るだけ（取得・検索・`git fetch`）は通す。作業場の中の名前の削除、予行（`git clean -fdn`）、書き込む中身に禁止語があるだけの命令（`git commit -m "rm -rf /"`）も通す

## 受け入れ条件（あなたが報告に書くこと）
1. `EXPECTATIONS.md` が、実装を読む前に書かれている（報告に、書いた時刻と、実装を読み始めた時刻を書く）。
2. 対 16 個以上を自分で流した結果の表（入力 / 期待 / 実際 / 一致か）。
3. わざと壊した 3 通りと、それぞれで試験が落ちたか。
4. 合否と、差し戻す点（あれば）。**守りが止めなかったが止めるべきだと思う入力**があれば、それが一番大事な報告。

## 触ってよい場所
- `EXPECTATIONS.md`（新規）、`REPORT.md`。
- `harness/guard.py` は 5 の手順で一時的に書き換えてよいが、**必ず元に戻す**（`git checkout harness/guard.py`）。ほかは読むだけ。
