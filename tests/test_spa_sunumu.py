"""Derlenmis arayuzun ayni sunucudan sunulmasi.

Masaustu paketi ve tek konteynerli dagitim, arayuzu API ile ayni kokenden
sunar. Bu testler yonlendirmenin dogru calistigini ve statik sunumun bir yol
kacisi (path traversal) yuzeyi olusturmadigini dogrular.

Arayuz derlenmemisse (`frontend/dist` yok) testler atlanir; boylece yalnizca
backend uzerinde calisan gelistiriciyi engellemez.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import settings

pytestmark = pytest.mark.skipif(
    not settings.frontend_available,
    reason="Arayuz derlenmemis (`cd frontend; npm run build` ile derleyin)",
)


async def test_kok_adres_arayuzu_dondurur(client: AsyncClient) -> None:
    yanit = await client.get("/")
    assert yanit.status_code == 200
    assert yanit.headers["content-type"].startswith("text/html")
    assert "<div id=\"root\"" in yanit.text or "<div id='root'" in yanit.text


@pytest.mark.parametrize("yol", ["/tanklar", "/partiler/12", "/yapay-zeka", "/ayarlar"])
async def test_istemci_yonlendirmesi_index_dondurur(client: AsyncClient, yol: str) -> None:
    """Adres cubuguna dogrudan yazilan istemci rotasi 404 vermemeli."""
    yanit = await client.get(yol)
    assert yanit.status_code == 200
    assert yanit.headers["content-type"].startswith("text/html")


async def test_api_yollari_arayuze_dusmez(client: AsyncClient) -> None:
    """SPA yakalayicisi API'yi golgelememeli."""
    yanit = await client.get("/api/v1/tanks")
    # Kimlik dogrulama hatasi bekleriz -- HTML DEGIL
    assert yanit.status_code == 401
    assert yanit.headers["content-type"].startswith("application/json")


async def test_saglik_ucu_json_kalir(client: AsyncClient) -> None:
    yanit = await client.get("/health")
    assert yanit.status_code == 200
    assert yanit.json()["durum"] == "calisiyor"


async def test_openapi_semasi_erisilebilir(client: AsyncClient) -> None:
    yanit = await client.get("/openapi.json")
    assert yanit.status_code == 200
    assert yanit.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize(
    "yol",
    [
        "/../backend/app/core/config.py",
        "/..%2f..%2f.env",
        "/assets/../../.env",
        "/%2e%2e/%2e%2e/data/winery.db",
    ],
)
async def test_yol_kacisi_dosya_sizdirmaz(client: AsyncClient, yol: str) -> None:
    """`..` ile arayuz dizini disina cikilamaz; en kotu ihtimalle index doner."""
    yanit = await client.get(yol)
    assert yanit.status_code in (200, 404)
    if yanit.status_code == 200:
        govde = yanit.text
        # Kaynak kod veya gizli bilgi sizmamali
        assert "SECRET_KEY" not in govde
        assert "def " not in govde
        assert "sqlite" not in govde.lower()
