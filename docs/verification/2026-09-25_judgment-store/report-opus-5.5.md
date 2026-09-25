# 確認: T-0925-60（台帳の共有 init --from / sync / brief の pull。作者 GPT-6 Astra、658742e）
## 合否
差し戻し（穴 1 つ。ほかは期待どおり）
## 通ってしまった物（最上位）
- **作業場の remote を書き方違いの URL で台帳の origin にすると、sync が断らずに台帳を作業場の remote へ push した。** `safe_repo`（harness/judgment.py:90-103）が URL を文字列の完全一致で比べるだけのため。実測: 作業場の origin が `<dir>/wsremote.git`、台帳の origin が `<dir>/wsremote.git/`（末尾 `/`）や `file://<dir>/wsremote.git` → 終了 0「台帳を同期しました」。作業場の remote に `refs/heads/main` ができ、中身は decisions_journal.md ほか台帳 7 ファイル
  - 起きる条件: 作業場の remote が空（branch が 1 つも無い）とき。branch がある remote では先の `pull --rebase` が失敗して止まった（2 通り測った）。GitHub で作業場用の repo を作った直後で、まだ push していない、が当たる形
  - 直し方の案: 比べる前に URL をそろえる（末尾 `/` と `.git` を外す、`file://` を外して path を resolve する、`git@host:u/r` と `https://host/u/r` を同じ扱いにする）。試験に書き方違いの場面を足す
## 先に書いた対
EXPECTATIONS.md。要求ごとの対 21（止める 11・通す 10）＋抜け道 15（決めた順番どおり、実装を読む前に保存）
## 実測（作業木の中の tmp-eval/ に作業場の複製と bare repo を作って測った。/tmp は守りに止められた。終わったら消した）
- 36 件流して、ずれ 2 件（抜15a 末尾 `/`、抜15b `file://`）。抜15c（`..` 入りの path）は私の path の作り方が悪く git が失敗しただけなので数えない
- 期待どおり: init --new / 旗なし init / 再 init で上書きしない / --from は実 dir の clone（symlink の path でも）/ 型を補う / clone 元の config.env（偽 token 入り）を使わない / setup.json に 2 項目 / 一覧外・config.env・`.env`・`x.env`・`logs/`・`journal_archive/secret.env` は bare の全履歴に入らない（偽 token の文字列も無い）/ `.gitignore` を消しても `!` で書き換えても秘密は入らない / 同じ toplevel は断る / 同じ URL（完全一致）と pushInsteadOf で化けた URL は断る / upstream と pushDefault=upstream を足しても upstream に届かない / 衝突は 1 行・終了 1・送らない・再 sync でも解決しない（UU のまま）/ remote 無しは commit だけ / 変更なしは commit しない / brief は取り込む・届かない remote でも終了 0 で 1 行 / status の 2 択・setup.json を使う・env が優先
- わざと壊した 4 通り（URL の照合を消す / 一覧の絞りを消す / push を `git push` の既定にする / toplevel の照合を消す）→ 4 通りとも作者の試験が落ちた（ずれ 4 / 途中で例外 / ずれ 7 / ずれ 1）
- `python3 tests/test_judgment.py` → 50 場面、ずれ 0。`python3 tests/test_setup.py` → 22 場面、ずれ 0
## 気づいた点（差し戻しの理由ではない）
- origin に pushurl（`remote set-url --push`）で別の repo を足すと、そちらへ push した。「origin だけ」には合うが、作業場以外の第三の repo へは送れる
- clone 元が一覧外のファイル（README.md や config.env）を追跡していると、sync は毎回断る（抜12 で確認。偽 token は送られない）。GitHub 上の既存の台帳に README があると使えない。案内文に `git rm --cached` の案内が無い
- `init --from` に認証情報入りの URL を渡すと、`.loop/setup.json` の `judgment_remote` にそのまま残る（コードから読んだ。測っていない）
## 残り
- ssh / https の URL は網に出るので測っていない（`git@github.com:u/r.git` と `https://github.com/u/r` の比較も同じ文字列比較なので、断らないと読んでいる）
## 人の判断が要ること
- 上の穴を直すまで sync の採用を待つか
## 変更したファイル
- EXPECTATIONS.md、REPORT.md（tmp-eval/ は作って消した）
