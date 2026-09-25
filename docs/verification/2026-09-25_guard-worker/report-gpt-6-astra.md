# 報告: T-0925-17-astra

## 何をした

- 差し戻し。担い手で止めるべき 11 入力が allow（終了 0、標準出力・標準エラーとも空）。起動の抜け道は `env -u HARNESS_ROLE codex`、`bash ./harness/dsh.sh`、`python3 -B harness/delegate.py run`（`harness/guard.py:267`、`:296`、`:298`）。
- 守りの上書きは `cp /tmp/guard.py harness/` と `mv /tmp/guard.py harness/` が allow。行き先ディレクトリだけを調べ、コピー後の basename を見ない（`harness/guard.py:308`）。元ファイルが存在する場合の上書き経路であり、実際の上書きは未実行。
- 外への書き込みは `cp -t ../outside-dir README.md`、`cd .. && echo x > outside.txt`、`sed -i.bak s/x/y/ ../outside.txt`、`sed -i s/x/y/ ../outside.txt notes.txt`、`echo x &> ../outside.txt`、`echo x >| ../outside.txt` が allow（`harness/guard.py:251`、`:302`、`:306`、`:308`）。
- 要求だけから `EXPECTATIONS.md` に 88 対（要求 72、抜け道候補 16）を保存後、実装と `tests/test_guard.py` を読んだ。期待は保存後に変更せず、命令は判定器への入力だけとして扱った。

## 検証の結果

- 実行は `python3 -B -` の標準入力から独自の集計処理を動かし、各対の JSON（tool_name / tool_input / cwd）を `python3 -B harness/guard.py --dialect claude` に渡した。cwd はこの作業木（R1-subcwd-out / R5-subcwd-in は harness/）。担い手は HARNESS_ROLE=worker を維持、指示役は `env -u HARNESS_ROLE -u HARNESS_HANDS`、HARNESS_APPROVED / HARNESS_ATTENDED / HARNESS_GUARD_TRACE は個別指定以外外した。
- 事前 88 対中 87 件を実測、73 一致・14 不一致・1 未測定。実装を読んだ後の追加 20 件は 13 一致・7 不一致。計 107 判定の不一致 21 件は、上記 11、設計の限界 3、承認印の置き方 5、報告の shell 1、--staged と --worktree の併用 1。
- R1 の基本 12 件、R2 の 13 件（守り 2 ファイル＋hook 設定 9 つを含む）、R3 の直接起動 10 件、R5 の 11 件は期待どおり。git の 5 操作は担い手で deny、指示役の既定で判断カードを促す deny、HARNESS_ATTENDED=1 では ask。追加の apply_patch による守りの変更、Write の変数 path も deny。
- 承認印を判定器の環境に置いた事前 5 件は期待 allow に対し deny。要求の「先頭に付ける」を確認し、命令文字列を `HARNESS_APPROVED=1 git ...` にした追加 5 件は allow、その直後の印なし 5 件は deny。担い手は同じ接頭辞でも deny。事前期待の解釈違いとして残し、承認機能の不具合には数えない。
- R6: HARNESS_HANDS=none / HARNESS_REPORT=この作業木の REPORT.md で Write は allow、他ファイルの Write は deny。`printf x > REPORT.md` は deny（事前期待 allow と不一致）。既存の例外は path 欄で判定しており、shell まで通るという期待は広すぎた。Write による報告経路は維持。
- 設計の限界: `python3 -c "open('../outside.txt','w').write('x')"`、`dd if=/dev/zero of=../outside.txt count=1`、`ln -sf /tmp/outside.txt notes.txt` は allow。任意コードと未対応命令を隔離できない。ln 単独は外部内容の書き換えを実証しない。docs/SECURITY.md:95 の限界と分けて扱う。
- 故障を検出する確認はメモリ上だけで実行。外部書き込み判定、CLI 起動禁止、git 破棄禁止を別々に無効化した 3 種類で、事前の R1-write / R3-2 / R4-2-worker が終了 2 → 0 となり、期待 deny との差を 3/3 検出。実装・既存試験は書き換えていない。

## 残り

- 外部への既存 symlink は見つからず、作成は許可範囲外なので B-symlink-write は未測定。`python3 harness/check.py` と既存試験の全実行は、一時ディレクトリや Git リポジトリを書き込むため未実施。実際の CLI 起動・外部書き込み・履歴破棄は実行していない。

## 人の判断が要ること

- 上記 11 入力を修正担当へ戻す判断。別途 `git restore --staged --worktree README.md` も allow（終了 0、出力なし）。「--staged 無し」という列挙には従うが作業内容を消し得るため、要求 4 の対象を広げるか判断が必要。同じ OpenAI の別モデルによる確認であり、別会社という skill の原則については依頼の指定を優先した。

## 変更したファイル

- `EXPECTATIONS.md`、`REPORT.md` のみ。`git diff --check` は終了 0。`sha256sum` で事前期待・guard.py・test_guard.py・既存変更の docs/design/IMPROVE.md の hash が作業前後で一致。引き継ぎもこの報告に集約し、追加ファイルは作成していない。
