"""Basit, bagimliliksiz hiz sinirlama (sliding window sayaci).

Tek surec/tek makine dagitimi icin yeterlidir. Coklu isci (worker) veya yatay
olceklemede Redis tabanli bir sayaca gecirilmelidir - bkz. ARCHITECTURE.md.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings

_WINDOW = 60.0


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int) -> tuple[bool, int, float]:
        """(izin_var_mi, kalan, sifirlanma_saniyesi)"""
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - _WINDOW
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(0.0, bucket[0] + _WINDOW - now)
                return False, 0, retry_after
            bucket.append(now)
            return True, limit - len(bucket), _WINDOW

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


# Katı sınır YALNIZCA kimlik bilgisi doğrulayan uç noktalara uygulanır.
# `/auth/me` gibi okuma uç noktaları her sayfa yüklemesinde çağrıldığı için
# buraya DAHIL EDILMEZ; aksi hâlde sayfayı birkaç kez yenileyen normal bir
# kullanıcı kaba kuvvet koruması tarafından engellenirdi.
_KIMLIK_UC_NOKTALARI = ("/auth/login", "/auth/refresh", "/auth/change-password")


def _limit_for(path: str) -> int:
    onek = settings.API_V1_PREFIX
    if any(path.startswith(f"{onek}{uc}") for uc in _KIMLIK_UC_NOKTALARI):
        return settings.RATE_LIMIT_AUTH_PER_MINUTE
    if path.startswith((f"{onek}/ai", f"{onek}/terminal")):
        return settings.RATE_LIMIT_AI_PER_MINUTE
    return settings.RATE_LIMIT_DEFAULT_PER_MINUTE


def _client_key(request: Request) -> str:
    """Sayaç anahtarı: istemci IP'si + uç nokta grubu.

    Grup, yolun ilk dört parçasıdır (`/api/v1/<modül>`); böylece bir modülün
    yoğun kullanımı diğerini etkilemez.
    """
    fwd = request.headers.get("x-forwarded-for")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")
    grup = "/".join(request.url.path.split("/")[:4])
    return f"{ip}|{grup}|{_limit_for(request.url.path)}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not settings.RATE_LIMIT_ENABLED or request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in {"/health", "/api/health", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        limit = _limit_for(path)
        allowed, remaining, retry_after = limiter.check(_client_key(request), limit)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Çok fazla istek gönderildi. Lütfen biraz bekleyin.",
                    "retry_after_seconds": round(retry_after, 1),
                },
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
