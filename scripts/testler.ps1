<#
.SYNOPSIS
    Tüm kalite kapılarını çalıştırır: ruff, mypy, pytest ve frontend tip denetimi.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\testler.ps1
    powershell -ExecutionPolicy Bypass -File scripts\testler.ps1 -Hizli
    powershell -ExecutionPolicy Bypass -File scripts\testler.ps1 -CanliAI
#>

[CmdletBinding()]
param(
    [switch]$Hizli,        # yalnızca pytest
    [switch]$CanliAI,      # gerçek AI sağlayıcılarına küçük istek atan testleri de çalıştır
    [switch]$Kapsam        # kapsam (coverage) raporu üret
)

$ErrorActionPreference = 'Continue'
$KOK = Split-Path -Parent $PSScriptRoot
$VENV_PY = Join-Path $KOK '.venv\Scripts\python.exe'
$sonuc = @{}

function Yaz($m, $r = 'White') { Write-Host $m -ForegroundColor $r }
function Baslik($m) {
    Write-Host ''
    Yaz ('─' * 70) DarkGray
    Yaz "  $m" Cyan
    Yaz ('─' * 70) DarkGray
}

if (-not (Test-Path $VENV_PY)) {
    Yaz 'HATA: Sanal ortam yok. Önce scripts\kurulum.ps1 çalıştırın.' Red
    exit 1
}

Set-Location $KOK

if (-not $Hizli) {
    Baslik '1 · Ruff (kod kalitesi + güvenlik taraması)'
    & $VENV_PY -m ruff check backend tests
    $sonuc['Ruff'] = $LASTEXITCODE -eq 0

    Baslik '2 · mypy (statik tip denetimi)'
    Push-Location (Join-Path $KOK 'backend')
    $env:PYTHONPATH = Join-Path $KOK 'backend'
    & $VENV_PY -m mypy app --config-file pyproject.toml
    $sonuc['mypy'] = $LASTEXITCODE -eq 0
    Pop-Location
}

Baslik '3 · pytest (backend testleri)'
$pytestArgs = @('-m', 'pytest', 'tests', '-q')
if ($CanliAI) { $pytestArgs += @('-m', 'canli_ai or not canli_ai') }
if ($Kapsam) { $pytestArgs += @('--cov=backend/app', '--cov-report=term-missing:skip-covered') }
& $VENV_PY @pytestArgs
$sonuc['pytest'] = $LASTEXITCODE -eq 0

if (-not $Hizli -and (Test-Path (Join-Path $KOK 'frontend\node_modules'))) {
    Baslik '4 · TypeScript (frontend tip denetimi)'
    Push-Location (Join-Path $KOK 'frontend')
    # `-b` tüm projeleri denetler: uygulama, Vite yapılandırması ve E2E testleri.
    # Yalnızca `tsconfig.app.json` kullanılırsa E2E dosyaları sessizce atlanır.
    & npx tsc -b
    $sonuc['TypeScript'] = $LASTEXITCODE -eq 0
    Pop-Location
}

Baslik 'ÖZET'
$tumu = $true
foreach ($k in $sonuc.Keys) {
    if ($sonuc[$k]) { Yaz ("  ✓ {0,-12} geçti" -f $k) Green }
    else { Yaz ("  ✗ {0,-12} BAŞARISIZ" -f $k) Red; $tumu = $false }
}
Write-Host ''
if ($tumu) {
    Yaz '  Tüm kalite kapıları geçti.' Green
    exit 0
} else {
    Yaz '  Bazı kontroller başarısız. Yukarıdaki çıktıyı inceleyin.' Red
    exit 1
}
