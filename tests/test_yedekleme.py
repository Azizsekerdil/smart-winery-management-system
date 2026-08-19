"""Uygulama ici yedekleme: dogruluk ve guvenlik.

Yedek dosyasi TUM veritabaninin kopyasidir: argon2 parola ozetleri, sifreli
API anahtarlari, denetim gunlugu ve kullanici e-postalari. Bu yuzden testlerin
agirligi yetkilendirme ve yol kacisi uzerindedir.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.permissions import Perm, Role, permissions_for
from app.services import yedekleme


@pytest.fixture
def yedek_dizini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    kok = tmp_path / "backups"
    kok.mkdir()
    monkeypatch.setattr(yedekleme, "BACKUPS_DIR", kok)
    return kok


# ------------------------------------------------------------- yetki tasarimi
def test_yedek_yetkileri_read_ile_bitmiyor() -> None:
    """`:read` ile biten yetki `_ALL_READ` uzerinden DENETCIYE otomatik gider.

    Salt-okunur denetci tum veritabanini indirebilmemeli.
    """
    assert not Perm.BACKUP_MANAGE.value.endswith(":read")
    assert not Perm.BACKUP_DOWNLOAD.value.endswith(":read")


def test_denetci_yedege_erisemez() -> None:
    yetkiler = permissions_for([str(Role.DENETCI)])
    assert Perm.BACKUP_MANAGE not in yetkiler
    assert Perm.BACKUP_DOWNLOAD not in yetkiler


def test_isletme_yoneticisi_yedek_alir_ama_indiremez() -> None:
    """Yedek almak isletme sorumlulugu; makine disina cikarmak degil."""
    yetkiler = permissions_for([str(Role.ISLETME_YONETICISI)])
    assert Perm.BACKUP_MANAGE in yetkiler
    assert Perm.BACKUP_DOWNLOAD not in yetkiler


def test_sistem_yoneticisi_her_ikisine_de_sahip() -> None:
    yetkiler = permissions_for([str(Role.SISTEM_YONETICISI)])
    assert Perm.BACKUP_MANAGE in yetkiler
    assert Perm.BACKUP_DOWNLOAD in yetkiler


@pytest.mark.parametrize(
    "rol",
    [Role.ENOLOG, Role.LABORATUVAR_TEKNISYENI, Role.URETIM_OPERATORU, Role.SATIS_PERSONELI],
)
def test_uretim_rolleri_yedege_erisemez(rol: Role) -> None:
    yetkiler = permissions_for([str(rol)])
    assert Perm.BACKUP_MANAGE not in yetkiler
    assert Perm.BACKUP_DOWNLOAD not in yetkiler


# -------------------------------------------------------------- yol kacisi
@pytest.mark.parametrize(
    "ad",
    [
        "../.env",
        "..\\..\\data\\winery.db",
        "/etc/passwd",
        "C:\\Windows\\System32\\config\\SAM",
        "winery-20260101-000000.db/../../gizli-anahtarlar.json",
        "gizli-anahtarlar.json",
        ".env",
        "winery.db",  # kalibi tutmuyor (damga yok)
        "winery-2026-01-01.db",  # yanlis damga bicimi
        "kotu-20260101-000000.db",  # izinsiz onek
        "winery-20260101-000000.exe",  # izinsiz uzanti
    ],
)
def test_gecersiz_yedek_adi_reddedilir(ad: str, yedek_dizini: Path) -> None:
    with pytest.raises(ValueError):
        yedekleme.yedek_yolu(ad)


def test_gecerli_ad_kabul_edilir(yedek_dizini: Path) -> None:
    yol = yedekleme.yedek_yolu("winery-20260815-120000.db")
    assert yol.parent == yedek_dizini.resolve()
    yol2 = yedekleme.yedek_yolu("yuklemeler-20260815-120000.zip")
    assert yol2.parent == yedek_dizini.resolve()


# ------------------------------------------------------------------ listeleme
def test_yabanci_dosyalar_listelenmez(yedek_dizini: Path) -> None:
    """Yedek dizinine dusen ilgisiz dosya listede gorunmemeli."""
    (yedek_dizini / "winery-20260815-120000.db").write_bytes(b"x")
    (yedek_dizini / "notlar.txt").write_text("not", encoding="utf-8")
    (yedek_dizini / ".env").write_text("GIZLI=1", encoding="utf-8")

    adlar = {y.ad for y in yedekleme.yedekleri_listele()}
    assert adlar == {"winery-20260815-120000.db"}


def test_liste_yeniden_eskiye_siralanir(yedek_dizini: Path) -> None:
    import os
    import time

    for i, ad in enumerate(
        ["winery-20260101-000000.db", "winery-20260601-000000.db", "winery-20260815-000000.db"]
    ):
        p = yedek_dizini / ad
        p.write_bytes(b"x")
        os.utime(p, (time.time() + i, time.time() + i))

    liste = yedekleme.yedekleri_listele()
    assert [y.ad for y in liste] == [
        "winery-20260815-000000.db",
        "winery-20260601-000000.db",
        "winery-20260101-000000.db",
    ]


# ------------------------------------------------------------------ temizlik
def test_saklama_politikasi_en_yenileri_birakir(yedek_dizini: Path) -> None:
    import os
    import time

    adlar = [f"winery-2026080{i}-000000.db" for i in range(1, 6)]
    for i, ad in enumerate(adlar):
        p = yedek_dizini / ad
        p.write_bytes(b"x")
        os.utime(p, (time.time() + i, time.time() + i))

    silinen = yedekleme.eskileri_temizle(saklanan=2)
    kalan = {y.ad for y in yedekleme.yedekleri_listele()}

    assert len(kalan) == 2
    assert kalan == {"winery-20260805-000000.db", "winery-20260804-000000.db"}
    assert len(silinen) == 3


def test_saklama_sifir_olamaz(yedek_dizini: Path) -> None:
    """Kazayla tum yedekleri silmek mumkun olmamali."""
    with pytest.raises(ValueError):
        yedekleme.eskileri_temizle(saklanan=0)


def test_temizlik_turleri_ayri_sayar(yedek_dizini: Path) -> None:
    for ad in ("winery-20260801-000000.db", "winery-20260802-000000.db"):
        (yedek_dizini / ad).write_bytes(b"x")
    for ad in ("yuklemeler-20260801-000000.zip", "yuklemeler-20260802-000000.zip"):
        (yedek_dizini / ad).write_bytes(b"x")

    yedekleme.eskileri_temizle(saklanan=1)
    kalan = yedekleme.yedekleri_listele()
    assert len([y for y in kalan if y.tur == "veritabani"]) == 1
    assert len([y for y in kalan if y.tur == "yuklemeler"]) == 1


# --------------------------------------------------------------- gercek yedek
async def test_alinan_yedek_gecerli_bir_veritabani(
    yedek_dizini: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """VACUUM INTO ile alinan dosya gercekten acilabilmeli ve veri icermeli."""
    kaynak_dizin = tmp_path / "data"
    kaynak_dizin.mkdir()
    kaynak = kaynak_dizin / "winery.db"

    baglanti = sqlite3.connect(kaynak)
    baglanti.execute("PRAGMA journal_mode=WAL")
    baglanti.execute("CREATE TABLE partiler (id INTEGER PRIMARY KEY, ad TEXT)")
    baglanti.execute("INSERT INTO partiler (ad) VALUES ('Öküzgözü 2026')")
    baglanti.commit()
    # KAPATMADAN yedek al: WAL'de bekleyen islem var. Dosya kopyalansaydi
    # bu kayit yedege girmezdi.
    monkeypatch.setattr(yedekleme, "DATA_DIR", kaynak_dizin)

    sonuc = await yedekleme.yedek_al()
    baglanti.close()

    assert len(sonuc) == 1
    yedek = yedek_dizini / sonuc[0].ad
    assert yedek.is_file()

    kontrol = sqlite3.connect(yedek)
    try:
        satirlar = kontrol.execute("SELECT ad FROM partiler").fetchall()
    finally:
        kontrol.close()
    assert satirlar == [("Öküzgözü 2026",)], "WAL'deki kayıt yedeğe girmemiş"


async def test_veritabani_yoksa_anlasilir_hata(
    yedek_dizini: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(yedekleme, "DATA_DIR", tmp_path / "yok")
    with pytest.raises(FileNotFoundError):
        await yedekleme.yedek_al()


# ------------------------------------------------------------------- API
async def test_yetkisiz_kullanici_yedek_alamaz(client: AsyncClient, auth_headers) -> None:
    enolog_headers = await auth_headers(["enolog"], "enolog_yedek")
    yanit = await client.post("/api/v1/backups", headers=enolog_headers)
    assert yanit.status_code == 403


async def test_yetkisiz_kullanici_listeleyemez(client: AsyncClient, auth_headers) -> None:
    enolog_headers = await auth_headers(["enolog"], "enolog_yedek")
    yanit = await client.get("/api/v1/backups", headers=enolog_headers)
    assert yanit.status_code == 403


async def test_kimliksiz_erisim_reddedilir(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/backups")).status_code == 401


@pytest.mark.parametrize(
    "ad",
    [
        "..%2F..%2F.env",
        "gizli-anahtarlar.json",
        "winery.db",
        "ILK-GIRIS.txt",
        "..%5C..%5Cgizli-anahtarlar.json",
    ],
)
async def test_yol_kacisi_api_uzerinden_engellenir(
    client: AsyncClient, admin_headers, ad: str
) -> None:
    yanit = await client.get(f"/api/v1/backups/indir/{ad}", headers=admin_headers)
    assert yanit.status_code in (400, 404), f"{ad}: {yanit.status_code}"
    # Hicbir kosulda dosya icerigi donmemeli
    assert not yanit.headers.get("content-disposition")


async def test_api_yolu_asla_html_dondurmez(client: AsyncClient, admin_headers) -> None:
    """Bozuk bir API yolu, arayuz yakalayicisina dusup 200 HTML dondurmemeli.

    Aksi halde istemci hatayi basari sanir; ayrica bir uc noktanin var olup
    olmadigi belirsizlesir.
    """
    for yol in (
        "/api/v1/backups/indir/..%2F..%2F.env",
        "/api/v1/boyle-bir-uc-yok",
        "/api/v1/backups/indir/x/y/z",
    ):
        yanit = await client.get(yol, headers=admin_headers)
        assert yanit.status_code == 404, f"{yol}: {yanit.status_code}"
        assert "text/html" not in yanit.headers.get("content-type", ""), (
            f"{yol} arayüz sayfası döndürdü"
        )


async def test_yonetici_listeleyebilir(
    client: AsyncClient, admin_headers, yedek_dizini: Path
) -> None:
    yanit = await client.get("/api/v1/backups", headers=admin_headers)
    assert yanit.status_code == 200
    govde = yanit.json()
    assert "yedekler" in govde
    assert "disk" in govde
    assert govde["disk"]["disk_bos_bayt"] > 0
