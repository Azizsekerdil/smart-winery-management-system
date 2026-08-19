"""Uçtan uca şaraphane iş akışı: üzüm kabulü → parti → tank → fermantasyon
→ laboratuvar → fıçı → şişeleme, ve tam izlenebilirlik."""

from __future__ import annotations

import datetime as dt

import pytest
from httpx import AsyncClient


@pytest.fixture
async def temel_veri(client: AsyncClient, admin_headers):
    """Test için minimum referans verisi kurar."""
    variety = await client.post(
        "/api/v1/varieties",
        json={"name": "Öküzgözü", "color": "kirmizi", "origin": "Elazığ"},
        headers=admin_headers,
    )
    assert variety.status_code == 201, variety.text

    vineyard = await client.post(
        "/api/v1/vineyards",
        json={"name": "Test Bağı", "region": "Ege", "altitude_m": 450},
        headers=admin_headers,
    )
    assert vineyard.status_code == 201, vineyard.text

    parcel = await client.post(
        "/api/v1/parcels",
        json={
            "name": "Parsel A",
            "vineyard_id": vineyard.json()["id"],
            "variety_id": variety.json()["id"],
            "area_da": 25.0,
        },
        headers=admin_headers,
    )
    assert parcel.status_code == 201, parcel.text

    tanks = []
    for cap in (10000, 10000, 5000):
        t = await client.post(
            "/api/v1/tanks",
            json={"capacity_l": cap, "tank_type": "paslanmaz_celik", "zone": "A"},
            headers=admin_headers,
        )
        assert t.status_code == 201, t.text
        tanks.append(t.json())

    return {
        "variety": variety.json(),
        "vineyard": vineyard.json(),
        "parcel": parcel.json(),
        "tanks": tanks,
    }


async def _intake(client, headers, temel, kg=10000, brix=23.5):
    response = await client.post(
        "/api/v1/harvest-intakes",
        json={
            "vineyard_id": temel["vineyard"]["id"],
            "parcel_id": temel["parcel"]["id"],
            "variety_id": temel["variety"]["id"],
            "harvest_date": dt.date.today().isoformat(),
            "net_weight_kg": kg,
            "brix": brix,
            "ph": 3.5,
            "total_acidity": 6.0,
            "quality_grade": "A",
            "unit_price": 18.5,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


# ------------------------------------------------------------ ÜZÜM KABULÜ
async def test_uzum_kabul_kaydi(client: AsyncClient, admin_headers, temel_veri):
    intake = await _intake(client, admin_headers, temel_veri)
    assert intake["code"].startswith("UZK-")
    assert intake["net_weight_kg"] == 10000
    assert intake["total_cost"] == pytest.approx(185000.0)
    assert intake["variety_name"] == "Öküzgözü"


async def test_uzum_kabul_agirlik_tutarsizligi_reddedilir(
    client: AsyncClient, admin_headers, temel_veri
):
    response = await client.post(
        "/api/v1/harvest-intakes",
        json={
            "variety_id": temel_veri["variety"]["id"],
            "harvest_date": dt.date.today().isoformat(),
            "gross_weight_kg": 14000,
            "tare_weight_kg": 4000,
            "net_weight_kg": 9000,  # 14000-4000 = 10000 olmalı
        },
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert "Net ağırlık" in response.text


async def test_uzum_kabul_qr_uretimi(client: AsyncClient, admin_headers, temel_veri):
    intake = await _intake(client, admin_headers, temel_veri)
    final = await client.post(
        f"/api/v1/harvest-intakes/{intake['id']}/finalize", headers=admin_headers
    )
    assert final.status_code == 200
    assert final.json()["qr_payload"].startswith("saraphane://uzum-kabul/")

    png = await client.get(f"/api/v1/harvest-intakes/{intake['id']}/qr.png", headers=admin_headers)
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"


# ------------------------------------------------------------------ PARTİ
async def test_partiye_donusturme_ve_izlenebilirlik(
    client: AsyncClient, admin_headers, temel_veri
):
    intake1 = await _intake(client, admin_headers, temel_veri, kg=12000)
    intake2 = await _intake(client, admin_headers, temel_veri, kg=8000, brix=24.1)

    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "Öküzgözü 2026",
            "wine_type": "kirmizi",
            "volume_l": 14000,
            "current_tank_id": temel_veri["tanks"][0]["id"],
            "sources": [
                {"intake_id": intake1["id"], "weight_kg": 12000, "juice_yield_l": 8400},
                {"intake_id": intake2["id"], "weight_kg": 8000, "juice_yield_l": 5600},
            ],
        },
        headers=admin_headers,
    )
    assert lot.status_code == 201, lot.text
    lot_id = lot.json()["id"]
    assert lot.json()["qr_payload"].startswith("saraphane://parti/")

    trace = await client.get(f"/api/v1/lots/{lot_id}/trace?direction=geri", headers=admin_headers)
    assert trace.status_code == 200
    graph = trace.json()
    kabul_dugumleri = [n for n in graph["nodes"] if n["kind"] == "uzum_kabul"]
    assert len(kabul_dugumleri) == 2
    assert {n["code"] for n in kabul_dugumleri} == {intake1["code"], intake2["code"]}

    timeline = await client.get(f"/api/v1/lots/{lot_id}/timeline", headers=admin_headers)
    assert timeline.status_code == 200
    assert any(e["event_type"] == "olusturma" for e in timeline.json())


async def test_parti_bolme_izlenebilirligi_korur(client: AsyncClient, admin_headers, temel_veri):
    intake = await _intake(client, admin_headers, temel_veri, kg=15000)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "Bölünecek Parti",
            "volume_l": 10000,
            "current_tank_id": temel_veri["tanks"][0]["id"],
            "sources": [{"intake_id": intake["id"], "weight_kg": 15000}],
        },
        headers=admin_headers,
    )
    parent_id = lot.json()["id"]

    split = await client.post(
        f"/api/v1/lots/{parent_id}/split",
        json={
            "volume_l": 3000,
            "new_lot_name": "Alt Parti",
            "target_tank_id": temel_veri["tanks"][1]["id"],
        },
        headers=admin_headers,
    )
    assert split.status_code == 200, split.text
    child_id = split.json()["id"]
    assert split.json()["volume_l"] == 3000

    parent = await client.get(f"/api/v1/lots/{parent_id}", headers=admin_headers)
    assert parent.json()["volume_l"] == 7000

    # Alt partiden geriye izleme üst partiyi ve üzüm kabulünü göstermeli
    trace = await client.get(f"/api/v1/lots/{child_id}/trace?direction=geri", headers=admin_headers)
    kinds = {n["kind"] for n in trace.json()["nodes"]}
    assert "parti" in kinds
    assert "uzum_kabul" in kinds


async def test_asiri_bolme_reddedilir(client: AsyncClient, admin_headers, temel_veri):
    intake = await _intake(client, admin_headers, temel_veri)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "Küçük Parti",
            "volume_l": 1000,
            "sources": [{"intake_id": intake["id"], "weight_kg": 1500}],
        },
        headers=admin_headers,
    )
    response = await client.post(
        f"/api/v1/lots/{lot.json()['id']}/split",
        json={"volume_l": 1500, "new_lot_name": "Olmaz"},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "küçük olmalıdır" in response.json()["detail"]


# ------------------------------------------------------------- TANK TRANSFER
async def test_tank_transferi_hacimleri_gunceller(client: AsyncClient, admin_headers, temel_veri):
    intake = await _intake(client, admin_headers, temel_veri)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "Transfer Partisi",
            "volume_l": 6000,
            "current_tank_id": temel_veri["tanks"][0]["id"],
            "sources": [{"intake_id": intake["id"], "weight_kg": 9000}],
        },
        headers=admin_headers,
    )
    lot_id = lot.json()["id"]

    transfer = await client.post(
        "/api/v1/transfers",
        json={
            "transfer_type": "tank_arasi",
            "lot_id": lot_id,
            "from_tank_id": temel_veri["tanks"][0]["id"],
            "to_tank_id": temel_veri["tanks"][1]["id"],
            "volume_l": 6000,
            "loss_l": 25,
        },
        headers=admin_headers,
    )
    assert transfer.status_code == 201, transfer.text

    lot_after = await client.get(f"/api/v1/lots/{lot_id}", headers=admin_headers)
    assert lot_after.json()["current_tank_id"] == temel_veri["tanks"][1]["id"]
    assert lot_after.json()["volume_l"] == 5975

    t0 = await client.get(f"/api/v1/tanks/{temel_veri['tanks'][0]['id']}", headers=admin_headers)
    assert t0.json()["current_volume_l"] == 0
    assert t0.json()["status"] == "bos"

    t1 = await client.get(f"/api/v1/tanks/{temel_veri['tanks'][1]['id']}", headers=admin_headers)
    assert t1.json()["current_volume_l"] == 5975


async def test_kapasite_asimi_reddedilir(client: AsyncClient, admin_headers, temel_veri):
    intake = await _intake(client, admin_headers, temel_veri, kg=20000)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "Büyük Parti",
            "volume_l": 9000,
            "current_tank_id": temel_veri["tanks"][0]["id"],
            "sources": [{"intake_id": intake["id"], "weight_kg": 20000}],
        },
        headers=admin_headers,
    )
    response = await client.post(
        "/api/v1/transfers",
        json={
            "transfer_type": "tank_arasi",
            "lot_id": lot.json()["id"],
            "from_tank_id": temel_veri["tanks"][0]["id"],
            "to_tank_id": temel_veri["tanks"][2]["id"],  # 5000 L kapasiteli
            "volume_l": 9000,
        },
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "kapasite" in response.json()["detail"].lower()


async def test_ayni_tanka_transfer_reddedilir(client: AsyncClient, admin_headers, temel_veri):
    intake = await _intake(client, admin_headers, temel_veri)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "Aynı Tank Testi",
            "volume_l": 1000,
            "sources": [{"intake_id": intake["id"], "weight_kg": 1500}],
        },
        headers=admin_headers,
    )
    response = await client.post(
        "/api/v1/transfers",
        json={
            "lot_id": lot.json()["id"],
            "from_tank_id": temel_veri["tanks"][0]["id"],
            "to_tank_id": temel_veri["tanks"][0]["id"],
            "volume_l": 100,
        },
        headers=admin_headers,
    )
    assert response.status_code == 422


# ------------------------------------------------------------ FERMANTASYON
@pytest.fixture
async def fermantasyon(client: AsyncClient, admin_headers, temel_veri):
    intake = await _intake(client, admin_headers, temel_veri, kg=12000)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "Ferm Partisi",
            "volume_l": 8000,
            "current_tank_id": temel_veri["tanks"][0]["id"],
            "sources": [{"intake_id": intake["id"], "weight_kg": 12000}],
        },
        headers=admin_headers,
    )
    ferm = await client.post(
        "/api/v1/fermentations/start",
        json={
            "lot_id": lot.json()["id"],
            "tank_id": temel_veri["tanks"][0]["id"],
            "initial_brix": 23.5,
            "target_brix": -1.0,
            "temp_min_c": 24,
            "temp_max_c": 29,
            "yeast_strain": "EC-1118",
            "volume_l": 8000,
        },
        headers=admin_headers,
    )
    assert ferm.status_code == 201, ferm.text
    return {"lot": lot.json(), "ferm": ferm.json()}


async def test_fermantasyon_baslatma(client: AsyncClient, admin_headers, fermantasyon):
    assert fermantasyon["ferm"]["status"] == "devam_ediyor"
    lot = await client.get(f"/api/v1/lots/{fermantasyon['lot']['id']}", headers=admin_headers)
    assert lot.json()["stage"] == "fermantasyon"


async def test_ayni_partide_ikinci_fermantasyon_reddedilir(
    client: AsyncClient, admin_headers, fermantasyon
):
    response = await client.post(
        "/api/v1/fermentations/start",
        json={"lot_id": fermantasyon["lot"]["id"], "initial_brix": 23, "target_brix": -1},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "devam eden" in response.json()["detail"]


async def test_olcum_girisi_ve_egri(client: AsyncClient, admin_headers, fermantasyon):
    ferm_id = fermantasyon["ferm"]["id"]
    now = dt.datetime.now(dt.UTC)
    brix_values = [23.5, 20.1, 15.4, 9.8, 4.2, 0.5]
    for i, brix in enumerate(brix_values):
        response = await client.post(
            f"/api/v1/fermentations/{ferm_id}/readings",
            json={
                "measured_at": (now - dt.timedelta(days=len(brix_values) - i)).isoformat(),
                "temperature_c": 26.5,
                "brix": brix,
                "density": 1 + brix * 0.004,
                "ph": 3.5,
            },
            headers=admin_headers,
        )
        assert response.status_code == 201, response.text

    curve = await client.get(f"/api/v1/fermentations/{ferm_id}/curve", headers=admin_headers)
    assert curve.status_code == 200
    body = curve.json()
    assert len(body["labels"]) == len(brix_values)
    assert body["brix"] == brix_values
    assert body["target_brix"] == -1.0
    assert body["predicted_end_date"] is not None


async def test_sicaklik_asimi_uyari_uretir(client: AsyncClient, admin_headers, fermantasyon):
    ferm_id = fermantasyon["ferm"]["id"]
    response = await client.post(
        f"/api/v1/fermentations/{ferm_id}/readings",
        json={"temperature_c": 34.5, "brix": 20.0},
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["is_anomaly"] is True
    assert "Sıcaklık üst sınırın üzerinde" in response.json()["anomaly_reason"]

    alerts = await client.get("/api/v1/alerts?category=fermantasyon", headers=admin_headers)
    assert alerts.status_code == 200
    assert any("sıcaklık" in a["title"].lower() for a in alerts.json()["items"])


async def test_hedef_brixe_ulasinca_otomatik_tamamlanir(
    client: AsyncClient, admin_headers, fermantasyon
):
    ferm_id = fermantasyon["ferm"]["id"]
    await client.post(
        f"/api/v1/fermentations/{ferm_id}/readings",
        json={"temperature_c": 26, "brix": -1.2},
        headers=admin_headers,
    )
    ferm = await client.get(f"/api/v1/fermentations/{ferm_id}", headers=admin_headers)
    assert ferm.json()["status"] == "tamamlandi"

    lot = await client.get(f"/api/v1/lots/{fermantasyon['lot']['id']}", headers=admin_headers)
    assert lot.json()["stage"] == "dinlendirme"


async def test_bos_olcum_reddedilir(client: AsyncClient, admin_headers, fermantasyon):
    response = await client.post(
        f"/api/v1/fermentations/{fermantasyon['ferm']['id']}/readings",
        json={"notes": "sadece not"},
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_katki_maddesi_ekleme(client: AsyncClient, admin_headers, fermantasyon):
    response = await client.post(
        f"/api/v1/fermentations/{fermantasyon['ferm']['id']}/additives",
        json={
            "additive_name": "Potasyum metabisülfit",
            "additive_type": "koruyucu",
            "amount": 400,
            "unit": "g",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    liste = await client.get(
        f"/api/v1/fermentations/{fermantasyon['ferm']['id']}/additives", headers=admin_headers
    )
    assert len(liste.json()) == 1


# ------------------------------------------------------------ LABORATUVAR
async def test_laboratuvar_onay_akisi(client: AsyncClient, auth_headers, admin_headers, temel_veri):
    intake = await _intake(client, admin_headers, temel_veri)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "Lab Partisi",
            "volume_l": 5000,
            "sources": [{"intake_id": intake["id"], "weight_kg": 7000}],
        },
        headers=admin_headers,
    )
    lot_id = lot.json()["id"]

    lab_headers = await auth_headers(["laboratuvar_teknisyeni"], "labtek")
    sample = await client.post(
        "/api/v1/lab/samples", json={"lot_id": lot_id}, headers=lab_headers
    )
    assert sample.status_code == 201, sample.text

    result = await client.post(
        f"/api/v1/lab/samples/{sample.json()['id']}/results",
        json={"ph": 3.55, "total_acidity": 5.8, "volatile_acidity": 0.42, "free_so2": 32,
              "total_so2": 95, "alcohol": 13.2},
        headers=lab_headers,
    )
    assert result.status_code == 201, result.text
    result_id = result.json()["id"]
    assert result.json()["approval_status"] == "bekliyor"
    assert result.json()["out_of_spec"] is False

    # Teknisyen onaylayamaz
    denied = await client.post(
        f"/api/v1/lab/results/{result_id}/approval",
        json={"approve": True},
        headers=lab_headers,
    )
    assert denied.status_code == 403

    # Enolog onaylar
    enolog_headers = await auth_headers(["enolog"], "enolog_lab")
    approved = await client.post(
        f"/api/v1/lab/results/{result_id}/approval",
        json={"approve": True},
        headers=enolog_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "onaylandi"

    # Onaylanmış sonuç değiştirilemez
    edit = await client.patch(
        f"/api/v1/lab/results/{result_id}", json={"ph": 3.9}, headers=lab_headers
    )
    assert edit.status_code == 409


async def test_spesifikasyon_disi_sonuc_uyari_uretir(
    client: AsyncClient, admin_headers, temel_veri
):
    await client.post(
        "/api/v1/lab/specs",
        json={
            "parameter": "volatile_acidity",
            "min_value": 0.0,
            "max_value": 0.9,
            "unit": "g/L",
            "severity": "kritik",
            "label_tr": "Uçucu asitlik",
        },
        headers=admin_headers,
    )
    intake = await _intake(client, admin_headers, temel_veri)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={"name": "Riskli", "volume_l": 3000,
              "sources": [{"intake_id": intake["id"], "weight_kg": 4500}]},
        headers=admin_headers,
    )
    sample = await client.post(
        "/api/v1/lab/samples", json={"lot_id": lot.json()["id"]}, headers=admin_headers
    )
    result = await client.post(
        f"/api/v1/lab/samples/{sample.json()['id']}/results",
        json={"volatile_acidity": 1.35, "ph": 3.6},
        headers=admin_headers,
    )
    assert result.status_code == 201
    assert result.json()["out_of_spec"] is True
    assert "Uçucu asitlik" in result.json()["out_of_spec_details"]

    alerts = await client.get("/api/v1/alerts?category=lab", headers=admin_headers)
    assert any("Spesifikasyon dışı" in a["title"] for a in alerts.json()["items"])


async def test_so2_tutarsizligi_reddedilir(client: AsyncClient, admin_headers, temel_veri):
    intake = await _intake(client, admin_headers, temel_veri)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={"name": "SO2 Testi", "volume_l": 1000,
              "sources": [{"intake_id": intake["id"], "weight_kg": 1500}]},
        headers=admin_headers,
    )
    sample = await client.post(
        "/api/v1/lab/samples", json={"lot_id": lot.json()["id"]}, headers=admin_headers
    )
    response = await client.post(
        f"/api/v1/lab/samples/{sample.json()['id']}/results",
        json={"free_so2": 60, "total_so2": 40},
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert "Serbest SO₂" in response.text


# ------------------------------------------------------- KUPAJ VE ŞİŞELEME
async def test_kupaj_ve_izlenebilirlik(client: AsyncClient, admin_headers, temel_veri):
    lots = []
    for i in range(2):
        intake = await _intake(client, admin_headers, temel_veri, kg=9000)
        lot = await client.post(
            "/api/v1/lots/with-sources",
            json={
                "name": f"Kupaj Bileşeni {i + 1}",
                "volume_l": 4000,
                "current_tank_id": temel_veri["tanks"][i]["id"],
                "sources": [{"intake_id": intake["id"], "weight_kg": 9000}],
            },
            headers=admin_headers,
        )
        lots.append(lot.json())

    blend = await client.post(
        "/api/v1/blends",
        json={
            "name": "Test Kupajı",
            "components": [
                {"source_lot_id": lots[0]["id"], "volume_l": 2500},
                {"source_lot_id": lots[1]["id"], "volume_l": 1500},
            ],
        },
        headers=admin_headers,
    )
    assert blend.status_code == 201, blend.text
    blend_id = blend.json()["id"]
    assert blend.json()["planned_volume_l"] == 4000
    assert blend.json()["components"][0]["percentage"] == pytest.approx(62.5)

    # Onaysız uygulama reddedilir
    early = await client.post(
        f"/api/v1/blends/{blend_id}/execute",
        json={"result_lot_name": "Erken"},
        headers=admin_headers,
    )
    assert early.status_code == 409
    assert "onayı gereklidir" in early.json()["detail"]

    approve = await client.post(
        f"/api/v1/blends/{blend_id}/approval", json={"approve": True}, headers=admin_headers
    )
    assert approve.status_code == 200

    execute = await client.post(
        f"/api/v1/blends/{blend_id}/execute",
        json={"result_lot_name": "Kupaj Sonucu", "target_tank_id": temel_veri["tanks"][2]["id"]},
        headers=admin_headers,
    )
    assert execute.status_code == 200, execute.text
    result_lot = execute.json()
    assert result_lot["is_blend"] is True
    assert result_lot["volume_l"] == 4000

    trace = await client.get(
        f"/api/v1/lots/{result_lot['id']}/trace?direction=geri", headers=admin_headers
    )
    graph = trace.json()
    parti_kodlari = {n["code"] for n in graph["nodes"] if n["kind"] == "parti"}
    assert lots[0]["code"] in parti_kodlari
    assert lots[1]["code"] in parti_kodlari
    assert len([n for n in graph["nodes"] if n["kind"] == "uzum_kabul"]) == 2

    # Kaynak partilerin hacmi düştü
    kaynak = await client.get(f"/api/v1/lots/{lots[0]['id']}", headers=admin_headers)
    assert kaynak.json()["volume_l"] == 1500


async def test_siseleme_tam_akis_ve_stok(client: AsyncClient, admin_headers, temel_veri):
    # Depo ve ambalaj stoğu
    warehouse = await client.post(
        "/api/v1/warehouses", json={"name": "Ana Depo"}, headers=admin_headers
    )
    wh_id = warehouse.json()["id"]

    items = {}
    for name, code_key, qty in [
        ("Şişe 750ml", "sise", 10000),
        ("Mantar", "mantar", 10000),
        ("Etiket", "etiket", 10000),
    ]:
        item = await client.post(
            "/api/v1/items",
            json={"name": name, "category": "ambalaj", "unit": "adet", "min_stock": 500},
            headers=admin_headers,
        )
        items[code_key] = item.json()
        stok = await client.post(
            "/api/v1/stock/in",
            json={
                "item_id": item.json()["id"],
                "warehouse_id": wh_id,
                "quantity": qty,
                "unit_cost": 5.0,
            },
            headers=admin_headers,
        )
        assert stok.status_code == 201, stok.text

    intake = await _intake(client, admin_headers, temel_veri, kg=8000)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "Şişelenecek Parti",
            "volume_l": 3000,
            "current_tank_id": temel_veri["tanks"][2]["id"],
            "sources": [{"intake_id": intake["id"], "weight_kg": 8000}],
        },
        headers=admin_headers,
    )
    lot_id = lot.json()["id"]

    order = await client.post(
        "/api/v1/bottling/orders",
        json={
            "lot_id": lot_id,
            "product_name": "Test Şarabı",
            "planned_bottles": 3000,
            "bottle_volume_ml": 750,
            "bottle_item_id": items["sise"]["id"],
            "closure_item_id": items["mantar"]["id"],
            "label_item_id": items["etiket"]["id"],
        },
        headers=admin_headers,
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]
    assert order.json()["lot_number"]

    # Başlatmadan bitirilemez
    early = await client.post(
        f"/api/v1/bottling/{order_id}/finish",
        json={"produced_bottles": 100},
        headers=admin_headers,
    )
    assert early.status_code == 409

    start = await client.post(
        f"/api/v1/bottling/{order_id}/start", json={}, headers=admin_headers
    )
    assert start.status_code == 200

    finish = await client.post(
        f"/api/v1/bottling/{order_id}/finish",
        json={
            "produced_bottles": 3900,
            "rejected_bottles": 20,
            "loss_l": 15,
            "qc_passed": True,
            "target_warehouse_id": wh_id,
        },
        headers=admin_headers,
    )
    assert finish.status_code == 200, finish.text
    body = finish.json()
    assert body["status"] == "tamamlandi"
    assert body["produced_bottles"] == 3900

    # Ambalaj stoğu tüketildi
    levels = await client.get("/api/v1/stock/levels", headers=admin_headers)
    sise = next(x for x in levels.json() if x["item_id"] == items["sise"]["id"])
    assert sise["on_hand"] == 10000 - 3920  # üretilen + red

    # Bitmiş ürün stoğa girdi
    bitmis = [x for x in levels.json() if x["category"] == "bitmis_urun"]
    assert len(bitmis) == 1
    assert bitmis[0]["on_hand"] == 3900

    # İleriye izleme şişeleme emrini göstermeli
    trace = await client.get(f"/api/v1/lots/{lot_id}/trace?direction=ileri", headers=admin_headers)
    assert any(n["kind"] == "siseleme" for n in trace.json()["nodes"])

    # Etiket önizleme
    label = await client.get(
        f"/api/v1/bottling/{order_id}/label-preview", headers=admin_headers
    )
    assert label.status_code == 200
    assert label.json()["lot_number"] == body["lot_number"]
    assert "18 yaşından küçüklere" in label.json()["warning_tr"]


async def test_siseleme_hacim_asimi_reddedilir(client: AsyncClient, admin_headers, temel_veri):
    intake = await _intake(client, admin_headers, temel_veri)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={"name": "Az Hacim", "volume_l": 500,
              "sources": [{"intake_id": intake["id"], "weight_kg": 800}]},
        headers=admin_headers,
    )
    response = await client.post(
        "/api/v1/bottling/orders",
        json={
            "lot_id": lot.json()["id"],
            "product_name": "Olmaz",
            "planned_bottles": 5000,  # 3750 L > 500 L
        },
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "aşıyor" in response.json()["detail"]


# ------------------------------------------------------------------ FIÇI
async def test_fici_dolum_bosaltim(client: AsyncClient, admin_headers, temel_veri):
    barrel = await client.post(
        "/api/v1/barrels",
        json={"oak_type": "fransiz", "capacity_l": 225, "cellar_zone": "Mahzen A"},
        headers=admin_headers,
    )
    assert barrel.status_code == 201
    barrel_id = barrel.json()["id"]

    intake = await _intake(client, admin_headers, temel_veri)
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={"name": "Fıçı Partisi", "volume_l": 1000,
              "current_tank_id": temel_veri["tanks"][0]["id"],
              "sources": [{"intake_id": intake["id"], "weight_kg": 1500}]},
        headers=admin_headers,
    )

    fill = await client.post(
        f"/api/v1/barrels/{barrel_id}/movements",
        json={"movement_type": "dolum", "lot_id": lot.json()["id"], "volume_l": 220},
        headers=admin_headers,
    )
    assert fill.status_code == 201, fill.text

    after = await client.get(f"/api/v1/barrels/{barrel_id}", headers=admin_headers)
    assert after.json()["status"] == "dolu"
    assert after.json()["current_volume_l"] == 220
    assert after.json()["fill_count"] == 1

    overfill = await client.post(
        f"/api/v1/barrels/{barrel_id}/movements",
        json={"movement_type": "dolum", "lot_id": lot.json()["id"], "volume_l": 100},
        headers=admin_headers,
    )
    assert overfill.status_code == 409
    assert "boş hacim" in overfill.json()["detail"]

    empty = await client.post(
        f"/api/v1/barrels/{barrel_id}/movements",
        json={"movement_type": "bosaltim", "volume_l": 220},
        headers=admin_headers,
    )
    assert empty.status_code == 201
    final = await client.get(f"/api/v1/barrels/{barrel_id}", headers=admin_headers)
    assert final.json()["status"] == "bos"


async def test_mahzen_haritasi(client: AsyncClient, admin_headers):
    for i in range(3):
        await client.post(
            "/api/v1/barrels",
            json={"oak_type": "amerikan", "cellar_zone": f"Mahzen {i % 2}"},
            headers=admin_headers,
        )
    response = await client.get("/api/v1/barrels/cellar/map", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total_barrels"] == 3
    assert len(response.json()["zones"]) == 2


# ------------------------------------------------------------------ PANO
async def test_kontrol_paneli(client: AsyncClient, admin_headers, fermantasyon):
    response = await client.get("/api/v1/dashboard", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["kpis"]) >= 6
    assert len(body["active_fermentations"]) == 1
    assert body["active_fermentations"][0]["code"] == fermantasyon["ferm"]["code"]
    assert isinstance(body["tank_fills"], list)
    assert isinstance(body["ai_suggestions"], list)
