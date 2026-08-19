<#
.SYNOPSIS
    MSI kurulum paketi üretir ve (sertifika tanımlıysa) imzalar.

.DESCRIPTION
    Sıra önemlidir:

        1. Masaüstü paketi (PyInstaller)   -> dist\Saraphane\
        2. İÇERİK imzalanır (exe + imzasız uzantılar)
        3. MSI derlenir (WiX)              -> dist\Saraphane-<sürüm>-x64.msi
        4. MSI imzalanır

    MSI, içeriğinden SONRA imzalanmalıdır: önce imzalanırsa içerik değişikliği
    MSI imzasını geçersiz kılar.

    İmzalama sertifikası yoksa adım 2 ve 4 uyarı vererek atlanır; paket yine
    üretilir. Sertifika ayarları için: scripts\imzala.ps1

.PARAMETER ArayuzuAtla
    Arayüz zaten derlenmişse yeniden derlemez.

.PARAMETER PaketiAtla
    dist\Saraphane zaten hazırsa PyInstaller'ı atlar (yalnızca MSI üretir).

.PARAMETER ImzaZorunlu
    Sertifika yoksa hata ver. Yayın derlemesinde kullanın.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\msi-paketle.ps1
    powershell -ExecutionPolicy Bypass -File scripts\msi-paketle.ps1 -PaketiAtla
#>
[CmdletBinding()]
param(
    [switch]$ArayuzuAtla,
    [switch]$PaketiAtla,
    [switch]$ImzaZorunlu
)

$ErrorActionPreference = 'Stop'
$KOK = Split-Path -Parent $PSScriptRoot
$VENV_PY = Join-Path $KOK '.venv\Scripts\python.exe'
$DAGITIM = Join-Path $KOK 'dist\Saraphane'
$WIX = Join-Path $env:USERPROFILE '.dotnet\tools\wix.exe'

function Baslik($metin) {
    Write-Host ''
    Write-Host "  $metin" -ForegroundColor Cyan
    Write-Host ('  ' + ('-' * $metin.Length)) -ForegroundColor DarkGray
}

# ------------------------------------------------------------------ sürüm
$surumMetni = Get-Content (Join-Path $KOK 'backend\app\__init__.py') -Raw -Encoding UTF8
if ($surumMetni -notmatch '__version__\s*=\s*"([^"]+)"') {
    throw 'Sürüm numarası backend\app\__init__.py içinde bulunamadı.'
}
$SURUM = $Matches[1]

# ------------------------------------------------------- 1. masaüstü paketi
if (-not $PaketiAtla) {
    Baslik "1 · Masaüstü paketi (sürüm $SURUM)"
    $arg = @()
    if ($ArayuzuAtla) { $arg += '-ArayuzuAtla' }
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'masaustu-paketle.ps1') @arg
    if ($LASTEXITCODE -ne 0) { throw 'Masaüstü paketi üretilemedi.' }
}
else {
    Baslik '1 · Masaüstü paketi (atlandı)'
}

if (-not (Test-Path (Join-Path $DAGITIM 'Saraphane.exe'))) {
    throw "Paket bulunamadı: $DAGITIM\Saraphane.exe"
}

# Çalışma verisi artıkları MSI'a girmemeli (geliştirici veritabanı sızması).
foreach ($artik in @('data', 'logs')) {
    $yol = Join-Path $DAGITIM $artik
    if (Test-Path $yol) {
        Remove-Item $yol -Recurse -Force
        Write-Host "  Çalışma verisi temizlendi: $artik\" -ForegroundColor DarkGray
    }
}

# --------------------------------------------------------- 2. içerik imzası
Baslik '2 · İçerik imzalama'

# Yalnızca çalıştırılabilir içerik imzalanır; imzala.ps1 zaten imzalı
# dosyaları (Microsoft, Python Software Foundation) kendisi atlar.
$imzalanacak = Get-ChildItem $DAGITIM -Recurse -File -Include '*.exe', '*.dll', '*.pyd' |
    Select-Object -ExpandProperty FullName

Write-Host "  Aday dosya: $($imzalanacak.Count)" -ForegroundColor DarkGray

# Yollar dosyayla aktarılır: yüzlerce yol komut satırı uzunluk sınırını aşar.
$liste = Join-Path $env:TEMP "saraphane-imza-listesi.txt"
$imzalanacak | Set-Content -LiteralPath $liste -Encoding UTF8

try {
    $imzaArg = @('-DosyaListesi', $liste)
    if ($ImzaZorunlu) { $imzaArg += '-Zorunlu' }
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'imzala.ps1') @imzaArg
    if ($LASTEXITCODE -ne 0) { throw 'İçerik imzalama başarısız.' }
}
finally {
    Remove-Item $liste -Force -ErrorAction SilentlyContinue
}

# --------------------------------------------------------------- 3. MSI
Baslik '3 · MSI derlemesi'

if (-not (Test-Path $WIX)) {
    throw @"
WiX Toolset bulunamadı: $WIX

Kurmak için:
    dotnet tool install --global wix --version 5.0.2

NOT: Sürüm 5 bilinçli seçilmiştir. WiX v6 ve üzeri, yıllık brüt geliri
10.000 USD ve üzerinde olan ticari kullanıcılara aylık ücret yükümlülüğü
getiren OSMF EULA'sının kabulünü zorunlu tutar. v5, MS-RL lisanslıdır ve
ticari kullanım için ücretsizdir.
"@
}

$msi = Join-Path $KOK "dist\Saraphane-$SURUM-x64.msi"
if (Test-Path $msi) { Remove-Item $msi -Force }

# DİKKAT: `-d Ad=(ifade)` yazımı PowerShell tarafından İKİ ayrı argümana
# bölünür ve WiX yolu bir kaynak dosyası sanır. Değerler önce tek bir dizeye
# toplanmalıdır.
$simge = Join-Path $KOK 'desktop\saraphane.ico'
$kaynak = Join-Path $KOK 'desktop\saraphane.wxs'

$wixArg = @(
    'build',
    '-arch', 'x64',
    '-d', "Surum=$SURUM",
    '-d', "KaynakDizin=$DAGITIM",
    '-d', "SimgeDosyasi=$simge",
    '-out', $msi,
    $kaynak
)

& $WIX @wixArg
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $msi)) { throw 'MSI derlenemedi.' }

# ----------------------------------------------------------- 4. MSI imzası
Baslik '4 · MSI imzalama'

$msiArg = @('-Dosyalar', $msi)
if ($ImzaZorunlu) { $msiArg += '-Zorunlu' }
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'imzala.ps1') @msiArg
if ($LASTEXITCODE -ne 0) { throw 'MSI imzalama başarısız.' }

# ------------------------------------------------------------------ sonuç
Baslik '5 · Sonuç'

$boyut = (Get-Item $msi).Length
$imza = Get-AuthenticodeSignature $msi

Write-Host ''
Write-Host '  ✓ MSI hazır' -ForegroundColor Green
Write-Host "    Dosya  : $msi"
Write-Host ("    Boyut  : {0:N1} MB" -f ($boyut / 1MB))
Write-Host "    Sürüm  : $SURUM"
if ($imza.Status -eq 'Valid') {
    Write-Host "    İmza   : geçerli ($($imza.SignerCertificate.Subject))" -ForegroundColor Green
}
elseif ($imza.SignerCertificate) {
    Write-Host "    İmza   : var, zincir doğrulanmadı ($($imza.Status))" -ForegroundColor Yellow
}
else {
    Write-Host '    İmza   : YOK — SmartScreen uyarısı çıkacaktır' -ForegroundColor Yellow
}
Write-Host ''
Write-Host '  Kurulum (yönetici gerekir):' -ForegroundColor DarkGray
Write-Host "    msiexec /i `"$msi`"" -ForegroundColor DarkGray
Write-Host '  Sessiz kurulum:' -ForegroundColor DarkGray
Write-Host "    msiexec /i `"$msi`" /qn" -ForegroundColor DarkGray
Write-Host ''
Write-Host '  Kullanıcı verisi %LOCALAPPDATA%\Saraphane altında tutulur;' -ForegroundColor DarkGray
Write-Host '  kaldırma ve onarım işlemleri bu veriye dokunmaz.' -ForegroundColor DarkGray
Write-Host ''
