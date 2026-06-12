# 注册 Windows 计划任务：每 3 分钟检查并同步（无需常驻进程）
# 需以管理员运行：右键 PowerShell -> 以管理员身份运行

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = (Get-Command python).Source
}

$Script = Join-Path $PSScriptRoot "git_auto_sync.py"
$TaskName = "WechatToObs-GitAutoSync"

$action = New-ScheduledTaskAction -Execute $Python -Argument "-u `"$Script`" --once" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 3) -RepetitionDuration ([TimeSpan]::MaxValue)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "已注册计划任务: $TaskName"
Write-Host "频率: 每 3 分钟检查一次，有改动才提交推送"
Write-Host "删除: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
