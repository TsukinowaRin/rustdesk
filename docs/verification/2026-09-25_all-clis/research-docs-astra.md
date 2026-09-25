# 報告: T-0925-15-astra

**何をした** — 指定された順に文書・4 skill・前回報告を読み、現行コードと命令の結果を照合した。Opus の8案は再掲せず、外部 skill・vendor の変更も提案しない。skills.json で自前と確認できたのは leader / worker / independent-check の3本（handoff は commit 付き）。

**検証の結果**

- `python3 harness/check.py` → 終了0、「点検が通りました」。形8項目・試験10本。作業木での結果であり、配布物の新規展開ではない。
- `git ls-files | wc -l` → 820、`wc -lc AGENTS.md` → 47行・4,086 B、`python3 harness/sync_skills.py --check` → 26本・ずれ0、`python3 harness/check.py --list` → 試験10本。前回の固定ファイル数・HARNESS未着手表示・notify offの省略は解消、HARNESSの「試験8本」は再び不一致。
- `python3 harness/setup.py status` →「まだ」3件だが、`python3 harness/delegate.py team` は8名を表示、`python3 harness/judgment.py brief` も終了0。参照先を読んで確認すると setup は作業木内、後2つは本体の .loop。`python3 harness/delegate.py {--help,new --help,run --help}` の各命令で構文を確認した。
- 基準2＝未確認（展開・設定・1件起動は未実施）。基準7＝未達（量の上限内だが AGENTS:20・33 と leader:42 に同じ承認手順）。基準8＝未達（下記の前提・対象引き渡し・再開手順が不足）。これは観察結果であり、本報告の採否は別の担い手に委ねる。

**直す計画（重い順、行番号は現行）**

1. 独立確認の対象と権限が足りない。「独立の確認を1枚出す」（leader:22）だけでは、別作業木にある未commitの成果を確認できない。delegate.py:159 は HEAD から作業木を作り、252–258 の independent_of は会社の照合だけ。`.agents/skills/leader/SKILL.md:22` と `independent-check/SKILL.md:12–18` に対象作業木・対象差分の固定方法、expectations.md の出力先、実測には hands: workspace、壊す確認には隔離した複製と許可範囲を書く。確認方法: 本流と異なる未commit成果を用意し、確認者がその成果を測ったことを記録する。
2. 確認者が結論を書けない。「自分で『合格』と書かない」（worker:36、delegate.py:65）と「合否を書いて返す」（independent-check:19）が衝突する。`.agents/skills/worker/SKILL.md:36` と `harness/delegate.py:65` を「自作の成果を自分で検収しない」と限定し、独立確認の報告形式を使えると明記する。確認方法: 実装依頼と別人確認依頼の2枚を読み、誰がどの結論を返すか一意に決まること。
3. 新規導入の前提と最初の1件がつながらない。「python は3.10以上」（PLAN:192）に対し check.py:18 は tomllib を必須importし、README:29–32 は編成確認で終わる。`docs/PLAN.md:192` を Python 3.11以上へ訂正し、`docs/HARNESS.md:4` から導入手順を案内する。手順には必要コマンド、展開先のGit初期化・初回commit、設定、既存の task-1.md を使う new→run→報告確認を記す。確認方法: Git履歴も設定も無い展開先から、その文書だけで1件回す（今回は未実施）。
4. 「『まだ』を順に済ませる」（README:30）と実際の参照先が一致しない。setup:34・161 は作業木側を見るが、delegate・brief は inbox.py:16–21 により本体を見る。`harness/setup.py:34–36,161–164` の参照先を既存の共通関数にそろえ、`docs/HARNESS.md:101,108` に参照先と brief の副作用（dashboard生成、設定時の受信）を明記する。確認方法: 本体・作業木・HARNESS_LOOP_DIR指定で status/team/brief が同じ設定を示すこと。読取調査では副作用を確認してから実行する。
5. 引き継ぎの置き場が矛盾する。「handoff skillで…docs/から再開」（AGENTS:27）に対し、外部 handoff:8 の保存先はOSの一時領域。worker:13–16 は許可範囲と報告1本を要求する。外部 skill は変えず、`AGENTS.md:27` と自前 `leader/SKILL.md:23` に、指示役が一時成果の必要事項を docs/PLAN.md に反映する手順、担い手は REPORT.md を引き継ぎとする範囲を明記する。確認方法: 会話と一時ファイルを参照せず docs/ と報告から未完事項を復元できること。
6. 指示役の実作業禁止に相反する例外がある。「実作業はしない」（AGENTS:14）に対し leader:34–36 は全員不在・1〜2行・人がいる場合を許す。`.agents/skills/leader/SKILL.md:32–38` の例外を削り、担当不能は未実施として報告する形にそろえる。同:42 の重複した承認手順も AGENTS:33 / SECURITY:46–57 への参照へ置き換える。確認方法: 上記3場面で指示役の行動が両文書で一致すること。
7. 編集禁止の範囲が読み分けられない。「vendor/と.agents/skills/。中は編集しない」（AGENTS:37）と「直したら…sync」（同:41）、IMPROVE:20 の自前 handoff の例示が食い違う。`AGENTS.md:37,41` に skills.json の commit の有無を境界として記し、`docs/design/IMPROVE.md:20` から handoff の自前扱いを削る。確認方法: manifestから自前3本と外部23本に分類でき、外部の変更を誘導しないこと。
8. 終了後に指示役を起こす方法が無い。「裏で走らせて、終わりの知らせで起きる」（leader:20）と「events.jsonl…見張る」（HARNESS:68）は方針だけ。`delegate.py --help` に監視コマンドは無く、ファイル追記だけではCLIの次の応答を開始しない。`.agents/skills/leader/SKILL.md:20` と `docs/HARNESS.md:68` に、対応するCLIの完了通知の設定例と、対応しない場合は応答を終えず実行結果を待つ手順を記す。確認方法: 短い依頼の終了後、人の追加入力なしで報告の採否まで進むこと。

**削るべき文** — 上記6の例外・承認手順の重複、上記7の誤った自前扱い。`docs/HARNESS.md:28,126` の固定「試験8本」と古い列挙は `python3 harness/check.py --list` への参照にする（10本への単純更新では再発する）。READMEの「54行」「skill 12本」も実測と不一致だが、今回の提案対象には含めない。

**最初の30分のつまずき上位3つ** — ①展開後のPython・Gitの前提が見つからず、最初のrunまで到達できない。②作業木では「まだ」と実際に使える設定が食い違い、設定を二重に作り得る。③編成確認後、依頼の作成・終了待ち・報告を読む場所を自力でつなぐ必要がある。

**残り** — 新規展開、init・notify設定・syncの書換え・new/run・破壊例・外部送信・秘密への操作は範囲外のため未実施。Python 3.10での起動は未測（最低版の指摘はimportからの判断）。手編集前の作業木は git status --short が空。
**人の判断が要ること** — なし。提案の採否と独立確認は指示役へ返す。止められた操作の回避はしていない。
**変更したファイル** — 手編集は REPORT.md のみ。ただし指示された brief の実行により、本体側 .loop/dashboard/data.json の更新と既存 build の起動が生じた（judgment.py:212–217 / dashboard_data.py:88–95）。生成物の全差分は未測。判明後は再実行・巻き戻しをしていない。
