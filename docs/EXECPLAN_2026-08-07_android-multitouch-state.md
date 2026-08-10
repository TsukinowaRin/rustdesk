# Android multitouch state transition fix

plan_id: PLAN-20260807-ANDROID-MULTITOUCH-001
基準commit: 4234b99029bf32c23098b4eaeec8efc135c8e80a
plan_revision: 1

<!-- execplan:original:start -->

## 目的 / 全体像

Androidのリモートセッションで2本指または3本指以上の操作から指を減らしたとき、`CustomTouchGestureRecognizer`が古いgesture stateのまま更新を送り続ける不具合を、既存の200ms遷移猶予を保ちながら修正する。製品差分はrecognizerと直接回帰testだけに限定し、remote inputや他platformをrefactorしない。

## 背景と見取り図

- 再現環境: Android 16、Arm64、Xperia 1 VII。
- 動画: `Video/screen-20260807-193853.mp4`。16.20秒、1080x2340、H.264、約2.5MB。製品commitには含めない。
- 基準: upstream/origin/local masterはいずれも`4234b99029bf32c23098b4eaeec8efc135c8e80a`。
- Flutter Android CIは3.24.5を使用する。
- Flutter 3.24.5の`ScaleGestureRecognizer`はpointer構成変更時、`_reconfigure()`から新しい`pointerCount`を持つ`onEnd`を呼び、次のmoveで再start/updateする。
- 現コードは`onEnd`で200ms後の`_currentState = none`をscheduleするが、次の`onUpdate`先頭で同じtimerをcancelする。その後、2→1または3→2の開始を同じtimerへscheduleし、連続moveの各`onUpdate`が再びcancel/rearmするため、遷移が永続的に成立しない。古いtwo/three-finger stateへ新pointer countのupdateが流れ続ける。
- `rejectGesture()`はpending timerをcancelしないため、reject後に遅延startが発火する幽霊gestureの副経路もある。

## 作業計画

1. `CustomTouchGestureRecognizer`をcallback経由で直接駆動するFlutter testを追加し、現コードで次を再現する。
   - two-finger stateからone-finger detailsを200ms未満の間隔で連続投入しても、最初の本数変更から200ms程度でone-finger startが1回だけ発火するべきである。
   - three-finger stateからtwo-fingerへの同じ遷移も1回だけ成立する。
   - pending lower-finger startの後にpointer countが元へ戻った場合、古いpending startは発火しない。
   - reject/end後にpending startが幽霊発火しない範囲を、公開APIで決定的に検証できるなら追加する。
2. timerのpending用途を明示し、同じtargetへの連続updateではdeadlineを延長せず最新detailsだけを更新する。targetが変わった場合、end/reject/disposeの場合はpending遷移をcancelする。
3. `pointerCount >= 3`をthree-finger stateとして一貫して扱う。4本以上で余計なstate reset/startが起きないようにする。
4. 200ms猶予中の既存gesture動作を必要以上に変えない。全面state-machine改修、`remote_input.dart`のmouse lifecycle変更、新規依存は行わない。
5. format、対象test、analyzeを実行し、最終diffをupstream基準と突き合わせる。

## 予定変更範囲

- 予定変更ファイル:
  - `flutter/lib/common/widgets/gestures.dart`
  - `flutter/test/common/widgets/gestures_test.dart`（必要なら新規）
- 許容する付随変更:
  - `docs/EXECPLAN_2026-08-07_android-multitouch-state_impl.md`への実装記録
- 変更禁止範囲:
  - `flutter/lib/common/widgets/remote_input.dart`
  - Rustコード、Android Kotlinコード、lockfile、dependency、生成物
  - `Video/`、ハーネス設定、上位plan、upstreamの既存test

## 検証と受け入れ条件

- 連続move中でも2→1と3→2のstate遷移が最初の本数変更から有限時間内に1回だけ成立する。
- pointer countがpending targetから変わった場合、stale callbackが後から発火しない。
- end/reject後にactive pointerなしでone-finger startが発火しない。
- 通常の1本指start/update/end、2本指scale、3本指scroll callback順序を意図せず変えない。
- `dart format --output=none --set-exit-if-changed lib/common/widgets/gestures.dart test/common/widgets/gestures_test.dart`が成功する。
- `flutter test test/common/widgets/gestures_test.dart`が成功する。
- 実行可能なら対象`flutter analyze`とAndroid Arm64 build/checkを成功させる。環境不足はCIと実機確認へ明示的に委譲する。
- PR commitはDCO sign-off付きの1 commitとし、upstreamとの差分を上記2ファイル以内に保つ。
- PR本文に原因、修正、検証、Xperia/Android情報、動画へのlinkまたはnative attachmentを含める。

<!-- execplan:original:end -->

## 進捗

- [x] (2026-08-07 20:45 JST) 動画metadata、Flutter 3.24.5のpointer reconfigure、現在のtimer sequenceを確認。
- [x] (2026-08-07 20:45 JST) Grok 4.5初稿を反証し、訂正版でshared timer競合を確認。
- [x] (2026-08-07 21:36 JST) OpenCode DeepSeek V4 Flash 0731 Maxへtest-first実装と修正バッチを委任。
- [x] (2026-08-07 22:12 JST) 指揮官review、Flutter 3.24.5 failure-before/pass-after、analyze、Android Arm64 APK buildを完了。agy Opus reviewはPASS。
- [x] (2026-08-07 22:25 JST) 英語PR本文と実機checklistを準備し、再現動画を製品branch外のfork release assetへupload・hash検証。
- [x] (2026-08-07 22:29 JST) 製品2ファイルを1つのDCO commitとしてoriginへpushし、動画付きDraft PR #15786を作成。
- [x] (2026-08-08 09:18 JST) CodeRabbit指摘をOpenCodeへ差し戻し、reset timer分離、same-count restart、stale timer回帰testを追加。8 tests、analyze、Arm64 APK再build、agy Opus最終reviewを完了。
- [x] (2026-08-08 09:23 JST) 既存DCO commitを`3aece2c38`へamendしてforce-with-lease push。PR本文とCodeRabbit返信を更新し、valid findingはaddressed、座標findingはwithdrawn。
- [ ] Xperia実機結果の追記、PR Ready化、upstream CI確認。

## 現在の停止点

- 現在位置: 修正版head `3aece2c38`をDraft PR #15786へpush済み。Xperia実機確認待ち。
- 未完了: 実機確認、PR Ready化、maintainer承認後のupstream CI確認。
- 次の一手: `tmp/rustdesk-multitouch-fix-arm64-v8a.apk`をXperia 1 VIIで検証する。debug署名のため、署名が異なる既存RustDeskへは上書き不可。
- 次に読む文書: 本plan、`docs/WORKLOG.md`の最新checkpoint、`docs/REQS.md`。
- 次に実行するコマンド: `sha256sum tmp/rustdesk-multitouch-fix-arm64-v8a.apk`

## 発見事項

- 観測: Grok初稿はScaleのpointer reconfigure時`onEnd`を見落としたため不採用。訂正版はtimer競合を主因とした。
  根拠: Flutter 3.24.5 `packages/flutter/lib/src/gestures/scale.dart`の`handleEvent()`、`_reconfigure()`。
- 観測: OpenCode repo-reviewerはread-only調査中に許可外bashを要求し、headless policyが拒否した。
  根拠: mailbox batch log。モデル／provider認証とnative readは成功済み。

## 逸脱提案

<!-- execplan:deviations -->

## 判断ログ

- 判断: `remote_input.dart`のmouse up安全網は今回の予定範囲に含めない。
  理由: pointer state timerだけで症状と既知FIXMEを説明でき、PRを小さく保てる。testで反証された場合のみdeviationを提案する。
  日付/記録者: 2026-08-07 / commander

## 成果と振り返り

- 成果: pending-startとpost-end resetを分離した最小修正、8件の回帰test、Arm64 APK、動画付きDraft PR #15786を作成した。
- 不足: Xperia実機確認、PR Ready化、maintainer承認待ちのupstream CI確認。
- 学び: Flutterのpointer reconfigure時`onEnd` sequenceを前提にすると、症状はremote mouse lifecycle変更なしで説明・再現できる。
- 目的との差分: なし。

## 具体手順

1. OpenCode workerが対象2ファイルとimpl logだけを変更する。
2. 指揮官がevent sequence、timer cancellation、testのfailure-before/pass-afterをreviewする。
3. 不備があればmailboxで理由と必要なcounterexampleを返し、別batchで修正させる。
4. ローカルで利用可能なFlutter 3.24.5環境を準備するか、fork CIで検証する。
5. DCO sign-off commitを作成し、upstreamとの差分が小さいことを確認してoriginへpushする。
6. upstream PRを作成し、CIとreview結果を監視する。

## 冪等性と復旧

- 中断後の再開手順: 本planとimpl logの`plan_id`一致を確認し、`git diff --name-only upstream/master...HEAD`とworking treeの製品差分を分けて読む。

## 成果物とメモ

- VideoはPR source commitへ追加しない。
