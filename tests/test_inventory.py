"""Stok hareketleri, FIFO/FEFO, satın alma ve sevkiyat testleri."""

from __future__ import annotations

import datetime as dt

import pytest
from httpx import AsyncClient


@pytest.fixture
async def stok_ortami(client: AsyncClient, admin_headers):
    depolar = {}
    for ad in ("Ana Depo", "Yedek Depo"):
        response = await client.post(
            "/api/v1/warehouses", json={"name": ad}, headers=admin_headers
        )
        assert response.status_code == 201, response.text
        depolar[ad] = response.json()

    fifo = await client.post(
        "/api/v1/items",
        json={
            "name": "Şişe 750 ml",
            "category": "ambalaj",
            "unit": "adet",
            "min_stock": 1000,
            "reorder_qty": 5000,
            "valuation_method": "fifo",
        },
        headers=admin_headers,
    )
    fefo = await client.post(
        "/api/v1/items",
        json={
            "name": "Maya EC-1118",
            "category": "katki",
            "unit": "kg",
            "min_stock": 5,
            "valuation_method": "fefo",
            "has_expiry": True,
        },
        headers=admin_headers,
    )
    return {"depolar": depolar, "fifo": fifo.json(), "fefo": fefo.json()}


async def test_stok_girisi_ve_seviye(client: AsyncClient, admin_headers, stok_ortami):
    response = await client.post(
        "/api/v1/stock/in",
        json={
            "item_id": stok_ortami["fifo"]["id"],
            "warehouse_id": stok_ortami["depolar"]["Ana Depo"]["id"],
            "quantity": 5000,
            "unit_cost": 9.85,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    levels = await client.get("/api/v1/stock/levels", headers=admin_headers)
    kalem = next(x for x in levels.json() if x["item_id"] == stok_ortami["fifo"]["id"])
    assert kalem["on_hand"] == 5000
    assert kalem["stock_value"] == pytest.approx(49250.0)
    assert kalem["below_min"] is False


async def test_fifo_once_eski_partiden_tuketir(client: AsyncClient, admin_headers, stok_ortami):
    item_id = stok_ortami["fifo"]["id"]
    wh_id = stok_ortami["depolar"]["Ana Depo"]["id"]
    now = dt.datetime.now(dt.UTC)

    for gun_once, maliyet, adet, kod in [(30, 8.0, 1000, "ESKI"), (5, 12.0, 1000, "YENI")]:
        response = await client.post(
            "/api/v1/stock/in",
            json={
                "item_id": item_id,
                "warehouse_id": wh_id,
                "quantity": adet,
                "unit_cost": maliyet,
                "batch_code": kod,
                "occurred_at": (now - dt.timedelta(days=gun_once)).isoformat(),
            },
            headers=admin_headers,
        )
        assert response.status_code == 201

    cikis = await client.post(
        "/api/v1/stock/out",
        json={"item_id": item_id, "warehouse_id": wh_id, "quantity": 1200},
        headers=admin_headers,
    )
    assert cikis.status_code == 201, cikis.text
    hareketler = cikis.json()
    # 1000 adet ESKI (8.0) + 200 adet YENI (12.0)
    assert len(hareketler) == 2
    assert hareketler[0]["unit_cost"] == 8.0
    assert abs(hareketler[0]["quantity"]) == 1000
    assert hareketler[1]["unit_cost"] == 12.0
    assert abs(hareketler[1]["quantity"]) == 200

    batches = await client.get(
        f"/api/v1/stock/batches?item_id={item_id}", headers=admin_headers
    )
    kalanlar = {b["batch_code"]: b["quantity"] for b in batches.json()}
    assert kalanlar == {"YENI": 800}


async def test_fefo_once_son_kullanma_tarihi_yakin_partiyi_tuketir(
    client: AsyncClient, admin_headers, stok_ortami
):
    item_id = stok_ortami["fefo"]["id"]
    wh_id = stok_ortami["depolar"]["Ana Depo"]["id"]
    today = dt.date.today()

    # Erken giren ama geç bozulan parti
    await client.post(
        "/api/v1/stock/in",
        json={
            "item_id": item_id, "warehouse_id": wh_id, "quantity": 10, "unit_cost": 1400,
            "batch_code": "GEC-BOZULAN",
            "occurred_at": (dt.datetime.now(dt.UTC) - dt.timedelta(days=60)).isoformat(),
            "expiry_date": (today + dt.timedelta(days=365)).isoformat(),
        },
        headers=admin_headers,
    )
    # Sonra giren ama erken bozulan parti
    await client.post(
        "/api/v1/stock/in",
        json={
            "item_id": item_id, "warehouse_id": wh_id, "quantity": 10, "unit_cost": 1500,
            "batch_code": "ERKEN-BOZULAN",
            "expiry_date": (today + dt.timedelta(days=30)).isoformat(),
        },
        headers=admin_headers,
    )

    cikis = await client.post(
        "/api/v1/stock/out",
        json={"item_id": item_id, "warehouse_id": wh_id, "quantity": 8},
        headers=admin_headers,
    )
    assert cikis.status_code == 201
    # FEFO: ERKEN-BOZULAN partisinden tüketilmeli (birim maliyet 1500)
    assert cikis.json()[0]["unit_cost"] == 1500.0

    batches = await client.get(
        f"/api/v1/stock/batches?item_id={item_id}", headers=admin_headers
    )
    kalanlar = {b["batch_code"]: b["quantity"] for b in batches.json()}
    assert kalanlar["ERKEN-BOZULAN"] == 2
    assert kalanlar["GEC-BOZULAN"] == 10


async def test_yetersiz_stok_reddedilir(client: AsyncClient, admin_headers, stok_ortami):
    response = await client.post(
        "/api/v1/stock/out",
        json={
            "item_id": stok_ortami["fifo"]["id"],
            "warehouse_id": stok_ortami["depolar"]["Ana Depo"]["id"],
            "quantity": 100,
        },
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "yeterli stok yok" in response.json()["detail"]


async def test_minimum_stok_altinda_uyari_uretilir(
    client: AsyncClient, admin_headers, stok_ortami
):
    item_id = stok_ortami["fifo"]["id"]
    wh_id = stok_ortami["depolar"]["Ana Depo"]["id"]
    await client.post(
        "/api/v1/stock/in",
        json={"item_id": item_id, "warehouse_id": wh_id, "quantity": 1200, "unit_cost": 10},
        headers=admin_headers,
    )
    await client.post(
        "/api/v1/stock/out",
        json={"item_id": item_id, "warehouse_id": wh_id, "quantity": 500},
        headers=admin_headers,
    )
    alerts = await client.get("/api/v1/alerts?category=stok", headers=admin_headers)
    assert any("Minimum stok altında" in a["title"] for a in alerts.json()["items"])

    dusuk = await client.get("/api/v1/stock/alerts/low", headers=admin_headers)
    assert any(x["item_id"] == item_id for x in dusuk.json())


async def test_depolar_arasi_transfer(client: AsyncClient, admin_headers, stok_ortami):
    item_id = stok_ortami["fifo"]["id"]
    kaynak = stok_ortami["depolar"]["Ana Depo"]["id"]
    hedef = stok_ortami["depolar"]["Yedek Depo"]["id"]

    await client.post(
        "/api/v1/stock/in",
        json={"item_id": item_id, "warehouse_id": kaynak, "quantity": 3000, "unit_cost": 10},
        headers=admin_headers,
    )
    response = await client.post(
        "/api/v1/stock/transfer",
        json={
            "item_id": item_id,
            "from_warehouse_id": kaynak,
            "to_warehouse_id": hedef,
            "quantity": 1200,
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    levels = await client.get("/api/v1/stock/levels", headers=admin_headers)
    kalem = next(x for x in levels.json() if x["item_id"] == item_id)
    assert kalem["on_hand"] == 3000  # toplam değişmez
    assert len(kalem["warehouses"]) == 2


async def test_ayni_depoya_transfer_reddedilir(client: AsyncClient, admin_headers, stok_ortami):
    wh = stok_ortami["depolar"]["Ana Depo"]["id"]
    response = await client.post(
        "/api/v1/stock/transfer",
        json={
            "item_id": stok_ortami["fifo"]["id"],
            "from_warehouse_id": wh,
            "to_warehouse_id": wh,
            "quantity": 10,
        },
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_sayim_farki_duzeltilir(client: AsyncClient, admin_headers, stok_ortami):
    item_id = stok_ortami["fifo"]["id"]
    wh_id = stok_ortami["depolar"]["Ana Depo"]["id"]
    await client.post(
        "/api/v1/stock/in",
        json={"item_id": item_id, "warehouse_id": wh_id, "quantity": 1000, "unit_cost": 10},
        headers=admin_headers,
    )
    response = await client.post(
        "/api/v1/stock/count",
        json={"item_id": item_id, "warehouse_id": wh_id, "counted_quantity": 940},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    levels = await client.get("/api/v1/stock/levels", headers=admin_headers)
    kalem = next(x for x in levels.json() if x["item_id"] == item_id)
    assert kalem["on_hand"] == 940


async def test_son_kullanma_tarihi_yaklasanlar(client: AsyncClient, admin_headers, stok_ortami):
    await client.post(
        "/api/v1/stock/in",
        json={
            "item_id": stok_ortami["fefo"]["id"],
            "warehouse_id": stok_ortami["depolar"]["Ana Depo"]["id"],
            "quantity": 5,
            "unit_cost": 1400,
            "expiry_date": (dt.date.today() + dt.timedelta(days=15)).isoformat(),
        },
        headers=admin_headers,
    )
    response = await client.get("/api/v1/stock/alerts/expiring?days=30", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["days_left"] == 15


# ----------------------------------------------------------------- SATINALMA
async def test_satin_alma_ve_mal_kabul(client: AsyncClient, admin_headers, stok_ortami):
    supplier = await client.post(
        "/api/v1/suppliers", json={"name": "Test Tedarikçi", "supplier_type": "ambalaj"},
        headers=admin_headers,
    )
    order = await client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier.json()["id"],
            "lines": [
                {"item_id": stok_ortami["fifo"]["id"], "quantity": 5000, "unit_price": 9.5}
            ],
        },
        headers=admin_headers,
    )
    assert order.status_code == 201, order.text
    body = order.json()
    assert body["subtotal"] == pytest.approx(47500.0)
    assert body["total"] == pytest.approx(57000.0)  # %20 KDV

    line_id = body["lines"][0]["id"]
    receive = await client.post(
        f"/api/v1/purchases/{body['id']}/receive",
        json={
            "warehouse_id": stok_ortami["depolar"]["Ana Depo"]["id"],
            "lines": [{"line_id": line_id, "quantity": 5000}],
        },
        headers=admin_headers,
    )
    assert receive.status_code == 200, receive.text
    assert receive.json()["status"] == "teslim_alindi"

    levels = await client.get("/api/v1/stock/levels", headers=admin_headers)
    kalem = next(x for x in levels.json() if x["item_id"] == stok_ortami["fifo"]["id"])
    assert kalem["on_hand"] == 5000


async def test_fazla_teslim_alma_reddedilir(client: AsyncClient, admin_headers, stok_ortami):
    supplier = await client.post(
        "/api/v1/suppliers", json={"name": "T2"}, headers=admin_headers
    )
    order = await client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier.json()["id"],
            "lines": [{"item_id": stok_ortami["fifo"]["id"], "quantity": 100, "unit_price": 5}],
        },
        headers=admin_headers,
    )
    response = await client.post(
        f"/api/v1/purchases/{order.json()['id']}/receive",
        json={
            "warehouse_id": stok_ortami["depolar"]["Ana Depo"]["id"],
            "lines": [{"line_id": order.json()["lines"][0]["id"], "quantity": 150}],
        },
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "kalan miktar" in response.json()["detail"]


# ------------------------------------------------------------------ SEVKİYAT
async def test_sevkiyat_akisi(client: AsyncClient, admin_headers, stok_ortami):
    item_id = stok_ortami["fifo"]["id"]
    wh_id = stok_ortami["depolar"]["Ana Depo"]["id"]
    await client.post(
        "/api/v1/stock/in",
        json={"item_id": item_id, "warehouse_id": wh_id, "quantity": 2000, "unit_cost": 10},
        headers=admin_headers,
    )
    customer = await client.post(
        "/api/v1/customers", json={"name": "Test Müşteri", "city": "İzmir"},
        headers=admin_headers,
    )
    shipment = await client.post(
        "/api/v1/shipments",
        json={
            "customer_id": customer.json()["id"],
            "warehouse_id": wh_id,
            "lines": [{"item_id": item_id, "quantity": 600, "unit_price": 120}],
        },
        headers=admin_headers,
    )
    assert shipment.status_code == 201, shipment.text
    assert shipment.json()["total"] == pytest.approx(72000.0)
    sid = shipment.json()["id"]

    ship = await client.post(f"/api/v1/shipments/{sid}/ship", headers=admin_headers)
    assert ship.status_code == 200
    assert ship.json()["status"] == "sevk_edildi"

    levels = await client.get("/api/v1/stock/levels", headers=admin_headers)
    kalem = next(x for x in levels.json() if x["item_id"] == item_id)
    assert kalem["on_hand"] == 1400

    deliver = await client.post(f"/api/v1/shipments/{sid}/deliver", headers=admin_headers)
    assert deliver.status_code == 200
    assert deliver.json()["status"] == "teslim_edildi"

    # Sevk edilmiş kayıt değiştirilemez
    edit = await client.patch(
        f"/api/v1/shipments/{sid}", json={"carrier": "X"}, headers=admin_headers
    )
    assert edit.status_code == 409


async def test_stoksuz_sevkiyat_olusturulamaz(client: AsyncClient, admin_headers, stok_ortami):
    customer = await client.post(
        "/api/v1/customers", json={"name": "Stoksuz Müşteri"}, headers=admin_headers
    )
    response = await client.post(
        "/api/v1/shipments",
        json={
            "customer_id": customer.json()["id"],
            "warehouse_id": stok_ortami["depolar"]["Ana Depo"]["id"],
            "lines": [{"item_id": stok_ortami["fifo"]["id"], "quantity": 10, "unit_price": 100}],
        },
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "yeterli stok yok" in response.json()["detail"]


async def test_stok_hareketleri_denetlenebilir(client: AsyncClient, admin_headers, stok_ortami):
    await client.post(
        "/api/v1/stock/in",
        json={
            "item_id": stok_ortami["fifo"]["id"],
            "warehouse_id": stok_ortami["depolar"]["Ana Depo"]["id"],
            "quantity": 100,
            "unit_cost": 10,
        },
        headers=admin_headers,
    )
    hareketler = await client.get("/api/v1/stock/movements", headers=admin_headers)
    assert hareketler.status_code == 200
    assert len(hareketler.json()) >= 1
    assert hareketler.json()[0]["item_name"] == "Şişe 750 ml"
    assert hareketler.json()[0]["performed_by_name"]
