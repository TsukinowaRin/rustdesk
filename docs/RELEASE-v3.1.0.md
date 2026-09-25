# ハーネス V3.1.0（2026-09-26）

複数の AI エージェント CLI を「指示役 1 人 + 安い担い手たち」で回すための配布用テンプレート。9 本の CLI（Claude Code / Codex / Antigravity / Cursor / opencode / Kilo / Grok / oh-my-pi / DeepSeek Harness）で守り・担い手・skill の実測を通した版。

## 入れ方（1 分）

1. zip を展開し、その folder で自分の CLI（`claude` など、`harness/clis.json` にある 9 本のどれか）を開く。Claude Code は「このフォルダを信頼しますか」で信頼を選ぶ
2. 普通に最初の依頼を言う。準備（`git init`・最初の commit・担い手の編成 `.loop/team.json`）は CLI の開始 hook から `python3 harness/setup.py auto` が自動で走る（Claude Code / Codex / Cursor / opencode / Kilo / omp / dsh で配線済み。Antigravity と Grok は指示役が依頼の前に 1 回打つ）。人が打つ物は無い

自分で打ちたい人は `docs/HARNESS.md` の冒頭「入れてから最初の 1 件まで」に同じ手順がある。

## 入っている物

- 守り 1 本（`harness/guard.py`）で 9 CLI。壊す命令・秘密・管理者・子エージェント・main への push を止め、外へ出す操作は既定で承認画面を出さず「判断カード」に倒す。担い手は作業木の外に書けない・守りを書けない・別の担い手を起こせない
- 担い手へ回す（`harness/delegate.py`: new / run / adopt / eval / stats / retry / team --probe）。作業木ごとに動き、報告・守りの跡・費用（Codex と Claude）を記録
- 判断の輪（Kagemusha を上流のまま）。台帳は作業場をまたいで共有（`judgment.py init --from` / `sync`）
- skill 27 本（外 24 本は無編集。出どころと hash を記録）
- 案件のダッシュボード（1 枚を見張りで更新。私設の網で配る）と、スマホからの往復（Telegram。返事は受信箱で依頼 ID に結ぶ）。中継 hub で 1 つの bot から複数の作業場へ
- 使い捨ての Windows（Sandbox / Hyper-V）で画面操作、管理者の窓（UAC / sudo）

## 分かっている限界

- Windows + WSL でだけ実機で通した。macOS と素の Ubuntu は未検証
- 守りの既知の抜け 8（`docs/SECURITY.md`）。hook は「うっかり」を止める物で、「わざと」は台帳と人の目で見る
- 費用（トークン）が取れるのは Codex と Claude だけ
- 蒸留の本番は未実施

記録: `docs/verification/`（独立の確認 7 組、新規展開 2 回、9 CLI の実測 2 種、評価）。設計: `docs/PLAN.md`、`docs/design/`。
