---
name: TEMPLATE
max_iterations: 8
stall_limit: 2
iteration_timeout: 1800
gate_timeout: 600
iteration_interval: 0
max_runtime: 0
gates_every_iteration: false
gates:
  - git diff --check
---
# <この loop の1文 goal>

任意タスク用の loop profile scaffold。コピーして `<topic>.md` を作り、
goal・手順・完了条件を書き換えてから `scripts/agent_loop.py --profile` に渡す。

frontmatter の意味:
- max_iterations: 反復の上限。超えたら runner が停止する（既定 8）。
- stall_limit: workspace が無変化のまま CONTINUE が続いたら停止する回数（既定 2）。
- iteration_timeout / gate_timeout: 1 iteration / 1 gate の秒数上限。
- iteration_interval: iteration 間の最低秒数（スローモード、既定 0 = 無効）。loop が速く
  回りすぎて rate limit を短時間で使い切るときに、消費「速度」へ蓋をする。
  `--interval` で実行単位の上書きができる。
- max_runtime: run 全体の実時間上限秒（門限モード、既定 0 = 無効）。超過すると未完了でも
  exit 7 で正常停止し、同じコマンドの再実行で docs から続きになる。実行中の iteration は
  中断しないため、実際の終了は門限より最大 1 iteration ぶん遅れ得る。
  `--max-runtime` で上書きでき、profile に門限があっても `--max-runtime 0` で外せる。
- gates: 完了判定に使う機械実行コマンド。**空にはできない。**
  「テストが無いから gates も無し」にせず、最低でも smoke や `test -f <成果物>` を書く。
- gates_every_iteration: true にすると毎 iteration gates を回して失敗を即フィードバックする
  （gates が速い場合のみ推奨）。
- protect: loop 中の改変を許さないファイル（workdir からの相対 path）。gates が参照する
  スクリプト・テストを列挙する。profile と runner 本体は書かなくても常に保護される。
  改変を検出すると runner は exit 6 で即停止する。モデルや prompt の遵守に依存せず、
  gate を書き換えて pass させる経路を閉じるための決定論的対策。
- plan_file / implementation_log: 上位モデルの計画を保持したまま実行モデルに実装させる
  pair 運用（execplan skill「上位計画の保持と逸脱」参照）。両方指定するか両方省略。
  plan_file は自動で protect され、両ファイルの `plan_id:`（ちょうど1行）の一致を
  dry-run 含めて検証する。実行モデルは implementation_log へ `deviation:` 行で逸脱を
  提案し、承認は人間が loop 停止中に plan_file へ `approval: <ID> APPROVED|REJECTED ...`
  を追記する。未承認の deviation が残っていれば、モデルの宣言に関係なく exit 2 で停止。
  観測済み deviation 行の消失・変更・重複は exit 6 で停止する。

## 進め方

1. （goal を達成する手順を、1 iteration = 1 chunk になる粒度で書く）
2. 進捗と判断は docs/WORKLOG.md に残す（runner の prompt が毎回指示する）。

## してはいけないこと

- （このタスクで触ってはいけない範囲、禁止コマンドを書く）

## 完了条件

- （gates が pass する以外に、満たすべき条件があれば書く）
