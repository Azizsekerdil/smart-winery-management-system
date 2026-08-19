"""Veri kokunun kaynak dizininden ayrilmasi.

MSI ile ``C:\\Program Files\\Saraphane`` altina kurulan bir uygulama KENDI
DIZININE YAZAMAZ. Veritabani, gunluk ve yuklemeler oraya yazilmaya calisirsa
uygulama standart kullanicida acilista coker.

Bu yuzden "kaynak koku" (kod, derlenmis arayuz) ile "veri koku" ayrildi.
Testler dort senaryonun dogru cozuldugunu ve yazilabilirlik denetiminin
gercekten yazma denedigini dogrular.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

from app.core import config as yapilandirma


def _yeniden_yukle(monkeypatch: pytest.MonkeyPatch, **ortam: str | None):
    """config modulunu verilen ortamla bastan yukler ve doner."""
    for anahtar, deger in ortam.items():
        if deger is None:
            monkeypatch.delenv(anahtar, raising=False)
        else:
            monkeypatch.setenv(anahtar, deger)
    return importlib.reload(yapilandirma)


@pytest.fixture(autouse=True)
def _modulu_geri_yukle():
    """Her testten sonra modulu gercek ortamla geri yukler."""
    yield
    importlib.reload(yapilandirma)


# ------------------------------------------------------- yazilabilirlik denetimi
def test_yazilabilir_dizin_dogru_tespit_edilir(tmp_path: Path) -> None:
    assert yapilandirma._yazilabilir_mi(tmp_path) is True


def test_var_olmayan_dizin_yazilabilir_sayilmaz(tmp_path: Path) -> None:
    assert yapilandirma._yazilabilir_mi(tmp_path / "yok") is False


def test_dosya_yolu_dizin_sayilmaz(tmp_path: Path) -> None:
    dosya = tmp_path / "bir.txt"
    dosya.write_text("x", encoding="utf-8")
    assert yapilandirma._yazilabilir_mi(dosya) is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows'a ozgu korumali dizin")
def test_korumali_sistem_dizini_yazilabilir_degil() -> None:
    """Yonetici olmadan System32'ye yazilamaz; denetim bunu gormeli."""
    sistem = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
    if not sistem.is_dir():
        pytest.skip("System32 bulunamadi")
    # Yonetici olarak kosuluyorsa bu test anlamsizdir
    if yapilandirma._yazilabilir_mi(sistem):
        pytest.skip("Yonetici hakkiyla kosuluyor")
    assert yapilandirma._yazilabilir_mi(sistem) is False


def test_denetim_arkasinda_dosya_birakmaz(tmp_path: Path) -> None:
    oncesi = set(tmp_path.iterdir())
    assert yapilandirma._yazilabilir_mi(tmp_path) is True
    assert set(tmp_path.iterdir()) == oncesi, "Yazma denemesi dosyasi silinmemis"


# ------------------------------------------------------------------ senaryolar
def test_gelistirmede_veri_koku_proje_kokudur(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SARAPHANE_VERI_DIZINI", raising=False)
    assert yapilandirma.DONMUS is False
    assert yapilandirma.VERI_KOKU == yapilandirma.PROJECT_ROOT
    assert yapilandirma.DATA_DIR == yapilandirma.PROJECT_ROOT / "data"
    assert (
        yapilandirma._veri_koku(False, yapilandirma.PROJECT_ROOT)
        == yapilandirma.PROJECT_ROOT
    )


def test_ortam_degiskeni_her_seyi_ezer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hedef = tmp_path / "ozel-veri"
    hedef.mkdir()
    y = _yeniden_yukle(monkeypatch, SARAPHANE_VERI_DIZINI=str(hedef))
    assert hedef.resolve() == y.VERI_KOKU
    assert hedef.resolve() / "data" == y.DATA_DIR
    assert hedef.resolve() / "logs" == y.LOGS_DIR


def test_ortam_degiskeni_donmus_durumda_da_ezer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hedef = tmp_path / "ozel"
    hedef.mkdir()
    monkeypatch.setenv("SARAPHANE_VERI_DIZINI", str(hedef))
    assert yapilandirma._veri_koku(True, tmp_path) == hedef.resolve()


def test_bos_ortam_degiskeni_yok_sayilir(monkeypatch: pytest.MonkeyPatch) -> None:
    y = _yeniden_yukle(monkeypatch, SARAPHANE_VERI_DIZINI="   ")
    assert y.VERI_KOKU == y.PROJECT_ROOT


def test_tasinabilir_pakette_exe_yani_kullanilir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Zip acilmis kullanim: exe'nin yani yazilabilir -> veri orada durur."""
    monkeypatch.delenv("SARAPHANE_VERI_DIZINI", raising=False)
    kurulum = tmp_path / "Saraphane"
    kurulum.mkdir()

    assert yapilandirma._veri_koku(True, kurulum) == kurulum


def test_kurulu_pakette_localappdata_kullanilir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Program Files senaryosu: exe'nin yani YAZILAMAZ -> %LOCALAPPDATA%."""
    yazilamaz = tmp_path / "ProgramFiles" / "Saraphane"
    yazilamaz.mkdir(parents=True)
    yerel = tmp_path / "LocalAppData"
    yerel.mkdir()

    monkeypatch.delenv("SARAPHANE_VERI_DIZINI", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(yerel))
    # Kurulum dizinini "yazilamaz" olarak taklit et
    monkeypatch.setattr(
        yapilandirma,
        "_yazilabilir_mi",
        lambda d: d.resolve() != yazilamaz.resolve(),
    )

    kok = yapilandirma._veri_koku(True, yazilamaz)
    assert kok == (yerel / "Saraphane").resolve()
    assert kok != yazilamaz.resolve(), "Program Files'a yazmaya calisiyor"


def test_localappdata_yoksa_ev_dizinine_duser(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    yazilamaz = tmp_path / "kurulum"
    yazilamaz.mkdir()
    monkeypatch.delenv("SARAPHANE_VERI_DIZINI", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(yapilandirma, "_yazilabilir_mi", lambda d: False)

    kok = yapilandirma._veri_koku(True, yazilamaz)
    assert kok == (Path.home() / "Saraphane").resolve()


def test_veri_yollari_kaynak_kokune_bagli_degil(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Kurulu senaryoda hicbir veri yolu kurulum dizininin altinda olmamali."""
    kurulum = tmp_path / "ProgramFiles" / "Saraphane"
    kurulum.mkdir(parents=True)
    yerel = tmp_path / "Local"
    yerel.mkdir()
    monkeypatch.delenv("SARAPHANE_VERI_DIZINI", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(yerel))
    monkeypatch.setattr(yapilandirma, "_yazilabilir_mi", lambda d: False)

    kok = yapilandirma._veri_koku(True, kurulum)
    for alt in ("data", "logs", "data/uploads", "data/backups"):
        yol = kok / alt
        assert not yol.is_relative_to(kurulum), f"{alt} kurulum dizinine yazilacak"


# ------------------------------------------------------------------- ajan kapali
def test_paketlenmis_surumde_ai_terminali_varsayilan_kapali(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Son kullanici kurulumunda kod calistirma araci acik gelmemeli."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("AGENT_ENABLED", raising=False)
    try:
        y = _yeniden_yukle(monkeypatch)
        assert y.DONMUS is True
        assert y.Settings.model_fields["AGENT_ENABLED"].default is False
    finally:
        monkeypatch.delattr(sys, "frozen", raising=False)


def test_gelistirmede_ai_terminali_varsayilan_acik(monkeypatch: pytest.MonkeyPatch) -> None:
    y = _yeniden_yukle(monkeypatch)
    assert y.DONMUS is False
    assert y.Settings.model_fields["AGENT_ENABLED"].default is True
