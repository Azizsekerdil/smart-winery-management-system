<#
.SYNOPSIS
    Demo verisini yükler (yalnızca geliştirme/tanıtım içindir).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\demo-veri.ps1
    powershell -ExecutionPolicy Bypass -File scripts\demo-veri.ps1 -Sifirla
#>

[CmdletBinding()]
param(
    [switch]$Sifirla   # TÜM tabloları siler ve demo verisini yeniden yükler
)

$ErrorActionPreference = 'Stop'
$KOK = Split-Path -Parent $PSScriptRoot
$VENV_PY = Join-Path $KOK '.venv\Scripts\python.exe'

function Yaz($m, $r = 'White') { Write-Host $m -ForegroundColor $r }

if (-not (Test-Path $VENV_PY)) {
    Yaz 'HATA: Sanal ortam yok. Önce scripts\kurulum.ps1 çalıştırın.' Red
    exit 1
}

# Üretim ortamında demo verisi yüklenmesini engelle
$envYol = Join-Path $KOK '.env'
if (Test-Path $envYol) {
    $ortam = Select-String -Path $envYol -Pattern '^APP_ENV=(.+)$' | Select-Object -First 1
    if ($ortam -and $ortam.Matches[0].Groups[1].Value.Trim() -eq 'production') {
        Yaz 'ENGELLENDİ: APP_ENV=production. Demo verisi üretim ortamına yüklenemez.' Red
        Yaz 'Gerçekten istiyorsanız .env içindeki APP_ENV değerini geçici olarak değiştirin.' Yellow
        exit 1
    }
}

Push-Location (Join-Path $KOK 'backend')
$env:PYTHONPATH = Join-Path $KOK 'backend'

if ($Sifirla) {
    Yaz ''
    Yaz '  DİKKAT: Tüm tablolar silinip yeniden oluşturulacak.' Red
    Yaz '  Mevcut TÜM veriler kaybolacak.' Red
    $onay = Read-Host '  Devam etmek için EVET yazın'
    if ($onay -ne 'EVET') {
        Yaz '  İşlem iptal edildi.' Yellow
        Pop-Location
        exit 1
    }
    & $VENV_PY -m app.db.init_db --drop --seed --force --yes
} else {
    & $VENV_PY -m app.db.init_db --seed
}

$cikis = $LASTEXITCODE
Pop-Location

if ($cikis -ne 0) { Yaz 'HATA: Demo verisi yüklenemedi.' Red; exit 1 }

Yaz ''
Yaz '  UYARI: Demo kullanıcılar ve parolalar yalnızca geliştirme içindir.' Yellow
Yaz '  Üretime geçmeden önce bu hesapları silin (bkz. SECURITY.md).' Yellow
Yaz ''
