"""Kurulum (bootstrap) yonetici hesabinin guvenlik sozlesmesi.

Ilk calistirmada olusan yonetici hesabi tek kullanimliktir. Bu dosya, o hesabin
uymak ZORUNDA oldugu kurallari dogrular:

  1. Parola degistirilmeden korumali HICBIR uc nokta acilmaz
     (pano, musteri/personel verisi, mali kayit, AI/API ayarlari, disa
     aktarma, yedekleme, yonetim islemleri).
  2. Parola degistirilene kadar hesap YALNIZCA yerel makineden acilir;
     ag uzerinden giris reddedilir.
  3. Parola degistikten sonra ESKI parola kalici olarak gecersizdir.
  4. Yonetici parola sifirlamasi kurulum durumunu GERI GETIRMEZ.
  5. Yeni parola Argon2id ile karmalanir; hicbir yerde duz metin tutulmaz.
  6. Kaba kuvvet denemesi kilitlenme ile sonuclanir.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import verify_password
from app.db import ilk_kurulum
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User

YENI_PAROLA = "YeniGuvenliParola9!"


# --------------------------------------------------------------- yardimcilar
async def _kurulum_hesabi_olustur(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Bos veritabaninda kurulum hesabini olusturur; uretilen parolayi doner."""
    yol = tmp_path / "ILK-GIRIS.txt"
    monkeypatch.setattr(ilk_kurulum, "ILK_GIRIS_DOSYASI", yol)

    async with SessionLocal() as s:
        await s.execute(User.__table__.delete())
        await s.commit()
        await ilk_kurulum.ilk_yoneticiyi_olustur(s)

    metin = yol.read_text(encoding="utf-8")
    return next(r for r in metin.splitlines() if "Parola" in r).split(":", 1)[1].strip()


def _istemci(host: str) -> AsyncClient:
    """Belirli bir istemci IP'sinden geliyormus gibi davranan istemci."""
    transport = ASGITransport(app=app, client=(host, 12345))
    return AsyncClient(transport=transport, base_url="http://test")


async def _yerel_giris(parola: str) -> str:
    async with _istemci("127.0.0.1") as c:
        y = await c.post(
            "/api/v1/auth/login",
            json={"username": ilk_kurulum.YONETICI_ADI, "password": parola},
        )
    assert y.status_code == 200, y.text
    return y.json()["access_token"]


# ------------------------------------------------- 1. zorunlu parola degisimi
# Kurulum parolasiyla acilan oturum, korumali hicbir alani goremez.
KORUMALI_UC_NOKTALAR = [
    "/api/v1/dashboard",            # pano
    "/api/v1/users",                # personel verisi
    "/api/v1/ai/providers",         # AI / API anahtari ayarlari
    "/api/v1/stock/levels",         # stok
    "/api/v1/lots",                 # uretim verisi
    "/api/v1/customers",            # musteri verisi
    "/api/v1/reports/cost/summary", # mali kayit
    "/api/v1/reports/export",       # disa aktarma
    "/api/v1/backups",              # yedekleme
    "/api/v1/statistics/stok",      # istatistik
    "/api/v1/audit",                # denetim gunlugu
]


@pytest.mark.parametrize("yol", KORUMALI_UC_NOKTALAR)
async def test_parola_degismeden_korumali_alan_acilmaz(
    yol: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parola = await _kurulum_hesabi_olustur(tmp_path, monkeypatch)
    token = await _yerel_giris(parola)

    async with _istemci("127.0.0.1") as c:
        y = await c.get(yol, headers={"Authorization": f"Bearer {token}"})

    assert y.status_code == 403, (
        f"{yol} parola degistirilmeden acildi (durum {y.status_code}). "
        "Kurulum parolasiyla korumali veri goruntulenememeli."
    )
    assert y.headers.get("X-Password-Change-Required") == "true"


async def test_parola_degistirme_ve_kendi_bilgisi_serbesttir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kilit, kullanicinin parolayi degistirmesini engellememeli."""
    parola = await _kurulum_hesabi_olustur(tmp_path, monkeypatch)
    token = await _yerel_giris(parola)
    basliklar = {"Authorization": f"Bearer {token}"}

    async with _istemci("127.0.0.1") as c:
        assert (await c.get("/api/v1/auth/me", headers=basliklar)).status_code == 200
        y = await c.post(
            "/api/v1/auth/change-password",
            headers=basliklar,
            json={"old_password": parola, "new_password": YENI_PAROLA},
        )
    assert y.status_code == 200, y.text


async def test_parola_degisince_korumali_alan_acilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parola = await _kurulum_hesabi_olustur(tmp_path, monkeypatch)
    token = await _yerel_giris(parola)

    async with _istemci("127.0.0.1") as c:
        await c.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"old_password": parola, "new_password": YENI_PAROLA},
        )
        yeni = await c.post(
            "/api/v1/auth/login",
            json={"username": ilk_kurulum.YONETICI_ADI, "password": YENI_PAROLA},
        )
        assert yeni.status_code == 200, yeni.text
        y = await c.get(
            "/api/v1/ai/providers",
            headers={"Authorization": f"Bearer {yeni.json()['access_token']}"},
        )
    assert y.status_code == 200, y.text


# ------------------------------------------------------ 2. yalnizca yerel giris
async def test_kurulum_hesabi_ag_uzerinden_giris_yapamaz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parola = await _kurulum_hesabi_olustur(tmp_path, monkeypatch)

    async with _istemci("192.168.1.50") as c:
        y = await c.post(
            "/api/v1/auth/login",
            json={"username": ilk_kurulum.YONETICI_ADI, "password": parola},
        )
    assert y.status_code == 403, (
        "Kurulum hesabi ag uzerinden acilabildi; parola dosyaya yazildigi icin "
        "bu hesap yalnizca yerel makineden acilabilmeli."
    )


async def test_uzaktan_giris_x_forwarded_for_ile_taklit_edilemez(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Istemcinin gonderdigi baslik guven kaynagi olamaz."""
    parola = await _kurulum_hesabi_olustur(tmp_path, monkeypatch)

    async with _istemci("203.0.113.9") as c:
        y = await c.post(
            "/api/v1/auth/login",
            headers={"X-Forwarded-For": "127.0.0.1"},
            json={"username": ilk_kurulum.YONETICI_ADI, "password": parola},
        )
    assert y.status_code == 403, "X-Forwarded-For ile yerel giris taklit edilebildi"


async def test_parola_degisince_ag_uzerinden_giris_acilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parola = await _kurulum_hesabi_olustur(tmp_path, monkeypatch)
    token = await _yerel_giris(parola)

    async with _istemci("127.0.0.1") as c:
        await c.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"old_password": parola, "new_password": YENI_PAROLA},
        )

    async with _istemci("192.168.1.50") as c:
        y = await c.post(
            "/api/v1/auth/login",
            json={"username": ilk_kurulum.YONETICI_ADI, "password": YENI_PAROLA},
        )
    assert y.status_code == 200, y.text


# ------------------------------------------- 3. eski parola kalici olarak olur
async def test_eski_kurulum_parolasi_degisimden_sonra_calismaz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parola = await _kurulum_hesabi_olustur(tmp_path, monkeypatch)
    token = await _yerel_giris(parola)

    async with _istemci("127.0.0.1") as c:
        await c.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"old_password": parola, "new_password": YENI_PAROLA},
        )
        y = await c.post(
            "/api/v1/auth/login",
            json={"username": ilk_kurulum.YONETICI_ADI, "password": parola},
        )
    assert y.status_code == 401, "Eski kurulum parolasi hala calisiyor"


async def test_parola_dosyasi_degisimden_sonra_silinir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parola = await _kurulum_hesabi_olustur(tmp_path, monkeypatch)
    dosya = ilk_kurulum.ILK_GIRIS_DOSYASI
    assert dosya.is_file()

    token = await _yerel_giris(parola)
    async with _istemci("127.0.0.1") as c:
        await c.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"old_password": parola, "new_password": YENI_PAROLA},
        )
    assert not dosya.exists(), "Gecersiz kalan kurulum parolasi diskte kaldi"


# ------------------------------- 4. sifirlama kurulum durumunu geri getirmez
async def test_yonetici_sifirlamasi_kurulum_durumunu_geri_getirmez(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parola = await _kurulum_hesabi_olustur(tmp_path, monkeypatch)
    token = await _yerel_giris(parola)

    async with _istemci("127.0.0.1") as c:
        await c.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"old_password": parola, "new_password": YENI_PAROLA},
        )
        giris = await c.post(
            "/api/v1/auth/login",
            json={"username": ilk_kurulum.YONETICI_ADI, "password": YENI_PAROLA},
        )
        yonetici_token = giris.json()["access_token"]

        async with SessionLocal() as s:
            hesap = await s.scalar(
                select(User).where(User.username == ilk_kurulum.YONETICI_ADI)
            )
            hesap_id = hesap.id

        y = await c.post(
            f"/api/v1/users/{hesap_id}/reset-password",
            headers={"Authorization": f"Bearer {yonetici_token}"},
            json={"new_password": "BaskaParola77!", "must_change": True},
        )
        assert y.status_code == 200, y.text

    async with SessionLocal() as s:
        hesap = await s.get(User, hesap_id)
        assert hesap.bootstrap_pending is False, (
            "Parola sifirlama, hesabi tekrar 'kurulum modu'na dusurdu; "
            "varsayilan durum sifirlama yoluyla canlandirilabilir hale geldi."
        )

    # Sifirlanan hesap ag uzerinden acilabilmeli (artik kurulum hesabi degil)
    async with _istemci("192.168.1.50") as c:
        y = await c.post(
            "/api/v1/auth/login",
            json={"username": ilk_kurulum.YONETICI_ADI, "password": "BaskaParola77!"},
        )
    assert y.status_code == 200, y.text


# ------------------------------------------------------- 5. karma ve gizlilik
async def test_parola_hicbir_zaman_duz_metin_saklanmaz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parola = await _kurulum_hesabi_olustur(tmp_path, monkeypatch)

    async with SessionLocal() as s:
        hesap = await s.scalar(
            select(User).where(User.username == ilk_kurulum.YONETICI_ADI)
        )

    assert hesap.password_hash.startswith("$argon2id$"), (
        f"Argon2id bekleniyordu, gelen: {hesap.password_hash[:20]}"
    )
    assert parola not in hesap.password_hash
    assert verify_password(parola, hesap.password_hash)


async def test_giris_yaniti_parola_sizdirmaz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parola = await _kurulum_hesabi_olustur(tmp_path, monkeypatch)

    async with _istemci("127.0.0.1") as c:
        y = await c.post(
            "/api/v1/auth/login",
            json={"username": ilk_kurulum.YONETICI_ADI, "password": parola},
        )
    assert '"password"' not in y.text.lower(), "Parola alani giris yanitinda gorunuyor"
    assert "password_hash" not in y.text.lower()
    assert y.json()["user"].get("must_change_password") is True


# ------------------------------------------------------------ 6. kaba kuvvet
async def test_tekrarlanan_hatali_parola_hesabi_kilitler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    await _kurulum_hesabi_olustur(tmp_path, monkeypatch)

    async with _istemci("127.0.0.1") as c:
        for _ in range(settings.MAX_LOGIN_ATTEMPTS):
            await c.post(
                "/api/v1/auth/login",
                json={"username": ilk_kurulum.YONETICI_ADI, "password": "YanlisParola1!"},
            )
        y = await c.post(
            "/api/v1/auth/login",
            json={"username": ilk_kurulum.YONETICI_ADI, "password": "YanlisParola1!"},
        )

    assert y.status_code == 423, (
        f"Hesap {settings.MAX_LOGIN_ATTEMPTS} hatali denemeden sonra kilitlenmedi "
        f"(durum {y.status_code})"
    )
