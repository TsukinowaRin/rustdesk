#!/usr/bin/env bash
# DeepSeek Harness（dsh）の起動口。守りの追加設定（.dsh/guard.patch.yml）を必ず付けて起動する。
#   bash harness/dsh.sh web                         画面を開く（モデルの提供元へのサインインや鍵の登録はここで）
#   bash harness/dsh.sh --profile headless "<依頼>"  1 回だけ動かす
#   bash harness/dsh.sh --profile acp               担い手として（harness/delegate.py が使う）
#
# 認証情報は dsh 本体のグローバルな置き場（既定 ~/.dsh/）にだけ置く。Codex や Claude Code や opencode と同じ。
# この起動口は DSH_HOME を設定しない。ここから起動して登録した鍵やサインインも ~/.dsh/ に入り、
# repo にも配布物にも入らない。.dsh/ の設定に書くのは環境変数の「名前」だけ（鍵そのものは書かない）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ -n "${DSH_HOME:-}" ]]; then
  home="$(mkdir -p "$DSH_HOME" && cd "$DSH_HOME" && pwd -P)"
  case "$home/" in "$ROOT"/*) echo "dsh.sh: DSH_HOME が repo の中（$home）を指しています。認証情報を repo に置かないため、起動しません。DSH_HOME を外すか、repo の外にしてください。" >&2; exit 2;; esac
fi
cd "$ROOT"   # hook の設定（configPath）は起動した場所から解決される
DSH=(npx -y @deepseek-ai/dsh)
command -v dsh >/dev/null 2>&1 && DSH=(dsh)
extra=()
for f in "$ROOT"/.dsh/*.local.patch.yml; do [[ -e "$f" ]] && extra+=(--patch "$f"); done  # 人ごとの提供元の設定（git に入れない）
# 担い手の作業木（git worktree）には git に入らない patch が写らないので、本体の repo の .dsh/ も見る（9/25 実測: 作業木の dsh が提供元を知らず鍵なしで落ちた）
main="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
if [[ -n "$main" && "$(cd "$main/.." && pwd -P)" != "$(cd "$ROOT" && pwd -P)" ]]; then
  for f in "$main"/../.dsh/*.local.patch.yml; do [[ -e "$f" ]] && extra+=(--patch "$f"); done
fi
# `web` は `--profile web` の別名。別名のままだと、うしろの旗が画面の側へ渡ってしまう
if [[ "${1:-}" == "web" ]]; then shift; set -- --profile web "$@"; fi
exec "${DSH[@]}" --patch "$ROOT/.dsh/guard.patch.yml" "${extra[@]}" "$@"
