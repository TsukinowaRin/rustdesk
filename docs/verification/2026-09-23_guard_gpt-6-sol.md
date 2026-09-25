# 報告: 守りの独立の確認
## 何をした
- `EXPECTATIONS.md` に22対を先書き。保存 2026-09-23 03:35:09 UTC、実装を読み始めた時刻 03:35:17 UTC。
- 合否: 判定保留（D10を実測できないため）。確認済みの範囲で差し戻す点なし。最終採否は別担当。
## 検証の結果
- 各入力を `echo '<JSON>' | python3 harness/guard.py --dialect claude; echo exit=$?` で個別測定。21/22件実測、18件一致、3件はworker環境のask→deny変換、1件はhookが測定用shellを拒否。
| 入力 | 期待 | 実際 | 一致 | 入力 | 期待 | 実際 | 一致 |
|---|---|---|---|---|---|---|---|
| D01 `rm -rf ../guard-probe` | deny | deny(2) | ○ | A01 `pwd` | allow | allow(0) | ○ |
| D02 `rm -rf .` | deny | deny(2) | ○ | A02 `git fetch origin` | allow | allow(0) | ○ |
| D03 `rm -rf .git` | deny | deny(2) | ○ | A03 `curl -I https://example.org` | allow | allow(0) | ○ |
| D04 `cat .env.local` | deny | deny(2) | ○ | A04 `rm -rf ./scratch/cache` | allow | allow(0) | ○ |
| D05 `head -n 1 ~/.ssh/id_ed25519` | deny | deny(2) | ○ | A05 `git clean -fdn` | allow | allow(0) | ○ |
| D06 `sudo id` | deny | deny(2) | ○ | A06 `git commit -m "rm -rf /"` | allow | allow(0) | ○ |
| D07 `git push origin main` | deny | deny(2) | ○ | A07 `printf '%s\\n' 'sudo id'` | allow | allow(0) | ○ |
| D08 `dd if=/dev/zero of=/dev/sda` | deny | deny(2) | ○ | A08 `rg --files docs` | allow | allow(0) | ○ |
| D09 `printf 'unfinished` | deny | deny(2) | ○ | Q01 `git push origin feature/check` | ask | deny(2) | × |
| D10 `cat <<ENDMARK` | deny | 未測定 | ? | Q02 `curl -X POST -d sample https://example.org/upload` | ask | deny(2) | × |
| D11 `printf x \| xargs rm -rf` | deny | deny(2) | ○ | Q03 `rm -rf "$TARGET_DIR"` | ask | deny(2) | × |
- `python3 tests/test_guard.py` 原状と復元後: exit 0、「場面 104 + 入出力 28、ずれ 0」。
- 秘密名判定を一時無効化 → 同試験 exit 1、ずれ 13。
- `sudo` 判定を一時無効化 → 同試験 exit 1、ずれ 3。
- 作業木外の木ごとの削除判定を一時無効化 → 同試験 exit 1、ずれ 17。
- 各改変後に `git checkout harness/guard.py`。最後の `git diff --exit-code -- harness/guard.py` は exit 0。
## 残り
- D10は事前hookが測定用shellを拒否し、回避せず未測定。止めるべき入力を通した観測例はなし。
## 人の判断が要ること
- D10を別環境で追加測定するかの判断。Q01～Q03は `HARNESS_ROLE=worker` のためaskがdenyになったもので、別形で再実行していない。
## 変更したファイル
- `EXPECTATIONS.md`、`REPORT.md`（`harness/guard.py` は復元済み）。
