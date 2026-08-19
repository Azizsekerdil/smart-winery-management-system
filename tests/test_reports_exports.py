"""Maliyet, rapor ve dışa aktarma (Excel / CSV / PDF) testleri."""

from __future__ import annotations

import datetime as dt
import io
import zipfile

import pytest
from httpx import AsyncClient

from app.services.exports import to_csv, to_pdf, to_xlsx


# --------------------------------------------------------- BİRİM TESTLERİ
def test_xlsx_gecerli_dosya_uretir():
    data = to_xlsx("Test Raporu", ["Kod", "Miktar"], [["A-1", 100], ["B-2", 250.5]])
    assert data[:2] == b"PK"  # xlsx bir zip arşividir
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert "xl/workbook.xml" in zf.namelist()


def test_csv_turkce_karakterleri_korur():
    data = to_csv(["Çeşit", "Bağ"], [["Öküzgözü", "Güneşli Tepe"]])
    assert data.startswith("﻿".encode())  # Excel için UTF-8 BOM
    metin = data.decode("utf-8-sig")
    assert "Öküzgözü" in metin
    assert "Güneşli Tepe" in metin
    assert ";" in metin  # Türkçe Excel ayracı


def test_pdf_gecerli_dosya_uretir():
    data = to_pdf("Test Raporu", ["Kod", "Ad"], [["A-1", "Örnek"]], subtitle="Alt başlık")
    assert data[:5] == b"%PDF-"
    assert b"%%EOF" in data[-1024:]


def test_pdf_bos_veri_ile_calisir():
    data = to_pdf("Boş Rapor", ["Kod"], [])
    assert data[:5] == b"%PDF-"


def test_xlsx_genis_tablo_ile_calisir():
    headers = [f"Sütun {i}" for i in range(12)]
    rows = [[f"v{r}-{c}" for c in range(12)] for r in range(50)]
    data = to_xlsx("Geniş", headers, rows)
    assert len(data) > 1000


# ------------------------------------------------------------- API TESTLERİ
@pytest.fixture
async def maliyet_ortami(client: AsyncClient, admin_headers):
    variety = await client.post(
        "/api/v1/varieties", json={"name": "Maliyet Çeşidi", "color": "kirmizi"},
        headers=admin_headers,
    )
    intake = await client.post(
        "/api/v1/harvest-intakes",
        json={
            "variety_id": variety.json()["id"],
            "harvest_date": dt.date.today().isoformat(),
            "net_weight_kg": 10000,
            "brix": 23.0,
            "ph": 3.5,
            "unit_price": 18.0,
        },
        headers=admin_headers,
    )
    tank = await client.post(
        "/api/v1/tanks", json={"capacity_l": 10000}, headers=admin_headers
    )
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "Maliyet Partisi",
            "volume_l": 7000,
            "current_tank_id": tank.json()["id"],
            "sources": [{"intake_id": intake.json()["id"], "weight_kg": 10000, "juice_yield_l": 7000}],
        },
        headers=admin_headers,
    )
    return {"lot": lot.json(), "intake": intake.json(), "tank": tank.json()}


async def test_parti_maliyeti_hesaplanir(client: AsyncClient, admin_headers, maliyet_ortami):
    response = await client.get(
        f"/api/v1/reports/cost/lot/{maliyet_ortami['lot']['id']}", headers=admin_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["grape_cost"] == pytest.approx(180000.0)  # 10000 kg × 18 TRY
    assert body["labor_cost"] == pytest.approx(7000 * 3.50)
    assert body["energy_cost"] == pytest.approx(7000 * 1.20)
    assert body["total_cost"] > body["grape_cost"]
    assert body["cost_per_liter"] == pytest.approx(body["total_cost"] / 7000, rel=1e-3)
    assert any(d["kalem"] == "Üzüm" for d in body["details"])


async def test_maliyet_oranlari_ayarlanabilir(client: AsyncClient, admin_headers, maliyet_ortami):
    response = await client.get(
        f"/api/v1/reports/cost/lot/{maliyet_ortami['lot']['id']}",
        params={"labor_per_l": 0, "energy_per_l": 0, "overhead_per_l": 0},
        headers=admin_headers,
    )
    body = response.json()
    assert body["labor_cost"] == 0
    assert body["total_cost"] == pytest.approx(body["grape_cost"])


async def test_kupaj_maliyeti_kaynak_partilerden_tasinir(
    client: AsyncClient, admin_headers, maliyet_ortami
):
    """Kupaj sonucu partinin maliyeti, kaynak partilerden oransal gelmeli."""
    variety = await client.post(
        "/api/v1/varieties", json={"name": "İkinci Çeşit", "color": "kirmizi"},
        headers=admin_headers,
    )
    intake2 = await client.post(
        "/api/v1/harvest-intakes",
        json={
            "variety_id": variety.json()["id"],
            "harvest_date": dt.date.today().isoformat(),
            "net_weight_kg": 5000,
            "unit_price": 20.0,
        },
        headers=admin_headers,
    )
    tank2 = await client.post("/api/v1/tanks", json={"capacity_l": 8000}, headers=admin_headers)
    lot2 = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "İkinci Parti",
            "volume_l": 3500,
            "current_tank_id": tank2.json()["id"],
            "sources": [{"intake_id": intake2.json()["id"], "weight_kg": 5000}],
        },
        headers=admin_headers,
    )
    tank3 = await client.post("/api/v1/tanks", json={"capacity_l": 12000}, headers=admin_headers)

    blend = await client.post(
        "/api/v1/blends",
        json={
            "name": "Maliyet Kupajı",
            "components": [
                {"source_lot_id": maliyet_ortami["lot"]["id"], "volume_l": 4000},
                {"source_lot_id": lot2.json()["id"], "volume_l": 2000},
            ],
        },
        headers=admin_headers,
    )
    await client.post(
        f"/api/v1/blends/{blend.json()['id']}/approval", json={"approve": True},
        headers=admin_headers,
    )
    result = await client.post(
        f"/api/v1/blends/{blend.json()['id']}/execute",
        json={"result_lot_name": "Kupaj Maliyeti", "target_tank_id": tank3.json()["id"]},
        headers=admin_headers,
    )
    assert result.status_code == 200, result.text

    cost = await client.get(
        f"/api/v1/reports/cost/lot/{result.json()['id']}", headers=admin_headers
    )
    assert cost.status_code == 200
    body = cost.json()
    assert body["grape_cost"] > 0, "Kaynak parti maliyeti taşınmadı"
    assert any(d["kalem"] == "Kaynak parti" for d in body["details"])


async def test_uretim_ozeti(client: AsyncClient, admin_headers, maliyet_ortami):
    response = await client.get("/api/v1/reports/production", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["intake_kg"] == 10000
    assert body["intake_count"] == 1
    assert body["active_lots"] >= 1
    assert len(body["by_variety"]) == 1
    assert body["by_variety"][0]["label"] == "Maliyet Çeşidi"


@pytest.mark.parametrize("fmt", ["xlsx", "csv", "pdf"])
@pytest.mark.parametrize(
    "report", ["uretim", "maliyet", "stok", "laboratuvar", "fermantasyon"]
)
async def test_rapor_disa_aktarma(
    client: AsyncClient, admin_headers, maliyet_ortami, report: str, fmt: str
):
    response = await client.get(
        "/api/v1/reports/export", params={"report": report, "fmt": fmt}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    assert "attachment" in response.headers["content-disposition"]
    assert f".{fmt}" in response.headers["content-disposition"]

    if fmt == "pdf":
        assert response.content[:5] == b"%PDF-"
        assert len(response.content) > 800
    elif fmt == "xlsx":
        assert response.content[:2] == b"PK"
        assert len(response.content) > 1000
    else:
        # CSV başlık satırından ibaret olabilir; boyut değil içerik doğrulanır
        assert response.content.startswith("﻿".encode())
        metin = response.content.decode("utf-8-sig")
        assert ";" in metin.splitlines()[0]


async def test_izlenebilirlik_raporu_lot_gerektirir(client: AsyncClient, admin_headers):
    response = await client.get(
        "/api/v1/reports/export", params={"report": "izlenebilirlik"}, headers=admin_headers
    )
    assert response.status_code == 400
    assert "lot_id" in response.json()["detail"]


async def test_izlenebilirlik_raporu(client: AsyncClient, admin_headers, maliyet_ortami):
    response = await client.get(
        "/api/v1/reports/export",
        params={"report": "izlenebilirlik", "fmt": "pdf", "lot_id": maliyet_ortami["lot"]["id"]},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.content[:5] == b"%PDF-"


async def test_bilinmeyen_rapor_reddedilir(client: AsyncClient, admin_headers):
    response = await client.get(
        "/api/v1/reports/export", params={"report": "olmayan"}, headers=admin_headers
    )
    assert response.status_code == 400


async def test_disa_aktarma_denetim_gunlugune_yazilir(
    client: AsyncClient, admin_headers, maliyet_ortami
):
    await client.get(
        "/api/v1/reports/export", params={"report": "uretim", "fmt": "csv"},
        headers=admin_headers,
    )
    audit = await client.get(
        "/api/v1/audit", params={"action": "disa_aktar"}, headers=admin_headers
    )
    assert audit.status_code == 200
    assert any("Rapor dışa aktarıldı" in i["summary"] for i in audit.json()["items"])


async def test_disa_aktarma_yetkisi_gerekir(client: AsyncClient, auth_headers):
    headers = await auth_headers(["uretim_operatoru"], "op_rapor")
    response = await client.get(
        "/api/v1/reports/export", params={"report": "uretim"}, headers=headers
    )
    assert response.status_code == 403
