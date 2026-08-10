# Android multitouch PR draft

この文書は実機確認後にupstream PRへ転記する下書き。製品commitには含めない。

## PR title

`fix: prevent multitouch gesture state from sticking on Android`

## PR body

```markdown
## Problem

On Android, lifting a finger while continuing a multi-finger gesture can leave the
remote session in the old gesture mode. I reproduced this on an Xperia 1 VII running
Android 16 (Arm64): after a two- or three-finger gesture, cursor movement, taps and
scroll cancellation no longer behave normally.

[Reproduction video](https://github.com/TsukinowaRin/rustdesk/releases/download/android-multitouch-repro-20260807/screen-20260807-193853.mp4)

## Root cause

On pointer reconfiguration, Flutter 3.24.5's `ScaleGestureRecognizer` calls `onEnd`
with the new `pointerCount`, then resumes updates on the next move. RustDesk used one
`_debounceTimer` both to reset the ended state and to start the lower-finger state.
Each continuous update cancelled and re-armed that timer, so a 2-to-1 or 3-to-2
transition could be postponed indefinitely while updates continued in the stale state.

## Fix

Repeated updates for the same pending transition now refresh the gesture details
without extending the original 200 ms deadline. A changed target, `onEnd`, rejection
or disposal cancels the pending start. Pointer counts of three or more are handled
consistently as a three-finger drag.

Pending starts and post-end cleanup now use separate timers. An ended gesture cannot
receive further updates or fire its end callback twice, while a new gesture with the
same finger count still invokes its start callback.

The change is limited to the recognizer and its regression tests.

## Testing

- The new continuous 2-to-1 test fails before the fix (`Expected: 1`, `Actual: 0`).
- The same-count restart test fails on the first PR revision (`Expected: 2`, `Actual: 1`).
- All 8 focused gesture tests pass with Flutter 3.24.5.
- Focused `flutter analyze` reports no issues.
- An Arm64-only release APK builds successfully and passes ZIP, alignment and v1/v2
  signature verification.
- Xperia 1 VII / Android 16 confirmation is pending; the test APK is ready.

I could not find an existing issue for this state-transition bug.
```

## Xperia test checklist

APK: `tmp/rustdesk-multitouch-fix-arm64-v8a.apk`

SHA-256: `2dd60184a4d62909fcc70de995498a6a2a40dd15a742665514e9db893f46e289`

このAPKはAndroid Debug署名。同じ署名でない既存RustDeskには上書きできず、既存アプリをアンインストールすると設定も削除される。

1. リモートセッションを開始し、通常の1本指moveとtapが動くことを確認する。
2. 2本指で動かし、1本だけ離したまま残りの指を1秒以上動かす。その後のmove、tap、scroll cancelが正常ならPASS。
3. 3本指から2本、1本へ順に減らしながら動かす。全指を離した後のmoveとtapが正常ならPASS。
4. 4本以上でも操作し、全指を離した後に入力が残らないことを確認する。
5. 上記を5回繰り返し、再接続なしで復帰し続けることを確認する。

## Video delivery

公式`gh` CLIとGitHub REST / GraphQL APIには、PR本文のnative user attachmentをuploadする公開APIがない。製品branchへ動画をcommitせずheadlessで完結させるため、forkの専用release assetへupload済み。

- Release: `https://github.com/TsukinowaRin/rustdesk/releases/tag/android-multitouch-repro-20260807`
- Asset: `https://github.com/TsukinowaRin/rustdesk/releases/download/android-multitouch-repro-20260807/screen-20260807-193853.mp4`
- Asset SHA-256: `576d068e4fdbc1150e7999d06c9c3c0adcfa28f70dc4929f4d4af5b63003ccd4`
- Tag target: `4234b99029bf32c23098b4eaeec8efc135c8e80a`

remote assetを再downloadし、local videoとSHA-256が一致することを確認済み。ブラウザでPR本文へnative attachmentを追加できる場合は、後からこのlinkを置換してよい。

## Commit

Commit title:

`fix: prevent multitouch gesture state from sticking on Android`

DCO identity:

- name: `TsukinowaRin`
- email: `166277281+TsukinowaRin@users.noreply.github.com`

Stage only:

- `flutter/lib/common/widgets/gestures.dart`
- `flutter/test/common/widgets/gestures_test.dart`

Keep the fix as one signed-off commit. Mark the Draft PR ready only after the Xperia test passes.
