# 使い捨ての Windows（Hyper-V）

Windows Sandbox が無い環境（Windows Home は不可。Pro でも Sandbox を切っている機械）や、**中の状態を作り込みたい**とき用。
Sandbox と同じ台本（`../windows/probe.mjs`）を、Hyper-V の使い捨て VM の中で走らせる。

**2026-09-24 に実測して通った。** Windows 11 dev environment（評価版）を差分ディスクで起動 → 台本を管理者として起動 → MCP の診断 9/9 合格 → 1024x768 の画面を撮って母艦へ持ち出し → VM を削除。台本の開始から完了まで 174 秒。母艦の管理者権限は使っていない。

## 使い方（母艦の PowerShell。WSL からは `harness/tools/wsl_to_win.sh pwsh '& <この vm.ps1> ...'`）

前提: 利用者が `Hyper-V Administrators` グループに入っている（入れるには管理者の窓 `harness/admin_window.py` を 1 回通し、サインインし直す）。

1. 元の OS を 1 回だけ用意する（例: Windows 11 dev environment。23 GB の zip → 45 GB の .vhdx）
   - 一覧: `https://go.microsoft.com/fwlink/?linkid=851584`（UTF-16 の JSON。行コメントと末尾カンマがあるので、そのままでは `json.loads` できない）
   - 取得は Windows 側の `curl.exe` で（WSL の curl で `/mnt/c` に書くと 10 倍以上遅い）。hash を照合し、`tar.exe -xf` で取り出す
   - 置き場は利用者の領域（`%USERPROFILE%\harness-vm\dl\`）。**既定の `C:\ProgramData\...` は管理者権限が無いと書けない**
2. `vm.ps1 create -Name harness-win -Template <元の .vhdx>` — 元を親にした**差分ディスク**で VM を作る（元は書き換えない。消すのは差分だけ）
3. `vm.ps1 setup -Name harness-win -InDir <持ち込み> -PwFile <pw.txt>` — 起動 → `C:\in` へ写す → 中の台本を起動
4. `vm.ps1 run -Name harness-win -PwFile <pw.txt>` — `C:\out\DONE.txt` が出るまで待つ
5. `vm.ps1 fetch -Name harness-win -PwFile <pw.txt> -OutDir <持ち出し>` — `C:\out` を母艦へ
6. `vm.ps1 destroy -Name harness-win` — 電源を切り、VM と差分ディスクを消す

持ち込みフォルダに置く物: `node.zip` `vc_redist.x64.exe` `probe.mjs`（`../windows/` と同じ）と `pw.txt`（VM の中の利用者に付けるパスワード。乱数でよい。`.loop/` に置き、git に入れない）。`guest-setup.ps1` はこの場所の物が自動で入る。

## 母艦と VM の間の道（Sandbox との違い）

| 向き | Sandbox | Hyper-V |
|---|---|---|
| 母艦 → VM（持ち込み） | 共有フォルダ（読み取り専用） | `Copy-VMFile`（Guest Service Interface。一方通行） |
| 台本の起動 | `.wsb` の LogonCommand | **母艦からのキー入力**（`Msvm_Keyboard`: Win+R → 管理者として powershell → UAC に Alt+Y） |
| VM → 母艦（持ち出し） | 共有フォルダ | PowerShell Direct（`Invoke-Command -VMName`）で `C:\out` を読む。そのために台本が最初に利用者へパスワードを付ける |
| 画面を覗く | — | `vm.ps1 peek`（Hyper-V の縮小画像。VM の中に何も要らない） |

## 通すのに要ったもの（実測で分かった落とし穴）

| 落とし穴 | 症状 | 直し方 |
|---|---|---|
| 統合サービスの名前が OS の言語で変わる | `Enable-VMIntegrationService -Name 'Guest Service Interface'` が「見つかりません」（日本語では「ゲスト サービス インターフェイス」） | Id `6C09BB55-...` で選ぶ |
| `Restart-VM -Force` | 電源断と同じ扱い。2 回続けると Windows が Recovery 画面で止まり heartbeat が戻らない | `Stop-VM` → `Start-VM`。今の台本は再起動そのものをやめた |
| Startup フォルダに台本を置く方法 | 台本は走るが、`net user` が UAC で `Access is denied` | 管理者としての起動をキー入力で行い、UAC を Alt+Y で通す |
| 差分ディスクの初回起動 | heartbeat が OK になっても画面は「This might take a few minutes」。早く打ったキーは捨てられる | パスワードが通るまで 40 秒ごとに打ち直す。台本側は `STARTED.txt` で 2 重起動を防ぐ |
| PowerShell Direct の資格情報 | パスワード無しの利用者は「資格情報が無効です」 | 台本の最初でパスワードを付ける（`pw.txt`） |
| 評価版の期限 | 画面右下に「Windows License is expired」 | 短い試験なら動く。長く使うなら新しい版の評価版を取り直す |
| `vc_redist` の戻り値 3010 | 「再起動が要る」の意味で失敗ではない | `vcruntime140.dll` の有無で見る |
| 撮影の形式 | `shot.png` の中身は JPEG | 先頭のバイトで見る（Sandbox と同じ） |

## 守り

- VM の名前は `harness-` で始める。`vm.ps1` はそれ以外の名前を作らず消さない（母艦にある他の VM を巻き込まない）。
- ネットワークは `Default Switch`（NAT。`npx` が要る）。切るなら `-SwitchName` を外し、持ち込みに全部入れる。
- 母艦の管理者権限は要らない。UAC を通すのは VM の中だけ。
- `pw.txt` と持ち出した物は `.loop/` に置く。
