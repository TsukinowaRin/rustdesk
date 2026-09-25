# 旧版の道具の引き継ぎ検証（2026-09-23、担い手 Opus 5.5）

結論: **通知は旧版のまま移し、動いた。橋は 883 行を 66 行へ縮めて移し、動いた。SSH の窓は移していない。** SSH の窓は、管理者の窓（`admin_window.py`）の形に合わせれば 1 回限りの版で 200 行前後になる見積もり。
ただし、橋を通すと**新版の守りが PowerShell の中身を読めなくなる**。直接 `powershell.exe -Command` と打てば読めるのに、橋を通すと読めない。この扱いは人が決める（下の「橋」④）。

前提: 機械は WSL2（6.18.33.2-microsoft-standard-WSL2）+ Windows 11。`pwsh.exe`（7）、`powershell.exe`（5.1）、`wt.exe`、`msg.exe`、`csc.exe`（.NET 4）がある。

## 1. PC の通知（`notify.py` + `windows_toast.cs`）

1. **何をする物か**: 作業が終わったとき、OS の通知を音付きで 1 回出す。WSL / Windows では、Windows Terminal の名前を借りたトースト（画面の隅に出る知らせ）を出す。出せなければ `msg.exe` を使う。連打を防ぐ決まりもある（前の通知から 30 秒・1 時間に 20 回まで）。試験中（`HARNESS_TESTING=1`）は鳴らさない。
2. **依存**: 旧版の守り（`hooks_core`）には**依存していない**。依存は隣の `windows_toast.cs` と、抑制の記録を置く `.loop/notify-state.json` の場所だけ。
   旧版の `docs/HARNESS.md` と既定値を照合する点検（smoke）があったが、新版には無いので、その注記を消した。
3. **動かした結果: 動いた。** `python3 harness/tools/notify.py --title "ハーネスの試し" "引き継ぎの検証中"` → exit 0、3.7 秒。トーストに要る物（`wt.exe`・`csc.exe`・Windows の一時フォルダ）はそろっていた。すぐ 2 回目を打つと「前回の通知から30秒たっていません」で抑えられた。
   **画面に出たかは、担い手には見えない**。人の目で確かめる必要がある。
4. **価値: 要る。** 人が離れている間に「終わった / 止まった」を知らせる、ほかに代わりの無い道具。
5. **行数**: 416 行（旧版 411 行）。変えたのは 3 か所。冒頭の説明、smoke の注記、`.loop` の場所（`parents[1]`→`parents[2]`）。
   試験は `tests/test_notify.py` の 76 行（送らずに 16 場面）。縮めるなら、Windows 上で直接動かしたときの PowerShell 経路と Linux の音を削って 250 行ほど。今回は縮めていない。

## 2. WSL → Windows の橋（`wsl_to_win.sh`、逆向き `wsl_exec.ps1` / `.cmd`）

1. **何をする物か**: WSL の中から、Windows の PowerShell や Windows の実行ファイルを 1 回動かし、出力と終了値を受け取る。逆向きの `wsl_exec.ps1` は、Windows から WSL の命令を動かす（旧版では SSH の窓がこれを使っていた）。
2. **依存**: `hooks_core` の import は無い。旧版は、PowerShell の本文を守りが読めない穴を、橋の中の判定（`pwsh_inline_is_safe`、約 100 行）で埋めていた。
   ほかの依存は `python3`（判定と引数の符号化）、互換の入口 `win_pwsh.sh`、点検 `check_wsl_bridge.py`。
3. **動かした結果: 動いた**（新版 `harness/tools/wsl_to_win.sh`）。
   - `pwsh 'Get-Date'` → 日時を表示して exit 0。`pwsh.exe` を外した PATH では `powershell.exe`（5.1）で exit 0。
   - `throw` → exit 1、`Write-Error` → exit 1、`cmd /c exit 7` → exit 7（失敗を 0 と誤報しない）。引用符と改行を含む本文も崩れずに届いた。
   - `cli hostname`・`cli cmd.exe /d /c "echo a b"`・`cli 'C:\Windows\System32\whoami.exe'` → exit 0。
   - `cli ls`（Linux の命令）→ exit 4。引数なし → 使い方を出して exit 2。
   - 最初は日本語が CP932（Windows の古い文字コード）で化けた。出力を UTF-8 にする 1 行を足すと、正しく出た。
4. **価値: 縮めて要る。** 残したのは `pwsh '<本文>'` と `cli <実行ファイル> [引数...]` の 2 つ。
   消したのは次の物: SSH 経由・`--file`・codex / claude の決め打ち・cmd 経由・作業フォルダ指定・診断表示・旧版の inline 判定。
   **守りの限界**（依頼書どおり、止め方は足していない）: `harness/guard.py` の `evaluate_command` で実測した。
   | 命令 | 判定 |
   |---|---|
   | `powershell.exe -Command "Remove-Item -Recurse -Force C:/x"` | deny（中身を読める） |
   | `bash harness/tools/wsl_to_win.sh pwsh "Remove-Item -Recurse -Force C:/x"` | **allow** |
   | `harness/tools/wsl_to_win.sh cli cmd.exe /c "rd /s /q C:\x"` | **allow** |
   | `bash harness/tools/wsl_to_win.sh pwsh "Get-Content C:/Users/<人>/.ssh/id_ed25519"` | deny（秘密の path は文字列で当たる） |

   守りは、直接の `-EncodedCommand`（符号化した命令）を「読めない」として止める。**橋は中で同じ形を使うので、この止め方を迂回する入口になる。** 逆向き（`wsl_exec.*`）は SSH の窓を移さないなら要らないので、移していない。
5. **行数**: 66 行（旧版 883 行 + `win_pwsh.sh` 27 行）。

## 3. SSH の窓（`ssh_window.py` ほか 8 本、約 2,200 行）

1. **何をする物か**: エージェントが出した遠隔の命令を、**人の Windows コンソール**で SSH 実行する。パスワードは人が打つ。
   人が選んだ出力の行だけをエージェントへ返す。
   開いたまま使う版（`ssh_session*`）は、命令を順に送れて、読むだけの命令は確認なしで動く。
2. **依存**: `ssh_window.py` と `ssh_remote_policy.py` は `hooks_core`（`evaluate_tool_use`・`ADMIN_REASON`）を import している。
   ほかに `wsl_to_win.sh --file` → `ssh_window.ps1`（新しい窓を開く）→ `wsl_exec.ps1`（WSL へ戻る）の往復に依存する。練習用の模擬サーバーは `libssh.so.4` に依存する。
3. **動かした結果: 動かしていない。** 理由は 3 つ。①依頼書が「移さない」と決めている。②窓で人がキーを打つ前提で、人がいない。③旧版の練習は `old/.loop` へ書くが、`old/` は読むだけの約束。
4. **価値: 今は要らない。要るなら縮めて作り直す。** 守りを旧版の `hooks_core` に深く結んでいるので、そのままでは動かない。
   橋を往復する作りも重い。新版には、同じ考え方（人が同意し、秘密はエージェントを通らない）の `admin_window.py` がある。

### 旧版の設計の要約（20 行）

- **止める**: 命令 1 つだけを受け付ける。展開・連結・リダイレクト（`;|&><$` など）は断る。
- **止める**: 共通の守り（`hooks_core`）が deny / ask を返した命令は、窓でも実行しない（refuse）。
- **止める**: SSH の設定を固定する。利用者の config・鍵・known_hosts・agent・転送・接続の再利用を使わない（`-o` を約 30 個）。任意の `-o` は受けない。
- **止める**: 認証はパスワード方式だけ。OpenSSH が `/dev/tty` から直接読む。エージェントの pipe は通らない。
- **止める**: 要求は 0600 のファイルで渡す。SHA-256 と、表示後の読み直しで差し替えを見つける。1 回きりで、期限は既定 300 秒。
- **止める**: 出力に認証情報らしい行があれば、共有全体を止める（1 文字も返さない）。制御文字は無効にする。返すのは 8000 文字まで。
- **人に打たせる**: 実行してよいか（`y` / `Y` だけが承認）。空欄・`n`・`yes`・期限切れはすべて拒否。
- **人に打たせる**: SSH のパスワードと、接続先の鍵の確認（毎回）。
- **人に打たせる**: 返す行の選択（`a` 全部、`1,3`、`-2,5` など）。再表示のあと、もう一度 `y`。
- **表示する**: 命令の種類 1 行（例: 「`ls` — ファイルの一覧を見るだけ。遠隔側は変わりません」）、理由、接続先、送る原文。
- **開いたまま版**: 読むだけの形（`cat`・`git status` など）は確認なし（run）。未知の形は `y` を 1 キー（ask）。危ない形は質問せず拒否（refuse）。
- **開いたまま版**: pager や外部 diff を止める旗を自動で補う。補った全文を表示する。
- **開いたまま版**: 標準入力は `/dev/null`、1 命令の既定は 120 秒、窓の既定は 1 時間。再接続も再実行も自動ではしない。
- **記録する**: `.loop/ssh/usage-<ID>.jsonl` に 1 命令 1 行。時刻・判定・先頭語（既知の語だけ）・答え・終了値の 5 欄。
- **記録しない**: 引数・出力・接続先。秘密が入りうるため。
- **限界（旧版が自分で書いたもの）**: 同じ利用者のプログラムは窓へ入力でき、ファイルも書き換えられる。別の権限で守られた承認装置ではない。
- **限界**: 遠隔の PATH・別名・実体は文字列では確かめられない。`NOPASSWD` のような設定も覆せない。
- **対象外**: `scp` / `sftp` / `rsync`、鍵認証、ProxyJump、IPv6。

### `admin_window.py` に合わせて縮めた見積もり

- 形: `python3 harness/ssh_window.py --why "<理由>" --to user@host -- <命令> [引数...]`。1 回限り（開いたまま版は作らない）。
- 流用: `admin_window.check()`（命令 1 つ・記号・shell を断る）、`log()`（`.loop/ssh-window.jsonl`）、`--demo` / `--dry-run` の作り。
- 足す物は 5 つ。固定の `-o` 一式（約 30 行）、新版の `guard.evaluate_command` に命令を通す（約 5 行）、窓で理由・命令を表示して `y` を待つ（約 20 行）、出力の行を選んで秘密らしい行で止める（約 40 行）、Windows で新しい窓を開く（約 30 行。`wt.exe` か `Start-Process`、逆向きの橋を使わずに `wsl.exe -e` で戻る）。
- **見積もり: 本体 180〜230 行 + 試験 80 行前後。** 旧版の約 2,200 行から 1 割ほど（読んだ上での概算で、試作はしていない）。開いたまま版（判定表 `ssh_remote_policy` を含む）まで作るなら、さらに 400〜500 行。

### 移すときの依頼書の下書き

```markdown
# SSH の窓（1 回限り）を admin_window.py の形で作る
## 目的
エージェントが遠隔の命令を 1 つ提示し、人が窓で読んで同意し、パスワードを打ち、返す行を選ぶ。秘密はエージェントを通らない。
## 受け入れ条件
1. `harness/ssh_window.py`（250 行以内）。入口は `--why` `--to` `-- <命令>`、それに `--demo` `--dry-run`。
2. 命令は `admin_window.check()` と `guard.evaluate_command` の両方を通った物だけ。deny と ask は窓を開かずに断る。
3. ssh は固定の `-o`（config・鍵・agent・転送・接続の再利用・任意の -o を使わない。パスワード方式だけ）で、`shell=False` で起動する。
4. 窓に理由・接続先・送る原文を出す。`y` / `Y` だけで実行。空欄・`n`・期限切れ（既定 300 秒）は実行しない。
5. 出力は行番号付きで表示する。人が選んだ行だけを返す。認証情報らしい語を含む行があれば、何も返さない。返すのは 8000 文字まで。
6. `.loop/ssh-window.jsonl` に時刻・先頭語・判定・答え・終了値だけを書く（引数・出力・接続先は書かない）。
7. `tests/test_ssh_window.py` を足す（ssh を起動せず、断る形・`-o` の一式・行の選択・秘密の行の停止を確かめる）。`check.py` の `TESTS` に足す。
8. 実機（WSL2 + Windows 11）で `--demo` を人が 1 回操作し、窓が出る・`n` で止まる・`y` で結果が返ることを報告する。実在ホストへの接続は人が決める。
9. 独立の確認（`independent-check` skill）を通すまで採用しない（守りに関わるため）。
## 触ってよい場所
`harness/ssh_window.py`、`tests/test_ssh_window.py`、`harness/check.py` の `TESTS` の 1 行。`old/` と `harness/guard.py` は読むだけ。
```
