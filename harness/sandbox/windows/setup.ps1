$ErrorActionPreference = "Continue"
Start-Transcript -Path C:\out\setup-log.txt -Force
Copy-Item C:\in\vc_redist.x64.exe C:\Windows\Temp\vc.exe -Force
Unblock-File C:\Windows\Temp\vc.exe -ErrorAction SilentlyContinue
& C:\Windows\Temp\vc.exe /install /quiet /norestart | Out-Null
"VCEXIT=$LASTEXITCODE" | Out-File C:\out\env.txt -Encoding ascii
"VCRUNTIME=$(Test-Path C:\Windows\System32\vcruntime140.dll)" | Out-File C:\out\env.txt -Append -Encoding ascii
"ADMIN=$(([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrators'))" | Out-File C:\out\env.txt -Append -Encoding ascii
Get-ChildItem $env:TEMP -Filter "dd_vcredist*.log" -ErrorAction SilentlyContinue | Select-Object -First 1 | Copy-Item -Destination C:\out\vc-install.log -ErrorAction SilentlyContinue
Expand-Archive -Path C:\in\node.zip -DestinationPath C:\node -Force
$dir = (Get-ChildItem C:\node -Directory | Select-Object -First 1).FullName
$env:Path = "$dir;$env:Path"
"NODE=$(node --version)" | Out-File C:\out\env.txt -Append -Encoding ascii
Set-Location C:\out
node C:\in\probe.mjs
Stop-Transcript
"DONE" | Out-File C:\out\DONE.txt
Start-Sleep -Seconds 3
shutdown /s /t 0
