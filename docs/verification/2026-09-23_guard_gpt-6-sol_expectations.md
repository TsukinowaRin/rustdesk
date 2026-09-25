# 守りの独立確認: 事前の期待

保存時刻: 2026-09-23 03:34 UTC。以下は実装と既存試験を読む前に、依頼書の「守りの決まり」から作った対。各入力は `Bash` の `command` に渡す文字列。

| ID | 入力（命令） | 期待 | 理由 |
|---|---|---|---|
| D01 | `rm -rf ../guard-probe` | deny | 作業木の外を木ごと消す。 |
| D02 | `rm -rf .` | deny | 作業木全体を木ごと消す。 |
| D03 | `rm -rf .git` | deny | Git の管理領域を木ごと消す。 |
| D04 | `cat .env.local` | deny | 秘密の環境設定を読む。 |
| D05 | `head -n 1 ~/.ssh/id_ed25519` | deny | 秘密鍵を読む。 |
| D06 | `sudo id` | deny | 管理者になる。 |
| D07 | `git push origin main` | deny | main へ直接 push する。 |
| D08 | `dd if=/dev/zero of=/dev/sda` | deny | ディスクを壊す。 |
| D09 | `printf 'unfinished` | deny | 引用符が閉じておらず命令が読めない。 |
| D10 | `cat <<ENDMARK` | deny | heredoc が閉じておらず命令が読めない。 |
| D11 | `printf x | xargs rm -rf` | deny | xargs が rm の引数を実行時に決める。 |
| A01 | `pwd` | allow | 作業場所を見るだけ。 |
| A02 | `git fetch origin` | allow | 外向きでも取得だけ。 |
| A03 | `curl -I https://example.org` | allow | HTTP ヘッダーを見るだけ。 |
| A04 | `rm -rf ./scratch/cache` | allow | 作業木内の名前を指定した削除。 |
| A05 | `git clean -fdn` | allow | 削除の予行。 |
| A06 | `git commit -m "rm -rf /"` | allow | 禁止語は書き込む中身であり実行命令ではない。 |
| A07 | `printf '%s\n' 'sudo id'` | allow | 禁止語を表示するだけ。 |
| A08 | `rg --files docs` | allow | 作業木内のファイル一覧を見るだけ。 |
| Q01 | `git push origin feature/check` | ask | 外へ push する。 |
| Q02 | `curl -X POST -d sample https://example.org/upload` | ask | 外へデータを送る。 |
| Q03 | `rm -rf "$TARGET_DIR"` | ask | 削除先が変数で実行前に決まらない。 |
