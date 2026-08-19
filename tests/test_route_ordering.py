"""Rota sirasi tuzagi: sabit yol parcasinin {param} tarafindan golgelenmesi.

FastAPI rotalari KAYIT SIRASINA gore eslestirir. `/maintenance/{item_id}`
rotasi `/maintenance/due` rotasindan once kayitliysa, `GET /maintenance/due`
istegi `item_id` yoluna duser; "due" tamsayiya cevrilemedigi icin 422 doner ve
uc nokta -- dogru tanimlanmis olmasina ragmen -- erisilemez hale gelir.

Bu hata sessizdir: testler uc noktayi dogrudan cagirmiyorsa fark edilmez,
yalnizca arayuzde bos liste veya konsol hatasi olarak gorunur.

Kontrol, OpenAPI semasi uzerinden yapilir; `paths` sozlugu rotalarin kayit
sirasini korur ve tam (prefix uygulanmis) yollari icerir.
"""

from __future__ import annotations

import re

from app.main import app

_PARAM = re.compile(r"^\{[^}]+\}$")

# Yol parametresi tasimayan, yani sabit bir son parcaya sahip ozel uclar.
# Bunlar CRUD `/{id}` rotasindan ONCE kaydedilmelidir.
_HTTP_YONTEMLERI = {"get", "put", "post", "delete", "patch", "head", "options"}


def _sirali_uclar() -> list[tuple[str, str]]:
    """Kayit sirasinda (yontem, yol) ciftleri."""
    uclar: list[tuple[str, str]] = []
    for yol, islemler in app.openapi()["paths"].items():
        for yontem in islemler:
            if yontem.lower() in _HTTP_YONTEMLERI:
                uclar.append((yontem.lower(), yol))
    return uclar


def _parcala(yol: str) -> list[str]:
    return [p for p in yol.split("/") if p]


def _golgeler(onceki: str, sonraki: str) -> bool:
    """`onceki` rotasi `sonraki` rotasini tamamen yutuyor mu?"""
    a, b = _parcala(onceki), _parcala(sonraki)
    if len(a) != len(b):
        return False
    param_yuttu = False
    for pa, pb in zip(a, b, strict=True):
        if _PARAM.match(pa):
            if _PARAM.match(pb):
                continue  # ikisi de degisken: golgeleme yok
            param_yuttu = True  # degisken, sabit parcayi yutar
            continue
        if pa != pb:
            return False
    return param_yuttu


def golgelenen_uclar() -> list[tuple[str, str, str]]:
    """(yontem, erisilemeyen_yol, onu_yutan_yol) uclulerini doner."""
    uclar = _sirali_uclar()
    bulunanlar: list[tuple[str, str, str]] = []
    for i, (yontem, yol) in enumerate(uclar):
        for onceki_yontem, onceki_yol in uclar[:i]:
            if onceki_yontem == yontem and _golgeler(onceki_yol, yol):
                bulunanlar.append((yontem, yol, onceki_yol))
                break
    return bulunanlar


def test_hicbir_uc_nokta_param_rotasi_tarafindan_golgelenmiyor() -> None:
    golgelenen = golgelenen_uclar()
    if golgelenen:
        satirlar = "\n".join(
            f"  {y.upper():6} {golge}\n         yutan: {yutan}" for y, golge, yutan in golgelenen
        )
        raise AssertionError(
            f"{len(golgelenen)} uc nokta erisilemez durumda: daha once kayitli bir "
            "{param} rotasi istegi yutuyor ve 422 donduruyor.\n"
            "Cozum: ilgili modulun `routers` listesinde 'extra' router'i CRUD "
            f"router'indan ONCE yazin.\n{satirlar}"
        )


def test_rota_tablosu_beklenen_buyuklukte() -> None:
    """Sema uretimi bozulursa golgeleme testi sessizce bosa dusmesin."""
    uclar = _sirali_uclar()
    assert len(uclar) > 100, f"Yalnizca {len(uclar)} uc bulundu; sema uretimi bozuk olabilir"
    assert ("get", "/api/v1/maintenance/due") in uclar
