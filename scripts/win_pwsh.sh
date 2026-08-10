#!/usr/bin/env bash
set -euo pipefail

WINHOST="${WINHOST:-localhost}"
WINUSER="${WINUSER:-}"
WINPORT="${WINPORT:-2222}"

# If unset, prefer PowerShell 7 (`pwsh.exe`) and fall back to Windows PowerShell (`powershell.exe`).
# You can also set an explicit Windows executable path:
#   export WIN_PWSH='<path-to-pwsh.exe>'
WIN_PWSH="${WIN_PWSH:-}"
WIN_TRANSPORT="${WIN_TRANSPORT:-auto}" # auto (prefer direct; ssh only if configured) | direct | ssh

WIN_PWSH_DEBUG="${WIN_PWSH_DEBUG:-0}"
WIN_SSH_TTY="${WIN_SSH_TTY:-0}"
WIN_ALLOW_DANGEROUS="${WIN_ALLOW_DANGEROUS:-0}"

SSH_OPTS=(
  -p "$WINPORT"
  -o BatchMode=yes
  -o StrictHostKeyChecking=accept-new
  -o ServerAliveInterval=15
  -o ServerAliveCountMax=4
  -o ConnectTimeout=8
)

usage() {
  cat >&2 <<'USAGE'
Usage:
  win_pwsh.sh '<pwsh-script>'
  win_pwsh.sh --file <path-to-ps1> [args...]

Examples:
  scripts/win_pwsh.sh '$PSVersionTable.PSVersion.ToString()'
  scripts/win_pwsh.sh 'Set-Location "<windows-repo-path>"; npm run compile'
  scripts/win_pwsh.sh --file <wsl-repo-path>/scripts/task.ps1 foo bar

Env:
  WINHOST WINUSER WINPORT
  WIN_PWSH            (default: auto -> pwsh.exe, fallback: powershell.exe)
  WIN_TRANSPORT       (auto|direct|ssh, default: auto; direct preferred, ssh optional)
  WIN_SSH_TTY         (0: -T (default), 1: -tt)
  WIN_PWSH_DEBUG      (0/1)
  WIN_ALLOW_DANGEROUS (0/1)  # 0 blocks some destructive keywords for command mode

Notes:
  WINUSER is only required when WIN_TRANSPORT=ssh or auto resolves to ssh.
USAGE
}

resolve_windows_exe() {
  local value="$1"

  if [[ "$value" =~ ^[A-Za-z]:\\ ]]; then
    wslpath -u "$value"
    return 0
  fi

  if [[ "$value" == /* ]]; then
    printf '%s\n' "$value"
    return 0
  fi

  if command -v "$value" >/dev/null 2>&1; then
    command -v "$value"
    return 0
  fi

  return 1
}

windows_pwsh_candidates() {
  if [[ -n "$WIN_PWSH" ]]; then
    printf '%s\n' "$WIN_PWSH"
    return 0
  fi

  printf '%s\n' "pwsh.exe" "powershell.exe"
}

resolve_preferred_windows_exe() {
  local candidate

  while IFS= read -r candidate; do
    if resolve_windows_exe "$candidate" >/dev/null 2>&1; then
      resolve_windows_exe "$candidate"
      return 0
    fi
  done < <(windows_pwsh_candidates)

  return 1
}

pick_transport() {
  case "$WIN_TRANSPORT" in
    direct|ssh)
      printf '%s\n' "$WIN_TRANSPORT"
      ;;
    auto)
      if resolve_preferred_windows_exe >/dev/null 2>&1; then
        printf '%s\n' "direct"
      else
        printf '%s\n' "ssh"
      fi
      ;;
    *)
      echo "[win_pwsh] invalid WIN_TRANSPORT: $WIN_TRANSPORT" >&2
      exit 2
      ;;
  esac
}

b64_nolf() {
  if base64 --help 2>/dev/null | grep -q -- '-w'; then
    base64 -w0
  else
    base64 | tr -d '\r\n'
  fi
}

b64_utf16le_nolf() {
  if command -v iconv >/dev/null 2>&1; then
    iconv -f UTF-8 -t UTF-16LE | b64_nolf
  else
    python3 - <<'PY'
import sys, base64
data = sys.stdin.read().encode('utf-16le')
sys.stdout.write(base64.b64encode(data).decode('ascii'))
PY
  fi
}

to_windows_path() {
  local input="$1"

  if [[ "$input" =~ ^[A-Za-z]:\\ ]]; then
    printf '%s\n' "$input"
    return 0
  fi

  if [[ "$input" == /* ]]; then
    wslpath -w "$input"
    return 0
  fi

  printf '%s\n' "$input"
}

build_file_mode_script() {
  local ps1_win="$1"
  local args_b64=""
  local ps1_b64
  local script

  shift || true
  ps1_b64="$(printf '%s' "$ps1_win" | b64_nolf)"

  if [[ $# -gt 0 ]]; then
    args_b64="$(printf '%s\0' "$@" | b64_nolf)"
  fi

  if [[ "$WIN_PWSH_DEBUG" == "1" ]]; then
    echo "[win_pwsh] Ps1PathWin=$ps1_win" >&2
    echo "[win_pwsh] Ps1PathB64Len=${#ps1_b64}" >&2
    echo "[win_pwsh] ArgsB64Len=${#args_b64}" >&2
  fi

  read -r -d '' script <<'PS' || true
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { $PSStyle.OutputRendering = 'PlainText' } catch {}

$Ps1PathB64 = '__PS1_B64__'
$ArgsB64    = '__ARGS_B64__'
$Debug      = ('__DBG__' -eq '1')

function Decode-NullSeparatedUtf8Args([string]$b64) {
  if ([string]::IsNullOrEmpty($b64)) { return @() }

  $bytes = [Convert]::FromBase64String($b64)
  $raw   = [Text.Encoding]::UTF8.GetString($bytes)

  if ($raw.Length -gt 0 -and $raw.EndsWith([string][char]0)) {
    $raw = $raw.Substring(0, $raw.Length - 1)
  }
  if ([string]::IsNullOrEmpty($raw)) { return @() }

  return $raw.Split([char]0, [System.StringSplitOptions]::None)
}

try {
  $Ps1Path = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Ps1PathB64))
  if ($Debug) { Write-Output "[win_pwsh.ps] Ps1Path=$Ps1Path" }

  if (-not (Test-Path -LiteralPath $Ps1Path)) {
    throw ("PS1 not found: {0}" -f $Ps1Path)
  }

  $argsList = @(Decode-NullSeparatedUtf8Args $ArgsB64)

  if ($Debug) {
    Write-Output ("[win_pwsh.ps] ArgsCount=" + $argsList.Count)
    if ($argsList.Count -gt 0) { Write-Output ("[win_pwsh.ps] Args=" + ($argsList -join ' | ')) }
  }

  & $Ps1Path @argsList

  $ok = $?
  $hasErr = ($Error.Count -gt 0)

  $v = Get-Variable -Name LASTEXITCODE -ErrorAction SilentlyContinue
  if ($null -ne $v) {
    $code = [int]$v.Value
    if ($code -ne 0) { exit $code }
  }

  if (-not $ok -or $hasErr) { exit 1 }
  exit 0
}
catch {
  Write-Error ($_.Exception.Message)
  exit 1
}
PS

  script=${script//__PS1_B64__/$ps1_b64}
  script=${script//__ARGS_B64__/$args_b64}
  script=${script//__DBG__/$WIN_PWSH_DEBUG}

  printf '%s' "$script"
}

build_remote_pwsh_command() {
  local enc_cmd="$1"
  local remote_pwsh=""

  if [[ -n "$WIN_PWSH" ]]; then
    remote_pwsh="$WIN_PWSH"
    if [[ "$remote_pwsh" == *" "* ]]; then
      remote_pwsh="\"${remote_pwsh//\"/\\\"}\""
    fi
    printf '%s\n' "${remote_pwsh} -NoProfile -NonInteractive -ExecutionPolicy Bypass -OutputFormat Text -EncodedCommand ${enc_cmd}"
    return 0
  fi

  printf '%s\n' "cmd.exe /V:ON /C \"(where pwsh.exe >nul 2>nul && set PWSH=pwsh.exe) || (where powershell.exe >nul 2>nul && set PWSH=powershell.exe) || (echo [win_pwsh] no PowerShell found 1>&2 & exit /b 9009) & !PWSH! -NoProfile -NonInteractive -ExecutionPolicy Bypass -OutputFormat Text -EncodedCommand ${enc_cmd}\""
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

mode="command"
cmd=""
ps1_input=""

if [[ "${1-}" == "--file" ]]; then
  [[ $# -ge 2 ]] || usage
  mode="file"
  ps1_input="$2"
  shift 2 || true
  cmd="$(build_file_mode_script "$(to_windows_path "$ps1_input")" "$@")"
else
  cmd="$(printf '%s' "$1" | tr -d '\r')"
  shift || true
fi

if [[ "$mode" == "command" && "$WIN_ALLOW_DANGEROUS" != "1" ]]; then
  if printf '%s' "$cmd" | grep -Eiq '\b(rm|rmdir|dd|mkfs|format|diskpart|bcdedit|takeown|icacls|del|rd|remove-item|stop-process|taskkill|restart-computer|shutdown|reg[[:space:]]+(add|delete)|sc[[:space:]]+(stop|delete)|net[[:space:]]+(user|localgroup))\b'; then
    echo "[win_pwsh] BLOCKED: command looks destructive. Set WIN_ALLOW_DANGEROUS=1 to override." >&2
    echo "[win_pwsh] cmd: $cmd" >&2
    exit 3
  fi
fi

transport="$(pick_transport)"
enc_cmd="$(printf '%s' "$cmd" | b64_utf16le_nolf)"

if [[ "$WIN_PWSH_DEBUG" == "1" ]]; then
  echo "== win_pwsh ==" >&2
  if [[ -n "$WINUSER" ]]; then
    echo "Target : ${WINUSER}@${WINHOST}:${WINPORT}" >&2
  else
    echo "Target : ${WINHOST}:${WINPORT}" >&2
  fi
  echo "Pref   : ${WIN_PWSH:-pwsh.exe -> powershell.exe}" >&2
  echo "Mode   : ${transport}" >&2
  echo "Input  : ${mode}" >&2
  echo "TTY    : ${WIN_SSH_TTY}" >&2
  if [[ "$mode" == "command" ]]; then
    echo "Script : ${cmd}" >&2
  else
    echo "File   : ${ps1_input}" >&2
  fi
fi

if [[ "$transport" == "direct" ]]; then
  direct_pwsh="$(resolve_preferred_windows_exe)" || {
    echo "[win_pwsh] direct mode failed: cannot resolve preferred PowerShell" >&2
    exit 4
  }

  "$direct_pwsh" -NoProfile -NonInteractive -ExecutionPolicy Bypass -OutputFormat Text -EncodedCommand "$enc_cmd"
  exit $?
fi

if [[ "$WIN_SSH_TTY" == "1" ]]; then
  SSH_OPTS+=(-tt)
else
  SSH_OPTS+=(-T)
fi

if [[ -z "$WINUSER" ]]; then
  echo "[win_pwsh] WINUSER is required for ssh transport." >&2
  echo "[win_pwsh] Set WINUSER to the Windows SSH account name or use direct transport." >&2
  exit 5
fi

ssh "${SSH_OPTS[@]}" "${WINUSER}@${WINHOST}" "$(build_remote_pwsh_command "$enc_cmd")"
