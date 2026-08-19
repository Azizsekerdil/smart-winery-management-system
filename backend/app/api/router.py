"""Tum v1 yonlendiricilerinin toplandigi yer."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    ai,
    auth,
    cellar,
    dashboard,
    egitim,
    inventory,
    istatistik,
    ops,
    production,
    quality,
    reports,
    terminal,
    users,
    vineyards,
    yedekleme,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)

for module in (vineyards, production, quality, cellar, inventory, ops):
    for sub in module.routers:
        api_router.include_router(sub)

api_router.include_router(reports.router)
api_router.include_router(istatistik.router)
api_router.include_router(egitim.router)
api_router.include_router(ai.router)
api_router.include_router(terminal.router)
api_router.include_router(yedekleme.router)
