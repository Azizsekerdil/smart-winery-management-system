<#
.SYNOPSIS
    Akıllı Şaraphane Yönetim Sistemi — Windows geliştirme ortamı kurulumu.

.DESCRIPTION
    - Python ve Node.js sürümlerini denetler
    - .venv sanal ortamını oluşturur (sistem geneli Python'a DOKUNMAZ)
    - Backend ve frontend bağımlılıklarını kurar
    - .env dosyasını şablondan üretir ve güvenli rastgele anahtarlar yazar
    - Veritabanını hazırlar, istenirse demo verisini yükler

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\kurulum.ps1
    powershell -ExecutionPolicy Bypass -File scripts\kurulum.ps1 -DemoVerisiz
#>

[CmdletBinding()]
param(
    [switch]$DemoVerisiz,
    [switch]$FrontendAtla
)

$ErrorActionPreference = 'Stop'
$KOK = Split-Path -Parent $PSScriptRoot
$VENV_PY = Join-Path $KOK '.venv\Scripts\python.exe'

function Yaz($mesaj, $renk = 'White') { Write-Host $mesaj -ForegroundColor $renk }
function Baslik($mesaj) {
    Write-Host ''
    Yaz ('=' * 70) DarkGray
    Yaz "  $mesaj" Cyan
    Yaz ('=' * 70) DarkGray
}

Baslik 'Akıllı Şaraphane Yönetim Sistemi — Kurulum'
Yaz "Proje dizini: $KOK" DarkGray

# ------------------------------------------------------------ 1. Ön koşullar
Baslik '1/6 · Gerekli araçlar denetleniyor'

$pythonKomut = $null
foreach ($aday in @('3.14', '3.13', '3.12')) {
    try {
        $null = & py "-V:$aday" --version 2>$null
        if ($LASTEXITCODE -eq 0) { $pythonKomut = @('py', "-V:$aday"); break }
    } catch { }
}
if (-not $pythonKomut) {
    try {
        $surum = (& python --version) -replace 'Python ', ''
        $parcalar = $surum.Split('.')
        if ([int]$parcalar[0] -ge 3 -and [int]$parcalar[1] -ge 12) { $pythonKomut = @('python') }
    } catch { }
}
if (-not $pythonKomut) {
    Yaz 'HATA: Python 3.12 veya üzeri bulunamadı.' Red
    Yaz 'https://www.python.org/downloads/ adresinden kurup tekrar deneyin.' Yellow
    exit 1
}
Yaz "  ✓ Python bulundu: $($pythonKomut -join ' ')" Green

try {
    $nodeSurum = & node --version
    Yaz "  ✓ Node.js bulundu: $nodeSurum" Green
} catch {
    if (-not $FrontendAtla) {
        Yaz 'HATA: Node.js bulunamadı (frontend için gerekli).' Red
        Yaz 'https://nodejs.org adresinden kurun veya -FrontendAtla ile devam edin.' Yellow
        exit 1
    }
}

try { $null = & git --version; Yaz '  ✓ Git bulundu' Green }
catch { Yaz '  ! Git bulunamadı — sürüm kontrolü ve AI terminali kontrol noktaları kullanılamaz.' Yellow }

# --------------------------------------------------------- 2. Sanal ortam
Baslik '2/6 · Python sanal ortamı'
if (Test-Path $VENV_PY) {
    Yaz '  ✓ .venv zaten var, yeniden kullanılıyor' Green
} else {
    Yaz '  → .venv oluşturuluyor…' DarkGray
    & $pythonKomut[0] $pythonKomut[1..($pythonKomut.Length - 1)] -m venv (Join-Path $KOK '.venv')
    Yaz '  ✓ Sanal ortam oluşturuldu' Green
}
& $VENV_PY -m pip install --upgrade pip --quiet
Yaz '  ✓ pip güncel' Green

# ------------------------------------------------------ 3. Backend bağımlılık
Baslik '3/6 · Backend bağımlılıkları'
& $VENV_PY -m pip install -r (Join-Path $KOK 'backend\requirements-dev.txt') --quiet
if ($LASTEXITCODE -ne 0) { Yaz 'HATA: Bağımlılıklar kurulamadı.' Red; exit 1 }
Yaz '  ✓ Backend bağımlılıkları kuruldu' Green

# ---------------------------------------------------------------- 4. .env
Baslik '4/6 · Ortam yapılandırması (.env)'
$envYol = Join-Path $KOK '.env'
if (Test-Path $envYol) {
    Yaz '  ✓ .env zaten var — DEĞİŞTİRİLMEDİ' Green
} else {
    Copy-Item (Join-Path $KOK '.env.example') $envYol
    # Güvenli rastgele anahtarlar üret (ekrana YAZILMAZ)
    $gizli = & $VENV_PY -c "import secrets; print(secrets.token_urlsafe(48))"
    $sifre = & $VENV_PY -c "import secrets; print(secrets.token_urlsafe(48))"
    $icerik = Get-Content $envYol -Raw -Encoding UTF8
    $icerik = $icerik -replace '(?m)^SECRET_KEY=$', "SECRET_KEY=$gizli"
    $icerik = $icerik -replace '(?m)^SECRETS_ENCRYPTION_KEY=$', "SECRETS_ENCRYPTION_KEY=$sifre"
    $icerik = $icerik -replace '(?m)^AGENT_WORKSPACE=.*$', "AGENT_WORKSPACE=$KOK"
    [System.IO.File]::WriteAllText($envYol, $icerik, (New-Object System.Text.UTF8Encoding $false))
    Yaz '  ✓ .env oluşturuldu ve güvenli anahtarlar üretildi (ekranda gösterilmez)' Green
    Yaz '  ℹ API anahtarlarını uygulama içi Ayarlar ekranından girebilirsiniz.' DarkGray
}

# ------------------------------------------------------------ 5. Veritabanı
Baslik '5/6 · Veritabanı'
Push-Location (Join-Path $KOK 'backend')
$env:PYTHONPATH = Join-Path $KOK 'backend'
if ($DemoVerisiz) {
    & $VENV_PY -m app.db.init_db
} else {
    & $VENV_PY -m app.db.init_db --seed
}
Pop-Location
Yaz '  ✓ Veritabanı hazır' Green

# ------------------------------------------------------------- 6. Frontend
if (-not $FrontendAtla) {
    Baslik '6/6 · Frontend bağımlılıkları'
    Push-Location (Join-Path $KOK 'frontend')
    & npm install --no-fund --no-audit
    Pop-Location
    if ($LASTEXITCODE -ne 0) { Yaz 'HATA: npm install başarısız.' Red; exit 1 }
    Yaz '  ✓ Frontend bağımlılıkları kuruldu' Green
} else {
    Baslik '6/6 · Frontend atlandı (-FrontendAtla)'
}

Baslik 'Kurulum tamamlandı'
Yaz ''
Yaz 'Sistemi başlatmak için:' White
Yaz '  .\Baslat.bat                        (tek tık — backend + frontend)' Cyan
Yaz '  powershell -File scripts\baslat.ps1  (aynısı, PowerShell)' DarkGray
Yaz ''
Yaz 'Adresler:' White
Yaz '  Arayüz : http://localhost:5173' Cyan
Yaz '  API    : http://127.0.0.1:8000/docs' Cyan
Yaz ''
if (-not $DemoVerisiz) {
    Yaz 'Demo giriş bilgileri yukarıda listelendi (yalnızca geliştirme içindir).' Yellow
}
