"""Ceviri sozluklerinin butunlugu.

Iki dilli bir arayuzde en sik gorulen kusur, bir dile eklenen anahtarin
digerine eklenmemesidir. Sonuc sessizdir: kullanici Ingilizce secer, ekranin
bir kismi Turkce kalir ya da ham anahtar (`stok.tablo.miktar`) gorunur.

Bu testler sozlukleri kaynak dosyadan okuyup anahtar kumelerini karsilastirir.
TypeScript derleyicisi bunu yakalayamaz: her iki sozluk de
`Record<string, string>` tipindedir.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.config import PROJECT_ROOT

CEVIRI_DIZINI = PROJECT_ROOT / "frontend" / "src" / "lib" / "ceviriler"
TR_DOSYA = CEVIRI_DIZINI / "tr.ts"
EN_DOSYA = CEVIRI_DIZINI / "en.ts"

# `  'anahtar': 'deger',` veya cok satirli deger
_ANAHTAR = re.compile(r"^\s*'([a-z0-9_.]+)':", re.MULTILINE)


def _anahtarlar(dosya: Path) -> set[str]:
    return set(_ANAHTAR.findall(dosya.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def tr() -> set[str]:
    return _anahtarlar(TR_DOSYA)


@pytest.fixture(scope="module")
def en() -> set[str]:
    return _anahtarlar(EN_DOSYA)


def test_sozluk_dosyalari_var() -> None:
    assert TR_DOSYA.is_file(), f"{TR_DOSYA} bulunamadi"
    assert EN_DOSYA.is_file(), f"{EN_DOSYA} bulunamadi"


def test_sozlukler_bos_degil(tr: set[str], en: set[str]) -> None:
    """Ayristirma bozulursa test sessizce bosa dusmesin."""
    assert len(tr) > 50, f"TR sozlugunde yalnizca {len(tr)} anahtar bulundu"
    assert len(en) > 50, f"EN sozlugunde yalnizca {len(en)} anahtar bulundu"


def test_ingilizcede_eksik_anahtar_yok(tr: set[str], en: set[str]) -> None:
    eksik = sorted(tr - en)
    assert not eksik, (
        f"{len(eksik)} anahtar Ingilizce sozlukte YOK; bu ekranlarda Turkce metin "
        f"veya ham anahtar gorunur:\n  " + "\n  ".join(eksik[:40])
    )


def test_turkcede_eksik_anahtar_yok(tr: set[str], en: set[str]) -> None:
    eksik = sorted(en - tr)
    assert not eksik, (
        f"{len(eksik)} anahtar Turkce sozlukte YOK; Turkce varsayilan dil oldugu "
        f"icin bu anahtarlar hicbir dilde cozulemez:\n  " + "\n  ".join(eksik[:40])
    )


def test_anahtar_bicimi_tutarli(tr: set[str]) -> None:
    """Anahtarlar kucuk harf, nokta ayracli ve Turkce karaktersiz olmali."""
    hatali = [a for a in tr if a != a.lower() or re.search(r"[çğıöşüÇĞİÖŞÜ]", a)]
    assert not hatali, f"Bicim disi anahtarlar: {sorted(hatali)[:20]}"


def test_bos_ceviri_yok() -> None:
    """Bos dize, eksik anahtardan daha sinsidir: ekranda hicbir sey gorunmez."""
    for dosya in (TR_DOSYA, EN_DOSYA):
        metin = dosya.read_text(encoding="utf-8")
        bos = re.findall(r"^\s*'([a-z0-9_.]+)':\s*''\s*,", metin, re.MULTILINE)
        assert not bos, f"{dosya.name} icinde bos ceviri: {bos}"


def test_kullanilan_anahtarlar_tanimli(tr: set[str]) -> None:
    """Kodda `t('...')` ile cagrilan her anahtar sozlukte bulunmali."""
    kaynak = PROJECT_ROOT / "frontend" / "src"
    cagrilan: set[str] = set()
    for dosya in list(kaynak.rglob("*.tsx")) + list(kaynak.rglob("*.ts")):
        if "ceviriler" in dosya.parts:
            continue
        metin = dosya.read_text(encoding="utf-8")
        cagrilan |= set(re.findall(r"\bt\(\s*'([a-z0-9_.]+)'\s*\)", metin))

    eksik = sorted(cagrilan - tr)
    assert not eksik, (
        f"{len(eksik)} anahtar kodda kullaniliyor ama sozlukte YOK; ekranda ham "
        f"anahtar gorunur:\n  " + "\n  ".join(eksik[:40])
    )
