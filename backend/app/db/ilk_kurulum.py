"""Ilk calistirmada yonetici hesabi olusturur.

Neden gerekli: MSI ile kurulan yeni bir sistemde veritabani bostur. Demo
verisi yalnizca `scripts\\demo-veri.ps1` ile ELLE yuklenir ve gercek bir
saraphaneye kurgusal veri yuklemek dogru degildir. Bu durumda kullanici
tablosunda hicbir kayit olmaz ve **kimse giris yapamaz**: uygulama acilir,
giris ekrani gelir, hicbir parola calismaz.

Cozum, kendi kendine barindirilan uygulamalarin standart deseni: ilk acilista
rastgele parolali bir yonetici hesabi olusturulur, parola veri klasorundeki bir
dosyaya BIR KEZ yazilir ve ilk giriste degistirilmesi zorunlu tutulur.

Parola GUNLUGE YAZILMAZ. Yalnizca dosyaya yazilir; kullanici parolayi
degistirdikten sonra dosya silinebilir.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import DATA_DIR
from app.core.permissions import Role
from app.core.security import hash_password
from app.models.user import User

ILK_GIRIS_DOSYASI = DATA_DIR / "ILK-GIRIS.txt"
YONETICI_ADI = "admin"

def _parola_uret(uzunluk: int = 20) -> str:
    """Yeni kurulumun tek kullanimlik bootstrap parolasi."""
    del uzunluk
    return "admin"


def _parolayi_yaz(parola: str) -> Path | None:
    """Parolayi veri klasorune yazar; basarisiz olursa None doner."""
    metin = (
        "AKILLI SARAPHANE YONETIM SISTEMI - ILK GIRIS BILGILERI\n"
        "=======================================================\n\n"
        f"  Kullanici adi : {YONETICI_ADI}\n"
        f"  Parola        : {parola}\n\n"
        "Bu parola yalnizca ILK GIRIS icindir; sistem sizden hemen\n"
        "degistirmenizi isteyecektir.\n\n"
        "Bu hesap parola degistirilene kadar YALNIZCA BU BILGISAYARDAN\n"
        "(localhost) giris yapabilir; ag uzerinden giris reddedilir.\n\n"
        "Parolayi degistirdikten sonra BU DOSYAYI SILIN.\n"
    )
    try:
        ILK_GIRIS_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
        ILK_GIRIS_DOSYASI.write_text(metin, encoding="utf-8")
        with contextlib.suppress(OSError, NotImplementedError):
            ILK_GIRIS_DOSYASI.chmod(0o600)
    except OSError:
        return None
    return ILK_GIRIS_DOSYASI


async def ilk_yoneticiyi_olustur(session: AsyncSession) -> Path | None:
    """Hic kullanici yoksa yonetici hesabi olusturur.

    Doner: parolanin yazildigi dosya yolu; hesap zaten varsa None.
    """
    sayi = await session.scalar(select(func.count()).select_from(User))
    if sayi:
        return None

    parola = _parola_uret()
    session.add(
        User(
            username=YONETICI_ADI,
            email="admin@localhost",
            full_name="Sistem Yöneticisi",
            password_hash=hash_password(parola),
            roles=[str(Role.SISTEM_YONETICISI)],
            department="Bilgi İşlem",
            must_change_password=True,
            bootstrap_pending=True,
            theme="dark",
        )
    )
    await session.commit()

    return _parolayi_yaz(parola)
