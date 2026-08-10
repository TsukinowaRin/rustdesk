param(
  [string]$Distro = "",
  [string]$Workdir = "",
  [string]$ShellCommand = "",
  [string[]]$Exec = @(),
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CommandArgs = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$debugEnabled = ($env:WSL_EXEC_DEBUG -eq "1")
$traceFile = if ($env:WSL_EXEC_TRACE_FILE) { $env:WSL_EXEC_TRACE_FILE } else { "" }

function Write-TraceLine {
  param([string]$Message)
  if (-not $traceFile) { return }
  Add-Content -LiteralPath $traceFile -Value $Message
}

function Show-Usage {
  @"
Usage:
  .\scripts\wsl_exec.ps1 [-Distro <name>] [-Workdir <path>] -Exec <command> [args...]
  .\scripts\wsl_exec.ps1 [-Distro <name>] [-Workdir <path>] -ShellCommand "<bash -lc body>"
  .\scripts\wsl_exec.cmd [-Distro <name>] [-Workdir <path>] -Exec <command> [args...]

Examples:
  .\scripts\wsl_exec.ps1 -Workdir <wsl-repo-path> -Exec pwd
  .\scripts\wsl_exec.ps1 -Workdir <windows-repo-path> -Exec git status
  .\scripts\wsl_exec.ps1 -Workdir <wsl-repo-path> -ShellCommand "python3 -m pytest -q"
  .\scripts\wsl_exec.cmd -Workdir <windows-repo-path> -Exec git status

Env:
  WSL_EXEC_DISTRO   Default distro override
  WSL_EXEC_WORKDIR  Default workdir override

Notes:
  - Workdir accepts WSL path or Windows path.
  - If Workdir is omitted, WSL default current directory resolution is used.
  - This wrapper forwards stdout/stderr and exit code from wsl.exe.
"@ | Write-Error
  exit 2
}

function Convert-ToWslPath {
  param([string]$InputPath)

  if ([string]::IsNullOrWhiteSpace($InputPath)) {
    return ""
  }

  if ($InputPath -match '^[A-Za-z]:\\') {
    $drive = $InputPath.Substring(0, 1).ToLowerInvariant()
    $tail = $InputPath.Substring(2) -replace '\\', '/'
    return "/mnt/$drive/$tail"
  }

  if ($InputPath -like '/*') {
    return $InputPath
  }

  $resolved = Resolve-Path -LiteralPath $InputPath -ErrorAction Stop
  return Convert-ToWslPath -InputPath $resolved.Path
}

function Convert-ToPwshSingleQuoted {
  param([string]$Value)
  return "'" + ($Value -replace "'", "''") + "'"
}

function Convert-ToBashSingleQuoted {
  param([string]$Value)
  return "'" + ($Value -replace "'", "'\''") + "'"
}

$effectiveDistro = if ($Distro) { $Distro } elseif ($env:WSL_EXEC_DISTRO) { $env:WSL_EXEC_DISTRO } else { "" }
$effectiveWorkdir = if ($Workdir) { $Workdir } elseif ($env:WSL_EXEC_WORKDIR) { $env:WSL_EXEC_WORKDIR } else { "" }
$CommandArgs = @($Exec) + @($CommandArgs)

if ($CommandArgs.Count -gt 0 -and $CommandArgs[0] -eq "--") {
  $CommandArgs = $CommandArgs[1..($CommandArgs.Count - 1)]
}

if ([string]::IsNullOrWhiteSpace($ShellCommand) -and $CommandArgs.Count -eq 0) {
  Show-Usage
}

$wslPath = if ($effectiveWorkdir) { Convert-ToWslPath -InputPath $effectiveWorkdir } else { "" }
$bashCommand = if ($ShellCommand) {
  $ShellCommand
} else {
  ($CommandArgs | ForEach-Object { Convert-ToBashSingleQuoted -Value $_ }) -join " "
}

$wslArgs = @()
if ($effectiveDistro) {
  $wslArgs += @("-d", $effectiveDistro)
}

if ($wslPath) {
  $wslArgs += @("--cd", $wslPath)
}

$wslArgs += @("bash", "-lc", $bashCommand)
$displayInvoke = "wsl.exe " + (($wslArgs | ForEach-Object { Convert-ToPwshSingleQuoted -Value $_ }) -join " ")

if ($debugEnabled) {
  Write-Host "[wsl_exec] $displayInvoke" -ForegroundColor Yellow
}
Write-TraceLine ("invoke=" + $displayInvoke)

& wsl.exe @wslArgs
$exitCode = 0
if (Test-Path variable:LASTEXITCODE) {
  $exitCode = [int]$LASTEXITCODE
}
Write-TraceLine ("exit=" + $exitCode)
exit $exitCode
