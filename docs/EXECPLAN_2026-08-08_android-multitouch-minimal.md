# Android multitouch minimal correction

plan_id: PLAN-20260808-ANDROID-MULTITOUCH-MINIMAL-001
基準commit: 4234b99029bf32c23098b4eaeec8efc135c8e80a
plan_revision: 1

## 2026-08-08 実機失敗による状態変更

このplanで作成した純粋追加1行版はXperia 1 VIIで不合格だった。3本指操作後はpointerと画面が操作不能、2本指操作後も画面操作が異常になった。以降、このplanのroot causeと成果を確定事項として使わない。再開時はClaude Code Opus5 Highを編集禁止の計画役として新しいExecPlanを作り、`remote_input.dart`を含むevent sequenceを再構築する。

後継planは`docs/EXECPLAN_2026-08-08_android-multitouch-reset-timer.md`。本planへの実装追記は終了する。

<!-- execplan:original:start -->

## 目的 / 全体像

maintainerがPR #15786を「core logicの変更が大きい」と却下したため、既存の`CustomTouchGestureRecognizer`構造を維持したまま、Androidの2本指・3本指操作後にgesture判定が残る症状だけを局所的に直す。検証済みになるまでremote branchとPRは変更しない。

## 背景と見取り図

- 基準commitはupstream `4234b99029bf32c23098b4eaeec8efc135c8e80a`。
- 現PR head `3aece2c38`は製品コードを大きく組み替え、testを8件追加したためmaintainerが受け入れを拒否した。
- 根本原因は、`onUpdate`が同じ`_debounceTimer`を毎moveでcancelし、2→1 / 3→2のdelayed startを永続的に延期すること。
- 既存の200ms挙動を守る案と、`onEnd`で即座にstateをresetする案を比較し、変更行数だけでなくcallback sequenceのリスクで選ぶ。

## 作業計画

1. OpenCodeに元コードからの極小案を複数提示させ、各案の変更行数とevent sequenceを記録する。
2. agy Opusにread-onlyで案を比較させ、same-count restart、double-end、ghost timer、special holdへの影響を確認する。
3. 指揮官が案を1つ選び、OpenCodeへ実装と1件のfocused regression testを委任する。
4. 元コードでfailure、最小版でpassを確認し、既存の8件suiteを非commit検証として通す。
5. format、analyze、Arm64 APK build、独立reviewを通した後だけ、既存1commitをamendしてPR #15786を更新する。

## 予定変更範囲

- 予定変更ファイル:
  - `flutter/lib/common/widgets/gestures.dart`
  - `flutter/test/common/widgets/gestures_test.dart`（focused test 1件だけ。不要なら追加しない）
- 許容する付随変更:
  - `docs/EXECPLAN_2026-08-08_android-multitouch-minimal_impl.md`への事実記録
- 変更禁止範囲:
  - `flutter/lib/common/widgets/remote_input.dart`
  - 新しいdependency、lockfile、Rust/Kotlinコード、Video、harness設定
  - 検証完了前のcommit、push、PR編集、maintainer返信

## 検証と受け入れ条件

- 製品コードは原則15変更行以内で、新しいfield/helper/enumを追加しない。
- 元のclass構造とcallback分岐を維持し、報告された連続move中のstuck stateだけを解消する。
- committed testは1件を基本とし、元コードで失敗、最小版で成功する。
- 旧PRで使った8件suiteを隔離worktreeで通し、same-count restart、double-end、ghost callbackの退行がない。
- Flutter 3.24.5 format/analyze/testとAndroid Arm64 APK buildが成功する。
- PRはDCO付き1commit、製品差分は最大2ファイル、動画linkを維持する。

<!-- execplan:original:end -->

## 進捗

- [x] (2026-08-08 10:31 JST) maintainerの拒否理由を取得。「big change to core logic」と確認。
- [x] (2026-08-08 11:05 JST) 極小案を比較し、`onEnd`末尾のtimer 3行を即時reset 1行へ置換する案を選定。
- [x] (2026-08-08 11:16 JST) OpenCodeが即時reset 1行とfocused test 1件を実装し、mailbox ACKを返却。
- [x] (2026-08-08 12:00 JST) failure-before / pass-after、安全性4件、Opus review、analyze、Arm64 APK検証を完了。
- [x] (2026-08-08 12:05 JST) ClosedのPR #15786へ返信し、再Open不可のため最小版Draft PR #15799を作成。
- [ ] (2026-08-08 実機確認) 純粋追加1行版APKはFAIL。自動testのPASSは実機症状の解決を示さなかった。

## 現在の停止点

- 現在位置: 実機FAILを受領し、PC再起動前のhandoff checkpoint。
- 未完了: 実機event sequenceの再診断、Opus5計画、OpenCode実装、failure-before test、新APK、Xperia再確認、PR訂正。
- 次の一手: Opus5 Highへread-onlyで、1指→2指→3指→全指up時のrecognizer callbackと`remote_input.dart`のflag/mouse eventを時系列化させる。
- 次に読む文書: `docs/WORKLOG.md`、`docs/REQS.md`、本plan、`flutter/lib/common/widgets/remote_input.dart:354`以降、`flutter/lib/common/widgets/gestures.dart:40`以降。
- 次に実行するコマンド: `git status --short && git rev-parse HEAD && claude --help | sed -n '1,220p'`

## 発見事項

- 観測: maintainerは具体的なlogic defectではなく、core logicの変更量を拒否理由にした。
  根拠: `https://github.com/rustdesk/rustdesk/pull/15786#issuecomment-5223842682`
- 観測: PR #14652はtouch/mouse routingを広く変更した後、iPad trackpadのscroll/pinch退行 #15209を起こしてrevertされた。
  根拠: PR #14652のmaintainer commentとissue #15209。
- 観測: OpenCode案Cは`ScaleGestureRecognizer.onEnd`が最後のpointerだけで発火する前提だったが、Flutter 3.24.5の`_reconfigure()`はpointer追加・削除の構成変更時にも`onEnd(pointerCount: ...)`を呼ぶ。
  根拠: `/tmp/rustdesk-flutter-3.24.5-20260807/flutter/packages/flutter/lib/src/gestures/scale.dart:663`。
- 観測: 即時reset 1行を既存のpost-end timer直前へ追加すれば、削除なしで同じ修正効果になる。次の`onUpdate`はtimerをcancelし、更新が無ければtimerは`none`を`none`へ書くだけである。
  根拠: focused testと安全性4件が成功し、agy Opus最終reviewがPASS。
- 観測: 上記の自動検証を通したAPKでも、Xperia実機では3本指後にpointer/画面が操作不能、2本指後に画面操作が異常になった。
  根拠: 2026-08-08 user実機報告。timer resetだけではremote input側の残留状態を解消できない。
- 観測: `onOneFingerPanStart`はtouch modeで`_touchModePanStarted = true`とleft mouse downを送るが、`onOneFingerPanCancel`はflagをfalseにするだけでmouse upを送らない。3本指gestureは`makeGestures`でupdateだけが配線され、start/end callbackは未配線。
  根拠: `flutter/lib/common/widgets/remote_input.dart:354-445,517-585`。これは次回調査の有力候補であり、まだ主因と確定しない。

## 逸脱提案

<!-- execplan:deviations -->

## 判断ログ

- 判断: 既存PRを検証済みの極小commitへforce-with-lease更新する方針とし、新しいPRを重複作成しない。
  理由: maintainerの会話と動画を維持し、修正量の縮小を同じthreadで示せる。
  日付/記録者: 2026-08-08 / commander
- 判断: baseの`onEnd`末尾にある200ms reset timerを`_currentState = GestureState.none`へ置換する。
  理由: pointer構成変更時にend callback後のstateを残す窓がstuckとduplicate endを生む。即時resetなら次のupdateが既存start関数をそのまま使い、製品差分は削除3・追加1、新field/helper/enumなしになる。
  日付/記録者: 2026-08-08 / commander
- 判断: 上記の置換案を、timer直前へ即時reset 1行だけを追加する案へ縮小する。
  理由: 既存timerを残しても次のupdateが必ずcancelし、更新なしなら冪等なno-opになる。製品diffを純粋追加1行にできる。
  日付/記録者: 2026-08-08 / commander
- 判断: 旧8件suiteは200ms delayed transitionを仕様として固定するため、完全PASSを必須にせず、即時resetで意図的に変わるtiming assertionと安全性の退行を分類する。
  理由: maintainer要求に応じてdelay保持のstate-machine再設計を撤回するため。committed testは連続2→1とsame-count restartを1件で直接検証する。
  日付/記録者: 2026-08-08 / commander
- 判断: 純粋追加1行版とtimer単独root causeを不採用へ戻す。
  理由: Xperia実機で報告症状が継続し、受け入れ条件を満たさなかった。自動testはrecognizer callback countしか検証せず、mouse button、touch flag、canvas/scroll cleanupを観測していない。
  日付/記録者: 2026-08-08 / commander
- 判断: 再開時の計画をClaude Code Opus5 Highへ委任し、編集は禁止する。
  理由: user指定。実装前に広いevent sequenceと最小修正案を高精度モデルで比較し、OpenCodeには承認済み局所実装だけを渡す。
  日付/記録者: 2026-08-08 / commander

## 成果と振り返り

- 成果: 差分最小化と自動test/buildの手順は確立したが、修正自体は実機FAIL。
- 不足: 実際に残るmouse/touch/canvas stateの特定とXperiaでの解決確認。
- 学び: recognizer内部callback countだけでは、remoteへ送ったmouse-down/upやUI側flagの対称性を保証できない。
- 目的との差分: PR #15799とAPKは作成済みだが解決品ではない。PRはDraftのまま訂正が必要。

## 具体手順

1. 案ごとにproduction diff行数、timer lifecycle、pointer sequenceを比較する。
2. 最小案だけをOpenCodeが対象2ファイル内で実装する。
3. 指揮官がdiffとtestを査読し、不備は理由付きで差し戻す。
4. 全gate後に既存commitをamendし、remote headをlease確認してpushする。

## 冪等性と復旧

- 中断後は本planとimpl logを読み、`git diff 4234b9902...HEAD`とworking treeを分離して確認する。
- push前なら`3aece2c38`がremoteの既知head。leaseが異なる場合はpushせず再確認する。

## 成果物とメモ

- 旧8件testは検証oracleとして保持できるが、極小PRへ全件commitしない。
