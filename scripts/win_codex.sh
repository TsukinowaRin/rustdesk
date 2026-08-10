#!/usr/bin/env bash
set -euo pipefail

WIN_CODEX_CMD="${WIN_CODEX_CMD:-codex}"
WIN_CODEX_WORKDIR="${WIN_CODEX_WORKDIR:-$PWD}"
WIN_CODEX_RUNNER="${WIN_CODEX_RUNNER:-auto}" # auto|pwsh|powershell|cmd
WIN_CODEX_PWSH="${WIN_CODEX_PWSH:-${WIN_PWSH:-}}"
WIN_CMD="${WIN_CMD:-cmd.exe}"

usage() {
  cat >&2 <<'USAGE'
Usage:
  win_codex.sh [--workdir <path>] [--] <codex-args...>

Examples:
  scripts/win_codex.sh --version
  scripts/win_codex.sh exec --skip-git-repo-check "hello"
  scripts/win_codex.sh --workdir <wsl-repo-path> exec "task"

Env:
  WIN_CODEX_CMD      Windows-side Codex command (default: codex).
                     The default is intentionally not codex.cmd: npm installs often expose
                     codex.ps1 to PowerShell even when codex.cmd is not visible to cmd.exe.
  WIN_CODEX_RUNNER   auto|pwsh|powershell|cmd (default: auto; prefer PowerShell 7).
                     cmd keeps the legacy codex.cmd path for environments that need it.
  WIN_CODEX_PWSH     Explicit PowerShell executable/path for pwsh/powershell runner.
  WIN_CMD            Windows cmd runner for WIN_CODEX_RUNNER=cmd (default: cmd.exe).
  WIN_CODEX_WORKDIR  Working directory source path (default: current WSL cwd).
USAGE
  exit 2
}

to_wsl_path() {
  local input="$1"

  if [[ "$input" =~ ^[A-Za-z]:\\ ]]; then
    wslpath -u "$input"
    return 0
  fi

  printf '%s\n' "$input"
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

pick_pwsh() {
  local candidate

  if [[ -n "$WIN_CODEX_PWSH" ]]; then
    resolve_windows_exe "$WIN_CODEX_PWSH"
    return 0
  fi

  for candidate in pwsh.exe powershell.exe; do
    if resolve_windows_exe "$candidate" >/dev/null 2>&1; then
      resolve_windows_exe "$candidate"
      return 0
    fi
  done

  return 1
}

resolve_cmd_command() {
  local command_name="$1"
  local resolved=""

  if [[ "$command_name" =~ ^[A-Za-z]:\\ ]] || [[ "$command_name" == *\\* ]]; then
    printf '%s\n' "$command_name"
    return 0
  fi

  resolved="$("$WIN_CMD" /d /c "where $command_name" 2>/dev/null | tr -d '\r' | sed -n '1p' || true)"
  if [[ -n "$resolved" ]]; then
    printf '%s\n' "$resolved"
    return 0
  fi

  printf '%s\n' "$command_name"
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
import base64
import sys
data = sys.stdin.read().encode("utf-16le")
sys.stdout.write(base64.b64encode(data).decode("ascii"))
PY
  fi
}

run_with_powershell() {
  local pwsh="$1"
  local args_b64=""
  local enc_cmd
  shift

  if [[ $# -gt 0 ]]; then
    args_b64="$(printf '%s\0' "$@" | b64_nolf)"
  fi

  # Windows npm shims are inconsistent across shells: this machine exposes
  # `codex.ps1` to PowerShell while `cmd.exe /c codex.cmd` may fail. Resolve with
  # Get-Command and execute the discovered Source so both .ps1 and .cmd installs work.
  local ps_script
  read -r -d '' ps_script <<'PS' || true
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { $PSStyle.OutputRendering = 'PlainText' } catch {}

$ArgsB64 = '__ARGS_B64__'
$commandName = $env:WIN_CODEX_CMD
if ([string]::IsNullOrWhiteSpace($commandName)) { $commandName = 'codex' }

function Decode-NullSeparatedUtf8Args([string]$b64) {
  if ([string]::IsNullOrEmpty($b64)) { return @() }

  $bytes = [Convert]::FromBase64String($b64)
  $raw = [Text.Encoding]::UTF8.GetString($bytes)
  if ($raw.Length -gt 0 -and $raw.EndsWith([string][char]0)) {
    $raw = $raw.Substring(0, $raw.Length - 1)
  }
  if ([string]::IsNullOrEmpty($raw)) { return @() }

  return $raw.Split([char]0, [System.StringSplitOptions]::None)
}

function Resolve-WindowsCodexSource([string]$name) {
  if ($name -match '^[A-Za-z]:\\' -or $name.Contains('\')) {
    return $name
  }

  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if ($null -ne $cmd -and -not [string]::IsNullOrWhiteSpace($cmd.Source)) {
    return $cmd.Source
  }

  $candidateNames = @($name)
  if ($name -eq 'codex') {
    $candidateNames = @('codex.ps1', 'codex.cmd', 'codex.exe', 'codex-x86_64-pc-windows-msvc.exe')
  } elseif ([IO.Path]::GetExtension($name) -eq '') {
    $candidateNames = @("$name.ps1", "$name.cmd", "$name.exe")
  }

  $candidateDirs = @()
  if (-not [string]::IsNullOrWhiteSpace($env:APPDATA)) {
    $candidateDirs += (Join-Path $env:APPDATA 'npm')
  }
  if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    $candidateDirs += (Join-Path $env:USERPROFILE 'AppData\Roaming\npm')
  }
  if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    $wingetRoot = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
    $candidateDirs += (Join-Path $wingetRoot 'OpenAI.Codex_Microsoft.Winget.Source_8wekyb3d8bbwe')
    if (Test-Path -LiteralPath $wingetRoot) {
      $candidateDirs += @(Get-ChildItem -LiteralPath $wingetRoot -Directory -Filter 'OpenAI.Codex_*' -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    }
  }

  foreach ($dir in ($candidateDirs | Select-Object -Unique)) {
    foreach ($file in $candidateNames) {
      $path = Join-Path $dir $file
      if (Test-Path -LiteralPath $path) {
        return $path
      }
    }
  }

  throw ("Unable to resolve Windows Codex command: {0}" -f $name)
}

try {
  $codexArgs = @(Decode-NullSeparatedUtf8Args $ArgsB64)
  $source = Resolve-WindowsCodexSource $commandName

  & $source @codexArgs

  $ok = $?
  $lastExit = Get-Variable -Name LASTEXITCODE -ErrorAction SilentlyContinue
  if ($null -ne $lastExit -and $null -ne $lastExit.Value) {
    $code = [int]$lastExit.Value
    if ($code -ne 0) { exit $code }
  }

  if (-not $ok) { exit 1 }
  exit 0
}
catch {
  Write-Error ($_.Exception.Message)
  exit 1
}
PS

  ps_script="${ps_script//__ARGS_B64__/$args_b64}"
  enc_cmd="$(printf '%s' "$ps_script" | b64_utf16le_nolf)"

  export WIN_CODEX_CMD
  exec "$pwsh" -NoProfile -NonInteractive -ExecutionPolicy Bypass -OutputFormat Text -EncodedCommand "$enc_cmd"
}

run_with_cmd() {
  local codex_cmd

  codex_cmd="$(resolve_cmd_command "$WIN_CODEX_CMD")"
  exec "$WIN_CMD" /d /c "$codex_cmd" "$@"
}

workdir="$WIN_CODEX_WORKDIR"
if [[ "${1-}" == "--workdir" ]]; then
  [[ $# -ge 3 ]] || usage
  workdir="$2"
  shift 2
fi

if [[ "${1-}" == "--" ]]; then
  shift
fi

if [[ $# -lt 1 ]]; then
  usage
fi

workdir="$(to_wsl_path "$workdir")"
if [[ ! -d "$workdir" ]]; then
  printf 'Working directory not found: %s\n' "$workdir" >&2
  exit 1
fi

(
  cd "$workdir"

  case "$WIN_CODEX_RUNNER" in
    auto)
      if pwsh_path="$(pick_pwsh 2>/dev/null)"; then
        run_with_powershell "$pwsh_path" "$@"
      fi
      run_with_cmd "$@"
      ;;
    pwsh|powershell)
      pwsh_path="$(pick_pwsh)" || {
        printf 'PowerShell runner not found. Set WIN_CODEX_PWSH or use WIN_CODEX_RUNNER=cmd.\n' >&2
        exit 1
      }
      run_with_powershell "$pwsh_path" "$@"
      ;;
    cmd)
      run_with_cmd "$@"
      ;;
    *)
      printf 'Invalid WIN_CODEX_RUNNER: %s\n' "$WIN_CODEX_RUNNER" >&2
      exit 2
      ;;
  esac
)
