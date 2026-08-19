"""Sunucu tarafi dil secimi.

Arayuz cevirilerinin cogu istemcide tutulur, ancak rol adlari ve yetki
aciklamalari sunucudan gelir. Bunlar Ingilizce secildiginde Turkce kalirsa
ekran yarim cevrilmis gorunur.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.i18n import dil_sec
from app.core.permissions import (
    PERM_LABELS_EN,
    PERM_LABELS_TR,
    ROLE_LABELS_EN,
    ROLE_LABELS_TR,
    rol_etiketleri,
    yetki_etiketleri,
)


class _SahteIstek:
    def __init__(self, deger: str | None) -> None:
        self.headers = {"accept-language": deger} if deger is not None else {}


# ------------------------------------------------------------- baslik ayristirma
@pytest.mark.parametrize(
    ("baslik", "beklenen"),
    [
        ("en", "en"),
        ("tr", "tr"),
        ("en-US", "en"),
        ("tr-TR", "tr"),
        ("en-US,en;q=0.9,tr;q=0.8", "en"),
        ("tr-TR,tr;q=0.9,en;q=0.8", "tr"),
        # Desteklenmeyen dil -> varsayilan
        ("de-DE,de;q=0.9", "tr"),
        ("fr", "tr"),
        ("", "tr"),
        ("*", "tr"),
        (None, "tr"),
        # Desteklenmeyen dilden sonra desteklenen geliyorsa o secilir
        ("de,en;q=0.7", "en"),
    ],
)
def test_accept_language_ayristirmasi(baslik: str | None, beklenen: str) -> None:
    assert dil_sec(_SahteIstek(baslik)) == beklenen  # type: ignore[arg-type]


def test_istek_yoksa_varsayilan() -> None:
    assert dil_sec(None) == "tr"


# ------------------------------------------------------------------- sozlukler
def test_rol_sozlukleri_ayni_anahtarlara_sahip() -> None:
    assert set(ROLE_LABELS_TR) == set(ROLE_LABELS_EN)


def test_yetki_sozlukleri_ayni_anahtarlara_sahip() -> None:
    eksik = set(PERM_LABELS_TR) - set(PERM_LABELS_EN)
    assert not eksik, f"Ingilizce karsiligi olmayan yetkiler: {sorted(str(e) for e in eksik)}"


def test_ingilizce_etiketler_turkce_karakter_icermez() -> None:
    """Kopyala-yapistir hatasini yakalar."""
    for sozluk, ad in ((ROLE_LABELS_EN, "rol"), (PERM_LABELS_EN, "yetki")):
        for anahtar, deger in sozluk.items():
            assert not any(c in deger for c in "çğıöşüÇĞİÖŞÜ"), (
                f"{ad} etiketi hala Turkce: {anahtar} -> {deger}"
            )


def test_etiket_secicileri_dile_gore_calisir() -> None:
    tr = rol_etiketleri("tr")
    en = rol_etiketleri("en")
    assert tr["sistem_yoneticisi"] == "Sistem Yöneticisi"
    assert en["sistem_yoneticisi"] == "System Administrator"

    assert yetki_etiketleri("tr")["lot:read"] == "Parti görüntüle"
    assert yetki_etiketleri("en")["lot:read"] == "View lots"


def test_bilinmeyen_dil_turkceye_duser() -> None:
    assert rol_etiketleri("de") == rol_etiketleri("tr")
    assert yetki_etiketleri("fr") == yetki_etiketleri("tr")


# ------------------------------------------------------------------------- API
async def test_auth_me_dile_gore_rol_etiketi_dondurur(
    client: AsyncClient, admin_headers
) -> None:
    tr = await client.get("/api/v1/auth/me", headers={**admin_headers, "Accept-Language": "tr"})
    en = await client.get("/api/v1/auth/me", headers={**admin_headers, "Accept-Language": "en"})

    assert tr.json()["role_labels"] == ["Sistem Yöneticisi"]
    assert en.json()["role_labels"] == ["System Administrator"]


async def test_yetki_uclari_dile_gore_doner(client: AsyncClient, admin_headers) -> None:
    tr = (
        await client.get(
            "/api/v1/users/permissions", headers={**admin_headers, "Accept-Language": "tr"}
        )
    ).json()
    en = (
        await client.get(
            "/api/v1/users/permissions", headers={**admin_headers, "Accept-Language": "en"}
        )
    ).json()

    assert tr["lab:approve"] == "Laboratuvar sonucu onayla/reddet"
    assert en["lab:approve"] == "Approve/reject lab results"
    assert set(tr) == set(en), "Iki dilde farkli yetki kumesi donuyor"


async def test_baslik_yoksa_turkce_doner(client: AsyncClient, admin_headers) -> None:
    yanit = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert yanit.json()["role_labels"] == ["Sistem Yöneticisi"]
