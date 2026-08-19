"""Sunucu tarafi dil secimi.

Arayuz iki dillidir ve cevirilerinin cogu istemcide tutulur. Ancak bazi
etiketler sunucudan gelir ve istemcide karsiligi yoktur:

  * rol adlari (`/auth/me`, `/users`)
  * yetki aciklamalari (`/users/permissions`)
  * yapay zeka gorev turleri (`/ai/task-kinds`)

Bunlar Ingilizce secildiginde Turkce kalirsa arayuz yarim cevrilmis gorunur.
Bu modul istegin `Accept-Language` basligindan dili secer.

KAPSAM NOTU: hata mesajlari (HTTPException detaylari) Turkce kalir. Bunlar
yuzlerce noktada uretilir ve cevrilmeleri ayri bir istir; SECURITY.md ve
README'de bilinen sinir olarak belgelenmistir.
"""

from __future__ import annotations

from fastapi import Request

DESTEKLENEN = ("tr", "en")
VARSAYILAN = "tr"


def dil_sec(request: Request | None) -> str:
    """`Accept-Language` basligindan desteklenen bir dil secer.

    Basit ve bagimliliksiz: `en-US,en;q=0.9,tr;q=0.8` gibi bir degerde
    parcalari sirayla tarar ve ilk desteklenen dili doner. Kalite (q) degerleri
    tarayicilar tarafindan zaten tercih sirasina gore gonderildigi icin ayrica
    siralanmaz.
    """
    if request is None:
        return VARSAYILAN
    ham = request.headers.get("accept-language", "")
    for parca in ham.split(","):
        kod = parca.split(";")[0].strip().lower()
        if not kod:
            continue
        # `en-US` -> `en`
        kisa = kod.split("-")[0]
        if kisa in DESTEKLENEN:
            return kisa
    return VARSAYILAN


def sozlukten(tr: dict, en: dict, dil: str) -> dict:
    """Dile gore sozluk secer; eksik anahtarlarda Turkce karsiliga duser."""
    if dil != "en":
        return tr
    return {anahtar: en.get(anahtar, deger) for anahtar, deger in tr.items()}
