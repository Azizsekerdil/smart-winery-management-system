"""Kimlik doğrulama ve oturum testleri."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_PASSWORD


async def test_saglik_kontrolu(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["durum"] == "calisiyor"


async def test_giris_basarili(client: AsyncClient, make_user):
    await make_user(["enolog"], "enolog1")
    response = await client.post(
        "/api/v1/auth/login", json={"username": "enolog1", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["username"] == "enolog1"


async def test_giris_hatali_parola(client: AsyncClient, make_user):
    await make_user(["enolog"], "enolog2")
    response = await client.post(
        "/api/v1/auth/login", json={"username": "enolog2", "password": "YanlisParola1!"}
    )
    assert response.status_code == 401
    # Kullanıcı numaralandırmasını engellemek için genel mesaj
    assert "hatalı" in response.json()["detail"].lower()


async def test_giris_olmayan_kullanici_ayni_hata(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login", json={"username": "yokboyle", "password": "Herhangi123!"}
    )
    assert response.status_code == 401
    assert "hatalı" in response.json()["detail"].lower()


async def test_hesap_kilitleme(client: AsyncClient, make_user):
    await make_user(["enolog"], "kilitli")
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login", json={"username": "kilitli", "password": "Yanlis123!"}
        )
    response = await client.post(
        "/api/v1/auth/login", json={"username": "kilitli", "password": TEST_PASSWORD}
    )
    assert response.status_code == 423
    assert "kilit" in response.json()["detail"].lower()


async def test_belirtecsiz_erisim_reddedilir(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_gecersiz_belirtec_reddedilir(client: AsyncClient):
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer sahte.belirtec.degeri"}
    )
    assert response.status_code == 401


async def test_me_yetkileri_dondurur(client: AsyncClient, auth_headers):
    headers = await auth_headers(["enolog"], "enolog3")
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "lab:approve" in body["permissions"]
    assert "Enolog" in body["role_labels"][0]


async def test_belirtec_yenileme(client: AsyncClient, make_user):
    await make_user(["enolog"], "yenile")
    login = await client.post(
        "/api/v1/auth/login", json={"username": "yenile", "password": TEST_PASSWORD}
    )
    refresh_token = login.json()["refresh_token"]
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_cikis_yenileme_belirtecini_iptal_eder(client: AsyncClient, make_user):
    await make_user(["enolog"], "cikis"),
    login = await client.post(
        "/api/v1/auth/login", json={"username": "cikis", "password": TEST_PASSWORD}
    )
    body = login.json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}

    logout = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]}, headers=headers
    )
    assert logout.status_code == 200

    again = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert again.status_code == 401


async def test_parola_degistirme(client: AsyncClient, auth_headers):
    headers = await auth_headers(["enolog"], "parola")
    response = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": TEST_PASSWORD, "new_password": "YeniParola456!"},
        headers=headers,
    )
    assert response.status_code == 200

    login = await client.post(
        "/api/v1/auth/login", json={"username": "parola", "password": "YeniParola456!"}
    )
    assert login.status_code == 200


@pytest.mark.parametrize(
    "zayif",
    ["kisa1A", "tumukucukharf123", "TUMUBUYUKHARF123", "RakamsizParola"],
)
async def test_zayif_parola_reddedilir(client: AsyncClient, admin_headers, zayif: str):
    response = await client.post(
        "/api/v1/users",
        json={
            "username": "zayifkullanici",
            "email": "zayif@example.com",
            "full_name": "Zayıf Parola",
            "roles": ["enolog"],
            "password": zayif,
        },
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_parola_karmasi_yanitlarda_gorunmez(client: AsyncClient, admin_headers):
    response = await client.post(
        "/api/v1/users",
        json={
            "username": "yenikullanici",
            "email": "yeni@example.com",
            "full_name": "Yeni Kullanıcı",
            "roles": ["laboratuvar_teknisyeni"],
            "password": "GucluParola123!",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert "password" not in response.text.lower() or "password_hash" not in response.json()

