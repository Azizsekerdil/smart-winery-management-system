"""Gizli değerlerin loglarda/denetimde maskelenmesi ve şifreli saklanması."""

from __future__ import annotations

import logging

import pytest
from httpx import AsyncClient

from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret, secret_fingerprint
from app.core.logging import MASK, ScrubbingFilter, scrub

ORNEK_ANAHTARLAR = [
    "sk-ant-api03-AbCdEf0123456789GhIjKlMnOpQrStUvWxYz",
    "nvapi-0123456789abcdefghijklmnopqrstuvwxyzABCDEF",
    "sk-proj0123456789abcdefghijklmnopqrstuvwxyz",
    "ghp_0123456789abcdefghijklmnopqrstuvwxyzAB",
    "swm_0123456789abcdefghijklmnopqrstuvwxyz-_",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk",
    "AKIAIOSFODNN7EXAMPLE",
]


@pytest.mark.parametrize("anahtar", ORNEK_ANAHTARLAR)
def test_bilinen_anahtar_bicimleri_maskelenir(anahtar: str):
    metin = f"Sağlayıcı hatası oluştu, anahtar: {anahtar} — lütfen kontrol edin."
    temiz = scrub(metin)
    assert anahtar not in temiz, f"Anahtar sızdı: {temiz}"
    assert MASK in temiz


def test_anahtar_deger_ciftleri_maskelenir():
    ornekler = [
        "ANTHROPIC_API_KEY=cok-gizli-deger-123456",
        "api_key: 'gizli-anahtar-abcdef'",
        'password="ParolaDegeri123"',
        "Authorization: Bearer abcdefghijklmnop",
        "secret_key = uzun-gizli-deger-987654",
    ]
    for ornek in ornekler:
        temiz = scrub(ornek)
        assert MASK in temiz, f"Maskelenmedi: {ornek} → {temiz}"


def test_sozluk_alanlari_maskelenir():
    veri = {
        "username": "enolog",
        "password": "AcikParola123",
        "api_key": "sk-ant-gizli",
        "nested": {"anthropic_api_key": "sk-ant-baska", "not": "zararsız metin"},
        "liste": ["nvapi-0123456789abcdefghijklmnop", "normal"],
    }
    temiz = scrub(veri)
    assert temiz["password"] == MASK
    assert temiz["api_key"] == MASK
    assert temiz["nested"]["anthropic_api_key"] == MASK
    assert temiz["nested"]["not"] == "zararsız metin"
    assert MASK in temiz["liste"][0]
    assert temiz["liste"][1] == "normal"
    assert temiz["username"] == "enolog"


def test_zararsiz_metin_degismez():
    metin = "Fermantasyon FRM-2025-0001 için Brix 12.4 ölçüldü, sıcaklık 26.5 °C."
    assert scrub(metin) == metin


def test_logging_filtresi_kaydi_temizler(caplog):
    logger = logging.getLogger("maskeleme_testi")
    logger.addFilter(ScrubbingFilter())
    with caplog.at_level(logging.INFO):
        logger.info("Bağlantı hatası: anahtar sk-ant-api03-COKGIZLIDEGER123456 geçersiz")
    assert "sk-ant-api03-COKGIZLIDEGER123456" not in caplog.text
    assert MASK in caplog.text


# ------------------------------------------------------------- ŞİFRELEME
def test_sifreleme_gidis_donus():
    duz = "nvapi-cok-gizli-anahtar-degeri-1234567890"
    sifreli = encrypt_secret(duz)
    assert sifreli != duz
    assert duz not in sifreli
    assert decrypt_secret(sifreli) == duz


def test_bozuk_sifreli_deger_bos_doner():
    assert decrypt_secret("bozuk-veri") == ""
    assert decrypt_secret("") == ""


def test_ayni_deger_farkli_sifreli_metin_uretir():
    """Fernet rastgele IV kullanır; aynı anahtar iki kez farklı şifrelenir."""
    a = encrypt_secret("ayni-deger")
    b = encrypt_secret("ayni-deger")
    assert a != b
    assert decrypt_secret(a) == decrypt_secret(b) == "ayni-deger"


def test_maskeleme_yalnizca_son_karakterleri_gosterir():
    assert mask_secret("sk-ant-api03-1234567890abcdef").endswith("cdef")
    assert "sk-ant" not in mask_secret("sk-ant-api03-1234567890abcdef")
    assert mask_secret("") == ""


def test_parmak_izi_geri_donusturulemez():
    fp = secret_fingerprint("gizli-anahtar")
    assert len(fp) == 12
    assert "gizli" not in fp
    assert secret_fingerprint("gizli-anahtar") == fp
    assert secret_fingerprint("baska-anahtar") != fp


# ------------------------------------------------------------ API TESTLERİ
async def test_api_anahtari_hicbir_uctan_okunamaz(client: AsyncClient, admin_headers):
    gizli = "nvapi-TESTANAHTARI0123456789abcdefghijklmnop"

    kaydet = await client.put(
        "/api/v1/ai/providers/nvidia/api-key", json={"api_key": gizli}, headers=admin_headers
    )
    assert kaydet.status_code == 200
    assert gizli not in kaydet.text

    detay = await client.get("/api/v1/ai/providers/nvidia", headers=admin_headers)
    assert detay.status_code == 200
    assert gizli not in detay.text
    body = detay.json()
    assert body["has_api_key"] is True
    assert body["api_key_fingerprint"]
    assert "api_key" not in body or body.get("api_key") is None

    liste = await client.get("/api/v1/ai/providers", headers=admin_headers)
    assert gizli not in liste.text


async def test_anahtar_degisikligi_denetime_maskeli_yazilir(client: AsyncClient, admin_headers):
    gizli = "sk-ant-api03-DENETIMTESTI0123456789abcdefgh"
    await client.put(
        "/api/v1/ai/providers/anthropic/api-key", json={"api_key": gizli}, headers=admin_headers
    )
    audit = await client.get(
        "/api/v1/audit", params={"entity_type": "ai_provider_configs"}, headers=admin_headers
    )
    assert audit.status_code == 200
    assert gizli not in audit.text
    kayit = audit.json()["items"][0]
    assert kayit["after_data"]["api_key"] == MASK


async def test_parola_denetim_gunlugunde_gorunmez(client: AsyncClient, admin_headers):
    parola = "CokGizliParola456!"
    await client.post(
        "/api/v1/users",
        json={
            "username": "denetimtest",
            "email": "denetimtest@example.com",
            "full_name": "Denetim Testi",
            "roles": ["enolog"],
            "password": parola,
        },
        headers=admin_headers,
    )
    audit = await client.get(
        "/api/v1/audit", params={"entity_type": "users"}, headers=admin_headers
    )
    assert parola not in audit.text
    assert "$argon2" not in audit.text


async def test_gizli_alanlar_arayuzde_maskeli(client: AsyncClient, admin_headers):
    await client.put(
        "/api/v1/ai/providers/nvidia/api-key",
        json={"api_key": "nvapi-MASKETEST0123456789abcdefghijklmn"},
        headers=admin_headers,
    )
    detay = await client.get("/api/v1/ai/providers/nvidia", headers=admin_headers)
    masked = detay.json()["api_key_masked"]
    assert masked.startswith("*")
    assert "nvapi" not in masked


async def test_anahtar_silinebilir(client: AsyncClient, admin_headers):
    await client.put(
        "/api/v1/ai/providers/nvidia/api-key",
        json={"api_key": "nvapi-SILINECEK0123456789abcdefghijklmn"},
        headers=admin_headers,
    )
    sil = await client.delete("/api/v1/ai/providers/nvidia/api-key", headers=admin_headers)
    assert sil.status_code == 200
    detay = await client.get("/api/v1/ai/providers/nvidia", headers=admin_headers)
    assert detay.json()["has_api_key"] is False


async def test_denetim_kaydi_silinemez(client: AsyncClient, admin_headers):
    audit = await client.get("/api/v1/audit", headers=admin_headers)
    if audit.json()["items"]:
        aid = audit.json()["items"][0]["id"]
        response = await client.delete(f"/api/v1/audit/{aid}", headers=admin_headers)
        assert response.status_code == 405
        assert "değiştirilemez" in response.json()["detail"]


async def test_guvenlik_basliklari_mevcut(client: AsyncClient):
    response = await client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
