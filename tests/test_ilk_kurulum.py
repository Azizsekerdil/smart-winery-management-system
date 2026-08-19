"""Yeni kurulumda yonetici hesabinin olusmasi.

MSI ile kurulan bos bir sistemde demo verisi YUKLENMEZ (gercek bir saraphaneye
kurgusal veri koymak dogru degildir). Hesap olusturulmazsa kullanici tablosu
bos kalir ve **kimse giris yapamaz**: uygulama acilir, giris ekrani gelir,
hicbir parola calismaz. Bu, kurulum testinde fiilen yasandi.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.permissions import Role
from app.core.security import verify_password
from app.db import ilk_kurulum
from app.models.user import User


@pytest.fixture
def parola_dosyasi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    yol = tmp_path / "ILK-GIRIS.txt"
    monkeypatch.setattr(ilk_kurulum, "ILK_GIRIS_DOSYASI", yol)
    return yol


# --------------------------------------------------------------- parola uretimi
def test_tek_kullanimlik_bootstrap_parolasi() -> None:
    assert ilk_kurulum._parola_uret() == "admin"


def test_paroladaki_karistirici_karakterler_elenmis() -> None:
    """`l/I/O/0/1` el ile yazarken karisir; alfabeden cikarildi."""
    birlesik = "".join(ilk_kurulum._parola_uret() for _ in range(40))
    for karakter in "lIO01":
        assert karakter not in birlesik


def test_bootstrap_parolasi_sabit_ama_tek_kullanimliktir() -> None:
    assert {ilk_kurulum._parola_uret() for _ in range(10)} == {"admin"}


# ------------------------------------------------------------------- hesap
async def test_bos_veritabaninda_yonetici_olusur(session, parola_dosyasi: Path) -> None:
    await session.execute(User.__table__.delete())
    await session.commit()

    dosya = await ilk_kurulum.ilk_yoneticiyi_olustur(session)
    assert dosya is not None, "Hesap olusturulmadi"

    yonetici = await session.scalar(
        select(User).where(User.username == ilk_kurulum.YONETICI_ADI)
    )
    assert yonetici is not None
    assert str(Role.SISTEM_YONETICISI) in yonetici.roles
    assert yonetici.is_active is True
    assert yonetici.must_change_password is True, "Ilk parola degistirilmeye zorlanmali"


async def test_parola_dosyaya_yazilir_ve_gercekten_calisir(
    session, parola_dosyasi: Path
) -> None:
    await session.execute(User.__table__.delete())
    await session.commit()

    await ilk_kurulum.ilk_yoneticiyi_olustur(session)
    assert parola_dosyasi.is_file()

    metin = parola_dosyasi.read_text(encoding="utf-8")
    satir = next(s for s in metin.splitlines() if "Parola" in s)
    parola = satir.split(":", 1)[1].strip()

    yonetici = await session.scalar(
        select(User).where(User.username == ilk_kurulum.YONETICI_ADI)
    )
    assert verify_password(parola, yonetici.password_hash), (
        "Dosyaya yazilan parola hesaba ait degil"
    )


async def test_mevcut_kullanici_varsa_hicbir_sey_yapilmaz(
    session, parola_dosyasi: Path
) -> None:
    """Ikinci acilista yeni hesap olusmamali, parola dosyasi yazilmamali."""
    session.add(
        User(
            username="mevcut",
            email="mevcut@ornek.com",
            full_name="Mevcut Kullanıcı",
            password_hash="x",
            roles=[str(Role.DENETCI)],
        )
    )
    await session.commit()

    onceki = await session.scalar(select(func.count()).select_from(User))
    assert onceki > 0

    dosya = await ilk_kurulum.ilk_yoneticiyi_olustur(session)
    assert dosya is None
    assert not parola_dosyasi.exists()

    sonraki = await session.scalar(select(func.count()).select_from(User))
    assert sonraki == onceki


async def test_ikinci_calistirmada_parola_degismez(session, parola_dosyasi: Path) -> None:
    await session.execute(User.__table__.delete())
    await session.commit()

    await ilk_kurulum.ilk_yoneticiyi_olustur(session)
    ilk_metin = parola_dosyasi.read_text(encoding="utf-8")

    # Uygulama yeniden acildi
    assert await ilk_kurulum.ilk_yoneticiyi_olustur(session) is None
    assert parola_dosyasi.read_text(encoding="utf-8") == ilk_metin


async def test_yazilamayan_konumda_hesap_yine_olusur(
    session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dosya yazilamasa bile hesap olusmali; aksi halde sistem kilitlenir."""
    monkeypatch.setattr(
        ilk_kurulum, "ILK_GIRIS_DOSYASI", tmp_path / "yok" / "olmayan" / "x.txt"
    )
    monkeypatch.setattr(
        Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("engellendi"))
    )
    await session.execute(User.__table__.delete())
    await session.commit()

    dosya = await ilk_kurulum.ilk_yoneticiyi_olustur(session)
    assert dosya is None  # dosya yazilamadi

    yonetici = await session.scalar(
        select(User).where(User.username == ilk_kurulum.YONETICI_ADI)
    )
    assert yonetici is not None, "Dosya yazilamayinca hesap da olusmamis"


async def test_olusan_hesapla_api_uzerinden_giris_yapilir(
    client: AsyncClient, session, parola_dosyasi: Path
) -> None:
    """Asil dogrulama: kullanici gercekten sisteme girebiliyor mu?"""
    await session.execute(User.__table__.delete())
    await session.commit()

    await ilk_kurulum.ilk_yoneticiyi_olustur(session)
    metin = parola_dosyasi.read_text(encoding="utf-8")
    parola = next(s for s in metin.splitlines() if "Parola" in s).split(":", 1)[1].strip()

    yanit = await client.post(
        "/api/v1/auth/login",
        json={"username": ilk_kurulum.YONETICI_ADI, "password": parola},
    )
    assert yanit.status_code == 200, yanit.text
    assert yanit.json()["access_token"]


def test_parola_dosyasi_git_tarafindan_yok_sayilir() -> None:
    from app.core.config import PROJECT_ROOT

    kurallar = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "ILK-GIRIS" in kurallar, ".gitignore ilk giris parolasini kapsamiyor"
