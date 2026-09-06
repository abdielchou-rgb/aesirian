# Aesirian M3-1: one-click start for Four-Cards review page (Windows PowerShell)
# Starts mcp_server_fast.py --transport http (8765) then opens pwa/four_cards.html.
# Port check: if 8765 is already used by a python process from this repo, reuse it.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$port = 8765
$server = Join-Path $root "mcp_server_fast.py"
$page = Join-Path $root "pwa\four_cards.html"
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

# 1) port occupancy check
$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $reuse = $false
    foreach ($l in $listener) {
        $proc = Get-Process -Id $l.OwningProcess -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -match "python") { $reuse = $true }
    }
    if ($reuse) {
        Write-Host "[run_fourcards] Port ${port} already serving this repo; reusing it."
    } else {
        Write-Host "[run_fourcards] Port ${port} is occupied by another process. Free it first and retry." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[run_fourcards] Starting MCP HTTP server @ http://127.0.0.1:${port}/mcp ..."
    $job = Start-Process -FilePath $python -ArgumentList @($server, "--transport", "http", "--port", "$port") -WorkingDirectory $root -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 4
    try {
        $payload = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"boot","version":"1"}}}'
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:${port}/mcp" -Method Post -Headers @{ "Accept" = "application/json, text/event-stream" } -ContentType "application/json" -Body $payload -UseBasicParsing -TimeoutSec 6
        Write-Host "[run_fourcards] Server ready (PID $($job.Id))."
    } catch {
        Write-Host "[run_fourcards] Server failed to start: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

# 2) open the page
if (Test-Path $page) {
    Write-Host "[run_fourcards] Opening $page"
    Start-Process $page
} else {
    Write-Host "[run_fourcards] Page not found: $page" -ForegroundColor Red
}
Write-Host "[run_fourcards] Done. On the page connect to http://127.0.0.1:${port}/mcp and click 'Load Demo: Luoyang Starport'."
