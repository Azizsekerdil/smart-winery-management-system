"""Sandbox kacis yollari: kapatilan somut acikların gerileme testleri.

Bu dosyadaki her test, gercekten calisan bir atlatma yontemini temsil eder.
Hicbiri teorik degildir; hepsi once calisir durumdayken bulunmus, sonra
kapatilmistir. Gevsetilmeleri halinde AI terminali `D:\\Wine` disina cikabilir.
"""

from __future__ import annotations

import pytest

from app.agent.sandbox import check_command
from app.core.config import settings as yapilandirma


def _engellendi(komut: str) -> None:
    v = check_command(komut)
    assert not v.allowed, f"Bu komut engellenmeliydi ama izin verildi: {komut!r}"
    assert v.risk == "engellendi"
    assert v.reason.strip(), "Engelleme gerekcesi bos olmamali"


# ---------------------------------------------------- satir ici kod calistirma
# Yorumlayiciya `-c` ile verilen kod, izin listesinden de yol hapsinden de
# gecer: token bir "yol" gibi gorunmedigi icin denetlenmez, ama calistiginda
# istedigi dosyayi acabilir.
@pytest.mark.parametrize(
    "komut",
    [
        'python -c "open(\'C:/Windows/Temp/x.txt\',\'w\')"',
        "python -c import os",
        "python -cimport os",  # bitisik yazim
        "py -c print(1)",
        'node -e "require(\'fs\').writeFileSync(\'C:/x\',\'1\')"',
        'node --eval "1"',
        "node -p process.env",
        "node --print process.env",
    ],
)
def test_satir_ici_kod_calistirma_engellenir(komut: str) -> None:
    _engellendi(komut)


def test_satir_ici_kod_gerekcesi_alternatif_onerir() -> None:
    """Kullanici ne yapacagini bilmeli; salt 'hayir' yeterli degil."""
    v = check_command('python -c "print(1)"')
    assert "dosya" in v.reason.lower()


# ------------------------------------------------------- yol ayraci atlatmasi
# Windows hem `\` hem `/` kabul eder. Kara liste yalnizca ters bolu ararsa
# `C:/Windows/...` yazimi denetimden kacar.
@pytest.mark.parametrize(
    "komut",
    [
        "dir C:/Windows/System32",
        "ls C:/Users/ornek-kullanici",
        "dir C:\\Windows\\System32",
        "type C:/Program Files/gizli.txt",
        "dir c:/windows/temp",  # kucuk harf
    ],
)
def test_sistem_dizini_her_iki_ayracla_da_engellenir(komut: str) -> None:
    _engellendi(komut)


# ------------------------------------------------------------- mesru komutlar
# Guvenlik siki olmali ama gelistirmeyi bloke etmemeli.
@pytest.mark.parametrize(
    "komut",
    [
        "python -m pytest -q",
        "python -m ruff check backend",
        "python -m mypy backend",
        "git status",
        "git diff",
        "npm run build",
        "alembic upgrade head",
    ],
)
def test_mesru_gelistirme_komutlari_izinli_kalir(komut: str) -> None:
    v = check_command(komut)
    assert v.allowed, f"Bu komut izinli olmaliydi ama engellendi: {komut!r} -- {v.reason}"


def test_npx_varsayilan_olarak_engellenir(monkeypatch: pytest.MonkeyPatch) -> None:
    """npx yerelde olmayan paketi indirip calistirabilir.

    Bu, izin listesinin TAMAMEN disinda kod calistirmak demektir; onay bayragi
    (bir politika kontrolu) bunu teknik olarak engellemez. Bu yuzden varsayilan
    olarak engellidir.
    """
    monkeypatch.setattr(yapilandirma, "AGENT_ALLOW_PACKAGE_INSTALL", False)
    v = check_command("npx playwright test")
    assert not v.allowed, "npx varsayilan olarak engellenmeliydi"
    assert v.matched_rule == "npx:paket_kurulumu"


def test_npx_acik_ayarla_onay_ister(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bilincli olarak acildiginda calisir, ancak yuksek risk isaretlenir."""
    monkeypatch.setattr(yapilandirma, "AGENT_ALLOW_PACKAGE_INSTALL", True)
    v = check_command("npx playwright test")
    assert v.allowed, v.reason
    assert v.risk == "yuksek", f"npx yuksek riskli isaretlenmeli, gelen: {v.risk}"


def test_python_m_modul_calistirma_hala_calisir() -> None:
    """`-m` satir ici kod degildir; kurulu modulu calistirir ve izinli kalmali."""
    v = check_command("python -m pytest tests/test_sandbox.py")
    assert v.allowed
