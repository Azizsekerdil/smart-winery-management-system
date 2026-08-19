<#
.SYNOPSIS
    Backend ve frontend'i birlikte başlatır.

.DESCRIPTION
    Her servis kendi PowerShell penceresinde açılır; böylece günlükleri ayrı
    izleyebilir, birini kapatmadan diğerini yeniden başlatabilirsiniz.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\baslat.ps1
    powershell -ExecutionPolicy Bypass -File scripts\baslat.ps1 -SadeceBackend
#>

[CmdletBinding()]
param(
    [switch]$SadeceBackend,
    [switch]$SadeceFrontend,
    [switch]$TarayiciAcma,
    [int]$Port = 0
)

$ErrorActionPreference = 'Stop'
$KOK = Split-Path -Parent $PSScriptRoot
$VENV_PY = Join-Path $KOK '.venv\Scripts\python.exe'

function Yaz($m, $r = 'White') { Write-Host $m -ForegroundColor $r }

function PortBosMu([int]$p) {
    $null -eq (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Test-Path $VENV_PY)) {
    Yaz 'HATA: Sanal ortam bulunamadı.' Red
    Yaz 'Önce kurulumu çalıştırın:  powershell -File scripts\kurulum.ps1' Yellow
    exit 1
}

# ------------------------------------------------------------ port belirleme
if ($Port -eq 0) {
    $Port = 8010
    $envYol = Join-Path $KOK '.env'
    if (Test-Path $envYol) {
        $satir = Select-String -Path $envYol -Pattern '^PORT=(\d+)' | Select-Object -First 1
        if ($satir) { $Port = [int]$satir.Matches[0].Groups[1].Value }
    }
}
if (-not (PortBosMu $Port)) {
    $yeni = $Port
    while ($yeni -lt $Port + 20 -and -not (PortBosMu $yeni)) { $yeni++ }
    if ($yeni -ne $Port) {
        Yaz "  ! Port $Port kullanımda; $yeni portuna geçiliyor." Yellow
        $Port = $yeni
    }
}

Yaz ''
Yaz '  Akıllı Şaraphane Yönetim Sistemi başlatılıyor…' Cyan
Yaz ''

if (-not $SadeceFrontend) {
    Yaz "  → Backend  : http://127.0.0.1:$Port  (dokümantasyon: /docs)" DarkGray
    $backendKomut = @"
`$host.UI.RawUI.WindowTitle = 'Saraphane — Backend (API) :$Port'
Set-Location '$KOK\backend'
`$env:PYTHONPATH = '$KOK\backend'
Write-Host 'Backend baslatiliyor... Kapatmak icin Ctrl+C' -ForegroundColor Cyan
& '$VENV_PY' -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
"@
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendKomut
}

if (-not $SadeceBackend) {
    Start-Sleep -Milliseconds 1500
    Yaz '  → Frontend : http://localhost:5173' DarkGray
    $frontendKomut = @"
`$host.UI.RawUI.WindowTitle = 'Saraphane — Frontend (Arayuz)'
Set-Location '$KOK\frontend'
`$env:VITE_API_PROXY = 'http://127.0.0.1:$Port'
Write-Host 'Arayuz baslatiliyor... Kapatmak icin Ctrl+C' -ForegroundColor Cyan
& npm run dev
"@
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendKomut
}

if (-not $TarayiciAcma -and -not $SadeceBackend) {
    Yaz ''
    Yaz '  Tarayıcı açılıyor (5 sn)…' DarkGray
    Start-Sleep -Seconds 5
    Start-Process 'http://localhost:5173'
}

Yaz ''
Yaz '  Servisler ayrı pencerelerde çalışıyor.' Green
Yaz '  Durdurmak için ilgili pencerede Ctrl+C yapın veya pencereyi kapatın.' DarkGray
Yaz ''
