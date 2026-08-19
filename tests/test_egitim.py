"""Egitim modulu ilerleme takibi.

En kritik nokta IZOLASYONDUR: bir kullanici yalnizca KENDI ilerlemesini
gorebilmeli ve yazabilmelidir. Ekip ozeti ise yonetici yetkisi ister; gida
guvenligi denetiminde "personel egitildi mi" sorusunun cevabi budur.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def test_kimliksiz_erisim_reddedilir(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/training/progress")).status_code == 401
    assert (
        await client.post(
            "/api/v1/training/progress/giris",
            json={"correct_count": 1, "question_count": 1},
        )
    ).status_code == 401


async def test_baslangicta_ilerleme_bos(client: AsyncClient, admin_headers) -> None:
    yanit = await client.get("/api/v1/training/progress", headers=admin_headers)
    assert yanit.status_code == 200
    assert yanit.json() == []


async def test_sonuc_kaydedilir_ve_puan_hesaplanir(
    client: AsyncClient, admin_headers
) -> None:
    yanit = await client.post(
        "/api/v1/training/progress/uzum-kabulu",
        json={"correct_count": 3, "question_count": 4},
        headers=admin_headers,
    )
    assert yanit.status_code == 200, yanit.text
    v = yanit.json()
    assert v["module_code"] == "uzum-kabulu"
    assert v["score_percent"] == 75.0
    assert v["passed"] is True
    assert v["attempt_count"] == 1
    assert v["completed_at"] is not None


async def test_esik_altinda_gecmez(client: AsyncClient, admin_headers) -> None:
    """%70 esigi: 4 soruda 2 dogru gecmemeli."""
    v = (
        await client.post(
            "/api/v1/training/progress/tank-yonetimi",
            json={"correct_count": 2, "question_count": 4},
            headers=admin_headers,
        )
    ).json()
    assert v["score_percent"] == 50.0
    assert v["passed"] is False
    assert v["completed_at"] is None


async def test_daha_dusuk_ikinci_deneme_basariyi_silmez(
    client: AsyncClient, admin_headers
) -> None:
    """Tekrar deneyip dusuk puan almak, kazanilmis basariyi goturmemeli."""
    await client.post(
        "/api/v1/training/progress/lab-onay",
        json={"correct_count": 4, "question_count": 4},
        headers=admin_headers,
    )
    v = (
        await client.post(
            "/api/v1/training/progress/lab-onay",
            json={"correct_count": 1, "question_count": 4},
            headers=admin_headers,
        )
    ).json()

    assert v["correct_count"] == 4, "En iyi sonuç korunmadı"
    assert v["score_percent"] == 100.0
    assert v["passed"] is True
    assert v["attempt_count"] == 2, "Deneme sayısı artmalı"


async def test_daha_yuksek_ikinci_deneme_kaydedilir(
    client: AsyncClient, admin_headers
) -> None:
    await client.post(
        "/api/v1/training/progress/fici",
        json={"correct_count": 1, "question_count": 4},
        headers=admin_headers,
    )
    v = (
        await client.post(
            "/api/v1/training/progress/fici",
            json={"correct_count": 4, "question_count": 4},
            headers=admin_headers,
        )
    ).json()
    assert v["score_percent"] == 100.0
    assert v["passed"] is True


async def test_tekrar_kayit_yeni_satir_acmaz(
    client: AsyncClient, admin_headers
) -> None:
    for _ in range(3):
        await client.post(
            "/api/v1/training/progress/stok",
            json={"correct_count": 2, "question_count": 3},
            headers=admin_headers,
        )
    liste = (await client.get("/api/v1/training/progress", headers=admin_headers)).json()
    stok = [k for k in liste if k["module_code"] == "stok"]
    assert len(stok) == 1, "Aynı modül için birden fazla kayıt açılmış"
    assert stok[0]["attempt_count"] == 3


@pytest.mark.parametrize(
    ("dogru", "toplam"),
    [(5, 4), (-1, 4), (0, 0), (1, 200)],
)
async def test_gecersiz_sonuc_reddedilir(
    client: AsyncClient, admin_headers, dogru: int, toplam: int
) -> None:
    yanit = await client.post(
        "/api/v1/training/progress/deneme",
        json={"correct_count": dogru, "question_count": toplam},
        headers=admin_headers,
    )
    assert yanit.status_code == 422


async def test_kullanicilar_birbirinin_ilerlemesini_gormez(
    client: AsyncClient, admin_headers, auth_headers
) -> None:
    """ASIL IZOLASYON TESTI."""
    await client.post(
        "/api/v1/training/progress/gizli-modul",
        json={"correct_count": 4, "question_count": 4},
        headers=admin_headers,
    )

    baskasi = await auth_headers(["enolog"], "enolog_egitim")
    liste = (await client.get("/api/v1/training/progress", headers=baskasi)).json()
    assert liste == [], "Başka kullanıcının ilerlemesi sızdı"


async def test_ayni_modul_farkli_kullanicilarda_bagimsiz(
    client: AsyncClient, admin_headers, auth_headers
) -> None:
    baskasi = await auth_headers(["enolog"], "enolog_egitim2")
    await client.post(
        "/api/v1/training/progress/ortak",
        json={"correct_count": 4, "question_count": 4},
        headers=admin_headers,
    )
    await client.post(
        "/api/v1/training/progress/ortak",
        json={"correct_count": 1, "question_count": 4},
        headers=baskasi,
    )

    benim = (await client.get("/api/v1/training/progress", headers=admin_headers)).json()
    onun = (await client.get("/api/v1/training/progress", headers=baskasi)).json()
    assert next(k for k in benim if k["module_code"] == "ortak")["score_percent"] == 100.0
    assert next(k for k in onun if k["module_code"] == "ortak")["score_percent"] == 25.0


# ------------------------------------------------------------------ ekip ozeti
async def test_ekip_ozeti_yetki_ister(client: AsyncClient, auth_headers) -> None:
    """Uretim operatoru baskalarinin egitim durumunu gormemeli."""
    basliklar = await auth_headers(["uretim_operatoru"], "operator_egitim")
    assert (
        await client.get("/api/v1/training/team", headers=basliklar)
    ).status_code == 403


async def test_yonetici_ekip_ozetini_gorur(
    client: AsyncClient, admin_headers, auth_headers
) -> None:
    await auth_headers(["enolog"], "enolog_ekip")
    await client.post(
        "/api/v1/training/progress/modul-a",
        json={"correct_count": 4, "question_count": 4},
        headers=admin_headers,
    )

    yanit = await client.get("/api/v1/training/team", headers=admin_headers)
    assert yanit.status_code == 200
    satirlar = yanit.json()
    assert len(satirlar) >= 2
    yonetici = next(s for s in satirlar if s["username"] == "admin_test")
    assert yonetici["tamamlanan"] == 1
    assert yonetici["denenen"] == 1
