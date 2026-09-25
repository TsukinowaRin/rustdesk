#!/usr/bin/env bash
# WSL から Windows 側を 1 回だけ動かす橋。旧版（v3.0.x の scripts/wsl_to_win.sh）の要る部分だけ。
#
#   wsl_to_win.sh pwsh '<PowerShell の本文>'      PowerShell を 1 つ実行する
#   wsl_to_win.sh cli <実行ファイル> [引数...]     Windows 側の実行ファイルを 1 つ実行する
#
# 守り: harness/guard.py はこの橋を知っていて、pwsh の本文と cli の命令を直接の powershell / cmd と
# 同じに読む（2026-09-23）。守りの判定はここに足さない（1 か所に置く）。
set -euo pipefail

usage() {
  sed -n '4,5p' "$0" | sed 's/^# *//' >&2
  exit 2
}

# 本文は UTF-16LE の base64（-EncodedCommand）で渡す。WSL → Windows の引数変換で
# 引用符や改行が崩れないようにするため。
run_pwsh() {
  [[ $# -eq 1 && -n "$1" ]] || usage
  local exe body_b64 wrapper enc
  exe="$(command -v pwsh.exe || command -v powershell.exe)" || {
    echo "wsl_to_win: PowerShell（pwsh.exe / powershell.exe）が見つかりません" >&2
    exit 4
  }
  body_b64="$(printf '%s' "$1" | tr -d '\r' | base64 -w0)"
  # 失敗を 0 と誤報しない: throw・Write-Error・外部命令の非 0 を終了値に出す。
  # 出力は UTF-8 にそろえる（既定の CP932 だと日本語が WSL 側で化ける。2026-09-23 に実測）。
  wrapper="\$ErrorActionPreference='Stop'; \$ProgressPreference='SilentlyContinue'
try {
  [Console]::OutputEncoding = [Text.Encoding]::UTF8
  \$b = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('${body_b64}'))
  \$global:LASTEXITCODE = 0; \$Error.Clear()
  & ([scriptblock]::Create(\$b)); \$ok = \$?
  if (\$LASTEXITCODE -ne 0) { exit \$LASTEXITCODE }
  if (-not \$ok -or \$Error.Count -gt 0) { exit 1 }
  exit 0
} catch { [Console]::Error.WriteLine(\$_.Exception.Message); exit 1 }"
  enc="$(printf '%s' "$wrapper" | iconv -f UTF-8 -t UTF-16LE | base64 -w0)"
  exec "$exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -OutputFormat Text -EncodedCommand "$enc"
}

run_cli() {
  [[ $# -ge 1 && -n "$1" ]] || usage
  local target="$1" exe
  shift
  if [[ "$target" =~ ^[A-Za-z]:[\\/] ]]; then
    exe="$(wslpath -u "$target")"
  else
    # 拡張子が無ければ .exe を先に探す（同じ名前の Linux の命令を掴まないため）
    exe="$(command -v "$target.exe" || command -v "$target")" || exe=""
  fi
  if [[ ! "$exe" =~ ^/mnt/[A-Za-z]/ ]]; then
    echo "wsl_to_win: Windows 側の実行ファイルが見つかりません: $target" >&2
    exit 4
  fi
  exec "$exe" "$@"
}

[[ $# -ge 1 ]] || usage
sub="$1"
shift
case "$sub" in
  pwsh) run_pwsh "$@" ;;
  cli) run_cli "$@" ;;
  *) usage ;;
esac
