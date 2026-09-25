# skill 27 本が全 CLI から見えて使えるか（2026-09-26）

ユーザーの指示: 「全てのスキルが全てのCLIから使えることを確かめて。」
やり方: 各 CLI を担い手にして同じ依頼（`task-example-flash.md`）を流す。①CLI の仕組みで見える skill を列挙して `.agents/skills`（27 本）と比べる ②`consulting-pptx-skill` の script でデッキ 3 枚を作り `check_deck.py` を FAIL 0 で通す ③`test-audit` の 4 つの問いを当てはめる。
機械の点検は別にある: `python3 harness/sync_skills.py --check` → 27 本 / 直接読む 7 CLI・写し 1（Claude Code）・設定で指す 1（Kilo）、ずれ 0。

| CLI | 担い手 | 見えた数 | 27 本との差 | ②デッキ | ③4 問 | 秒 |
|---|---|---|---|---|---|---|
| Claude Code | opus55 | 25 | `handoff` `i-have-adhd`（skill 側の `disable-model-invocation: true`。人が `/handoff` と打てば動く設計） | FAIL 0 | 合 | 125 |
| Cursor | cursor | 25 | 同上 | FAIL 0 | 合 | 107 |
| Antigravity | agy | 25（+ CLI 自身の 3） | 同上 | FAIL 0 | 合 | 158 |
| Grok | grok47 | 25（+ CLI 自身の 20） | 同上 | FAIL 0 | 合 | 434 |
| opencode | flash | 27（+ 利用者の 5） | 差なし（opencode は `disable-model-invocation` を読まない） | FAIL 0 | 合 | 498 |
| Kilo | kilo | 27（+ 利用者の 4 + CLI 自身の 1） | 差なし（`kilo.jsonc` の `skills.paths` が効いている。`disable-model-invocation` は読まない） | デッキは作れた（FAIL 0）。ただし 20 分で時間切れ、報告なし、プレースホルダー 6 個残り → 一覧だけの短い依頼（T-0925-72、268 秒）で見える数を確認 | — | 1199 + 268 |
| Codex | astra（gpt-6-astra、CLIProxyAPI 経由） | 25（+ Codex 自身の 5 + 利用者の 2 + plugin 19） | `handoff` `i-have-adhd`（Codex も `disable-model-invocation` を読む） | FAIL 0 | 合 | 291（枠切れで 17:23・18:25 に落ち、18:42 に通った。94,718 トークン） |
| Codex | sol6（gpt-6-sol、CLIProxyAPI 経由） | 25（+ 同上） | 同上 | FAIL 0 | 合 | 232（91,904 トークン） |
| oh-my-pi | omp（CLIProxyAPI 経由の gpt-6-sol） | 25（+ 利用者の 1） | `handoff` `i-have-adhd`（omp も `disable-model-invocation` を読む） | FAIL 0 | 合 | 140 |
| DeepSeek Harness | deepseek（dsh、CLIProxyAPI 経由の gpt-6-sol） | 25（+ 利用者の 1） | `handoff` `i-have-adhd`（dsh も `disable-model-invocation` を読む） | FAIL 0 | 合 | 152（3 回目。1 回目は作業木に git に入らない提供元の patch が写らず鍵なし → `dsh.sh` が本体の patch も当てるように / 2 回目は流し直しが古い作業木を使い回していた → `delegate.py` が作り直すように） |

分かったこと:
- 見えない・読めない・使えない skill は、**9 CLI すべてで 0 件**（Codex は Astra と Sol の両方で確認）。差の 2 本は skill 自身の宣言（`disable-model-invocation: true`）で、置き場や写しの不足ではない。
- `disable-model-invocation` を読む CLI（Claude Code / Cursor / Antigravity / Grok）と読まない CLI（opencode）がある。人が呼ぶ前提の skill（`handoff` `i-have-adhd`）は、読まない CLI では自動で提示される。害は無いが、挙動の差として記録。
- 各 CLI は自分の同梱 skill や利用者の skill も並べて見せる（Antigravity 3、Grok 20、opencode 5）。ハーネスの物ではないので数に入れない。
