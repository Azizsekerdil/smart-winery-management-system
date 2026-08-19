"""MSI kurulum paketi yapilandirmasinin dogrulugu.

Bu testler .msi UretMEZ (WiX kurulumu gerektirir); paketin dogrulugunu belirleyen
KAYNAK dosyalari denetler. Buradaki hatalarin tamami sessizdir: paket sorunsuz
uretilir, sorun ancak musteride ortaya cikar.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from app.core.config import PROJECT_ROOT

WXS = PROJECT_ROOT / "desktop" / "saraphane.wxs"
SPEC = PROJECT_ROOT / "desktop" / "saraphane.spec"
SIMGE = PROJECT_ROOT / "desktop" / "saraphane.ico"
AD_ALANI = "http://wixtoolset.org/schemas/v4/wxs"

# Bu deger DEGISMEMELIDIR. Degisirse yeni surum, kurulu eski surumu yukseltme
# olarak taniyamaz; iki kopya yan yana kurulur ve kullanici hangisinin guncel
# oldugunu bilemez.
UPGRADE_CODE = "685DB88C-326E-4BFA-A29F-0374A84BFBDA"


@pytest.fixture(scope="module")
def paket() -> ET.Element:
    kok = ET.parse(WXS).getroot()
    ogeler = kok.find(f"{{{AD_ALANI}}}Package")
    assert ogeler is not None, "Package ogesi bulunamadi"
    return ogeler


def test_wxs_dosyasi_var_ve_gecerli_xml() -> None:
    assert WXS.is_file(), f"{WXS} bulunamadi"
    ET.parse(WXS)  # bozuksa burada patlar


def test_dogru_ad_alani_kullaniliyor() -> None:
    """WiX v5 kaynaklari HALA v4 ad alanini kullanir; 'v5' diye bir sema yok."""
    kok = ET.parse(WXS).getroot()
    assert kok.tag == f"{{{AD_ALANI}}}Wix", f"Beklenmeyen ad alani: {kok.tag}"


def test_upgrade_code_sabit(paket: ET.Element) -> None:
    assert paket.get("UpgradeCode", "").upper() == UPGRADE_CODE, (
        "UpgradeCode degistirilmis! Bu deger surumler arasi SABIT kalmalidir; "
        "aksi halde yukseltme calismaz ve iki kopya yan yana kurulur."
    )


def test_kurulum_kapsami_per_machine(paket: ET.Element) -> None:
    """C:\\Program Files hedefi icin perMachine sarttir."""
    assert paket.get("Scope") == "perMachine"


def test_surum_ve_kaynak_dizin_disaridan_verilir(paket: ET.Element) -> None:
    """Surum .wxs icine sabitlenmemeli; tek dogruluk kaynagi __init__.py'dir."""
    assert paket.get("Version") == "$(var.Surum)"

    metin = WXS.read_text(encoding="utf-8")
    assert "$(var.KaynakDizin)" in metin
    # Mutlak gelistirici yolu sizmamali
    assert "D:\\Wine" not in metin, "Sabitlenmis gelistirici yolu bulundu"


def test_major_upgrade_tanimli(paket: ET.Element) -> None:
    """Yukseltme kurgusu yoksa yeni surum eskisinin yanina kurulur."""
    yukseltme = paket.find(f"{{{AD_ALANI}}}MajorUpgrade")
    assert yukseltme is not None, "MajorUpgrade tanimli degil"
    assert yukseltme.get("DowngradeErrorMessage"), "Surum dusurme mesaji yok"


def test_kisayollar_tanimli(paket: ET.Element) -> None:
    kisayollar = paket.iter(f"{{{AD_ALANI}}}Shortcut")
    hedefler = {k.get("Target") for k in kisayollar}
    assert hedefler == {"[INSTALLFOLDER]Saraphane.exe"}, hedefler


def test_kullanici_verisi_pakete_dahil_edilmiyor() -> None:
    """Veritabani/gunluk MSI bileseni olursa Onarim musteri verisini ezer."""
    metin = WXS.read_text(encoding="utf-8")
    for yasak in ("winery.db", "app.log", ".env", "gizli-anahtarlar"):
        assert yasak not in metin, f"MSI kaynaginda kullanici verisi gecmemeli: {yasak}"


def test_xml_yorumlarinda_cift_tire_yok() -> None:
    """XML yorumu '--' iceremez; icerirse derleme WIX0104 ile durur."""
    metin = WXS.read_text(encoding="utf-8")
    for yorum in re.findall(r"<!--(.*?)-->", metin, re.DOTALL):
        assert "--" not in yorum, f"Yorumda '--' var: {yorum[:60]}"


# ------------------------------------------------------------- PyInstaller spec
def test_spec_alembic_ve_belgeleri_gomuyor() -> None:
    """Eksikse: sema yukseltmesi calistirilamaz, RAG indeksleme bos doner."""
    metin = SPEC.read_text(encoding="utf-8")
    assert "alembic.ini" in metin, "alembic.ini pakete girmiyor"
    assert '"docs"' in metin, "docs klasoru pakete girmiyor"


def test_spec_simge_ve_surum_kaynagi_kullaniyor() -> None:
    metin = SPEC.read_text(encoding="utf-8")
    assert "saraphane.ico" in metin
    assert "version=" in metin, "VERSIONINFO kaynagi tanimli degil"
    assert "VSVersionInfo" in metin


def test_spec_surumu_tek_kaynaktan_okuyor() -> None:
    """Surum iki yerde tutulursa er ya da gec ayrisirlar."""
    metin = SPEC.read_text(encoding="utf-8")
    assert "__version__" in metin
    assert '__init__.py' in metin


def test_spec_gelistirme_araclarini_disliyor() -> None:
    metin = SPEC.read_text(encoding="utf-8")
    for arac in ("pytest", "mypy", "ruff", "playwright"):
        assert f'"{arac}"' in metin, f"{arac} pakete girmemeli (excludes)"


# --------------------------------------------------------------------- simge
def test_simge_dosyasi_cok_boyutlu() -> None:
    from PIL import Image

    assert SIMGE.is_file(), "saraphane.ico bulunamadi"
    with Image.open(SIMGE) as im:
        boyutlar = set(im.info.get("sizes", []))
    for gerekli in ((16, 16), (32, 32), (48, 48), (256, 256)):
        assert gerekli in boyutlar, f"{gerekli} boyutu eksik: {sorted(boyutlar)}"


# ------------------------------------------------------------------- betikler
@pytest.mark.parametrize("betik", ["msi-paketle.ps1", "imzala.ps1"])
def test_paketleme_betikleri_var(betik: str) -> None:
    assert (PROJECT_ROOT / "scripts" / betik).is_file()


def test_imzalama_betigi_zaman_damgasi_kullaniyor() -> None:
    """Zaman damgasiz imza, sertifika suresi dolunca sahada topluca bozulur."""
    metin = (PROJECT_ROOT / "scripts" / "imzala.ps1").read_text(encoding="utf-8")
    assert "/tr" in metin, "RFC 3161 zaman damgasi (/tr) kullanilmiyor"
    assert "/td" in metin
    assert "/fd" in metin, "signtool 4.00'de /fd zorunludur"


def test_imzalama_betigi_uretici_imzasini_korur() -> None:
    """Microsoft/Python imzali dosyalari yeniden imzalamak imzayi siler."""
    metin = (PROJECT_ROOT / "scripts" / "imzala.ps1").read_text(encoding="utf-8")
    assert "NotSigned" in metin, "Zaten imzali dosyalar atlanmiyor"


def test_imzalama_betigi_parola_sizdirmaz() -> None:
    metin = (PROJECT_ROOT / "scripts" / "imzala.ps1").read_text(encoding="utf-8")
    # Hata mesajinda parola maskeleniyor mu?
    assert "Replace($pfxParola" in metin or "'***'" in metin


def test_hicbir_betikte_sertifika_gomulu_degil() -> None:
    """Sertifika ve parola ASLA depoda tutulmaz."""
    for betik in (PROJECT_ROOT / "scripts").glob("*.ps1"):
        metin = betik.read_text(encoding="utf-8")
        assert "-----BEGIN" not in metin, f"{betik.name} icinde gomulu anahtar"
        assert ".pfx'" not in metin.replace("$pfxYolu", ""), f"{betik.name}"
