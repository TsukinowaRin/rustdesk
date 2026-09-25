# 使い捨ての Windows デスクトップ（Windows Sandbox）

画面操作を、母艦のデスクトップではなく**使い捨ての Windows** の中でやるための台本。
閉じると中身は全部消える。鍵もパスワード管理も入っていないので、うっかり見えることがない。

**2026-09-20 に実測して通った。** 診断 9/9 合格、画面 2032x1111 を認識、JPEG 1024x559 を取り出せた。

## 使い方

1. 取ってくる（初回だけ。版は固定する）
   - Node: `https://nodejs.org/dist/v22.20.0/node-v22.20.0-win-x64.zip` → `in/node.zip`
   - MSVC の実行時ライブラリ: `https://aka.ms/vs/17/release/vc_redist.x64.exe` → `in/vc_redist.x64.exe`
2. `test.wsb`（下の形）を書いて `WindowsSandbox.exe <その .wsb>` で起動する
3. 中で `setup.ps1` が走り、結果が `out/` に出る。終わると自分で閉じる

## 通すのに要ったもの（実測で分かった落とし穴）

| 落とし穴 | 症状 | 直し方 |
|---|---|---|
| **MSVC の実行時ライブラリが無い** | MCP サーバーは起動するが `initialize` が `Internal server error`。stderr に `The specified module could not be found` | `vc_redist.x64.exe` を**手元に写してから**実行する（読み取り専用の場所から直接だと入らない） |
| Sandbox は同時に 1 つだけ | 2 回目の起動が黙って何も起きない | 台本の最後で `shutdown /s /t 0` して自分で閉じる |
| 管理者権限 | — | **要らなかった**。ただし機能自体が有効になっている必要がある（Windows Pro / Enterprise のみ） |
| 文字化け | 記録の日本語が読めない | 機械が読む値は `Out-File -Encoding ascii` で英数字にする |
| 撮影の形式 | `shot.png` という名前だが中身は JPEG | 名前で判断せず、先頭のバイトで見る |

## 持ち込みと持ち出し

- 持ち込みは `in/` を**読み取り専用**で 1 つだけ。持ち出しは `out/` だけ。
- クリップボードの共有は切る（`<ClipboardRedirection>Disable</ClipboardRedirection>`）。
- ネットワークは既定で入り（`npx` が要る）。切るなら、必要な物を全部 `in/` に入れてから。

## .wsb の形

```xml
<Configuration>
  <MappedFolders>
    <MappedFolder><HostFolder>...\in</HostFolder><SandboxFolder>C:\in</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>...\out</HostFolder><SandboxFolder>C:\out</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
  </MappedFolders>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <Networking>Default</Networking>
  <LogonCommand><Command>powershell -ExecutionPolicy Bypass -File C:\in\setup.ps1</Command></LogonCommand>
</Configuration>
```
