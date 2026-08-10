# Worklog archive — 2026-08-07

直近3件を超えた作業記録。通常の再開では読まない。

### 2026-08-08: Android multitouch修正 — 純粋追加1行版checkpoint

- maintainerの「big change to core logic」を受け、旧state-machine rewriteをbaseへ戻した。
- 本番変更は`onEnd`の既存200ms timer直前へ`_currentState = GestureState.none;`を追加する1行だけ。削除、新field/helper/enum、platform gate、座標変更なし。
- Flutter 3.24.5: focused testはbaseで`Expected: 1 / Actual: 0`、修正後pass。3→2、二重end、same-count restart、special holdの非commit 4 testsもpass。focused analyze `No issues found`、formatと`git diff --check`成功。
- agy Claude Opus 4.6 Thinking最終review: PASS。dispose時の既存timer非cancelはbase由来で、今回のtimerは`none`への冪等書込に変わるためblocking regressionではない。
- Arm64 release APK build成功。ZIP integrity、zipalign、package `com.carriez.flutter_hbb` 1.4.9 (2067)、minSdk 22、targetSdk 33、Arm64-only、debug certificateのv1/v2署名を確認した。
- APK: `tmp/rustdesk-multitouch-fix-arm64-v8a.apk`
- SHA-256: `f074710ca8109679fda6f2ab6524fb4942ba8b00528171548845243a09f322e8`
- commit `42ccff2e886572ef35de0da255c77b0fbe92a932`へamendし、force-with-lease push済み。製品diffは2 files、52 additions、0 deletions。本番コードは1行追加のみ。
- PR #15786はClosedで再Open不可。縮小内容を返信し、新しいDraft PR #15799を作成した。
- 未完了: Xperia実機確認、DraftのReady化、maintainer承認後のCI確認。
- 次の一手: `sha256sum tmp/rustdesk-multitouch-fix-arm64-v8a.apk`を確認し、Xperiaへinstallする。

### 2026-08-07: Android multitouch修正 — APK handoff checkpoint

- 原因:
  - Flutter 3.24.5はpointer構成変更時に新`pointerCount`で`onEnd`を呼び、次のmoveで再度`onUpdate`する。
  - RustDeskはend後のstate resetと2→1 / 3→2の遅延startに同じ`_debounceTimer`を使う。
  - 連続moveがtimerを毎回cancel/rearmし、lower-finger stateへ永続的に遷移できなかった。
- 製品変更:
  - `flutter/lib/common/widgets/gestures.dart`: pending targetと最新detailsを保持し、同じtargetのupdateで200ms deadlineを延長しない。target変更、end、reject、disposeでcancelする。3本以上を一貫処理する。
  - `flutter/test/common/widgets/gestures_test.dart`: 2→1、3→2、reversion、all-up、3本以上、single-touchの6件。
- 検証:
  - Flutter 3.24.5 / matching bridge artifactでpre-fixの2→1 testが`Expected: 1 / Actual: 0`で失敗。
  - 同環境で修正後の6 testsが全て成功。
  - `flutter analyze lib/common/widgets/gestures.dart test/common/widgets/gestures_test.dart`: `No issues found`。
  - `dart format`適用、`git diff --check`成功。
  - agy Claude Opus 4.6 Thinking final review: PASS。200ms中の旧state updateは既存挙動を有限時間へ限定する非blocking risk。
  - Flutter 3.24.5、JDK 17、Android SDK 34で`flutter build apk --release --target-platform android-arm64 --split-per-abi --no-pub`成功。
  - APKはZIP integrity成功、package `com.carriez.flutter_hbb`、version `1.4.9` (2067)、minSdk 22、targetSdk 33、ABIは`arm64-v8a`のみ。
  - APK署名はAndroid Debug certificateでv1/v2 verify成功。
- APK:
  - path: `tmp/rustdesk-multitouch-fix-arm64-v8a.apk`（gitignore済み、製品PRへ含めない）
  - size: 約26.9MB
  - SHA-256: `4352efdbd22bfa70b4435c2bd7bc666b3e1212759d6cc2840ea0d8e4fae440ef`
- build上の判断:
  - Dart変更だけなので、基準commitと同じupstream CI run `31157306586`のArm64 `librustdesk.so` artifactを再利用した。
  - build隔離worktreeだけでdebug署名とRust Maven pathを設定し、製品diffへ混入させていない。
- 未完了:
  - Xperia 1 VII / Android 16実機確認、PR本文更新、Ready化、upstream CI確認。
- PR準備:
  - title/body/device checklist: `docs/PR_DRAFT_2026-08-07_android-multitouch.md`
  - video: `https://github.com/TsukinowaRin/rustdesk/releases/download/android-multitouch-repro-20260807/screen-20260807-193853.mp4`
  - remote asset SHA-256はlocal videoと一致: `576d068e4fdbc1150e7999d06c9c3c0adcfa28f70dc4929f4d4af5b63003ccd4`
- 次の一手:
  - 実機PASSを受けたら`gh pr view 15786 -R rustdesk/rustdesk --json body,isDraft,statusCheckRollup`を最初に実行し、本文更新後にReady化する。

### 2026-08-07: Android multitouch 残留 — 却下済み初稿調査 (grok-investigator)

- 目的: 2/3+ 指操作後に 1 本分 touch が残る原因と event sequence を特定する（編集なし）。
- mailbox: `batch-20260807T113004Z-39c1f0c5c861` / `TASK-ANDROID-MULTITOUCH-20260807` / role `grok-investigator`
- 変更: コード変更なし。本 WORKLOG のみ更新。
- 観測（コード）:
  - `CustomTouchGestureRecognizer` が `ScaleGestureRecognizer` 上で `_currentState` を `pointerCount` で切替。
  - `onEnd` 後 200ms は state を残す。`_debounceTimer` が start debounce と end reset で共有され、`onUpdate` 先頭で cancel される。
  - 1指→2指へ遷移時に `onOneFingerPanEnd` を呼ばない。
  - 2指→3指へ遷移時に `onTwoFingerScaleEnd` を呼ばない。
  - 3指 end は callback 任意。`makeGestures` は start/end を未配線。peer Android では update も null だが state 自体は入る。
  - touch mode の 1 指 pan は `sendMouse(down)` + `_touchModePanStarted=true`。cancel は flag のみ false で **mouse up なし**。
  - 2 指 end だけが補償的に `sendMouse(up)` する。3 指 end / reject cancel 経路では補償されない。
- 当時の最有力 sequence（後続調査で不採用）:
  1. 1 指 pan start → remote left down, `_touchModePanStarted=true`
  2. 2 指追加 → `twoFingerScale`（1 指 end なし、button 維持）
  3. 3 指追加 → `threeFingerVerticalDrag`（2 指 end なし）
  4. 全指 up → `onEnd` が 3 指 branch、release なし
  5. residual: remote left held +/or `_touchModePanStarted` 残留 → 以降の move/tap/scroll が壊れる
- 検証:
  - 静的読取のみ。shell は `AGENT_DELEGATED_SHELL=deny` で不可。
  - 動画 `Video/screen-20260807-193853.mp4` は未再生。
- 判断と仮定:
  - 制御側は Android（Xperia）。peer が Android だと 3 指 update 無効でも state は立つため、3 指を使うと cleanup 穴が特に出やすい。
  - 最小 fix は recognizer の state 遷移で「前 state の end」を必ず呼ぶ + cancel/end で mouse up を対にする。
- 未完了: 実装、自動 test、実機確認、本家 PR。
- 訂正:
  - Flutter 3.24.5のpointer reconfigure時`onEnd`を初稿が見落としていた。主因はmouse-up経路ではなくshared timerのcancel/rearm競合であり、`remote_input.dart`変更は不要と確認した。

### 2026-08-07: Universal Agent Harness v2.6.2導入

- 目的: 指定releaseの最新ハーネスをこのRustDesk forkへ導入し、検証済みの運用基盤にする。
- 変更:
  - v2.6.2 clean assetの101ファイルを基に、競合しないハーネス構成を追加。
  - RustDeskの`README.md`とproject固有`AGENTS.md`を維持し、共有rule、Claude bridge、ignore、line-ending設定をマージ。
  - `docs/PROJECT_BRIEF.md`をRustDeskのRust/Flutter構成とbuild/test入口で初期化。
  - Antigravityが`AGENTS.md`をnative読込するv2契約に合わせ、旧1行bridgeの`GEMINI.md`を削除。
- 検証:
  - GitHub latest API: `v2.6.2`（published 2026-08-05）。
  - asset SHA-256: `cb57c5df24c46d679d417b9a68d6a7efcd288ea465f3254aedb7eb5a951f992e`、release記載値と一致。
  - `python3 scripts/sync_shared_context.py --check`: 成功（7 CLI）。
  - `TEMPLATE_SMOKE_WINDOWS=0 bash scripts/smoke_template.sh`: 成功。Windows wrapperの実機部分だけ意図的にskip。
  - `bash scripts/security_smoke.sh`: 成功。
  - `git diff --check`: 成功。
- 判断と仮定:
  - 「取得」はarchive保存ではなくworkspaceへの導入まで含むと解釈した。
  - 製品READMEは置換せず、ハーネス説明の正本を`docs/HARNESS.md`とした。
- 観測した失敗:
  - browser download URLは404だったため、認証済みGitHub asset APIから取得した。
  - `unzip`が未導入だったため、Python標準`zipfile`で展開した。
  - 初回smokeは既存`GEMINI.md`を廃止済みv1構造として検出し停止。旧bridgeを削除後に再実行して成功した。
- 未完了: なし。外部CLIのuser-level設定、plugin、認証、modelは変更していない。
