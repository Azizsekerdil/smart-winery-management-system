"""Veritabani yedekleme servisi.

Neden uygulama icinde: kurulu (MSI) surumde `scripts\\yedekle.ps1` pakete
girmez ve son kullanicinin PowerShell calistirmasi beklenemez. Yedek alma yolu
olmayan bir uretim sistemi, ilk disk arizasinda tum uzum kabul, fermantasyon ve
laboratuvar gecmisini kaybeder.

Neden `VACUUM INTO`: veritabani WAL kipinde calisir. Dosyayi kopyalamak,
henuz ana dosyaya islenmemis islemleri disarida birakir ve BOZUK bir yedek
uretir. `VACUUM INTO` tutarli, sikistirilmis ve tek dosyalik bir kopya yazar.

GERI YUKLEME BILEREK UYGULANMAMISTIR. Bir kullanicinin hazirladigi veritabani
dosyasini sisteme yuklemek, dogrudan ayricalik yukseltme yoludur: saldirgan
kendisini yonetici yapan bir veritabani yukleyip tum sisteme sahip olur.
Geri yukleme, uygulama kapaliyken dosya degistirilerek yapilir; yordam
SECURITY.md icinde belgelenmistir.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.core.config import BACKUPS_DIR, DATA_DIR, UPLOADS_DIR, settings
from app.core.logging import get_logger

log = get_logger("yedekleme")

# Yedek dosya adlari yalnizca bu kalibi tasir. Indirme/silme uclari gelen adi
# bu kalibla dogrular; boylece `..\..\.env` gibi yol kacislari imkansizdir.
AD_KALIBI = re.compile(r"^(winery|yuklemeler)-\d{8}-\d{6}\.(db|zip)$")

# Cok sayida yedek diski doldurur; en yenilerden bu kadari saklanir.
VARSAYILAN_SAKLANAN = 30


@dataclass(slots=True)
class YedekBilgi:
    ad: str
    tur: str  # veritabani | yuklemeler
    boyut: int
    olusturma: dt.datetime

    def to_dict(self) -> dict:
        return {
            "ad": self.ad,
            "tur": self.tur,
            "boyut": self.boyut,
            "boyut_mb": round(self.boyut / 1_048_576, 2),
            "olusturma": self.olusturma.isoformat(),
        }


def _damga() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def yedek_dizini() -> Path:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUPS_DIR


def yedek_yolu(ad: str) -> Path:
    """Dogrulanmis yedek dosyasi yolu.

    Ad kalibi disindaki her sey reddedilir; ayrica cozumlenen yolun yedek
    dizininin ICINDE oldugu ayrica dogrulanir (derinlemesine savunma).
    """
    if not AD_KALIBI.match(ad):
        raise ValueError(f"Geçersiz yedek adı: {ad}")
    kok = yedek_dizini().resolve()
    yol = (kok / ad).resolve()
    if yol.parent != kok:
        raise ValueError(f"Yedek dizini dışında: {ad}")
    return yol


def _sqlite_yedegi(kaynak: Path, hedef: Path) -> None:
    """`VACUUM INTO` ile tutarli kopya. Senkron; is parcaciginda cagrilir."""
    baglanti = sqlite3.connect(kaynak)
    try:
        # Parametre baglama kullanilir; dosya adi SQL'e gomulmez.
        baglanti.execute("VACUUM INTO ?", (str(hedef),))
    finally:
        baglanti.close()


def _yuklemeleri_arsivle(hedef: Path) -> int:
    """Yuklenen belgeleri zip'ler; dosya sayisini doner."""
    sayi = 0
    with zipfile.ZipFile(hedef, "w", zipfile.ZIP_DEFLATED) as arsiv:
        for dosya in UPLOADS_DIR.rglob("*"):
            if dosya.is_file():
                arsiv.write(dosya, dosya.relative_to(UPLOADS_DIR))
                sayi += 1
    return sayi


def _senkron_yedek_al(yuklemeler: bool) -> list[YedekBilgi]:
    kok = yedek_dizini()
    damga = _damga()
    sonuc: list[YedekBilgi] = []

    if settings.is_sqlite:
        kaynak = DATA_DIR / "winery.db"
        if not kaynak.is_file():
            raise FileNotFoundError(f"Veritabanı bulunamadı: {kaynak}")
        hedef = kok / f"winery-{damga}.db"
        _sqlite_yedegi(kaynak, hedef)
        sonuc.append(
            YedekBilgi(hedef.name, "veritabani", hedef.stat().st_size, dt.datetime.now())
        )
    else:
        # PostgreSQL: pg_dump gerekir ve baglanti bilgisi ortamdan gelir.
        raise RuntimeError(
            "PostgreSQL yedeği uygulama içinden alınamaz; `pg_dump` kullanın "
            "(bkz. scripts\\yedekle.ps1)."
        )

    if yuklemeler and UPLOADS_DIR.is_dir() and any(UPLOADS_DIR.iterdir()):
        hedef = kok / f"yuklemeler-{damga}.zip"
        if _yuklemeleri_arsivle(hedef):
            sonuc.append(
                YedekBilgi(
                    hedef.name, "yuklemeler", hedef.stat().st_size, dt.datetime.now()
                )
            )
        else:
            hedef.unlink(missing_ok=True)

    return sonuc


async def yedek_al(*, yuklemeler: bool = False) -> list[YedekBilgi]:
    """Yedek alir. `VACUUM INTO` senkron oldugu icin is parcaciginda calisir."""
    sonuc = await asyncio.to_thread(_senkron_yedek_al, yuklemeler)
    for y in sonuc:
        log.info("yedek_alindi", dosya=y.ad, boyut=y.boyut, tur=y.tur)
    return sonuc


def yedekleri_listele() -> list[YedekBilgi]:
    """Yeniden eskiye dogru siralanmis yedek listesi."""
    kok = yedek_dizini()
    liste: list[YedekBilgi] = []
    for dosya in kok.iterdir():
        if not dosya.is_file() or not AD_KALIBI.match(dosya.name):
            continue
        bilgi = dosya.stat()
        liste.append(
            YedekBilgi(
                ad=dosya.name,
                tur="veritabani" if dosya.suffix == ".db" else "yuklemeler",
                boyut=bilgi.st_size,
                olusturma=dt.datetime.fromtimestamp(bilgi.st_mtime),
            )
        )
    return sorted(liste, key=lambda y: y.olusturma, reverse=True)


def yedek_sil(ad: str) -> None:
    yedek_yolu(ad).unlink(missing_ok=True)
    log.info("yedek_silindi", dosya=ad)


def eskileri_temizle(saklanan: int = VARSAYILAN_SAKLANAN) -> list[str]:
    """En yeni `saklanan` adet disindaki yedekleri siler; silinenleri doner."""
    if saklanan < 1:
        raise ValueError("Saklanacak yedek sayısı en az 1 olmalıdır.")

    silinen: list[str] = []
    for tur in ("veritabani", "yuklemeler"):
        ayni_tur = [y for y in yedekleri_listele() if y.tur == tur]
        for eski in ayni_tur[saklanan:]:
            yedek_yolu(eski.ad).unlink(missing_ok=True)
            silinen.append(eski.ad)
    if silinen:
        log.info("eski_yedekler_silindi", sayi=len(silinen))
    return silinen


def disk_durumu() -> dict:
    """Yedek diskinin doluluk bilgisi; kullaniciya uyari gostermek icin."""
    kok = yedek_dizini()
    toplam, _kullanilan, bos = shutil.disk_usage(kok)
    yedekler = yedekleri_listele()
    return {
        "dizin": str(kok),
        "yedek_sayisi": len(yedekler),
        "yedek_toplam_bayt": sum(y.boyut for y in yedekler),
        "disk_bos_bayt": bos,
        "disk_toplam_bayt": toplam,
    }
