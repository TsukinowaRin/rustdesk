# 使い捨ての Windows（Hyper-V）を、母艦の PowerShell から 5 つの動詞で扱う。管理者権限は要らない
# （利用者が Hyper-V Administrators に入っていればよい）。
#
#   vm.ps1 create  -Name <名前> -Template <元の .vhdx>        元を触らない差分ディスクで VM を作る
#   vm.ps1 setup   -Name <名前> -InDir <持ち込み> -PwFile <pw> 起動 → C:\in へ写す → キー入力で台本を管理者として起動
#   vm.ps1 run     -Name <名前> -PwFile <pw>                    C:\out\DONE.txt が出るまで待つ
#   vm.ps1 fetch   -Name <名前> -PwFile <pw> -OutDir <持ち出し>  C:\out を母艦へ写す（PowerShell Direct）
#   vm.ps1 destroy -Name <名前>                                  電源を切って VM と差分ディスクを消す
#   vm.ps1 status  [-Name <名前>]
#   vm.ps1 peek    -Name <名前> -OutDir <置き場>               VM の画面の縮小画像（800x600, RGB565 生データ）を母艦へ。peek.py で PNG に
#
# 決まり: 置き場は利用者の領域（%USERPROFILE%\harness-vm。既定の ProgramData は権限で書けない）/
# 持ち込みは Copy-VMFile（母艦 → VM の一方通行）/ 中の台本は母艦からのキー入力（Msvm_Keyboard）で
# 「Win+R → 管理者として powershell → UAC に Alt+Y」で起動する（ログオン中の画面で動くので撮影できる。
# Startup フォルダに置く方法は、パスワードを付ける net user が UAC で断られて使えなかった）/
# 持ち出しは PowerShell Direct で読むだけ /
# 元の .vhdx は差分ディスクの親にするだけで書き換えない / 名前に harness- が付く VM しか消さない。
param(
  [Parameter(Mandatory)][ValidateSet('create','setup','run','fetch','destroy','status','peek')][string]$Verb,
  [string]$Name = 'harness-win',
  [string]$Template, [string]$InDir, [string]$OutDir, [string]$PwFile,
  [int]$MemoryGB = 4, [int]$Cpu = 2, [int]$TimeoutSec = 900
)
$ErrorActionPreference = 'Stop'
$Base = Join-Path $env:USERPROFILE 'harness-vm'

function Say($s) { Write-Output ("[vm] " + $s) }
function Cred() {
  if (-not $PwFile) { throw '-PwFile が要ります' }
  $pw = (Get-Content $PwFile -Raw).Trim()
  New-Object System.Management.Automation.PSCredential('User', (ConvertTo-SecureString $pw -AsPlainText -Force))
}
function WaitHeartbeat($sec) {
  $t0 = Get-Date
  while (((Get-Date) - $t0).TotalSeconds -lt $sec) {
    $hb = (Get-VM -Name $Name).Heartbeat
    if ("$hb" -like 'Ok*') { Say "heartbeat: $hb"; return }
    Start-Sleep -Seconds 5
  }
  throw "VM が $sec 秒たっても応答しません（heartbeat: $((Get-VM -Name $Name).Heartbeat)）"
}
function Keyboard() {
  $vm = Get-CimInstance -Namespace root\virtualization\v2 -ClassName Msvm_ComputerSystem | Where-Object ElementName -eq $Name
  Get-CimAssociatedInstance -InputObject $vm -ResultClassName Msvm_Keyboard
}
function Chord($kb, [uint32]$mod, [uint32]$key) {
  Invoke-CimMethod -InputObject $kb -MethodName PressKey -Arguments @{ keyCode = $mod } | Out-Null
  Invoke-CimMethod -InputObject $kb -MethodName TypeKey -Arguments @{ keyCode = $key } | Out-Null
  Invoke-CimMethod -InputObject $kb -MethodName ReleaseKey -Arguments @{ keyCode = $mod } | Out-Null
}
function TypeRun($kb, [string]$text) {
  Chord $kb 0x5B 0x52                       # Win+R
  Start-Sleep -Seconds 3
  Invoke-CimMethod -InputObject $kb -MethodName TypeText -Arguments @{ asciiText = $text } | Out-Null
  Start-Sleep -Seconds 1
  Invoke-CimMethod -InputObject $kb -MethodName TypeKey -Arguments @{ keyCode = [uint32]0x0D } | Out-Null   # Enter
}
function Guard() { if ($Name -notlike 'harness-*') { throw "名前は harness- で始める（$Name）。母艦にある他の VM を巻き込まないため" } }

switch ($Verb) {
  'status' {
    Get-VM | Where-Object { -not $PSBoundParameters.ContainsKey('Name') -or $_.Name -eq $Name } |
      Select-Object Name, State, Heartbeat, Uptime, @{n='MemGB';e={[math]::Round($_.MemoryAssigned/1GB,1)}} | Format-Table -AutoSize | Out-String -Width 120
  }
  'peek' {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
    $vm = Get-CimInstance -Namespace root\virtualization\v2 -ClassName Msvm_ComputerSystem | Where-Object ElementName -eq $Name
    $vsms = Get-CimInstance -Namespace root\virtualization\v2 -ClassName Msvm_VirtualSystemManagementService
    $sd = Get-CimAssociatedInstance -InputObject $vm -ResultClassName Msvm_VirtualSystemSettingData | Where-Object { $_.VirtualSystemType -eq 'Microsoft:Hyper-V:System:Realized' } | Select-Object -First 1
    $r = Invoke-CimMethod -InputObject $vsms -MethodName GetVirtualSystemThumbnailImage -Arguments @{ TargetSystem = $sd; WidthPixels = [uint16]800; HeightPixels = [uint16]600 }
    if ($r.ReturnValue -ne 0) { throw "画面を取れません（$($r.ReturnValue)）" }
    $f = Join-Path $OutDir 'peek.rgb565'
    [IO.File]::WriteAllBytes($f, [byte[]]$r.ImageData)
    Say "画面: $f（python3 harness/sandbox/hyperv/peek.py で PNG に）"
  }
  'create' {
    Guard
    if (-not (Test-Path $Template)) { throw "元の .vhdx がありません: $Template" }
    if (Get-VM -Name $Name -ErrorAction SilentlyContinue) { throw "同じ名前の VM があります: $Name（先に destroy）" }
    New-Item -ItemType Directory -Path $Base -Force | Out-Null
    $child = Join-Path $Base "$Name.vhdx"
    if (Test-Path $child) { Remove-Item $child -Force }
    New-VHD -Path $child -ParentPath $Template -Differencing | Out-Null
    Say "差分ディスク: $child（親 $Template は書き換えない）"
    $vm = New-VM -Name $Name -Generation 2 -MemoryStartupBytes ($MemoryGB * 1GB) -VHDPath $child -Path $Base -SwitchName 'Default Switch'
    Set-VM -Name $Name -AutomaticCheckpointsEnabled $false -CheckpointType Disabled -AutomaticStopAction TurnOff
    Set-VMProcessor -VMName $Name -Count $Cpu
    Set-VMFirmware -VMName $Name -EnableSecureBoot On
    # 名前は OS の言語で変わる（日本語では「ゲスト サービス インターフェイス」）ので Id で選ぶ
    Get-VMIntegrationService -VMName $Name | Where-Object Id -like '*6C09BB55-D683-4DA0-8931-C9BF705F6480*' | Enable-VMIntegrationService
    Say "作成: $Name（$MemoryGB GB, $Cpu CPU, Default Switch）"
  }
  'setup' {
    Guard
    if (-not (Test-Path $InDir)) { throw "持ち込みフォルダがありません: $InDir" }
    if ((Get-VM -Name $Name).State -ne 'Running') { Start-VM -Name $Name; Say '起動' }
    WaitHeartbeat $TimeoutSec
    Start-Sleep -Seconds 20   # ログオンと Guest Service が上がるまで少し待つ
    Get-ChildItem $InDir -File | ForEach-Object {
      Copy-VMFile -VMName $Name -SourcePath $_.FullName -DestinationPath ("C:\in\" + $_.Name) -FileSource Host -CreateFullPath -Force
      Say ("持ち込み: " + $_.Name)
    }
    $gs = Join-Path $PSScriptRoot 'guest-setup.ps1'
    Copy-VMFile -VMName $Name -SourcePath $gs -DestinationPath 'C:\in\guest-setup.ps1' -FileSource Host -CreateFullPath -Force
    Say '持ち込み: guest-setup.ps1（この台本と同じ場所の物）'
    # 差分ディスクの初回起動は heartbeat の後も「This might take a few minutes」が続き、早く打つと
    # キー入力が捨てられる（実測）。台本は最初にパスワードを付けるので、それが通るまで打ち直す。
    $c = Cred; $kb = Keyboard; $t0 = Get-Date; $n = 0
    while (((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec) {
      $n++
      TypeRun $kb "powershell -Command Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File C:\in\guest-setup.ps1'"
      Start-Sleep -Seconds 6
      Chord $kb 0x12 0x59                     # UAC の「はい」= Alt+Y
      Start-Sleep -Seconds 30
      try {
        Invoke-Command -VMName $Name -Credential $c -ScriptBlock { 1 } -ErrorAction Stop | Out-Null
        Say "キー入力で台本を管理者として起動した（$n 回目で通った。UAC は Alt+Y）"; return
      } catch { Say "まだ画面が受け付けない（$n 回目）" }
    }
    throw "台本を起動できません（$TimeoutSec 秒）"
  }
  'run' {
    $c = Cred; $t0 = Get-Date
    WaitHeartbeat $TimeoutSec
    while (((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec) {
      Start-Sleep -Seconds 15
      try {
        $done = Invoke-Command -VMName $Name -Credential $c -ScriptBlock { Test-Path 'C:\out\DONE.txt' } -ErrorAction Stop
        if ($done) { Say ("完了（" + [int]((Get-Date) - $t0).TotalSeconds + " 秒）"); return }
        Say 'まだ（台本が走っている）'
      } catch { Say ("まだ（" + $_.Exception.Message.Split("`n")[0] + "）") }
    }
    throw "時間切れ（$TimeoutSec 秒）"
  }
  'fetch' {
    $c = Cred
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
    $files = Invoke-Command -VMName $Name -Credential $c -ScriptBlock {
      Get-ChildItem 'C:\out' -File | ForEach-Object { @{ name = $_.Name; b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($_.FullName)) } }
    }
    foreach ($f in $files) {
      [IO.File]::WriteAllBytes((Join-Path $OutDir $f.name), [Convert]::FromBase64String($f.b64))
      Say ("持ち出し: " + $f.name + " (" + [Convert]::FromBase64String($f.b64).Length + " B)")
    }
  }
  'destroy' {
    Guard
    $vm = Get-VM -Name $Name -ErrorAction SilentlyContinue
    if ($vm) {
      if ($vm.State -ne 'Off') { Stop-VM -Name $Name -TurnOff -Force }
      $disks = (Get-VMHardDiskDrive -VMName $Name).Path
      Remove-VM -Name $Name -Force
      foreach ($d in $disks) { if ($d -like "$Base\*") { Remove-Item $d -Force; Say "消した: $d" } }
      Say "消した: $Name"
    } else { Say "無い: $Name" }
    if (Test-Path (Join-Path $Base $Name)) { Remove-Item (Join-Path $Base $Name) -Recurse -Force }
  }
}
