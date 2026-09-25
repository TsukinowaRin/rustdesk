# Hyper-V の使い捨て Windows の中で、ログオン直後に 1 回だけ走る台本（Startup フォルダから起動）。
# Sandbox 用の setup.ps1 と同じ流れ。違いは 2 つ: 結果を母艦へ返す道が無いので、まず利用者に
# パスワードを付けて PowerShell Direct（母艦から VM の中の PowerShell を呼ぶ仕組み）を通せるようにする /
# 最後に電源を切らず、母艦が結果を取りに来るのを待つ。
$ErrorActionPreference = "Continue"
New-Item -ItemType Directory -Path C:\out -Force | Out-Null
if (Test-Path C:\out\STARTED.txt) { exit 0 }   # 母艦が打ち直しても 2 重に走らない
"started" | Out-File C:\out\STARTED.txt -Encoding ascii
Start-Transcript -Path C:\out\setup-log.txt -Force
$pw = Get-Content C:\in\pw.txt -Raw
$pw = $pw.Trim()
net user User $pw | Out-Null
"PWSET=$LASTEXITCODE" | Out-File C:\out\env.txt -Encoding ascii
Copy-Item C:\in\vc_redist.x64.exe C:\Windows\Temp\vc.exe -Force
Unblock-File C:\Windows\Temp\vc.exe -ErrorAction SilentlyContinue
& C:\Windows\Temp\vc.exe /install /quiet /norestart | Out-Null
"VCEXIT=$LASTEXITCODE" | Out-File C:\out\env.txt -Append -Encoding ascii
"VCRUNTIME=$(Test-Path C:\Windows\System32\vcruntime140.dll)" | Out-File C:\out\env.txt -Append -Encoding ascii
"ADMIN=$(([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrators'))" | Out-File C:\out\env.txt -Append -Encoding ascii
"SESSION=$([System.Diagnostics.Process]::GetCurrentProcess().SessionId)" | Out-File C:\out\env.txt -Append -Encoding ascii
Expand-Archive -Path C:\in\node.zip -DestinationPath C:\node -Force
$dir = (Get-ChildItem C:\node -Directory | Select-Object -First 1).FullName
$env:Path = "$dir;$env:Path"
"NODE=$(node --version)" | Out-File C:\out\env.txt -Append -Encoding ascii
Set-Location C:\out
node C:\in\probe.mjs
Stop-Transcript
"DONE" | Out-File C:\out\DONE.txt -Encoding ascii
