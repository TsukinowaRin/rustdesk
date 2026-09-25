# 台帳の共有（init --from / sync / brief の pull）の独立の確認

作った側: GPT-6 Astra（openai、T-0925-61）。確認: Opus 5.5（anthropic、T-0925-60、636 秒）。実装を読む前に対 21 + 抜け道 15 を保存してから測った（36 件、ずれ 2）。

結果: **差し戻し（穴 1 つ）。** 作業場の remote と台帳の origin の URL を「書き方違い」（末尾 `/`、`file://`）にすると、`sync` の照合（文字列の完全一致）をすり抜けて、台帳を作業場の remote に push できた（作業場の remote が空のときだけ）。直し: URL を正規化してから比べる（末尾 `/` と `.git`、`file://`、`git@host:u/r` と `https://host/u/r`）。

ほかは期待どおり: 秘密（`config.env`・`*.env`・`logs/`）は全履歴に入らない / `.gitignore` を消しても入らない / 同じ toplevel・同じ URL・pushInsteadOf は断る / upstream には届かない / 衝突は止まる / 壊した 4 通りを作者の試験が 4 通りとも検出。
気づき（差し戻しではない）: pushurl で第三の repo へは送れる / clone 元に一覧外のファイル（README など）があると毎回断る（案内が要る）/ 認証情報入りの URL が `setup.json` に残る。

直しは Opus 5.5（T-0925-63、289 秒。Sol が枠切れだったため）: URL を正規化して比べる / push 先を origin の fetch URL に固定（pushurl があれば送らない）/ 一覧外の案内に `git rm --cached` / 認証情報を `setup.json` に残さない。Opus の実測 2 件は断られることを再現し、試験 58 場面。取り込み済み。
