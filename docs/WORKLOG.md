# 作業ログ

このファイルは current task の停止点と次の一手だけを残す。テンプレート配布時には「現在の状態」とエントリを空 scaffold に戻す。

## handoff の最低基準

- chat 履歴に依存せず、docs だけで再開できること。
- 「たぶんこうだろう」で埋めなくてよいこと: 観測事実、実行したコマンドと結果、判断と仮定を残す。
- 次のエージェントが最初に開く文書と、最初に打つコマンドが分かること。
- 未確認部分と失敗した試行を隠さないこと。「途中です」「だいたい終わった」は handoff にならない。

## 現在の状態

- 現在の作業:
  - TASK-HARNESS-DOCS-VIDEO-20260810: ハーネス、Docs、再現動画を製品PRと分離したbranchへpush
- 直近の状態:
  - `codex/harness-docs-video`は製品修正の親commit `4234b9902`から作成。Android製品ファイルの差分は含まない
  - `Video/screen-20260807-193853.mp4`は2,534,420 bytesで、GitHubの100MB制限内。`tmp/`、APK、`node_modules`、local設定は対象外
  - security smoke、template smoke、`git diff --check`はPASS。Windows Codex未導入だけoptional skip
  - 製品PR #15799は引き続きOpen/Draft、head `edc508957`。本文、maintainer会話、Ready状態は変更しない
- 次にやること:
  - Xperiaへ最終universal v3をinstallし、ロゴからメイン画面へ遷移することを確認する
  - remote sessionで2本指・3本指後のpointer移動、tap、screen pan/scale、scroll/cancel復帰を確認する
  - FAILならremote peer OS、Xperia入力mode（Touch/Mouse）、relative mouse modeを記録し、`remote_input.dart`候補へ戻る
  - PASSならPR #15799本文更新、Ready化、maintainer返信を行う
- ブロッカー:
  - agent側startup gateは完了。Xperia実機のArm64 startupとgesture結果だけ未確認
  - upstream CIはfork PRのため`action_required`。maintainer approval前でありcode failureではない
- 次に最初に読む文書:
  - 本WORKLOG、`docs/EXECPLAN_2026-08-08_android-multitouch-reset-timer.md`、`docs/REQS.md`
- 次に最初に実行するコマンド:
  - `sha256sum tmp/rustdesk-multitouch-reset-timer-universal-release-v3.apk`

---

## エントリ

### 2026-08-10: ハーネス・Docs・Video分離push checkpoint

- ユーザーの明示許可に基づき、未コミットのハーネス、Docs、再現動画を`codex/harness-docs-video`へcommit・通常pushする。PRは作らない。
- branch基準は製品修正前の`4234b9902`。`flutter/lib/common/widgets/gestures.dart`と回帰testは含めず、PR #15799の小さな差分を維持する。
- 再現動画は`Video/screen-20260807-193853.mp4`の1本、2,534,420 bytes。100MB超のfileとAPKは対象にない。
- 検証: `bash scripts/security_smoke.sh`、`TEMPLATE_SMOKE_WINDOWS_TIMEOUT=20s bash scripts/smoke_template.sh`、`git diff --check`はPASS。Windows Codexの検出だけoptional skip。
- 安全性: `.env`、token、秘密鍵、証明書、credential、local設定、`tmp/`、`node_modules`、`__pycache__`をcommit対象外にした。
- 残リスク: ハーネスbranchのPRは作成しないため、必要な場合の取込み判断はユーザー側に残る。
- 次の一手: `docs/REQS.md`とreset timer ExecPlanを読み、Xperiaで最終universal v3の2本指・3本指gestureを確認する。

### 2026-08-09: reset timer分離 — 自動gate/APK checkpoint

- 原因確定: Flutterはback-to-back pointer-upで最初の`onEnd(1)`だけを呼び得る。RustDeskはend resetとlower-finger startで`_debounceTimer`を共有し、後続moveがresetをcancelするため旧multi-touch stateが残留した。
- 修正: reset専用`Timer? _resetTimer`を追加。`onUpdate`はstart debounceだけをcancelし、実start・end・reject・disposeでreset timerの所有を閉じる。`remote_input.dart`は未変更。
- 3版比較: baseは最終assertが`Expected 1 / Actual 0`、現PR版は200ms内assertが`Expected 0 / Actual 1`、最終案のみPASS。
- focused test、非commit安全性7件、formatter、focused analyze、`git diff --check`は全PASS。
- `TEMPLATE_SMOKE_WINDOWS=0 bash scripts/smoke_template.sh`と`bash scripts/security_smoke.sh`もPASS。
- Flutter 3.24.5、JDK 17.0.20、Android SDK 34、base commit一致のbridge/Rust artifactでArm64 debug/profile APKをbuild。profile APKは37MB、package `com.carriez.flutter_hbb` 1.4.9 (2067)、minSdk 22、targetSdk 33、Arm64-only、zipalign、v1/v2署名を確認。
- 初回profile/debugは`libc++_shared.so`を含めず、Xperiaで起動クラッシュ。旧起動可能APKとのnative entry比較と`readelf -d`で原因を確定した。
- 同じAArch64 runtimeを追加してprofile v2を再build。embedded `libc++_shared.so`のSHA-256は旧APKと一致し、`librustdesk.so`の残りのNEEDEDはAndroid system libraryだけ。
- profile v2はXperiaでロゴ停止。release universal v3をWindows/WHPX API 33 AVDへinstallし、Visionでメイン画面とSettings画面を確認。3回cold relaunchもPID生存、crash buffer空。
- 最終APKは`tmp/rustdesk-multitouch-reset-timer-universal-release-v3.apk`、SHA-256 `cd08115113341c21024ecc1224ccbe22842ae1d05dbac9fac5c8b816d1f0242f`。Arm64/x86_64を同梱するため、Vision確認した同じAPKをXperiaへ渡せる。
- 製品2ファイルだけをcommit `edc508957`へamendし、force-with-lease push済み。PR #15799はOpen/Draftのまま、本文とmaintainer会話は未変更。
- 未完了: Xperia実機gesture確認、PR #15799本文更新、Ready化。
- 次の一手: 最終universal v3をXperiaへinstallし、2本指・3本指を各3回行った後のpointer/tap/pan/scroll cancelを確認する。

### 2026-08-08: Xperia実機FAIL — PC再起動handoff

- user実機結果: 3本指操作後はpointerと画面が操作不能。2本指操作後も画面操作が異常。純粋追加1行版は解決していない。
- 現branchは`codex/fix-android-multitouch-stuck-state`、HEADは`42ccff2e886572ef35de0da255c77b0fbe92a932`。製品diffは`gestures.dart` 1行追加とfocused test 51行。製品working treeはclean。
- PR #15799はOpen/Draft、head `42ccff2e8`。新しいmaintainer reviewはなくCodeRabbitはDraftのためskip。本文は成功前提なのでReady化禁止。
- 不合格APKのhashは`f074710ca8109679fda6f2ab6524fb4942ba8b00528171548845243a09f322e8`。build検証結果は有効だが機能合格には使わない。
- static observation: `onOneFingerPanStart`はtouch modeでleft downと`_touchModePanStarted=true`、cancelはflag resetのみ。`makeGestures`は3本指updateだけを配線し、start/endは未配線。次回調査候補であり原因確定ではない。
- user指定により、再開後はClaude Code Opus5 Highを計画専任・編集禁止で使う。OpenCodeは承認後の実装担当。
- 実行中agent/processなし。再起動前に新しいagent、commit、push、PR編集は行っていない。
- 次の一手: 上記3文書と`remote_input.dart:354-585`を読んだ後、`claude --help`で利用可能なOpus5/effort指定を確認し、read-only planを依頼する。
