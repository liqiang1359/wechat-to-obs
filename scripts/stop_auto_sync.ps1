# 停止后台 Git 自动同步进程
$PidFile = Join-Path $PSScriptRoot "auto_sync.pid"

if (-not (Test-Path $PidFile)) {
  Write-Host "未找到 PID 文件，自动同步可能未在运行"
  exit 0
}

$pid = [int](Get-Content $PidFile -ErrorAction SilentlyContinue)
if ($pid -and (Get-Process -Id $pid -ErrorAction SilentlyContinue)) {
  Stop-Process -Id $pid -Force
  Write-Host "已停止自动同步 (PID: $pid)"
} else {
  Write-Host "进程不存在，可能已退出"
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
