"""PowerShell betiklerinin Windows'ta gercekten calistigini dogrular.

Windows PowerShell 5.1 (`powershell.exe`), BOM tasimayan `.ps1` dosyalarini
sistem ANSI kod sayfasiyla okur. Turkce karakter iceren bir betik bu durumda
bozulur ve cogu zaman AYRISTIRMA HATASI verir -- yani betik hic calismaz.

README kullaniciya `powershell -ExecutionPolicy Bypass -File scripts\\...`
komutlarini onerdigi icin bu, belgelenmis her komutu kiran sessiz bir hatadir.
Cozum: betikleri UTF-8 BOM ile kaydetmek.
"""

from __future__ import annotations

import pytest

from app.core.config import PROJECT_ROOT

BOM = b"\xef\xbb\xbf"
BETIKLER = sorted((PROJECT_ROOT / "scripts").glob("*.ps1"))


def test_betik_dosyalari_bulundu() -> None:
    """Testin sessizce bosa dusmedigini garanti eder."""
    assert BETIKLER, "scripts/ altinda hic .ps1 dosyasi bulunamadi"


@pytest.mark.parametrize("betik", BETIKLER, ids=lambda p: p.name)
def test_betikler_utf8_bom_ile_kaydedilmis(betik) -> None:
    ham = betik.read_bytes()
    assert ham.startswith(BOM), (
        f"{betik.name} UTF-8 BOM tasimiyor. Windows PowerShell 5.1 dosyayi ANSI "
        "olarak okur; Turkce karakterler bozulur ve betik ayristirilamaz. "
        "Duzeltmek icin dosyayi 'UTF-8 with BOM' olarak kaydedin."
    )


@pytest.mark.parametrize("betik", BETIKLER, ids=lambda p: p.name)
def test_betikler_gecerli_utf8(betik) -> None:
    ham = betik.read_bytes()
    try:
        ham.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssertionError(
            f"{betik.name} gecerli UTF-8 degil ({exc}). Dosya muhtemelen bir "
            "duzenleme sirasinda ANSI/cp1254 olarak yeniden kaydedildi."
        ) from exc


@pytest.mark.parametrize("betik", BETIKLER, ids=lambda p: p.name)
def test_betiklerde_mojibake_yok(betik) -> None:
    """UTF-8 metnin cp1254 sanilarak yeniden kodlanmasi tipik izler birakir."""
    metin = betik.read_bytes().decode("utf-8", errors="replace")
    izler = ("Ã¶", "Ã§", "ÅŸ", "Ä±", "ÅŸ", "Ã¼", "Ã‡", "Ã–", "â€™", "�")
    bulunan = [iz for iz in izler if iz in metin]
    assert not bulunan, (
        f"{betik.name} icinde bozuk karakter dizisi var: {bulunan}. "
        "Dosya yanlis kodlamayla yeniden kaydedilmis olabilir."
    )
