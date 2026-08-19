"""Egitim iceriginin butunlugu.

Icerik TypeScript dosyasinda tutulur ve derleyici yalnizca TIPLERI dogrular.
Anlamsal hatalar sessizdir ve kullaniciya yanlis bilgi olarak ulasir:

  * dogru cevap indeksi secenek sayisini asarsa sinav HER ZAMAN yanlis sayar
  * `ekran` yolu var olmayan bir rotayi gosterirse "Ekrana git" 404'e goturur
  * bir modul yalnizca tek dilde yazilirsa Ingilizce kullanici Turkce metin gorur
  * ayni `kod` iki modulde kullanilirsa ilerleme kayitlari birbirine karisir
"""

from __future__ import annotations

import re

import pytest

from app.core.config import PROJECT_ROOT
from app.core.permissions import Role

ICERIK = PROJECT_ROOT / "frontend" / "src" / "lib" / "egitim-icerik.ts"
APP_TSX = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


@pytest.fixture(scope="module")
def kaynak() -> str:
    return ICERIK.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def modul_kodlari(kaynak: str) -> list[str]:
    return re.findall(r"^\s*kod: '([a-z0-9-]+)',", kaynak, re.MULTILINE)


def test_icerik_dosyasi_var() -> None:
    assert ICERIK.is_file(), f"{ICERIK} bulunamadi"


def test_modul_sayisi_makul(modul_kodlari: list[str]) -> None:
    """Bos veya kirpilmis icerik sessizce gecmesin."""
    assert len(modul_kodlari) >= 10, f"Yalnizca {len(modul_kodlari)} modul var"


def test_modul_kodlari_benzersiz(modul_kodlari: list[str]) -> None:
    """Ayni kod iki modulde olursa ilerleme kayitlari birbirine karisir."""
    tekrar = {k for k in modul_kodlari if modul_kodlari.count(k) > 1}
    assert not tekrar, f"Tekrar eden modul kodu: {sorted(tekrar)}"


def test_modul_kodlari_kebab_case(modul_kodlari: list[str]) -> None:
    for k in modul_kodlari:
        assert re.fullmatch(r"[a-z][a-z0-9-]*", k), f"Gecersiz kod: {k}"


def test_her_alan_iki_dilli(kaynak: str) -> None:
    """`{ tr: ..., en: ... }` bicimini bozan alan olmamali."""
    ciftler = re.findall(r"\{ tr: '(?:[^'\\]|\\.)*', en: '(?:[^'\\]|\\.)*' \}", kaynak)
    # Her modulde: baslik + ozet, her adimda baslik + metin (+ipucu), her soruda soru (+aciklama)
    assert len(ciftler) > 200, f"Yalnizca {len(ciftler)} iki dilli alan bulundu"

    tek_dilli = re.findall(r"\{ tr: '(?:[^'\\]|\\.)*' \}", kaynak)
    assert not tek_dilli, f"{len(tek_dilli)} alan yalnizca Turkce"


def test_ingilizce_metinler_bos_degil(kaynak: str) -> None:
    bos = re.findall(r"en: ''", kaynak)
    assert not bos, f"{len(bos)} bos Ingilizce metin var"


def test_dogru_cevap_indeksi_gecerli(kaynak: str) -> None:
    """`dogru`, secenek sayisindan kucuk olmali; degilse sinav hep yanlis sayar."""
    bloklar = re.findall(
        r"secenekler: \{ tr: \[(.*?)\], en: \[(.*?)\] \},\s*\n\s*dogru: (\d+),",
        kaynak,
        re.DOTALL,
    )
    assert bloklar, "Hicbir soru blogu ayristirilamadi"

    for i, (tr_ham, en_ham, dogru) in enumerate(bloklar):
        tr_sayi = len(re.findall(r"'(?:[^'\\]|\\.)*'", tr_ham))
        en_sayi = len(re.findall(r"'(?:[^'\\]|\\.)*'", en_ham))
        idx = int(dogru)
        assert tr_sayi >= 2, f"Soru {i}: {tr_sayi} secenek (en az 2 olmali)"
        assert tr_sayi == en_sayi, f"Soru {i}: TR {tr_sayi} / EN {en_sayi} secenek"
        assert 0 <= idx < tr_sayi, f"Soru {i}: dogru={idx} ama {tr_sayi} secenek var"


def test_ekran_yollari_gercek_rotalar(kaynak: str) -> None:
    """`ekran` alani var olmayan bir rotayi gosterirse kullanici 404 gorur."""
    # `path="..."` cok satirli `<Route>` yaziminda da bulunmali; App.tsx icinde
    # `path` niteligi yalnizca rotalarda gecer.
    rotalar = set(re.findall(r'\bpath="([^"]+)"', APP_TSX.read_text(encoding="utf-8")))
    # Parametreli rotalari kalibi ile karsilastirmak icin sadelestir
    sabit = {r for r in rotalar if ":" not in r and r != "*"}

    kullanilan = set(re.findall(r"^\s*ekran: '([^']+)',", kaynak, re.MULTILINE))
    assert kullanilan, "Hicbir adimda ekran baglantisi yok"

    gecersiz = {e for e in kullanilan if e not in sabit and not e.startswith("/partiler/")}
    assert not gecersiz, (
        f"Var olmayan rotalara baglanti: {sorted(gecersiz)}\nTanimli: {sorted(sabit)}"
    )


def test_roller_gercek_rol_kodlari(kaynak: str) -> None:
    """Yazim hatasi olan rol, modulun hicbir kullaniciya gorunmemesine yol acar."""
    gecerli = {str(r) for r in Role}
    bloklar = re.findall(r"^\s*roller: \[(.*?)\],", kaynak, re.MULTILINE)
    kullanilan = {r for b in bloklar for r in re.findall(r"'([^']+)'", b)}

    gecersiz = kullanilan - gecerli
    assert not gecersiz, f"Bilinmeyen rol kodu: {sorted(gecersiz)}"


def test_her_modulde_adim_ve_soru_var(kaynak: str) -> None:
    modul_bloklari = kaynak.split("\n  {\n    kod: ")[1:]
    for blok in modul_bloklari:
        kod = blok.split("'")[1]
        assert "adimlar: [\n      {" in blok, f"{kod}: adim yok"
        assert "sorular: [\n      {" in blok, f"{kod}: soru yok"


def test_sure_makul(kaynak: str) -> None:
    sureler = [int(s) for s in re.findall(r"^\s*sureDk: (\d+),", kaynak, re.MULTILINE)]
    assert sureler, "Sure bilgisi yok"
    for s in sureler:
        assert 3 <= s <= 60, f"Makul olmayan sure: {s} dk"


def test_gecme_esigi_iki_tarafta_ayni() -> None:
    """Arayuz %70 gosterip sunucu baska bir esik uygularsa kullanici yanilir."""
    tip = (PROJECT_ROOT / "frontend" / "src" / "lib" / "egitim-tip.ts").read_text(
        encoding="utf-8"
    )
    model = (PROJECT_ROOT / "backend" / "app" / "models" / "egitim.py").read_text(
        encoding="utf-8"
    )
    assert "GECME_ESIGI = 70" in tip
    assert ">= 70.0" in model
