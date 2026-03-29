# Graph Viewer 启动脚本 - 干净启动（自动清理旧进程）
$ErrorActionPreference = 'SilentlyContinue'

# 检查 7892 端口是否被占用，若有则杀掉
$port = 7892
$procs = Get-NetTCPConnection -LocalPort $port | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique
foreach ($pid in $procs) {
    if ($pid -and $pid -ne 0) {
        Write-Host "Killing process $pid occupying port $port..."
        Stop-Process -Id $pid -Force
    }
}

Start-Sleep -Seconds 1

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverScript = Join-Path $scriptDir 'server.py'

Write-Host "Starting Graph Viewer at http://127.0.0.1:$port ..."
Start-Process uv -ArgumentList "run python `"$serverScript`"" -WindowStyle Hidden
Start-Sleep -Seconds 2

# 验证启动
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$port/api/stats" -UseBasicParsing -TimeoutSec 5
    Write-Host "Server started successfully. Status: $($resp.StatusCode)"
} catch {
    Write-Host "Warning: Server may not be ready yet, check manually."
}
