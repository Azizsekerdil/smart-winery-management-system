"""Istatistik uc noktalari.

Her konu KENDI yetkisiyle korunur; tek bir `/statistics` ucu bilerek
kullanilmamistir. Gerekce: `satis_personeli` rolu `report:read` tasir ama
`cost:read`, `lab:read` ve `harvest:read` TASIMAZ. Tek bir uc, bu role
bilincli olarak kapatilmis maliyet ve laboratuvar verisini sizdirirdi.

Konu -> yetki eslesmesi:

    hasat         -> harvest:read
    fire          -> lot:read
    fermantasyon  -> fermentation:read
    laboratuvar   -> lab:read
    siseleme      -> bottling:read
    stok          -> inventory:read
    bakim         -> maintenance:read
    fici          -> barrel:read
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep, require_perms
from app.core.permissions import Perm
from app.models.user import User
from app.services import istatistik

router = APIRouter(prefix="/statistics", tags=["İstatistikler"])

OkuHasat = Annotated[User, Depends(require_perms(Perm.HARVEST_READ))]
OkuParti = Annotated[User, Depends(require_perms(Perm.LOT_READ))]
OkuFerm = Annotated[User, Depends(require_perms(Perm.FERMENTATION_READ))]
OkuLab = Annotated[User, Depends(require_perms(Perm.LAB_READ))]
OkuSiseleme = Annotated[User, Depends(require_perms(Perm.BOTTLING_READ))]
OkuStok = Annotated[User, Depends(require_perms(Perm.INVENTORY_READ))]
OkuBakim = Annotated[User, Depends(require_perms(Perm.MAINTENANCE_READ))]
OkuFici = Annotated[User, Depends(require_perms(Perm.BARREL_READ))]

Yil = Annotated[int | None, Query(ge=1900, le=2200, description="Rekolte yılı")]


@router.get("/hasat", summary="Bağ ve parsel verimi, kalite dağılımı")
async def hasat(session: SessionDep, _user: OkuHasat, yil: Yil = None) -> dict:
    return await istatistik.hasat(session, yil=yil)


@router.get("/fire", summary="Üzümden şişeye hacim kaybı hunisi")
async def fire(session: SessionDep, _user: OkuParti, yil: Yil = None) -> dict:
    return await istatistik.fire(session, yil=yil)


@router.get("/fermantasyon", summary="Fermantasyon süresi ve Brix düşüşü")
async def fermantasyon(session: SessionDep, _user: OkuFerm, yil: Yil = None) -> dict:
    return await istatistik.fermantasyon(session, yil=yil)


@router.get("/laboratuvar", summary="Spesifikasyon dışı oranı ve parametre trendleri")
async def laboratuvar(
    session: SessionDep,
    _user: OkuLab,
    baslangic: dt.date | None = None,
    bitis: dt.date | None = None,
) -> dict:
    return await istatistik.laboratuvar(session, baslangic=baslangic, bitis=bitis)


@router.get("/siseleme", summary="Üretim, verim ve fire oranları")
async def siseleme(session: SessionDep, _user: OkuSiseleme, yil: Yil = None) -> dict:
    return await istatistik.siseleme(session, yil=yil)


@router.get("/stok", summary="Tüketim ve hareketsiz stok")
async def stok(
    session: SessionDep,
    _user: OkuStok,
    gun: int = Query(90, ge=7, le=1095, description="Değerlendirme dönemi (gün)"),
) -> dict:
    return await istatistik.stok(session, gun=gun)


@router.get("/bakim", summary="Duruş, arıza sıklığı ve CIP doğrulama")
async def bakim(
    session: SessionDep,
    _user: OkuBakim,
    gun: int = Query(365, ge=7, le=1825),
) -> dict:
    return await istatistik.bakim(session, gun=gun)


@router.get("/fici", summary="Fıçı yaşı, kullanım ve buharlaşma kaybı")
async def fici(session: SessionDep, _user: OkuFici) -> dict:
    return await istatistik.fici(session)
