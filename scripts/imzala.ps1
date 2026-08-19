<#
.SYNOPSIS
    Windows kod imzalama: verilen dosyaları SHA-256 + RFC 3161 zaman damgasıyla imzalar.

.DESCRIPTION
    Sertifika ASLA depoda tutulmaz. İki kaynaktan biri kullanılır:

      1. Sertifika deposu parmak izi (ÖNERİLEN — hiçbir yerde parola yoktur)
         $env:SARAPHANE_IMZA_PARMAK_IZI = "A1B2C3..."

      2. PFX dosyası + parola (parola yalnızca ortam değişkeninde)
         $env:SARAPHANE_IMZA_PFX    = "D:\gizli\saraphane.pfx"
         $env:SARAPHANE_IMZA_PAROLA = "..."

    Hiçbiri tanımlı değilse imzalama ATLANIR ve uyarı verilir; derleme
    başarısız olmaz. Böylece sertifikası olmayan bir geliştirici de paket
    üretebilir.

    Zaman damgası neden zorunlu: zaman damgası olmayan bir imza, sertifikanın
    geçerlilik süresi dolduğunda GEÇERSİZ olur. Zaman damgalı imza, sertifika
    süresi dolsa bile geçerli kalır.

.PARAMETER Dosyalar
    İmzalanacak dosya yolları.

.PARAMETER Aciklama
    İmzada görünecek uygulama açıklaması.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\imzala.ps1 -Dosyalar dist\Saraphane\Saraphane.exe
#>
[CmdletBinding()]
param(
    # İmzalanacak dosyalar. Çok sayıda dosya için -DosyaListesi kullanın:
    # `powershell -File` dizi parametrelerini bağlayamaz ve komut satırı
    # uzunluk sınırı (~32 KB) yüzlerce yol için yetersiz kalır.
    [string[]]$Dosyalar = @(),

    # Her satırında bir dosya yolu bulunan metin dosyası (UTF-8).
    [string]$DosyaListesi,

    [string]$Aciklama = 'Akıllı Şaraphane Yönetim Sistemi',

    [string]$AciklamaUrl = 'https://github.com/Azizsekerdil/smart-winery-management-system',

    # İmzalanacak sertifika yoksa hata ver (CI/yayın derlemesi için).
    [switch]$Zorunlu,

    # Zaten imzalı dosyaları da yeniden imzala. VARSAYILAN OLARAK KAPALI:
    # üreticinin (Microsoft, Python Software Foundation) imzasını silmemek için.
    [switch]$YenidenImzala
)

$ErrorActionPreference = 'Stop'

# RFC 3161 zaman damgası sunucuları — gerçek TimeStampReq ile ölçülmüş yanıt
# sürelerine göre sıralı. İlki yanıt vermezse sıradaki denenir.
#
# Zaman damgası neden vazgeçilmez: paketin içindeki `python314.dll` bunun canlı
# kanıtıdır. İmzalayan sertifikası 10 ay, ara CA'sı 4 ay önce süresi dolmuş
# olmasına rağmen imza hâlâ geçerli — çünkü sertifika geçerliyken zaman damgası
# alınmış. Damgasız bir imza, sertifikanın son kullanma tarihinde sahadaki TÜM
# kurulumlarda aynı anda bozulur.
$ZAMAN_DAMGASI_SUNUCULARI = @(
    'http://timestamp.sectigo.com',
    'http://timestamp.digicert.com',
    'http://time.certum.pl',
    'http://timestamp.globalsign.com/tsa/r6advanced1'
)

function Bul-SignTool {
    $komut = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($komut) { return $komut.Source }

    $kokler = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin",
        "$env:ProgramFiles\Windows Kits\10\bin"
    )
    foreach ($kok in $kokler) {
        if (-not (Test-Path $kok)) { continue }
        $adaylar = Get-ChildItem $kok -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending
        foreach ($surum in $adaylar) {
            foreach ($mimari in @('x64', 'x86')) {
                $yol = Join-Path $surum.FullName "$mimari\signtool.exe"
                if (Test-Path $yol) { return $yol }
            }
        }
    }
    return $null
}

# ------------------------------------------------------------- sertifika kaynağı
$parmakIzi = $env:SARAPHANE_IMZA_PARMAK_IZI
$pfxYolu = $env:SARAPHANE_IMZA_PFX
$pfxParola = $env:SARAPHANE_IMZA_PAROLA

$kaynakVar = $parmakIzi -or ($pfxYolu -and (Test-Path -LiteralPath $pfxYolu))

if (-not $kaynakVar) {
    $mesaj = @'
İmzalama sertifikası tanımlı değil — paket İMZASIZ üretildi.

Kullanıcı, uygulamayı ilk çalıştırdığında Windows SmartScreen uyarısı görecektir.
Yayına çıkmadan önce bir kod imzalama sertifikası edinin ve şunlardan birini ayarlayın:

  $env:SARAPHANE_IMZA_PARMAK_IZI = "<sertifika parmak izi>"      (önerilen)
  $env:SARAPHANE_IMZA_PFX        = "<pfx dosya yolu>"
  $env:SARAPHANE_IMZA_PAROLA     = "<pfx parolası>"

Ayrıntı: SECURITY.md > Kod imzalama
'@
    if ($Zorunlu) { throw $mesaj }
    Write-Host ''
    Write-Host '  ! ' -ForegroundColor Yellow -NoNewline
    Write-Host $mesaj -ForegroundColor Yellow
    Write-Host ''
    exit 0
}

$signtool = Bul-SignTool
if (-not $signtool) {
    $m = 'signtool.exe bulunamadı. Windows SDK kurulu olmalıdır.'
    if ($Zorunlu) { throw $m }
    Write-Warning $m
    exit 0
}

Write-Host "  signtool: $signtool" -ForegroundColor DarkGray
if ($parmakIzi) {
    Write-Host '  sertifika: Windows sertifika deposu (parmak izi)' -ForegroundColor DarkGray
}
else {
    Write-Host '  sertifika: PFX dosyası' -ForegroundColor DarkGray
}

# --------------------------------------------------------------------- imzalama
$hedefler = @($Dosyalar)
if ($DosyaListesi) {
    if (-not (Test-Path -LiteralPath $DosyaListesi)) {
        throw "Dosya listesi bulunamadı: $DosyaListesi"
    }
    $hedefler += Get-Content -LiteralPath $DosyaListesi -Encoding UTF8 |
        Where-Object { $_.Trim() }
}
if ($hedefler.Count -eq 0) { throw 'İmzalanacak dosya belirtilmedi.' }

$bulunan = @()
foreach ($d in $hedefler) {
    if (Test-Path -LiteralPath $d) { $bulunan += (Resolve-Path -LiteralPath $d).Path }
    else { Write-Warning "Bulunamadı, atlanıyor: $d" }
}
if ($bulunan.Count -eq 0) { throw 'İmzalanacak dosya bulunamadı.' }

# Zaten imzalı dosyaları ATLA.
#
# Paketin içindeki ikililerin büyük çoğunluğu (Microsoft çalışma zamanı
# kütüphaneleri, CPython ikilileri) üreticileri tarafından imzalanmıştır.
# Bunları yeniden imzalamak üreticinin imzasını SİLER ve yerine bizimkini
# koyar: hem güven zinciri zayıflar hem de dosya bütünlüğü izlenemez hale
# gelir. Yalnızca kendi ürettiğimiz ve imzasız üçüncü taraf uzantıları
# imzalanır.
$mevcut = @()
$atlanan = 0
foreach ($dosya in $bulunan) {
    if ($YenidenImzala) { $mevcut += $dosya; continue }
    $durum = (Get-AuthenticodeSignature -LiteralPath $dosya).Status
    if ($durum -eq 'NotSigned') { $mevcut += $dosya }
    else { $atlanan++ }
}

if ($atlanan -gt 0) {
    Write-Host "  $atlanan dosya zaten imzalı (üretici imzası korunuyor)." -ForegroundColor DarkGray
}
if ($mevcut.Count -eq 0) {
    Write-Host '  İmzalanacak yeni dosya yok.' -ForegroundColor Green
    exit 0
}

$imzalandi = 0
foreach ($dosya in $mevcut) {
    $basarili = $false

    foreach ($tsa in $ZAMAN_DAMGASI_SUNUCULARI) {
        $arg = @('sign', '/fd', 'sha256', '/td', 'sha256', '/tr', $tsa,
            '/d', $Aciklama, '/du', $AciklamaUrl)
        if ($parmakIzi) { $arg += @('/sha1', $parmakIzi) }
        else { $arg += @('/f', $pfxYolu); if ($pfxParola) { $arg += @('/p', $pfxParola) } }
        $arg += $dosya

        # Çıktı bastırılır: parola içeren komut satırı ekrana/günlüğe yazılmamalı.
        # `ErrorActionPreference='Stop'` altında yerel bir komutun stderr'e
        # yazması ölümcül hataya dönüşür; çıkış kodunu kendimiz kontrol
        # edeceğimiz için bu davranış geçici olarak kapatılır.
        $eski = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $cikti = & $signtool @arg 2>&1
        $ErrorActionPreference = $eski
        if ($LASTEXITCODE -eq 0) {
            $basarili = $true
            break
        }
        Write-Host "    zaman damgası sunucusu yanıt vermedi, sıradaki deneniyor…" -ForegroundColor DarkGray
    }

    if (-not $basarili) {
        # Hata metnini gösterirken parolayı sızdırma
        $temiz = ($cikti | Out-String)
        if ($pfxParola) { $temiz = $temiz.Replace($pfxParola, '***') }
        throw "İmzalama başarısız: $(Split-Path $dosya -Leaf)`n$temiz"
    }

    $imzalandi++
    Write-Host "  ✓ imzalandı: $(Split-Path $dosya -Leaf)" -ForegroundColor Green
}

# -------------------------------------------------------------------- doğrulama
Write-Host ''
Write-Host '  İmzalar doğrulanıyor…' -ForegroundColor DarkGray
foreach ($dosya in $mevcut) {
    # /pa : varsayılan kimlik doğrulama ilkesi, /v : ayrıntılı
    $eski = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $dogrula = & $signtool verify /pa /v $dosya 2>&1
    $dogrulamaKodu = $LASTEXITCODE
    $ErrorActionPreference = $eski
    $ad = Split-Path $dosya -Leaf
    if ($dogrulamaKodu -eq 0) {
        Write-Host "  ✓ geçerli: $ad" -ForegroundColor Green
    }
    else {
        # Kendinden imzalı sertifikada zincir güvenilmez olduğu için doğrulama
        # başarısız olur; imzanın kendisi yine de yapıdadır. Bu beklenen bir
        # durumdur ve yalnızca TEST sertifikaları için geçerlidir.
        $metin = ($dogrula | Out-String)
        if ($metin -match 'A certificate chain|zincir') {
            Write-Host "  ! zincir güvenilmiyor (test sertifikası?): $ad" -ForegroundColor Yellow
        }
        else {
            Write-Warning "Doğrulama başarısız: $ad`n$metin"
        }
    }
}

Write-Host ''
Write-Host "  $imzalandi dosya imzalandı." -ForegroundColor Green
