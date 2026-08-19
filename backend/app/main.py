"""FastAPI uygulama giris noktasi."""

from __future__ import annotations

import datetime as dt
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import __version__
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger, scrub
from app.core.ratelimit import RateLimitMiddleware
from app.db.base import Base
from app.db.session import SessionLocal, dispose_engine, engine
from app.models import *
from app.services.ai.base import ProviderError

log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log.info(
        "baslatiliyor",
        app=settings.APP_NAME,
        version=__version__,
        env=settings.APP_ENV,
        db="sqlite" if settings.is_sqlite else "postgresql",
    )

    # Sema Alembic ile yonetilir: `create_all` mevcut tabloya sutun eklemedigi
    # icin surum yukseltmelerinde (MSI) uygulama bozulurdu. Ayrintili gerekce:
    # app/db/sema.py
    from app.db.sema import semayi_hazirla

    try:
        sonuc = await semayi_hazirla()
    except Exception as exc:
        log.error("sema_guncellenemedi", detail=scrub(str(exc)))
        sonuc = "hata"

    if sonuc in ("alembic_yok", "hata"):
        # Goc dosyalari yoksa veya goc basarisizsa en azindan eksik tablolari
        # olustur; uygulama acilabilsin.
        log.warning("sema_yedek_yontem", detail="create_all kullaniliyor", sonuc=sonuc)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        log.info("sema_hazir", islem=sonuc)

    from app.db.ilk_kurulum import ilk_yoneticiyi_olustur
    from app.services.ai.registry import ensure_default_configs

    async with SessionLocal() as session:
        await ensure_default_configs(session)
        # Yeni kurulumda hic kullanici yoktur; hesap olusturulmazsa kimse
        # giris yapamaz. Parola gunluge YAZILMAZ, yalnizca dosyaya.
        dosya = await ilk_yoneticiyi_olustur(session)
        if dosya is not None:
            log.warning("ilk_yonetici_olusturuldu", parola_dosyasi=str(dosya))

    if settings.is_production:
        problems = []
        if not settings.DATABASE_URL:
            problems.append("DATABASE_URL tanımlı değil (üretimde PostgreSQL önerilir).")
        if "*" in settings.cors_origins:
            problems.append("CORS ayarı üretimde '*' olmamalıdır.")
        for p in problems:
            log.warning("uretim_uyarisi", detail=p)

    yield

    log.info("kapatiliyor")
    await dispose_engine()


app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description=(
        "Bağdan şişeye tüm şaraphane süreçlerini yöneten API. "
        "Yapay zekâ sağlayıcıları (LM Studio / Claude / NVIDIA) ortak bir "
        "soyutlama katmanı üzerinden kullanılır."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={"name": "Şaraphane Yönetim Sistemi"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Accept-Language"],
    expose_headers=["Content-Disposition", "X-RateLimit-Remaining"],
    max_age=600,
)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def security_headers(request: Request, call_next: Any) -> Any:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ------------------------------------------------------------- hata isleme
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for err in exc.errors():
        loc = " → ".join(str(x) for x in err.get("loc", []) if x != "body")
        errors.append({"alan": loc or "gövde", "hata": err.get("msg", "")})
    return JSONResponse(
        status_code=422,  # Unprocessable Content
        content={
            "detail": "Girdi doğrulaması başarısız.",
            "hatalar": errors,
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    log.warning("veritabani_kisit_ihlali", path=request.url.path, error=scrub(str(exc.orig)))
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": (
                "Kayıt işlemi veritabanı kısıtına takıldı. Benzersiz olması gereken "
                "bir alan (kod, ad veya e-posta) zaten kullanılıyor olabilir."
            )
        },
    )


@app.exception_handler(ProviderError)
async def provider_handler(request: Request, exc: ProviderError) -> JSONResponse:
    """Yapay zekâ sağlayıcı hataları 503 döner; mesaj zaten maskelenmiştir."""
    log.warning(
        "ai_saglayici_hatasi",
        path=request.url.path,
        kind=exc.kind,
        error=exc.safe_message,
    )
    code = (
        status.HTTP_401_UNAUTHORIZED
        if exc.kind == "yetkilendirme"
        else status.HTTP_429_TOO_MANY_REQUESTS
        if exc.kind == "hiz_siniri"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=code, content={"detail": exc.safe_message})


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    log.error(
        "veritabani_hatasi",
        path=request.url.path,
        error=scrub(str(exc)),
        traceback=scrub(traceback.format_exc()) if settings.DEBUG else None,
    )
    detail = "Veritabanı hatası oluştu. Sistem yöneticisine bildirin."
    if settings.DEBUG:
        detail += f" ({scrub(str(exc))[:300]})"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": detail}
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error(
        "beklenmeyen_hata",
        path=request.url.path,
        error_type=type(exc).__name__,
        error=scrub(str(exc)),
        traceback=scrub(traceback.format_exc()) if settings.DEBUG else None,
    )
    detail = "Beklenmeyen bir hata oluştu."
    if settings.DEBUG:
        detail += f" ({type(exc).__name__}: {scrub(str(exc))[:300]})"
    return JSONResponse(status_code=500, content={"detail": detail})


# ------------------------------------------------------------------ genel
@app.get("/health", tags=["Sistem"], summary="Sağlık kontrolü")
async def health() -> dict:
    return {
        "durum": "calisiyor",
        "uygulama": settings.APP_NAME,
        "surum": __version__,
        "ortam": settings.APP_ENV,
        "zaman": dt.datetime.now(dt.UTC).isoformat(),
    }


app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# --------------------------------------------------------------------- arayüz
# Derlenmiş arayüz varsa (masaüstü paketi veya `npm run build` sonrası) aynı
# süreçten sunulur; böylece tek kökene tek adres yeter, ayrı bir web sunucusu
# ya da CORS yapılandırması gerekmez. Yoksa API salt JSON olarak çalışır ve
# geliştirmede arayüzü Vite sunar.
if settings.frontend_available:
    _ARAYUZ = settings.frontend_dist_path
    _INDEX = _ARAYUZ / "index.html"

    _varliklar = _ARAYUZ / "assets"
    if _varliklar.is_dir():
        app.mount("/assets", StaticFiles(directory=_varliklar), name="varliklar")

    # `response_model=None`: donus tipi iki farkli Response sinifi oldugu icin
    # FastAPI'nin sema uretmeye calismasi engellenir.
    @app.get("/{spa_yolu:path}", include_in_schema=False, response_model=None)
    async def arayuz(spa_yolu: str) -> FileResponse | JSONResponse:
        """Tek sayfa uygulaması: gerçek dosya varsa onu, yoksa `index.html`.

        İstemci tarafı yönlendirme kullanıldığı için `/tanklar` gibi adresler
        sunucuda dosya karşılığı olmadan doğrudan açılabilmelidir.
        """
        # API yolları ASLA arayüze düşmemeli. Tanımlı bir uç noktayla
        # eşleşmeyen `/api/...` isteği (örneğin bozuk/normalize edilmiş bir
        # yol) buraya gelir; HTML dönmek istemciyi yanıltır ve hatayı
        # 200 gibi gösterir.
        if f"/{spa_yolu}".startswith((settings.API_V1_PREFIX, "/api")):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "Böyle bir uç nokta yok."},
            )

        if spa_yolu:
            aday = (_ARAYUZ / spa_yolu).resolve()
            # Yol kaçışına (`../`) karşı: sonuç mutlaka arayüz dizini içinde olmalı
            if aday.is_file() and aday.is_relative_to(_ARAYUZ.resolve()):
                return FileResponse(aday)
        return FileResponse(_INDEX)

else:

    @app.get("/", tags=["Sistem"], summary="Kök")
    async def root() -> dict:
        return {
            "mesaj": f"{settings.APP_NAME} API çalışıyor.",
            "surum": __version__,
            "dokumantasyon": "/docs",
            "api": settings.API_V1_PREFIX,
            "arayuz": "Derlenmemiş — geliştirmede Vite (5173) kullanın.",
        }
