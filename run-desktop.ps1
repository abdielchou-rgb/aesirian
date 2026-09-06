# Æsirian 桌面版启动（#19）
# 一键：检查依赖 -> 启动后端（8765）-> Electron dev 窗口
# 用法: .\run-desktop.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

Write-Host "`n=== AEsirian Desktop ===" -ForegroundColor Cyan

# 1) Python 依赖检查
Write-Host "[1/3] Checking Python deps..." -ForegroundColor Yellow
python -c "import fastapi, sqlmodel, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing Python deps..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# 2) 后端（若未运行）
Write-Host "[2/3] Backend on :8765..." -ForegroundColor Yellow
$backend = Start-Process python -ArgumentList "-m","uvicorn","bridge.api_server:app","--host","127.0.0.1","--port","8765" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 3
try {
    $health = Invoke-RestMethod "http://127.0.0.1:8765/health" -TimeoutSec 5
    Write-Host ("Backend: " + $health.status + " (pid " + $backend.Id + ")") -ForegroundColor Green
} catch {
    Write-Host "Backend failed to start - check: python -m uvicorn bridge.api_server:app" -ForegroundColor Red
    exit 1
}

# 3) Electron dev
Write-Host "[3/3] Electron window..." -ForegroundColor Yellow
Set-Location electron_ide
if (-not (Test-Path node_modules)) {
    Write-Host "Installing npm deps (first run)..." -ForegroundColor Yellow
    npm install
}
$env:NODE_ENV = "development"
npx electron . --dev

# 退出时清理后端
Write-Host "Stopping backend..." -ForegroundColor Gray
Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
Write-Host "Done." -ForegroundColor Green