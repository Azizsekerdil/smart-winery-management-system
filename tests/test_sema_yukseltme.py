"""Sema yukseltmesi: MSI ile surum gecen kullanicinin veritabani ne olur?

`Base.metadata.create_all` yalnizca EKSIK TABLOLARI olusturur; mevcut bir
tabloya SUTUN EKLEMEZ. 0.1.0 kurup alti ay veri giren bir kullanici 0.2.0'a
gectiginde uygulama sorunsuz acilir, sonra ilk ekranda ``no such column`` ile
500 verir. Veri kaybolmaz ama uygulama kullanilamaz hale gelir.

Bu testler semanin Alembic ile yonetildigini ve uc senaryonun (bos veritabani,
damgasiz mevcut veritabani, damgali veritabani) dogru cozuldugunu dogrular.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from app.db import sema


def _tablolar(db: Path) -> set[str]:
    motor = create_engine(f"sqlite:///{db.as_posix()}", future=True)
    try:
        return set(inspect(motor).get_table_names())
    finally:
        motor.dispose()


@pytest.fixture
def gecici_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """config.settings'i gecici bir SQLite dosyasina yonlendirir."""
    db = tmp_path / "deneme.db"
    monkeypatch.setattr(
        type(sema.settings),
        "database_url",
        property(lambda _self: f"sqlite+aiosqlite:///{db.as_posix()}"),
    )
    monkeypatch.setattr(
        type(sema.settings),
        "sync_database_url",
        property(lambda _self: f"sqlite:///{db.as_posix()}"),
    )
    return db


# ------------------------------------------------------------- varlik denetimi
def test_alembic_dosyalari_bulunuyor() -> None:
    """Goc dosyalari yoksa yukseltme yetenegi hic yoktur."""
    kokler = sema._alembic_kokleri()
    assert kokler is not None, "alembic.ini veya alembic/env.py bulunamadi"
    ini, dizin = kokler
    assert ini.is_file()
    assert (dizin / "env.py").is_file()
    surumler = list((dizin / "versions").glob("*.py"))
    assert surumler, "Hicbir goc dosyasi yok"


def test_yapilandirma_mutlak_yol_kullanir() -> None:
    """Paketlenmis calistirmada calisma dizini farklidir; goreli yol kirilir."""
    cfg = sema._yapilandirma()
    assert cfg is not None
    yol = Path(cfg.get_main_option("script_location"))
    assert yol.is_absolute()
    assert (yol / "env.py").is_file()


# ------------------------------------------------------------------ senaryolar
def test_bos_veritabani_bastan_kurulur(gecici_db: Path) -> None:
    assert not gecici_db.exists()
    sonuc = sema._senkron_guncelle()

    assert sonuc == "olusturuldu"
    tablolar = _tablolar(gecici_db)
    assert sema.DAMGA_TABLOSU in tablolar, "Alembic damgasi yazilmadi"
    assert "users" in tablolar
    assert len(tablolar) > 40, f"Beklenenden az tablo kuruldu: {len(tablolar)}"


def test_damgasiz_mevcut_veritabani_devralinir(gecici_db: Path) -> None:
    """create_all ile kurulmus eski veritabani goc sistemine devredilmeli.

    Damgalanmazsa 0001 gocu var olan tablolari yeniden olusturmaya calisir
    ve `table already exists` ile patlar.
    """
    baglanti = sqlite3.connect(gecici_db)
    baglanti.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
    baglanti.execute("INSERT INTO users (username) VALUES ('mevcut_kullanici')")
    baglanti.commit()
    baglanti.close()

    sonuc = sema._senkron_guncelle()
    assert sonuc == "damgalandi"
    assert sema.DAMGA_TABLOSU in _tablolar(gecici_db)

    # KRITIK: mevcut veri korunmali
    baglanti = sqlite3.connect(gecici_db)
    try:
        satirlar = baglanti.execute("SELECT username FROM users").fetchall()
    finally:
        baglanti.close()
    assert satirlar == [("mevcut_kullanici",)], "Mevcut kullanici verisi kayboldu"


def test_damgali_veritabani_yukseltilir(gecici_db: Path) -> None:
    """Ikinci calistirma: sema zaten guncel, islem hatasiz tekrarlanabilmeli."""
    assert sema._senkron_guncelle() == "olusturuldu"
    assert sema._senkron_guncelle() == "yukseltildi"
    assert sema._senkron_guncelle() == "yukseltildi"


def test_yukseltme_veriyi_korur(gecici_db: Path) -> None:
    """Asil gerileme: surum gecisi kullanici verisine dokunmamali."""
    sema._senkron_guncelle()

    baglanti = sqlite3.connect(gecici_db)
    baglanti.execute(
        "INSERT INTO users (username, email, full_name, password_hash, roles, "
        "is_active, must_change_password, locale, theme, failed_login_count) "
        "VALUES ('uretici', 'u@ornek.com', 'Uretim Kullanicisi', 'x', '[\"denetci\"]', "
        "1, 0, 'tr', 'dark', 0)"
    )
    baglanti.commit()
    baglanti.close()

    # Yukseltmeyi tekrar calistir (MSI ile yeni surum kurulmus gibi)
    assert sema._senkron_guncelle() == "yukseltildi"

    baglanti = sqlite3.connect(gecici_db)
    try:
        satirlar = baglanti.execute("SELECT username FROM users").fetchall()
    finally:
        baglanti.close()
    assert ("uretici",) in satirlar, "Yukseltme kullanici verisini sildi"


def test_alembic_yoksa_yedek_yonteme_duser(
    gecici_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Goc dosyalari pakete girmemisse uygulama yine de acilabilmeli."""
    monkeypatch.setattr(sema, "_alembic_kokleri", lambda: None)
    assert sema._senkron_guncelle() == "alembic_yok"


async def test_asenkron_sarmalayici_calisir(gecici_db: Path) -> None:
    """env.py kendi icinde asyncio.run cagirir; calisan dongude patlamamali."""
    sonuc = await sema.semayi_hazirla()
    assert sonuc == "olusturuldu"
