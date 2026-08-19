# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller yapilandirmasi — Akilli Saraphane Yonetim Sistemi masaustu paketi.

Calistirma:
    powershell -ExecutionPolicy Bypass -File scripts\masaustu-paketle.ps1

Cikti:
    dist\Saraphane\Saraphane.exe

Not: `--onedir` (tek klasor) kullanilir, `--onefile` degil. Sebep: tek dosya
paketi her acilista ~100 MB'i gecici dizine acar; acilis birkac saniye uzar ve
antivirus yazilimlari bu davranisi sik sik karantinaya alir. Tek klasor paketi
hem hizli acilir hem de veri dizini (`data\`, `logs\`) exe'nin yaninda kalir.
"""

import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

KOK = Path(SPECPATH).parent
ARAYUZ = KOK / "frontend" / "dist"

# Surum, uygulamanin tek dogruluk kaynagindan okunur.
_surum_metni = (KOK / "backend" / "app" / "__init__.py").read_text(encoding="utf-8")
SURUM = re.search(r'__version__\s*=\s*"([^"]+)"', _surum_metni).group(1)
SURUM_DORTLU = tuple(int(p) for p in (SURUM.split(".") + ["0", "0", "0"])[:4])

if not (ARAYUZ / "index.html").is_file():
    raise SystemExit(
        "Arayuz derlenmemis. Once calistirin:  cd frontend; npm run build"
    )

# Derlenmis arayuz paket icine `arayuz` adiyla gomulur; `settings.
# frontend_dist_path` calisma aninda `sys._MEIPASS/arayuz` yolunu okur.
veriler = [(str(ARAYUZ), "arayuz")]

# Alembic goc dosyalari sema yukseltmesi icin gereklidir.
gocler = KOK / "backend" / "alembic"
if gocler.is_dir():
    veriler.append((str(gocler), "alembic"))

# Dinamik olarak ice aktarilan moduller statik analizde gorunmez.
gizli = [
    *collect_submodules("uvicorn"),
    *collect_submodules("app.models"),
    *collect_submodules("app.api.v1"),
    "aiosqlite",
    "sqlalchemy.dialects.sqlite.aiosqlite",
    "passlib.handlers.argon2",
    "argon2",
    "email_validator",
]

veriler += collect_data_files("webview")

# Belgeler: RAG indeksleme `DOCS_DIR` altini tarar. Pakete girmezse kurulu
# surumde "Belgeleri indeksle" sessizce 0 sonucla doner.
belgeler = KOK / "docs"
if belgeler.is_dir():
    veriler.append((str(belgeler), "docs"))

# Alembic yapilandirmasi. Sema yukseltmesi bunsuz calistirilamaz.
alembic_ini = KOK / "backend" / "alembic.ini"
if alembic_ini.is_file():
    veriler.append((str(alembic_ini), "."))

# ------------------------------------------------------------- surum kaynagi
# Windows'un dosya ozelliklerinde ve UAC/SmartScreen iletisim kutularinda
# gorunen bilgi. Kaynak yoksa dosya "bilinmeyen yayinci, surumsuz" gorunur.
surum_kaynagi = f"""
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={SURUM_DORTLU}, prodvers={SURUM_DORTLU},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('041F04B0', [
        StringStruct('CompanyName', 'Şaraphane'),
        StringStruct('FileDescription', 'Akıllı Şaraphane Yönetim Sistemi'),
        StringStruct('FileVersion', '{SURUM}'),
        StringStruct('InternalName', 'Saraphane'),
        StringStruct('LegalCopyright', 'Tüm hakları saklıdır.'),
        StringStruct('OriginalFilename', 'Saraphane.exe'),
        StringStruct('ProductName', 'Akıllı Şaraphane Yönetim Sistemi'),
        StringStruct('ProductVersion', '{SURUM}'),
      ])
    ]),
    # 0x041F = Turkce, 0x04B0 = Unicode
    VarFileInfo([VarStruct('Translation', [0x041F, 1200])])
  ]
)
"""
_surum_dosyasi = KOK / "build" / "surum_bilgisi.txt"
_surum_dosyasi.parent.mkdir(parents=True, exist_ok=True)
_surum_dosyasi.write_text(surum_kaynagi, encoding="utf-8")

a = Analysis(
    [str(KOK / "desktop" / "masaustu.py")],
    pathex=[str(KOK / "backend")],
    binaries=[],
    datas=veriler,
    hiddenimports=gizli,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Gelistirme araclari pakete girmemeli: boyutu buyuturler ve son
    # kullanicida hicbir islevleri yoktur.
    excludes=["pytest", "mypy", "ruff", "playwright", "IPython", "tkinter"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Saraphane",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # pencereli uygulama; konsol acilmaz
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(KOK / "desktop" / "saraphane.ico"),
    version=str(_surum_dosyasi),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Saraphane",
)
