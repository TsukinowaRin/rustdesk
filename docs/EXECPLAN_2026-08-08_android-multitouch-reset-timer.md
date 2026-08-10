# Android multitouch reset timer separation

plan_id: PLAN-20260808-ANDROID-MULTITOUCH-RESET-TIMER-001
基準commit: 4234b99029bf32c23098b4eaeec8efc135c8e80a
plan_revision: 1

<!-- execplan:original:start -->

## 目的

Xperia 1 VIIで2本指・3本指を離した後にpointerまたは画面操作が異常になる問題を、`CustomTouchGestureRecognizer`の既存state machineを組み替えずに直す。end後のstate resetと下位gesture startのdebounceで同じtimerを共有している点だけを分離し、指を離す途中の200ms guardを残す。

## Flutter 3.24.5の契約

- `ScaleGestureRecognizer.handleEvent()`はpointer構成変更ごとに`_reconfigure()`を呼ぶ。
- `_state == started`なら`_reconfigure()`は新しい`pointerCount`で`onEnd`を呼び、直後に`accepted`へ戻る。
- 2本をほぼ同時に離す場合、最初のupで`onEnd(1)`が呼ばれる。残りをmoveせずupするとstateは`accepted`のままなので`onEnd(0)`は呼ばれない。
- 現コードは`onEnd(1)`でresetを`_debounceTimer`へ入れ、次のtouch update先頭でcancelする。このため古いtwo/three-finger stateが残り、以後の1本指updateが古いcallbackへ配送される。

一次情報: Flutter 3.24.5 `packages/flutter/lib/src/gestures/scale.dart` の`handleEvent()`と`_reconfigure()`。

## 採用設計

`Timer? _resetTimer`を1本だけ追加する。

1. `onEnd`はstart debounceをcancelし、既存reset timerをcancelしてから新しいreset timerを所有する。
2. `onUpdate`は`_resetTimer`をcancelしない。連続moveでもendから200ms後のresetは必ず発火する。
3. one/two/three-finger gestureが実際にstartするときは`_resetTimer`をcancelし、active gestureを後発resetが`none`へ戻さないようにする。
4. `rejectGesture`と`dispose`はdebounce/reset timerを両方cancelする。
5. special-holdのearly returnと既存callback分岐は変更しない。

upstream base比の製品差分は`+14/-1`、15変更行。新helper、enum、dependencyは追加しない。

## 予定変更ファイル

- `flutter/lib/common/widgets/gestures.dart`
- `flutter/test/common/widgets/gestures_test.dart`
- 作業記録のみ: `docs/EXECPLAN_2026-08-08_android-multitouch-reset-timer_impl.md`

## 変更禁止

- `flutter/lib/common/widgets/remote_input.dart`
- Rust、Kotlin、dependency、lockfile、Video、harness設定
- state enum、callback分岐、座標計算、special-hold処理
- 検証完了前のcommit、push、PR編集、maintainer返信

## 実装手順

1. 現HEADで追加した`onEnd`末尾の無条件`_currentState = GestureState.none;`を撤回する。
2. `_debounceTimer`の隣へ`Timer? _resetTimer;`を追加する。
3. `onEnd`末尾のreset timer所有先を`_resetTimer`へ変更し、arm前に既存resetをcancelする。
4. one/two/three-fingerの実start地点でreset timerをcancelする。
5. `rejectGesture`で両timerをcancelする。
6. `dispose` overrideで両timerをcancelしてから`super.dispose()`を呼ぶ。
7. testを実pointer駆動の1件へ置換する。

## committed test

`RawGestureDetector`へ`CustomTouchGestureRecognizer`だけを載せ、実pointer eventを送る。

1. 2本を動かしてtwo-finger scaleを開始する。
2. 2本をpumpなしで連続upし、`onEnd(1)`だけが出るsequenceを作る。
3. 50ms後に新しい1本指gestureを開始し、200ms窓内ではone-finger startが出ないことを確認する。現HEADはここで早すぎるstartとなりFAILする。
4. 40msごとのmoveを継続し、endから200msを越えた後にone-finger startがちょうど1回出ることを確認する。baseはresetがcancelされ続け0回のためFAILする。
5. 全指up後にtimerが残らないことを確認する。

## 非commit安全性test

- 3→2→1で各段のstart/endが重複しない。
- 1→2、2→3の上向き遷移が即時のまま。
- same-count restartは200ms以内にbounded recoveryする。
- duplicate `onEnd`でlive reset timerが1本だけ。
- reject後にpending startが発火しない。
- special holdのearly returnを維持する。
- dispose後にpending timerが残らない。

## Gates

1. Flutter 3.24.5のpointer-up契約を一次sourceで再確認する。
2. 新testがbaseでlate-start assertionにFAIL、現HEADでearly-start assertionにFAIL、最終案でPASSする。
3. 非commit安全性testが全てPASSする。
4. 対象2ファイルへFlutter 3.24.5 formatterを適用する。
5. focused `flutter analyze`が`No issues found`、`git diff --check`が成功する。
6. base比の製品差分が15変更行以内で、対象外製品fileが無い。
7. Android Arm64 release APK build、ABI、alignment、v1/v2署名検証が成功する。
8. Xperiaで2本指・3本指後のcursor、tap、canvas pan/scale、scroll cancelが正常に復帰する。

## Stop

- Flutter一次sourceまたは実pointer testが前提sequenceを否定したら実装せず停止する。
- 製品差分が15変更行を超える場合はdeviationとして停止する。
- `remote_input.dart`変更が必要になった場合は、peer OS・入力mode・relative modeの実機情報を得るまで停止する。
- 自動gateを通ってもXperiaでFAILした場合はPRを更新せず、診断へ戻る。

## 復旧

- 検証は既存の隔離worktreeを使い、main working treeの既存変更を巻き戻さない。
- 対象fileの一時切替は明示したsourceからの`git restore`またはtask用worktreeで行う。`git reset --hard`と`git checkout --`は禁止。
- remote headの既知値は`42ccff2e886572ef35de0da255c77b0fbe92a932`。leaseが異なる場合はpushせず停止する。

<!-- execplan:original:end -->

## 進捗

- [x] Opus5 Highのread-only初稿を作成。
- [x] 未追跡timer積層と`pointerCount == 0` gateの反例を指揮官が発見し、2回差し戻した。
- [x] 専用reset timer 1本の最終計画をOpus5が作成し、指揮官が一次sourceと照合して承認。
- [x] OpenCode実装と指揮官修正（gestures.dart logic +14/-1、formatter後+15/-1、実pointer test置換）。
- [x] 3版failure-before、focused test/analyze/format、非commit安全性7件、Arm64 debug/profile APK。
- [x] agent側Vision/logcat startup gateとrelease universal APK。
- [x] 製品2ファイルをcommit `edc508957`へamendし、force-with-lease push。
- [ ] Xperia確認、PR #15799更新とReady化。

## 現在の停止点

- 現在位置: release universal v3のagent gateをPASSし、製品2ファイルだけをcommit `edc508957`へamend・push済み。PRはDraftのまま。Xperia gestureだけ未確認。
- 次の一手: `tmp/rustdesk-multitouch-reset-timer-universal-release-v3.apk`をXperiaへinstallし、2本指・3本指後のpointer/tap/pan/scroll cancel復帰を確認する。
- 次に読むfile: 本plan、`docs/WORKLOG.md`、`docs/REQS.md`。
- 最初のcommand: `sha256sum tmp/rustdesk-multitouch-reset-timer-universal-release-v3.apk`。

## 判断ログ

- 判断: fieldなしの未追跡reset timer案を不採用。
  理由: 3→2→1で複数timerが積まれ、後発timerがactive gestureをclobberする。
- 判断: 全指upだけ即時resetする案を不採用。
  理由: Flutterはほぼ同時upで`onEnd(0)`を呼ばず、元のshared timer bugが残る。
- 判断: 専用`_resetTimer` 1本を採用。
  理由: timer ownershipを明示し、既存state machineと200ms guardを保ったまま全sequenceを閉じられる最小案。
- 判断: Dart formatterが`dispose`前へ追加する空行を維持し、base比`+15/-1`を採用。
  理由: 意味のある変更は計画どおり`+14/-1`で、未整形にして1行減らすよりformatter gateを優先する。
- 判断: profile APKをXperia推奨、debug APKを予備とする。
  理由: profileはArm64 AOTでrelease挙動に近く、Android標準debug署名のためrepoへ鍵設定を追加しない。
- 判断: 次のAPK案内前にagent側Vision/logcat startup gateを必須とする。
  理由: v2はnative依存検証を通過してもロゴで停止し、packaging gateだけでは起動可能性を保証できなかった。
- 判断: profile APKを廃止し、debug署名のrelease universal APKを実機候補とする。
  理由: release候補は同一APKでagent側Vision/logcat gateを通り、Arm64とx86_64のnative runtimeを完全収録する。

deviation: DEV-001 | formatter必須空行により製品numstatが+15/-1 | 対象: flutter/lib/common/widgets/gestures.dart | 2026-08-09
approval: DEV-001 | 指揮官承認。logic差分は計画内で、formatter準拠を優先

## 保留

- peer OS、Xperia入力mode、relative mouse modeは未回答。
- `onOneFingerPanCancel`のmouse-up非対称と3本指start/end未配線は別候補。今回の実装では触らず、Xperia再検証結果で判断する。
- PR #15799のheadは`edc508957`。ユーザー明示許可により製品commit/pushだけ先行し、PR本文、maintainer会話、Ready状態はXperia PASS前に変更しない。
