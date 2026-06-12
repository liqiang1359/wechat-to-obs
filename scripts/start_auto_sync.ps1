# 在后台启动 Git 自动同步（监听变动 + 3 分钟兜底）
$ErrorActionPreference = "Stop"

# 项目根目录
$Root = Split-Path -Parent $PSScriptRoot
# Python 解释器（优先虚拟环境）
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}

# 日志与 PID 文件
$LogFile = Join-Path $PSScriptRoot "auto_sync.log"
$PidFile = Join-Path $PSScriptRoot "auto_sync.pid"

# 若已在运行则跳过
if (Test-Path $PidFile) {
  $oldPid = Get-Content $PidFile -ErrorAction SilentlyContinue
  if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
    Write-Host "自动同步已在运行 (PID: $oldPid)，日志: $LogFile"
    exit 0
  }
}

# 启动监听：变动后约 5 秒推送，最长 180 秒兜底
$args = @(
  (Join-Path $PSScriptRoot "git_auto_sync.py"),
  "--mode", "watch",
  "--poll", "10",
  "--debounce", "5",
  "--interval", "180"
)

$proc = Start-Process -FilePath $Python `
  -ArgumentList $args `
  -WorkingDirectory $Root `
  -WindowStyle Hidden `
  -PassThru

$proc.Id | Out-File -FilePath $PidFile -Encoding utf8
Write-Host "已启动自动同步 (PID: $($proc.Id))"
Write-Host "模式: 有变动约 5 秒后推送，最长 3 分钟兜底"
Write-Host "日志: $LogFile"
Write-Host "停止: .\scripts\stop_auto_sync.ps1"
