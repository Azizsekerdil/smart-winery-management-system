"""Veritabani semasini guncel surume getirir.

Neden gerekli: `Base.metadata.create_all` yalnizca EKSIK TABLOLARI olusturur;
mevcut bir tabloya SUTUN EKLEMEZ. Kurulu bir surumden yenisine gecen kullanici
(MSI yukseltmesi) icin bu, uygulamanin sorunsuz acilip ilk ekranda
``no such column`` ile 500 vermesi demektir. Veri kaybolmaz ama uygulama
kullanilamaz hale gelir ve sahadaki "cozum" (veritabanini sil) tum veriyi
goturur.

Bu yuzden sema Alembic ile yonetilir. Uc durum ele alinir:

  1. Bos veritabani            -> `upgrade head` (tum sema kurulur)
  2. Tablolar var, damga yok   -> `stamp head` (create_all ile kurulmus eski
                                  gelistirme veritabanini Alembic'e devret)
  3. Damga var                 -> `upgrade head` (normal yukseltme)

Alembic surumleri pakete girmemisse `create_all`'a duselir; uygulama yine
acilir, yalnizca yukseltme yetenegi olmaz.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import BACKEND_ROOT, settings
from app.core.logging import get_logger

log = get_logger("sema")

# Alembic'in kendi olusturdugu, uygulamaya ait olmayan tablo.
DAMGA_TABLOSU = "alembic_version"


def _alembic_kokleri() -> tuple[Path, Path] | None:
    """(alembic.ini, alembic dizini) — bulunamazsa None."""
    paket_koku = getattr(sys, "_MEIPASS", None)
    adaylar = []
    if paket_koku:
        adaylar.append((Path(paket_koku) / "alembic.ini", Path(paket_koku) / "alembic"))
    adaylar.append((BACKEND_ROOT / "alembic.ini", BACKEND_ROOT / "alembic"))

    for ini, dizin in adaylar:
        if ini.is_file() and (dizin / "env.py").is_file():
            return ini, dizin
    return None


def _yapilandirma() -> Config | None:
    kokler = _alembic_kokleri()
    if kokler is None:
        return None
    ini, dizin = kokler
    cfg = Config(str(ini))
    # `script_location` .ini icinde gorelidir; paketlenmis calistirmada calisma
    # dizini farkli oldugu icin mutlak yola cevrilir.
    cfg.set_main_option("script_location", str(dizin))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def _senkron_guncelle() -> str:
    cfg = _yapilandirma()
    if cfg is None:
        return "alembic_yok"

    motor = create_engine(settings.sync_database_url, future=True)
    try:
        tablolar = set(inspect(motor).get_table_names())
    finally:
        motor.dispose()

    uygulama_tablolari = tablolar - {DAMGA_TABLOSU}

    if DAMGA_TABLOSU in tablolar:
        command.upgrade(cfg, "head")
        return "yukseltildi"

    if uygulama_tablolari:
        # create_all ile kurulmus mevcut veritabani: mevcut hali "head" kabul
        # edilir, boylece 0001 gocu var olan tablolari yeniden olusturmaya
        # calisip patlamaz.
        command.stamp(cfg, "head")
        return "damgalandi"

    command.upgrade(cfg, "head")
    return "olusturuldu"


async def semayi_hazirla() -> str:
    """Semayi guncel surume getirir; yapilan islemin adini doner.

    Alembic'in `env.py` dosyasi kendi icinde `asyncio.run()` cagirir; zaten
    calisan bir olay dongusunden dogrudan cagrilirsa hata verir. Bu yuzden
    ayri bir is parcaciginda calistirilir.
    """
    return await asyncio.to_thread(_senkron_guncelle)
