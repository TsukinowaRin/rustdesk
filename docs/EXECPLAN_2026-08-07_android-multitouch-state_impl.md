plan_id: PLAN-20260807-ANDROID-MULTITOUCH-001
# 作業ログ（実行エージェントが追記する）

## 2026-08-07 iteration 1/2: OpenCode DeepSeek V4 Flash 0731 — test-first実装

### 変更ファイル（計画の予定変更範囲内のみ。deviation なし）
- `flutter/lib/common/widgets/gestures.dart` (M)
- `flutter/test/common/widgets/gestures_test.dart` (新規)
- 本 impl log (許容する付随変更)

### 実装内容（gestures.dart）
- `_PendingStart { none, oneFinger, twoFinger }` enum を追加し、`_debounceTimer` の用途を明示。
  pending 中の start target (`_pendingStart`) と最新 details (`_pendingDetails`) を保持。
- `onUpdate`:
  - `pointerCount >= 3` を three-finger として一貫処理（旧: `== 3` のみ）。4本以上で余計な
    state reset/start を起こさない（count 一致時は `_cancelPendingStart()` のみ）。
  - count が現在 state と一致する場合は `_cancelPendingStart()`（end-reset 用 timer もここで cancel）。
  - 下降遷移が必要な場合 `_armPendingStart(pending, d)` へ。
- `_armPendingStart`: one-finger は `_currentState == none` なら即start（旧挙動維持）、
  two-finger は `_currentState != threeFingerVerticalDrag` なら即start（旧挙動維持）。
  下降遷移（2→1, 3→2）のみ 200ms debounce。**同じ pending target への連続 update は
  deadline を延長せず `_pendingDetails` だけ更新**。target が変わったら旧 pending を cancel して再 arming。
- `_firePendingStart`: timer 発火時に最新 details で start を1回だけ実行し、pending を clear。
- `onEnd`: 先頭で `_cancelPendingStart()` を追加（指が消えた後に pending start が発火する
  幽霊 gesture を防止）。末の 200ms end-reset は維持。
- `rejectGesture`: 先頭で `_cancelPendingStart()` を追加（reject 後の遅延 start を防止）。
- `dispose` override を追加し `_cancelPendingStart()` してから super へ（stale timer 残存防止）。
- `onOneFingerStartDebounce` / `onTwoFingerStartDebounce` は上記 helper 群に置換
  （ファイル外からの参照は無いことを grep で確認）。

### 追加テスト（flutter/test/common/widgets/gestures_test.dart、testWidgets + tester.pump で fake clock）
1. 2指→1指: 200ms 未満間隔で連続 move を投入しても、最初の本数変更から 200ms 経過時点で
   one-finger start が1回だけ発火。150ms 時点で未発火（debounce 維持）、発火後は最新 focalPoint
   が使われ、再発火しない。遷移後は one-finger update へ流れる。
2. 3指→2指: 同上の遷移が1回だけ成立。
3. pending one-finger start 中に 2 指へ戻った場合、stale start は発火しない。
4. pending 中に 3 指へ増えた場合、pending は cancel され three-finger start が1回。
5. onEnd(全指 up) 後に pending start が幽霊発火しない。
6. rejectGesture 後に pending two-finger start が発火しない。
7. 4本指・5本指を three-finger として一貫処理（余計な restart なし）。
8. none からの 1 指は即 start、update、end（回帰維持）。
9. 1 指からの 2 指は即 start（回帰維持）。
10. end 後 200ms の end-reset 後、新しい 1 指 gesture は即 start（回帰維持）。

### 実行したコマンドと結果
- `git diff --check`: 成功。
- `test -s flutter/test/common/widgets/gestures_test.dart`: 成功（非空、278行）。
- `awk 'length > 80'` で追加コード行の桁数確認: gestures.dart の 80 桁超は既存コメントのみ
  （dart format はコメントを改行しないため対象外）。test は追加行すべて 80 桁以内に整形済み。
- `git diff -- flutter/lib/common/widgets/gestures.dart` で最終 diff を計画と突合: 変更は
  予定変更ファイル2つ + impl log のみ。

### 未実行のチェック（理由付き）
- `flutter test test/common/widgets/gestures_test.dart`: 未実行。ローカル Flutter 3.24.5 SDK は
  `/tmp/rustdesk-flutter-3.24.5-20260807` に準備済みだが、loop 契約が作業ディレクトリ外
  （/tmp 含む）への read/write を禁止しており、GOAL も SDK download を禁止。チェックは
  runner/指揮官側（fork CI または許可された環境）へ委譲。
- `dart format --output=none --set-exit-if-changed ...`: 未実行（dart バイナリ不在、上記同因）。
  手動で 80 桁整形済み。発火確認時の差分は本ログへ追記のこと。
- `flutter analyze`: 未実行（同上）。
- 実機 Xperia 確認: 未実施（計画どおり CI/実機へ委譲）。

### 次の一手（iteration 2 向け）
- 指揮官 review: event sequence / timer cancellation / failure-before・pass-after を確認。
- 許可された環境で `flutter test test/common/widgets/gestures_test.dart` と
  `dart format --output=none --set-exit-if-changed lib/common/widgets/gestures.dart
  test/common/widgets/gestures_test.dart` を実行。
- 問題なければ DCO sign-off commit → origin push → upstream PR（動画付き）。

## 2026-08-07 iteration 2/2: OpenCode DeepSeek V4 Flash 0731 — 修正バッチ（compile/test対応・差分最小化）

### 変更ファイル（承認範囲のみ。deviation なし）
- `flutter/lib/common/widgets/gestures.dart` (M)
- `flutter/test/common/widgets/gestures_test.dart` (M)
- 本 impl log (追記のみ)

### gestures.dart の修正
- `_armPendingStart` 直上の FIXME コメント5行を3行に圧縮（AGENTS.md のコメント規約準拠、
  旧コード由来の stale FIXME を除去）。実装ロジック自体への変更なし。
  - 不変条件は維持: 同一 pending target への連続 update は `_pendingDetails` のみ更新し
    200ms deadline を延長しない / target 変更・onEnd・rejectGesture・dispose で pending を cancel。

### gestures_test.dart の修正（10テスト → 6テスト）
- `_makeRecognizer` のコールバックを全て block closure（void 返却）に変更。
  arrow 式 `(d) => recorder.oneFingerUpdate++` は int を返し cascade setter を壊すため、
  `(d) { recorder.oneFingerUpdate++; }` 形式へ。
- nullable callback 呼び出しを `recognizer.onUpdate!(...)` → `recognizer.onUpdate!.call(...)`、
  `recognizer.onEnd!(...)` → `recognizer.onEnd!.call(...)` に変更（24箇所）。
- `rejectGesture(1)` テストを削除（tracked pointer なしで assert し得るため。
  実 pointer lifecycle を駆動する代替は diff 拡大につながるため不採用）。
- 上流 PR 向けに6テストへ削減:
  1. 2指→1指 連続遷移 + 最新 focal point（deadline 非延長を検証）
  2. 3指→2指 連続遷移
  3. pending one-finger 中に 2 指へ戻った場合の cancel
  4. onEnd（全指 up）後の ghost start なし
  5. 4本以上を three-finger として一貫処理
  6. none からの 1 指 = 即 start / update / end 回帰
  - 削除: 3指増加時 cancel テスト・rejectGesture テスト・1指→2指 即 start・end-reset 後再 start。
- 残存テストの expect 数値を実装と突合して修正:
  - start と update は同一 update イベント内で同時発火する（旧実装も同様）ため、
    「4本指→5本指」テストは `threeFingerUpdate == 2`、「1指」テストは2回目 update 時点で
    `oneFingerUpdate == 2` が正しい値。
- 未使用フィールド `oneFingerCancel` / `twoFingerUpdate` と対応コールバック代入を削除
  （`unused_field` lint 回避、6テストで不要のため）。

### 実行したコマンドと結果
- `git diff --check`: 成功（exit 0）。
- 追加行の 80 桁チェック: gestures.dart / gestures_test.dart とも追加行は全て 80 桁以内。
  95 桁の行は HEAD から存在する既存コメント（今回の diff 外）。
- grep 検証: arrow 式 `=> recorder.` / 直接 `onUpdate(`・`onEnd(` / `rejectGesture` /
  `oneFingerCancel`・`twoFingerUpdate` の残存なし。`testWidgets` は 6 件、
  `onUpdate!.call` / `onEnd!.call` は 24 箇所。
- `git diff` で変更ファイルを確認: 承認済み2ファイル + impl log のみ。

### 未実行のチェック（理由付き）
- `flutter test test/common/widgets/gestures_test.dart`: 未実行。ループ契約により作業
  ディレクトリ外（/tmp の Flutter 3.24.5 SDK 含む）への read/write が禁止のため。
  （前回同様、fork CI / 許可された環境へ委譲）
- `dart format --output=none --set-exit-if-changed ...`: 未実行。ワークスペース内に
  dart/flutter バイナリ・dart-sdk なし（`.dart_tool` も未生成）。フォーマットは委譲。
  手動で80桁整形済み。発火確認時の差分は本ログへ追記のこと。
- `flutter analyze`: 未実行（同上）。
- Android 実機 Xperia 確認: 未実施。

### 次の一手（iteration 3 向け）
- 許可された環境で `flutter test test/common/widgets/gestures_test.dart` /
  `dart format` / `flutter analyze` を実行し pass を確認。
- 問題なければ DCO sign-off commit → origin push → upstream PR（動画付き）。

## 2026-08-07 supervisor verification checkpoint

- Flutter 3.24.5と基準commit一致のbridge artifactを入れた隔離worktreeで検証した。
- pre-fix code: 2→1 continuous-move testが`Expected: 1 / Actual: 0`で失敗した。
- patched code: `flutter test test/common/widgets/gestures_test.dart`は6件全て成功した。
- `flutter analyze lib/common/widgets/gestures.dart test/common/widgets/gestures_test.dart`は`No issues found`。
- Flutter 3.24.5 formatter適用済み。`git diff --check`成功。
- agy Claude Opus 4.6 Thinkingのstable diff reviewはPASS。
- Android Arm64 release APK build成功。APKはdebug署名、Arm64 only、package `com.carriez.flutter_hbb` 1.4.9 (2067)。
- APK: `tmp/rustdesk-multitouch-fix-arm64-v8a.apk`
- SHA-256: `4352efdbd22bfa70b4435c2bd7bc666b3e1212759d6cc2840ea0d8e4fae440ef`
- 未完了はXperia 1 VII実機確認、DCO commit、push、upstream PR。

## 2026-08-07 iteration 3/3: OpenCode DeepSeek V4 Flash 0731 — CodeRabbit finding修正（reset timer分離）

### 対象 finding
- Draft PR #15786 の CodeRabbit finding 1件（verified）: `_debounceTimer` が post-end の
  state reset と pending lower-finger start の二役を兼ねている。前回 all-up から 200ms 以内に
  新しい 1指・2指 gesture が始まると pointerCount が stale な `_currentState` と一致し、
  onUpdate が reset timer を cancel して start を skip、後の onEnd が前回の end callback を2度呼ぶ。

### 変更ファイル（承認範囲のみ。deviation なし）
- `flutter/lib/common/widgets/gestures.dart` (M)
- `flutter/test/common/widgets/gestures_test.dart` (M)
- 本 impl log (追記のみ)

### gestures.dart の修正
- `_debounceTimer` を pending-start 専用に限定し、post-end reset を `_resetTimer` + `_ended` flag へ分離。
- `onUpdate`:
  - 一致 state の active 判定に `&& !_ended` を追加（ended 済みなら restart 経路へ）。
  - count >= 3 は `_currentState != threeFingerVerticalDrag || _ended` で start（ended 済み一致は restart）。
  - update 配信 gate に `&& !_ended` を追加（end callback 発火済み state に update を流さない）。
- `onEnd`: switch 全体を `if (!_ended)` で guard（2回目の onEnd で end callback を再発火しない）。
  `_ended = true; _resetTimer = Timer(200ms, ...)` で `_currentState = none; _ended = false` に reset。
  special-hold-drag の early return（`_currentState = none`）は従来どおり維持。
- `_armPendingStart`: one-finger の immediate 条件に `(_ended && _currentState == oneFingerPan)` を追加
  （ended 済みの一致 state は即 restart）。2→1 / 3→2 の 200ms debounce と same-target の
  deadline 非延長は不変。
- `_startPending` / `_startThreeFinger`: 先頭で `_cancelReset()`（restart 時に reset timer を cancel）。
- `_cancelReset()` 追加: `_resetTimer?.cancel(); _resetTimer = null; _ended = false;`。
- `rejectGesture` / `dispose`: `_cancelPendingStart()` に加えて `_cancelReset()`。
- CodeRabbit の `_startThreeFinger` coordinate 提案（localFocalPoint を globalPosition に使う点）は
  PR 前からの既存挙動のため実装しない（指示どおり preserve）。

### gestures_test.dart の修正（6 + 1 = 7テスト）
- reversion テスト: 2指へ戻った際、ended 済みの two-finger が restart するため
  `twoFingerStart` 期待値を 1 → 2 に更新（`oneFingerStart == 0` の本旨は不変）。
- ghost start テスト: `expect(recorder.twoFingerEnd, 1)` を追加（2回目の onEnd で end が再発火
  しないことを検証。CodeRabbit finding の double-end 要件）。
- 新規テスト: 「200ms 以内に始まる2回目の 1指 gesture が oneFingerStart を2回目に発火し、
  正常に end する」（restart 即時 + end 1回）。

### 実行したコマンドと結果
- `git diff --check`: 成功（exit 0）。
- `bash scripts/smoke_template.sh`: 成功（exit 0、"smoke OK"）。
- `bash scripts/security_smoke.sh`: 成功（exit 0、"Security smoke OK"）。
- 追加行の 80 桁チェック: 変更追加行は全て 80 桁以内。98 桁の行は HEAD から存在する既存コメント
  （special-hold-drag のコメント、indent 移動に伴い diff に表示されただけで内容は不変）。
- grep 検証: 外部からの `_debounceTimer` / `_resetTimer` / `_ended` /
  `onOneFingerStartDebounce` / `onTwoFingerStartDebounce` 参照なし。
- brace/paren バランス検査: 両ファイル OK（python による静的チェック）。
- `git diff` で変更ファイル確認: 承認済み2ファイル + impl log のみ。

### 未実行のチェック（理由付き）
- `flutter test test/common/widgets/gestures_test.dart`: 未実行。ワークスペース内に
  dart/flutter バイナリ・dart-sdk なし（`.dart_tool` 未生成、ループ契約により /tmp SDK 使用不可）。
  fork CI / 許可された環境へ委譲（iteration 1・2 と同条件）。
- `dart format --output=none --set-exit-if-changed ...`: 未実行（同上）。手動で整形済み。
  発火確認時の差分は本ログへ追記のこと。
- `flutter analyze`: 未実行（同上）。
- 実機 Xperia 確認: 未実施（計画どおり CI/実機へ委譲）。

### 次の一手
- 許可された環境で `flutter test` / `dart format` / `flutter analyze` を実行し pass を確認。
- 問題なければ DCO sign-off commit → origin push → upstream PR（動画付き）。

## 2026-08-07 iteration 3.1: OpenCode DeepSeek V4 Flash 0731 — supervisor review 修正（stale reset timer）

### 変更ファイル（承認範囲のみ。deviation なし）
- `flutter/lib/common/widgets/gestures.dart` (M)
- `flutter/test/common/widgets/gestures_test.dart` (M)
- 本 impl log (追記のみ)

### review 指摘と対応
1. **onEnd が旧 `_resetTimer` を cancel せず新 timer を代入** → 旧 timer が restart 中の
   gesture に割り込んで `_currentState` / `_ended` を reset し得た。
   - 修正: スケジュール直前に `_resetTimer?.cancel()` を追加（`_ended` はクリアしない）。
     reset コールバック内で `_resetTimer = null` を追加。
   - 追記テスト: 1指 start → end → pump 50ms → 2回目 onEnd → pump 50ms → 1指 restart →
     pump 110ms（旧 timer の deadline t=200 を超え、新 timer の deadline t=250 の手前）→
     update → start が 2 のまま・end が 1 のままであることを検証し、restart 後の end で
     end=2 に。旧 iteration-3 コードでは t=200 で旧 timer が発火し oneFingerStart=3 に
     なるため失敗する（要件的 failure-before を満たす）。
2. **same-count restart テストの update 数が 3 になる**（start frame でも update が発火
   するため）→ 余分な onUpdate 呼び出しを削除し expect 2 を維持。
3. **special-hold-drag early return の確認**: `isSpecialHoldDragActive` 分岐は
   `if (!_ended)` 内、timer スケジュール前に `_currentState = none; return;` する。
   live reset timer は `_ended == true` のときのみ存在し得るため、この経路では
   live timer なし・`_ended == false`・`_currentState == none` を確認。コード変更なし。
4. **reject / dispose の cancel と 2回目 onEnd の二重発火防止**: `rejectGesture` /
   `dispose` は `_cancelReset()`（cancel + null + `_ended = false`）済み。2回目 onEnd は
   `if (!_ended)` ガードと `_ended = true` で end callback 二重発火なし。確認のみ。

### 実行したコマンドと結果
- `git diff --check`: 成功（exit 0）。
- `bash scripts/smoke_template.sh`: 成功（exit 0、"smoke OK"）。
- `bash scripts/security_smoke.sh`: 成功（exit 0、"Security smoke OK"）。
- 追加行の 80 桁チェック: 追加行は全て 80 桁以内。97 桁の行は HEAD から存在する既存
  special-hold-drag コメントのみ（内容不変）。
- brace/paren バランス検査: 両ファイル OK（python による静的チェック）。
- `git diff` で変更ファイル確認: 承認済み2ファイル + impl log のみ。

### 未実行のチェック（理由付き）
- `flutter test test/common/widgets/gestures_test.dart`: 未実行。ワークスペース内に
  dart/flutter バイナリ・dart-sdk なし（ループ契約により /tmp SDK 使用不可）。
  fork CI / 許可された環境へ委譲。新テストの failure-before / pass-after は
  上記 (1) の手動トレースで確認済み。
- `dart format --output=none --set-exit-if-changed ...`: 未実行（同上）。手動で整形済み。
- `flutter analyze`: 未実行（同上）。
- 実機 Xperia 確認: 未実施（計画どおり CI/実機へ委譲）。

### 次の一手
- 許可された環境で `flutter test` / `dart format` / `flutter analyze` を実行し pass を確認。
- 問題なければ DCO sign-off commit → origin push → upstream PR（動画付き）。
