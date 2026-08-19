"""Istatistik uclari: yetki ayrimi ve hesap dogrulugu.

En kritik nokta YETKI AYRIMIDIR. Tek bir `/statistics` ucu kullanilsaydi,
`report:read` tasiyan ama `cost:read`/`lab:read` TASIMAYAN roller (satis
personeli, depo/sevkiyat) maliyet ve laboratuvar verisini gorurdu. Bu yuzden
her konu kendi yetkisiyle korunur ve testler bunu rol rol dogrular.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services import istatistik

KONULAR = [
    ("hasat", "harvest:read"),
    ("fire", "lot:read"),
    ("fermantasyon", "fermentation:read"),
    ("laboratuvar", "lab:read"),
    ("siseleme", "bottling:read"),
    ("stok", "inventory:read"),
    ("bakim", "maintenance:read"),
    ("fici", "barrel:read"),
]


# ------------------------------------------------------------------ yardimci
def test_oran_sifira_bolmede_none_doner() -> None:
    """Veri yokken arayuz 'sonsuz' degil '—' gostermeli."""
    assert istatistik._oran(5, 0) is None
    assert istatistik._oran(0, 0) is None
    assert istatistik._oran(1, 4) == 0.25


def test_float_donusumu_none_guvenli() -> None:
    from decimal import Decimal

    assert istatistik._f(None) == 0.0
    assert istatistik._f(Decimal("12.50")) == 12.5


# ------------------------------------------------------------------ yetki
@pytest.mark.parametrize(("konu", "_yetki"), KONULAR)
async def test_kimliksiz_erisim_reddedilir(
    client: AsyncClient, konu: str, _yetki: str
) -> None:
    yanit = await client.get(f"/api/v1/statistics/{konu}")
    assert yanit.status_code == 401


@pytest.mark.parametrize(("konu", "_yetki"), KONULAR)
async def test_yonetici_tum_konulara_erisir(
    client: AsyncClient, admin_headers, konu: str, _yetki: str
) -> None:
    yanit = await client.get(f"/api/v1/statistics/{konu}", headers=admin_headers)
    assert yanit.status_code == 200, yanit.text
    assert isinstance(yanit.json(), dict)


async def test_satis_personeli_laboratuvar_istatistigini_goremez(
    client: AsyncClient, auth_headers
) -> None:
    """ASIL GEREKCE: tek bir /statistics ucu bu veriyi sizdirirdi."""
    basliklar = await auth_headers(["satis_personeli"], "satis_ist")

    yanit = await client.get("/api/v1/statistics/laboratuvar", headers=basliklar)
    assert yanit.status_code == 403

    # Buna karsilik kendi alanini gorebilmeli
    assert (
        await client.get("/api/v1/statistics/stok", headers=basliklar)
    ).status_code == 200


async def test_satis_personeli_hasat_istatistigini_goremez(
    client: AsyncClient, auth_headers
) -> None:
    basliklar = await auth_headers(["satis_personeli"], "satis_ist2")
    assert (
        await client.get("/api/v1/statistics/hasat", headers=basliklar)
    ).status_code == 403


async def test_laboratuvar_teknisyeni_kendi_alanini_gorur(
    client: AsyncClient, auth_headers
) -> None:
    basliklar = await auth_headers(["laboratuvar_teknisyeni"], "lab_ist")
    assert (
        await client.get("/api/v1/statistics/laboratuvar", headers=basliklar)
    ).status_code == 200
    # Stok yetkisi yok
    assert (
        await client.get("/api/v1/statistics/stok", headers=basliklar)
    ).status_code == 403


async def test_denetci_salt_okunur_olarak_hepsini_gorur(
    client: AsyncClient, auth_headers
) -> None:
    """Denetci tum `:read` yetkilerine sahiptir; istatistik okuma dogaldir."""
    basliklar = await auth_headers(["denetci"], "denetci_ist")
    for konu, _ in KONULAR:
        yanit = await client.get(f"/api/v1/statistics/{konu}", headers=basliklar)
        assert yanit.status_code == 200, f"{konu}: {yanit.status_code}"


# ------------------------------------------------------------------ yapi
async def test_hasat_beklenen_alanlari_dondurur(client: AsyncClient, admin_headers) -> None:
    veri = (await client.get("/api/v1/statistics/hasat", headers=admin_headers)).json()
    for alan in ("parseller", "cesitler", "kalite_dagilimi", "yillar"):
        assert alan in veri, f"{alan} eksik"
        assert isinstance(veri[alan], list)


async def test_fire_hunisi_tutarli(client: AsyncClient, admin_headers) -> None:
    veri = (await client.get("/api/v1/statistics/fire", headers=admin_headers)).json()
    assert [a["asama"] for a in veri["huni"]] == ["Üzüm (kg)", "Şıra (L)", "Şişelenen (L)"]
    ozet = veri["ozet"]
    for alan in ("uzum_kg", "sira_l", "sise_adet", "toplam_kayip_l"):
        assert alan in ozet
    # Veri yoksa oran None olmali, sifira bolme hatasi degil
    assert ozet["sira_verimi_l_kg"] is None or ozet["sira_verimi_l_kg"] >= 0


async def test_laboratuvar_tarih_araligi_yansitilir(
    client: AsyncClient, admin_headers
) -> None:
    yanit = await client.get(
        "/api/v1/statistics/laboratuvar",
        headers=admin_headers,
        params={"baslangic": "2026-01-01", "bitis": "2026-06-30"},
    )
    veri = yanit.json()
    assert veri["baslangic"] == "2026-01-01"
    assert veri["bitis"] == "2026-06-30"
    assert "spec_disi_orani" in veri["ozet"]


async def test_siseleme_oranlari_sql_de_hesaplanir(
    client: AsyncClient, admin_headers
) -> None:
    veri = (await client.get("/api/v1/statistics/siseleme", headers=admin_headers)).json()
    ozet = veri["ozet"]
    for alan in ("planlanan_sise", "uretilen_sise", "verim_orani", "fire_orani"):
        assert alan in ozet
    for alan in ("aylik", "ambalaj", "hatlar"):
        assert isinstance(veri[alan], list)


async def test_stok_donem_parametresi_gecerli(client: AsyncClient, admin_headers) -> None:
    veri = (
        await client.get(
            "/api/v1/statistics/stok", headers=admin_headers, params={"gun": 30}
        )
    ).json()
    assert veri["gun"] == 30
    assert "hareketsiz_sayisi" in veri


@pytest.mark.parametrize("gun", [0, 3, 5000])
async def test_stok_gecersiz_donem_reddedilir(
    client: AsyncClient, admin_headers, gun: int
) -> None:
    yanit = await client.get(
        "/api/v1/statistics/stok", headers=admin_headers, params={"gun": gun}
    )
    assert yanit.status_code == 422


async def test_gecersiz_yil_reddedilir(client: AsyncClient, admin_headers) -> None:
    yanit = await client.get(
        "/api/v1/statistics/hasat", headers=admin_headers, params={"yil": 1500}
    )
    assert yanit.status_code == 422


async def test_bakim_cip_orani_hesaplanir(client: AsyncClient, admin_headers) -> None:
    veri = (await client.get("/api/v1/statistics/bakim", headers=admin_headers)).json()
    assert "cip" in veri
    assert "dogrulama_orani" in veri["cip"]
    assert "geciken_bakim" in veri


async def test_fici_doluluk_orani_hesaplanir(client: AsyncClient, admin_headers) -> None:
    veri = (await client.get("/api/v1/statistics/fici", headers=admin_headers)).json()
    assert "doluluk_orani" in veri["ozet"]
    assert isinstance(veri["yas_dagilimi"], list)


# ---------------------------------------------------- uretim raporu duzeltmesi
async def test_uretim_verimi_tarih_penceresine_uyar(
    client: AsyncClient, admin_headers
) -> None:
    """Gerileme: sira hacmi tarih filtresizdi ve verim oraninı 10 kata sisiriyordu.

    Cok dar bir pencerede uzum kabulu yoksa verim de sifir olmali; veritabanindaki
    TUM sira hacmi burada gorunmemeli.
    """
    yanit = await client.get(
        "/api/v1/reports/production",
        headers=admin_headers,
        params={"start": "1990-01-01", "end": "1990-01-02"},
    )
    assert yanit.status_code == 200
    veri = yanit.json()
    assert veri["intake_kg"] == 0
    assert veri.get("juice_l", 0) == 0, (
        "Şıra hacmi tarih filtresine uymuyor — verim oranı şişer"
    )
