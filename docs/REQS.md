# 要件

このファイルは current task の source of truth。

## 依頼内容

- 依頼:
  - Android Arm64版をXperia 1 VIIで使用した際、リモートアクセス中の2本指・3本指以上の操作後に1本分のtouch判定が残留する不具合を修正し、本家RustDeskへ動画付きの小さなPRを送る
  - maintainerから「core logicの変更が大きい」と却下されたため、既存PRを極小の局所修正へ作り直す
- 背景:
  - 残留touchによりマウス移動・tap・scroll cancelなどが正常動作しなくなる
  - 再現動画はworkspace rootの`Video/`にある
  - 2026-08-08のXperia実機確認で、純粋追加1行版APKでも3本指操作後はpointerと画面が操作不能になり、2本指操作後も画面操作が異常になった
  - したがって、shared timerだけを原因とした診断とcommit `42ccff2e8`は不十分。現APKとPR #15799を解決済みとして扱わない
  - Claude Code Opus5 Highのread-only計画は、2回の差し戻し後に専用reset timer案として承認済み
  - 専用reset timer案のfocused test、3版比較、非commit安全性7件、format/analyze、Arm64 APK build/checkは完了。現在地はXperia実機確認前
  - 2026-08-09、profile APKをXperiaへinstallしたところ「アプリが繰り返し停止」し、通常操作へ到達できなかった。profile APKは機能不合格で再配布しない
  - packaging比較で原因を特定。`librustdesk.so`は`libc++_shared.so`をNEEDEDとするが、今回のprofile/debug APKには未収録。以前起動できたAPKには同じArm64 runtimeが収録されている
  - `libc++_shared.so`を追加したprofile v2はXperiaでロゴ表示まで進むが、メイン画面へ遷移せず停止した。v2も機能不合格
  - 今後はユーザーへAPKテストを依頼する前に、agent側Android環境でinstall・起動・画面capture・Vision入力によるメイン画面表示確認・logcat確認を必須とする
  - release universal v3はWindows/WHPX API 33 AVDへ同じAPKをinstallし、ロゴからメイン画面への遷移、Settings tap、3回cold relaunch、startup logcatを確認済み。次はXperia実機gesture確認
  - 2026-08-10、ユーザーが製品2ファイルのcommitとpushを明示許可。Xperia確認前でも既存1commitのamendとPR branch更新だけを行い、PR本文・会話・Ready状態は変更しない
  - 2026-08-10、ユーザーが未コミットのハーネス、Docs、`Video/`のcommitとpushを明示許可。製品PR #15799を小さく保つため、製品修正の親commit `4234b9902`から別branch `codex/harness-docs-video`を作り、PR #15799には混ぜない

## 目標

1. 動画とAndroid入力処理からtouch残留の原因とevent sequenceを特定する
2. Android入力経路だけを対象に、既存gestureを壊さない最小修正を実装する
3. 可能な限り自動回帰testを追加し、関連するformat/analyze/test/buildを通す
4. 指揮官が計画との差分と品質をレビューし、不備は実装agentへ理由付きで差し戻す
5. 本家RustDesk向けに原因、修正、検証、動画を含む小さなPRを作成する
6. 既存のgesture state machineを組み替えず、元コードの形を保った最小差分へ縮小する
7. 実機失敗を起点に、gesture stateだけでなく`remote_input.dart`のmouse down/up、`_touchModePanStarted`、scale/scroll終了処理を再調査する

## 非目標

- Android以外の入力方式やUIの無関係なrefactor
- 新規外部依存の追加
- ハーネス導入差分を本家PRへ含めること
- 本家branchへの直接pushやPRのmerge
- `codex/harness-docs-video`からのPR作成
- `tmp/`、APK、ユーザーのlocal設定、credential類のcommit

## 制約

- 指揮官は調査計画、レビュー、承認、PR品質管理を担当し、実装は原則Grok 4.5またはOpenCode CLIのAlibaba token plan DeepSeek V4 Flash 0731へ委任する
- 実装agentは計画で指定したファイル以外を変更しない。必要ならdeviationを提案して停止する
- 動画や秘密情報を製品commitへ追加しない
- PRは小さく保ち、無関係なformat変更を含めない
- 製品logicは15変更行以内、新しいhelper/enumを追加しない。専用`Timer? _resetTimer` 1本だけを例外として許容する。Dart formatterが追加する`dispose`前の空行1行はlogic行に数えない
- commitする回帰testは報告症状を直接示す1件を基本とし、追加検証は隔離worktreeの非commit testで行う
- Xperia検証前に変更できるのは、ユーザーが明示許可した製品2ファイルのcommit/amendとPR branchへのpushだけ。PR本文、maintainer会話、Ready状態は変更しない
- 承認済み計画からの実装・機械的修正はOpenCode DeepSeek V4 Flash Maxへ委任し、指揮官が差分と実機向けevent sequenceを査読する
- 新しい原因が確定しXperiaで成功するまで、PR #15799をReadyにせず、現APKを合格品として案内しない
- ハーネスは別branchだけへ通常pushし、既存remote branchの上書きとPR作成は行わない
- push前に`bash scripts/security_smoke.sh`、`TEMPLATE_SMOKE_WINDOWS_TIMEOUT=20s bash scripts/smoke_template.sh`、`git diff --check`を通す

## 受け入れ条件

- [ ] Xperia実機で2本指・3本指以上の終了後にactive pointer、mouse button、touch/scroll stateが残らない
- [ ] XperiaでAPKが安定起動し、クラッシュループせずremote sessionを開始できる
- [x] agent側Android環境でAPKを起動し、screen captureをVision入力で確認してロゴからRustDeskメイン画面へ遷移することを確認する
- [x] 同じagent側起動でlogcatにstartup exception、native load failure、ANR相当の停止がない
- [ ] Xperia実機でsingle-touchのmove/tapと画面pan/scaleが正常に再開する
- [ ] Xperia実機でtap、mouse movement、scroll/cancelが正常に復帰することを確認する
- [x] 最小版の関連test、format/analyze、および実行可能なAndroid build/checkが成功する
- [x] 最終commitに不具合修正と必要最小限のtest以外が含まれない
- [x] 本家RustDeskに動画付きPRが作成され、URLを提示できる
- [x] upstream基準からの製品コード差分が局所的で、既存state machineの全面的な組み替えを含まない
- [x] 自動testが実機で失敗したevent sequenceを再現し、failure-before / pass-afterを示す
- [x] ClosedのPR #15786へ変更量を返信し、純粋追加1行版をPR #15799として提出する

## 仮定

- まず既存動画とコードから原因を絞り込み、実機でしか確定できない項目だけを最後にユーザーへ依頼する
- GitHub CLI認証とorigin forkへのpush権限が利用可能と仮定し、read-only確認後にPR作成まで進める
- GitHub API/CLIで動画を直接添付できない場合は、製品commitを汚さない代替手段を評価してから最小限のユーザー操作を依頼する
- 200ms timer競合は実在するコード上の問題だが、実機症状の主因または唯一の原因という仮定は撤回する
- Flutter 3.24.5では、最初のpointer-upで`onEnd`後にrecognizerが`accepted`へ戻り、残りをmoveせず離すと最後のpointer-upで`onEnd(0)`は呼ばれない。修正はこのsequenceをtestで再現する
- `remote_input.dart`のcancel/end非対称は別の有力候補だが、peer OS・入力mode・relative mouse modeが確定するまで製品変更しない
