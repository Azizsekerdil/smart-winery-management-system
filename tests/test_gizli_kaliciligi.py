"""Otomatik uretilen gizli anahtarlarin kalici olmasi.

Kurulu (MSI) surumde `.env` `C:\\Program Files` altinda kalir ve standart
kullanici oraya yazamaz. Anahtarlar her surecte yeniden uretilseydi:

  * kullanicinin kaydettigi Claude/NVIDIA API anahtarlari cozulemez hale gelir
    ve `decrypt_secret` bunu SESSIZCE bos dize olarak dondururdu -- yani veri,
    hicbir hata mesaji olmadan kaybolurdu;
  * SECRET_KEY degistigi icin her acilista tum oturumlar duserdi.

Bu yuzden uretilen anahtar veri kokunde saklanir ve sonraki acilislarda
yeniden okunur.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core import config as yapilandirma


@pytest.fixture
def gizli_dosyasi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    yol = tmp_path / "gizli-anahtarlar.json"
    monkeypatch.setattr(yapilandirma, "GIZLI_DOSYASI", yol)
    return yol


def test_ilk_cagri_uretir_ve_dosyaya_yazar(gizli_dosyasi: Path) -> None:
    assert not gizli_dosyasi.exists()
    deger = yapilandirma._kalici_gizli_anahtar("SECRET_KEY")

    assert len(deger) >= 32
    assert gizli_dosyasi.is_file()
    assert json.loads(gizli_dosyasi.read_text(encoding="utf-8"))["SECRET_KEY"] == deger


def test_ikinci_cagri_ayni_degeri_dondurur(gizli_dosyasi: Path) -> None:
    """Asil gerileme: yeniden baslatmada anahtar DEGISMEMELI."""
    ilk = yapilandirma._kalici_gizli_anahtar("SECRETS_ENCRYPTION_KEY")
    ikinci = yapilandirma._kalici_gizli_anahtar("SECRETS_ENCRYPTION_KEY")
    assert ilk == ikinci, "Anahtar degisti; sifreli API anahtarlari cozulemez olurdu"


def test_farkli_anahtarlar_birbirinden_bagimsiz(gizli_dosyasi: Path) -> None:
    a = yapilandirma._kalici_gizli_anahtar("SECRET_KEY")
    b = yapilandirma._kalici_gizli_anahtar("SECRETS_ENCRYPTION_KEY")
    assert a != b

    icerik = json.loads(gizli_dosyasi.read_text(encoding="utf-8"))
    assert icerik["SECRET_KEY"] == a
    assert icerik["SECRETS_ENCRYPTION_KEY"] == b
    # Ikinci anahtar yazilirken birincisi silinmemeli
    assert len(icerik) == 2


def test_bozuk_dosya_uygulamayi_cokertmez(gizli_dosyasi: Path) -> None:
    gizli_dosyasi.write_text("{bu gecerli json degil", encoding="utf-8")
    deger = yapilandirma._kalici_gizli_anahtar("SECRET_KEY")
    assert len(deger) >= 32  # surec-basina degere duser, hata firlatmaz


def test_yazilamayan_konumda_cokmez(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Salt okunur/kilitli profilde uygulama yine acilabilmeli."""
    dosya = tmp_path / "yok" / "olmayan" / "gizli.json"
    monkeypatch.setattr(yapilandirma, "GIZLI_DOSYASI", dosya)

    def patlat(*_a, **_k):
        raise OSError("erisim engellendi")

    monkeypatch.setattr(Path, "mkdir", patlat)
    deger = yapilandirma._kalici_gizli_anahtar("SECRET_KEY")
    assert len(deger) >= 32


def test_acik_ayar_dosyayi_hic_okumaz(
    gizli_dosyasi: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`.env` veya ortam degiskeni verilmisse kalici dosyaya bakilmaz."""
    monkeypatch.setenv("SECRET_KEY", "acikca-verilmis-deger-123456789012345")
    ayarlar = yapilandirma.Settings()
    assert ayarlar.SECRET_KEY == "acikca-verilmis-deger-123456789012345"
    assert not gizli_dosyasi.exists(), "Ayar verilmisken dosya olusturulmamali"


def test_gizli_dosyasi_veri_kokunde_durur() -> None:
    """Kurulum dizininde degil, yazilabilir veri kokunde olmali."""
    assert yapilandirma.GIZLI_DOSYASI.parent == yapilandirma.DATA_DIR
    assert yapilandirma.GIZLI_DOSYASI.is_relative_to(yapilandirma.VERI_KOKU)


def test_gizli_dosyasi_git_tarafindan_yok_sayilir() -> None:
    """Anahtar dosyasi depoya ASLA girmemeli."""
    kurallar = (yapilandirma.PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "gizli-anahtarlar.json" in kurallar, (
        ".gitignore bu dosyayi kapsamiyor; uretilen sifreleme anahtari "
        "depoya islenebilir."
    )
