"""Uygulama yapilandirmasi.

Tum gizli degerler ortam degiskenlerinden (veya .env dosyasindan) okunur.
Kaynak kodda hicbir zaman gercek anahtar bulunmaz.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DONMUS = bool(getattr(sys, "frozen", False))

if DONMUS:
    # PyInstaller paketi: kaynaklar her calistirmada GECICI bir dizine acilir.
    # Kalici olan tek konum calistirilabilir dosyanin bulundugu dizindir.
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    # D:\Wine\backend\app\core\config.py -> D:\Wine
    PROJECT_ROOT = Path(__file__).resolve().parents[3]

BACKEND_ROOT = PROJECT_ROOT / "backend"
DOCS_DIR = PROJECT_ROOT / "docs"


def _yazilabilir_mi(dizin: Path) -> bool:
    """Dizine GERCEKTEN yazilabildigini dener.

    Windows'ta izin bayraklarina bakmak yeterli degildir: ACL'ler, UAC sanal
    dizin yonlendirmesi ve salt okunur baglamalar ancak yazma denendiginde
    ortaya cikar. Bu yuzden gecici bir dosya olusturulup hemen silinir.
    """
    if not dizin.is_dir():
        return False
    deneme = dizin / f".yazma_denemesi_{os.getpid()}"
    try:
        deneme.touch()
        deneme.unlink()
    except OSError:
        return False
    return True


def _veri_koku(donmus: bool, kaynak_koku: Path) -> Path:
    """Veritabani, gunluk ve yuklemelerin yazilacagi kok dizin.

    Kaynak dosyalarindan (kod, derlenmis arayuz) AYRI tutulur; cunku MSI ile
    ``C:\\Program Files`` altina kurulan bir uygulama kendi dizinine yazamaz.

    Sirasiyla:
      1. ``SARAPHANE_VERI_DIZINI`` ortam degiskeni — her seyi ezer
      2. Gelistirme — proje kokii (``D:\\Wine``)
      3. Tasinabilir paket — exe'nin yanindaki dizin yazilabiliyorsa orasi
         (zip acilmis kullanim; veri uygulamayla birlikte tasinir)
      4. Kurulu paket — ``%LOCALAPPDATA%\\Saraphane`` (Program Files yazilamaz)

    Saf fonksiyondur: kararini yalnizca parametrelerden ve ortamdan alir,
    boylece dort senaryonun tamami test edilebilir.
    """
    ozel = os.environ.get("SARAPHANE_VERI_DIZINI", "").strip()
    if ozel:
        return Path(ozel).expanduser().resolve()

    if not donmus:
        return kaynak_koku

    if _yazilabilir_mi(kaynak_koku):
        return kaynak_koku

    yerel = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    taban = Path(yerel) if yerel else Path.home()
    return (taban / "Saraphane").resolve()


VERI_KOKU = _veri_koku(DONMUS, PROJECT_ROOT)
DATA_DIR = VERI_KOKU / "data"
LOGS_DIR = VERI_KOKU / "logs"
UPLOADS_DIR = DATA_DIR / "uploads"
BACKUPS_DIR = DATA_DIR / "backups"

# Otomatik uretilen gizli anahtarlarin saklandigi dosya. ASLA depoya girmez ve
# yalnizca `.env`/ortam degiskeni verilmediginde kullanilir.
GIZLI_DOSYASI = DATA_DIR / "gizli-anahtarlar.json"


def _kalici_gizli_anahtar(ad: str) -> str:
    """Verilmeyen gizli anahtari uretir; ayni degeri sonraki acilislarda doner.

    Dosya okunamaz veya yazilamazsa surec-basina rastgele degere duselir:
    uygulama calismaya devam eder, ancak yeniden baslatmada oturumlar duser.
    """
    try:
        if GIZLI_DOSYASI.is_file():
            mevcut = json.loads(GIZLI_DOSYASI.read_text(encoding="utf-8"))
            deger = mevcut.get(ad)
            if isinstance(deger, str) and deger:
                return deger
        else:
            mevcut = {}
    except (OSError, ValueError):
        return secrets.token_urlsafe(48)

    yeni = secrets.token_urlsafe(48)
    mevcut[ad] = yeni
    try:
        GIZLI_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
        GIZLI_DOSYASI.write_text(json.dumps(mevcut, indent=2), encoding="utf-8")
        # Dosyayi yalnizca sahibinin okuyabilmesi icin daralt (POSIX'te etkili;
        # Windows'ta kullanici profili zaten ACL ile korunur).
        with contextlib.suppress(OSError, NotImplementedError):
            GIZLI_DOSYASI.chmod(0o600)
    except OSError:
        pass
    return yeni


class Settings(BaseSettings):
    """Ortam degiskeni tabanli ayarlar."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ genel
    APP_NAME: str = "Akilli Saraphane Yonetim Sistemi"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "127.0.0.1"
    # 8000 Windows'ta sik kullanilan bir port (Django vb.); catisma yasanmamasi
    # icin varsayilan 8010'dur. .env icinden degistirilebilir.
    PORT: int = 8010
    DEFAULT_LOCALE: Literal["tr", "en"] = "tr"

    # ------------------------------------------------------------- veritabani
    # Gelistirme: SQLite (aiosqlite). Uretim: PostgreSQL (asyncpg).
    DATABASE_URL: str = ""

    # ------------------------------------------------------------- guvenlik
    # Uretimde MUTLAKA .env uzerinden verilmelidir. Bos ise gelistirme icin
    # sureç basina rastgele uretilir (yeniden baslatmada oturumlar duser).
    SECRET_KEY: str = Field(default="")
    # API anahtarlarini veritabaninda sifrelemek icin kullanilan ana anahtar.
    SECRETS_ENCRYPTION_KEY: str = Field(default="")

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 saat - bir vardiya
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    JWT_ALGORITHM: str = "HS256"

    PASSWORD_MIN_LENGTH: int = 10
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # CORS - uretimde daraltilir
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Hiz sinirlama (dakika basina istek)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 300
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_AI_PER_MINUTE: int = 30

    # Dosya yukleme
    MAX_UPLOAD_MB: int = 15
    ALLOWED_UPLOAD_EXTENSIONS: str = ".pdf,.png,.jpg,.jpeg,.webp,.csv,.xlsx,.txt"

    # ------------------------------------------------------------------- AI
    AI_ENABLED: bool = True
    AI_DEFAULT_PROVIDER: str = "lmstudio"
    AI_REQUEST_TIMEOUT_SECONDS: int = 120
    AI_MAX_RETRIES: int = 2

    # LM Studio (yerel, OpenAI uyumlu)
    LMSTUDIO_ENABLED: bool = True
    LMSTUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LMSTUDIO_MODEL: str = ""
    LMSTUDIO_EMBEDDING_MODEL: str = "text-embedding-nomic-embed-text-v1.5"

    # Anthropic Claude
    ANTHROPIC_ENABLED: bool = True
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com/v1"
    ANTHROPIC_MODEL: str = ""
    ANTHROPIC_VERSION: str = "2023-06-01"

    # NVIDIA Build (OpenAI uyumlu)
    NVIDIA_ENABLED: bool = True
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = ""

    # Genel OpenAI uyumlu ek saglayici
    OPENAI_COMPAT_ENABLED: bool = False
    OPENAI_COMPAT_NAME: str = "openai-compat"
    OPENAI_COMPAT_API_KEY: str = ""
    OPENAI_COMPAT_BASE_URL: str = ""
    OPENAI_COMPAT_MODEL: str = ""

    # ------------------------------------------------------- AI terminal/ajan
    # Paketlenmis (masaustu/MSI) surumde VARSAYILAN OLARAK KAPALI. AI terminali
    # bir GELISTIRICI aracidir: kaynak kodu duzenler, testleri calistirir ve Git
    # kontrol noktasi olusturur. Son kullanici kurulumunda ne kaynak kod ne de
    # Git deposu bulunur; acik birakmak hicbir fayda saglamadan komut calistirma
    # yuzeyi eklerdi. Gerekirse AGENT_ENABLED=true ile bilincli olarak acilir.
    AGENT_ENABLED: bool = not DONMUS
    # Ajanin yazabilecegi TEK kok dizin. Disina cikis kod duzeyinde engellenir.
    AGENT_WORKSPACE: str = str(PROJECT_ROOT)
    AGENT_COMMAND_TIMEOUT_SECONDS: int = 180
    AGENT_MAX_OUTPUT_BYTES: int = 256_000
    AGENT_REQUIRE_APPROVAL: bool = True
    # Paket kurulumu (`pip install`, `npm install/ci`, `npx`) VARSAYILAN OLARAK
    # KAPALIDIR. Bir paketin kurulum betigi, izin listesinden ve yol hapsinden
    # BAGIMSIZ olarak rastgele kod calistirir; yani izin listesini teknik olarak
    # gecersiz kilar. Onay bayragi bunu engellemez, cunku onay bir POLITIKA
    # kontroludur, teknik sinir degildir. Gercekten gerekiyorsa bilincli olarak
    # acilir ve kurulan paketler el ile incelenir.
    AGENT_ALLOW_PACKAGE_INSTALL: bool = False

    # Derlenmis arayuzun yolu. Bos birakilirsa otomatik bulunur
    # (gelistirmede `frontend/dist`, masaustu paketinde paket ici `arayuz`).
    FRONTEND_DIST: str = ""

    # ------------------------------------------------------------- kayit/log
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_JSON: bool = False
    LOG_FILE: str = str(LOGS_DIR / "app.log")

    # --------------------------------------------------------------- demo
    SEED_DEMO_DATA: bool = True

    # ------------------------------------------------------------ dogrulama
    @field_validator("SECRET_KEY", "SECRETS_ENCRYPTION_KEY", mode="after")
    @classmethod
    def _fill_dev_secret(cls, v: str, info) -> str:
        """Verilmeyen gizli anahtari uretir ve KALICI hale getirir.

        Onceden her surecte yeniden uretiliyordu. Kurulu (MSI) surumde `.env`
        Program Files altinda kaldigi ve yazilamadigi icin bu, her acilista
        farkli bir sifreleme anahtari demekti: kullanicinin kaydettigi API
        anahtarlari cozulemez hale gelir ve `decrypt_secret` bunu sessizce bos
        dize olarak dondururdu -- yani veri, hata mesaji bile olmadan kaybolurdu.
        Ayni sebeple her acilista tum oturumlar duserdi.

        Bu yuzden uretilen anahtar veri kokunde saklanir. `.env` veya ortam
        degiskeni verilmisse dosyaya hic bakilmaz.
        """
        if v:
            return v
        return _kalici_gizli_anahtar(str(info.field_name))

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{(DATA_DIR / 'winery.db').as_posix()}"

    @property
    def sync_database_url(self) -> str:
        """Alembic ve yedekleme betikleri icin senkron surucu URL'si."""
        url = self.database_url
        return url.replace("+aiosqlite", "").replace("+asyncpg", "")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_upload_extensions(self) -> set[str]:
        return {
            e.strip().lower()
            for e in self.ALLOWED_UPLOAD_EXTENSIONS.split(",")
            if e.strip()
        }

    @property
    def agent_workspace_path(self) -> Path:
        return Path(self.AGENT_WORKSPACE).resolve()

    @property
    def frontend_dist_path(self) -> Path:
        """Derlenmis arayuzun bulundugu dizin.

        Masaustu paketinde (PyInstaller) kaynaklar gecici bir dizine acilir;
        `sys._MEIPASS` varsa oradan okunur.
        """
        if self.FRONTEND_DIST:
            return Path(self.FRONTEND_DIST).resolve()
        paket_koku = getattr(sys, "_MEIPASS", None)
        if paket_koku:
            return Path(paket_koku) / "arayuz"
        return PROJECT_ROOT / "frontend" / "dist"

    @property
    def frontend_available(self) -> bool:
        """Arayuz derlenmis mi? Degilse API salt JSON olarak calisir."""
        return (self.frontend_dist_path / "index.html").is_file()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    for d in (DATA_DIR, LOGS_DIR, UPLOADS_DIR, BACKUPS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    return s


settings = get_settings()
