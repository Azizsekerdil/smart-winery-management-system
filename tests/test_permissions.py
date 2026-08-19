"""Rol tabanlı yetkilendirme (RBAC) testleri."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.permissions import Perm, Role, has_permission, permissions_for


# ------------------------------------------------------------ birim testleri
def test_denetci_hicbir_yazma_yetkisine_sahip_degil():
    perms = permissions_for([Role.DENETCI])
    yazma = [p for p in perms if p.endswith((":write", ":approve", ":transfer"))]
    assert yazma == [], f"Denetçi rolünde yazma yetkisi bulundu: {yazma}"
    assert str(Perm.AUDIT_READ) in perms


def test_sistem_yoneticisi_tum_yetkilere_sahip():
    perms = permissions_for([Role.SISTEM_YONETICISI])
    assert perms == {p.value for p in Perm}


def test_laboratuvar_teknisyeni_kendi_sonucunu_onaylayamaz():
    perms = permissions_for([Role.LABORATUVAR_TEKNISYENI])
    assert str(Perm.LAB_WRITE) in perms
    assert str(Perm.LAB_APPROVE) not in perms


def test_enolog_onay_yetkisine_sahip():
    perms = permissions_for([Role.ENOLOG])
    assert str(Perm.LAB_APPROVE) in perms
    assert str(Perm.RECIPE_APPROVE) in perms


def test_ai_terminal_yetkisi_yalnizca_sistem_yoneticisinde():
    for role in Role:
        perms = permissions_for([role])
        if role == Role.SISTEM_YONETICISI:
            assert str(Perm.AI_TERMINAL_APPROVE) in perms
        else:
            assert str(Perm.AI_TERMINAL_APPROVE) not in perms, (
                f"{role} rolünde AI terminal onay yetkisi olmamalı"
            )


def test_roller_birlestirilir():
    perms = permissions_for([Role.LABORATUVAR_TEKNISYENI, Role.MAHZEN_SORUMLUSU])
    assert str(Perm.LAB_WRITE) in perms
    assert str(Perm.BARREL_WRITE) in perms


def test_bilinmeyen_rol_yok_sayilir():
    assert permissions_for(["olmayan_rol"]) == set()
    assert not has_permission(["olmayan_rol"], Perm.LOT_READ)


# ------------------------------------------------------------- API testleri
@pytest.mark.parametrize(
    ("rol", "beklenen"),
    [
        ("denetci", 403),
        ("bagcilik_uzmani", 201),
        ("enolog", 403),  # enolog bağ kaydı oluşturamaz (vineyard:write yok)
    ],
)
async def test_bag_olusturma_yetkisi(client: AsyncClient, auth_headers, rol, beklenen):
    headers = await auth_headers([rol], f"kul_{rol}")
    response = await client.post(
        "/api/v1/vineyards",
        json={"name": "Test Bağı", "region": "Ege"},
        headers=headers,
    )
    assert response.status_code == beklenen, response.text


async def test_denetci_okuyabilir(client: AsyncClient, auth_headers):
    headers = await auth_headers(["denetci"], "denetci1")
    response = await client.get("/api/v1/vineyards", headers=headers)
    assert response.status_code == 200


async def test_denetci_silme_reddedilir(client: AsyncClient, auth_headers, admin_headers):
    created = await client.post(
        "/api/v1/vineyards", json={"name": "Silinecek Bağ"}, headers=admin_headers
    )
    assert created.status_code == 201
    vid = created.json()["id"]

    headers = await auth_headers(["denetci"], "denetci2")
    response = await client.delete(f"/api/v1/vineyards/{vid}", headers=headers)
    assert response.status_code == 403


async def test_yetkisiz_erisim_denetim_gunlugune_yazilir(
    client: AsyncClient, auth_headers, admin_headers
):
    headers = await auth_headers(["denetci"], "denetci3")
    await client.post("/api/v1/vineyards", json={"name": "Yasak"}, headers=headers)

    audit = await client.get(
        "/api/v1/audit", params={"action": "izinsiz_erisim"}, headers=admin_headers
    )
    assert audit.status_code == 200
    items = audit.json()["items"]
    assert any("Yetkisiz erişim" in i["summary"] for i in items), items


async def test_kullanici_yonetimi_yalnizca_sistem_yoneticisinde(client: AsyncClient, auth_headers):
    headers = await auth_headers(["isletme_yoneticisi"], "mudur1")
    response = await client.post(
        "/api/v1/users",
        json={
            "username": "yenikisi",
            "email": "yenikisi@example.com",
            "full_name": "Yeni Kişi",
            "roles": ["enolog"],
            "password": "GucluParola123!",
        },
        headers=headers,
    )
    assert response.status_code == 403


async def test_son_sistem_yoneticisi_pasife_alinamaz(client: AsyncClient, admin_headers, client_user_id=None):
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    uid = me.json()["id"]
    response = await client.patch(
        f"/api/v1/users/{uid}", json={"is_active": False}, headers=admin_headers
    )
    assert response.status_code == 409
    assert "sistem yöneticisi" in response.json()["detail"].lower()


async def test_rol_katalogu_erisilebilir(client: AsyncClient, auth_headers):
    headers = await auth_headers(["uretim_operatoru"], "op1")
    response = await client.get("/api/v1/users/roles", headers=headers)
    assert response.status_code == 200
    roller = response.json()
    assert len(roller) == len(Role)
    assert all("ad" in r and "yetkiler" in r for r in roller)


async def test_ai_terminal_uc_noktasi_yetkisiz_reddedilir(client: AsyncClient, auth_headers):
    headers = await auth_headers(["enolog"], "enolog_terminal")
    response = await client.post(
        "/api/v1/terminal/plan",
        json={"request_text": "test", "use_llm": False},
        headers=headers,
    )
    assert response.status_code == 403
