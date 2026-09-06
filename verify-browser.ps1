# Æsirian 浏览器验证总装脚本 — L1 -> L2 -> L3 强制流程
# 用法: .\verify-browser.ps1
# 任何一层失败即中止，视为"未完成"（roadmap §9.2）

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

Write-Host "`n=== AEsirian Verification Pipeline ===" -ForegroundColor Cyan
Write-Host "L1 (JSDOM static) -> L2 (TestClient API) -> L3 (Playwright browser)`n"

# ── L1: 静态检查 ──
Write-Host "--- [L1] Static Check (Node.js + JSDOM) ---" -ForegroundColor Yellow
node tests/l1_static_check.js
if ($LASTEXITCODE -ne 0) { Write-Host "L1 FAILED - aborting" -ForegroundColor Red; exit 1 }
Write-Host "[L1] PASSED`n" -ForegroundColor Green

# ── L2: API 集成测试 ──
Write-Host "--- [L2] API Integration (pytest TestClient) ---" -ForegroundColor Yellow
python -X utf8 -m pytest tests/test_api_flows.py tests/test_blueprint_v1.py tests/test_product_v1.py tests/test_e2e.py tests/test_style_baseline.py -q
if ($LASTEXITCODE -ne 0) { Write-Host "L2 FAILED - aborting" -ForegroundColor Red; exit 1 }
Write-Host "[L2] PASSED`n" -ForegroundColor Green

# ── L3: 真实浏览器验证（Windows） ──
Write-Host "--- [L3] Browser Verification (Playwright + screenshots) ---" -ForegroundColor Yellow
python tests/l3_browser_test.py
if ($LASTEXITCODE -ne 0) { Write-Host "L3 FAILED - aborting" -ForegroundColor Red; exit 1 }
Write-Host "[L3] PASSED`n" -ForegroundColor Green

Write-Host "=== ALL LAYERS PASSED - feature verified ===" -ForegroundColor Green
Write-Host "Screenshots: output\screenshots\"
exit 0