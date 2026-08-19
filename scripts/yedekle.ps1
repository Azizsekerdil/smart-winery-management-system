<#
.SYNOPSIS
    Veritabanı ve yüklenen dosyaların yedeğini alır.

.DESCRIPTION
    SQLite için tutarlı yedek `VACUUM INTO` ile alınır (dosya kopyalamak
    WAL kipinde bozuk yedek üretebilir). PostgreSQL için pg_dump kullanılır.
    Yedekler data\backups altına zaman damgalı olarak yazılır.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\yedekle.ps1
    powershell -ExecutionPolicy Bypass -File scripts\yedekle.ps1 -SaklananGun 60
#>

[CmdletBinding()]
param(
    [int]$SaklananGun = 30,
    [switch]$YuklemeleriDahilEt
)

$ErrorActionPreference = 'Stop'
$KOK = Split-Path -Parent $PSScriptRoot
$VENV_PY = Join-Path $KOK '.venv\Scripts\python.exe'
$damga = Get-Date -Format 'yyyyMMdd-HHmmss'

function Yaz($m, $r = 'White') { Write-Host $m -ForegroundColor $r }

# Veri kökü uygulamanın KENDİ yapılandırmasından okunur; depo kökünden
# hesaplanmaz. Kurulu (MSI) sürümde veri %LOCALAPPDATA%\Saraphane altındadır
# ve depo kökü kullanılsaydı bu betik boş bir klasöre bakardı.
$env:PYTHONPATH = Join-Path $KOK 'backend'
$VERI_KOKU = (& $VENV_PY -c "from app.core.config import VERI_KOKU; print(VERI_KOKU)" 2>$null | Select-Object -Last 1)
if ($LASTEXITCODE -ne 0 -or -not $VERI_KOKU) {
    Yaz '  Uyarı: uygulama yapılandırması okunamadı, depo kökü kullanılıyor.' Yellow
    $VERI_KOKU = $KOK
}
$VERI_DIZIN = Join-Path $VERI_KOKU 'data'
$YEDEK_DIZIN = Join-Path $VERI_DIZIN 'backups'

New-Item -ItemType Directory -Force -Path $YEDEK_DIZIN | Out-Null

Yaz ''
Yaz '  Şaraphane veritabanı yedekleme' Cyan
Yaz ''

# .env içindeki DATABASE_URL okunur (değer ekrana YAZILMAZ)
$veritabaniTuru = 'sqlite'
$envYol = Join-Path $KOK '.env'
if (Test-Path $envYol) {
    $satir = Select-String -Path $envYol -Pattern '^DATABASE_URL=(.+)$' | Select-Object -First 1
    if ($satir -and $satir.Matches[0].Groups[1].Value -match 'postgres') { $veritabaniTuru = 'postgresql' }
}

if ($veritabaniTuru -eq 'sqlite') {
    $kaynak = Join-Path $VERI_DIZIN 'winery.db'
    if (-not (Test-Path $kaynak)) {
        Yaz "  Veritabanı bulunamadı: $kaynak" Yellow
        exit 1
    }
    $hedef = Join-Path $YEDEK_DIZIN "winery-$damga.db"
    # VACUUM INTO: WAL kipinde bile tutarlı, sıkıştırılmış yedek üretir
    & $VENV_PY -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute('VACUUM INTO ?', (sys.argv[2],)); c.close()" $kaynak $hedef
    if ($LASTEXITCODE -ne 0) { Yaz '  HATA: Yedek alınamadı.' Red; exit 1 }
    $boyut = [math]::Round((Get-Item $hedef).Length / 1MB, 2)
    Yaz "  ✓ Veritabanı yedeği: $hedef ($boyut MB)" Green
} else {
    $hedef = Join-Path $YEDEK_DIZIN "saraphane-$damga.sql"
    try {
        $null = Get-Command pg_dump -ErrorAction Stop
    } catch {
        Yaz '  HATA: pg_dump bulunamadı. PostgreSQL istemci araçlarını kurun.' Red
        exit 1
    }
    Yaz '  → pg_dump çalıştırılıyor (bağlantı bilgisi .env üzerinden okunur)…' DarkGray
    Yaz '  ! PostgreSQL yedeklemesi için PGPASSWORD ortam değişkenini kullanın;' Yellow
    Yaz '    parolayı komut satırına YAZMAYIN (süreç listesinde görünür).' Yellow
    & pg_dump --format=plain --no-owner --file=$hedef
    if ($LASTEXITCODE -ne 0) { Yaz '  HATA: pg_dump başarısız.' Red; exit 1 }
    Yaz "  ✓ Veritabanı yedeği: $hedef" Green
}

if ($YuklemeleriDahilEt) {
    $yuklemeDizin = Join-Path $VERI_DIZIN 'uploads'
    if (Test-Path $yuklemeDizin) {
        $arsiv = Join-Path $YEDEK_DIZIN "uploads-$damga.zip"
        Compress-Archive -Path "$yuklemeDizin\*" -DestinationPath $arsiv -Force -ErrorAction SilentlyContinue
        if (Test-Path $arsiv) {
            Yaz "  ✓ Yüklenen dosyalar: $arsiv" Green
        } else {
            Yaz '  ! Yüklenen dosya bulunamadı, arşiv oluşturulmadı.' DarkGray
        }
    }
}

# ------------------------------------------------------------- eski yedekler
$sinir = (Get-Date).AddDays(-$SaklananGun)
$eski = Get-ChildItem $YEDEK_DIZIN -File | Where-Object { $_.LastWriteTime -lt $sinir }
if ($eski) {
    Yaz "  → $SaklananGun günden eski $($eski.Count) yedek siliniyor…" DarkGray
    $eski | Remove-Item -Force
}

$toplam = (Get-ChildItem $YEDEK_DIZIN -File | Measure-Object -Property Length -Sum).Sum / 1MB
Yaz ''
Yaz ("  Yedek dizini: {0} ({1:N1} MB)" -f $YEDEK_DIZIN, $toplam) DarkGray
Yaz '  ÖNEMLİ: Yedekleri düzenli olarak farklı bir fiziksel ortama kopyalayın.' Yellow
Yaz ''
