# 9 CLI で同じ依頼を担い手として流す（1 周目、2026-09-25）

場所: 配布物の展開先 `dist/test-project/`。依頼: `evals/<担い手>/greet.py` と試験を作り、受け入れ条件 4 つを自分で確かめて報告する（`task-example-flash.md`）。
指示役は Claude Fable 5.1。GPT-6 Sol は前日に同じ依頼を通しているので（`2026-09-24_fresh-install/`）今回は外し、ダッシュボードの作り直しに使った。

| CLI | 担い手 | モデル | 結果 | 秒 | 報告 | 原因 / 使う人が直せるか |
|---|---|---|---|---|---|---|
| Claude Code | opus55 | claude-opus-5-5 | 合格 | 84 | あり | — |
| Grok | grok47 | grok-4.7 | 合格 | 88 | あり | — |
| Antigravity | agy | CLI の既定 | 合格 | 93 | あり | — |
| Cursor | cursor | auto | 合格 | 96 | あり | 報告に「REPORT.md が未追跡で出る」と正直に書いた（依頼書の条件 4 が REPORT.md を数えていなかった。依頼書側の不備） |
| opencode | flash | opencode-go/glm-5.3-flash | 合格 | 196 | あり | — |
| Kilo | kilo | kilo/kilo-auto/free | 落ちた → **直して再実行で合格** | 194 → 309 | 再実行であり | ファイルは書けたが `bash` の許可を Kilo が auto-rejecting し、試験も報告もできなかった。**ハーネスの不備**: 担い手の起動引数に `--dangerously-skip-permissions` が無かった（`harness/clis.json` を直した。守りは plugin が呼ぶので旗で外れない） |
| DeepSeek Harness | deepseek | CLI の既定 | 使えない | 32 | なし | `MISSING_CREDENTIAL`（DeepSeek の鍵が未設定）。使う人が鍵を入れれば直る。ハーネスは正しく終了 1 と記録した |
| oh-my-pi | omp | CLI の既定 | 使えない | 53 | なし | `401 Invalid credential`（既定の提供元の鍵が無効）。使う人が omp 側で直す。10 回 retry して 53 秒で諦めた |
| Codex | sol6 | gpt-6-sol | 合格（前日） | 191 | あり | — |

分かったこと（改善の材料）:

- **守りが呼ばれた跡が残らない。** 担い手の log には hook の呼び出しが出ない CLI が多い。`delegate.py` が `HARNESS_GUARD_TRACE` を依頼のフォルダに自動で指せば、9 本とも同じ形で跡が残る。
- **鍵が無い担い手は 30〜60 秒で正しく落ちる**が、`delegate.py team` の段階では分からない。1 分で「使えるか」を見る命令があると、編成の腐りに早く気づける。
- 依頼書の受け入れ条件は REPORT.md を数に入れておく（起動の前置きが REPORT.md を書かせる）。
- 費用: Codex 以外はトークンが取れていない。
