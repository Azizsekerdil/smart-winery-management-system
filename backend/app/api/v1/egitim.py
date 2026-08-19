"""Egitim modulu ilerleme uc noktalari.

Egitim ICERIGI arayuzde tutulur (iki dilli, paketle birlikte gelir). Burada
yalnizca kimin neyi tamamladigi saklanir.

Yetki: ozel bir yetki YOKTUR — egitim her kullaniciya aciktir. Bir kullanici
YALNIZCA KENDI ilerlemesini gorur ve yazar; baskasinin kaydina erisemez.
Ekip ozeti ise `user:read` yetkisi ister (yonetici, kimin egitildigi bilgisini
denetim ve gida guvenligi icin gormek zorundadir).
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import CurrentUser, SessionDep, require_perms
from app.core.permissions import Perm
from app.models.egitim import EgitimIlerleme
from app.models.user import User

router = APIRouter(prefix="/training", tags=["Eğitim"])

OkuKullanici = Annotated[User, Depends(require_perms(Perm.USER_READ))]


class SinavSonucu(BaseModel):
    """Bir modul sinavinin sonucu."""

    correct_count: int = Field(ge=0, le=100)
    question_count: int = Field(ge=1, le=100)


class IlerlemeOut(BaseModel):
    module_code: str
    correct_count: int
    question_count: int
    score_percent: float
    passed: bool
    attempt_count: int
    completed_at: dt.datetime | None


def _cikti(kayit: EgitimIlerleme) -> IlerlemeOut:
    return IlerlemeOut(
        module_code=kayit.module_code,
        correct_count=kayit.correct_count,
        question_count=kayit.question_count,
        score_percent=kayit.score_percent,
        passed=kayit.passed,
        attempt_count=kayit.attempt_count,
        completed_at=kayit.completed_at,
    )


@router.get("/progress", response_model=list[IlerlemeOut], summary="Kendi ilerlemem")
async def ilerlemem(session: SessionDep, user: CurrentUser) -> list[IlerlemeOut]:
    kayitlar = (
        (
            await session.execute(
                select(EgitimIlerleme).where(EgitimIlerleme.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    return [_cikti(k) for k in kayitlar]


@router.post(
    "/progress/{module_code}",
    response_model=IlerlemeOut,
    summary="Modül sınavı sonucunu kaydet",
)
async def sonucu_kaydet(
    module_code: str,
    payload: SinavSonucu,
    session: SessionDep,
    user: CurrentUser,
) -> IlerlemeOut:
    if payload.correct_count > payload.question_count:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Doğru cevap sayısı, soru sayısından büyük olamaz.",
        )

    kayit = (
        await session.execute(
            select(EgitimIlerleme).where(
                EgitimIlerleme.user_id == user.id,
                EgitimIlerleme.module_code == module_code,
            )
        )
    ).scalar_one_or_none()

    if kayit is None:
        # Sayaclar ACIKCA sifirlanir: SQLAlchemy'nin `default=0` degeri yalnizca
        # INSERT sirasinda uygulanir, nesne olusturulur olusturulmaz `None`dir
        # ve asagidaki `+= 1` islemi TypeError verirdi.
        kayit = EgitimIlerleme(
            user_id=user.id,
            module_code=module_code,
            correct_count=0,
            question_count=0,
            attempt_count=0,
        )
        session.add(kayit)

    kayit.attempt_count += 1
    # EN IYI sonuc korunur: tekrar deneyip daha dusuk puan almak, daha once
    # kazanilmis basariyi silmemeli.
    yeni_oran = payload.correct_count / payload.question_count
    eski_oran = (
        kayit.correct_count / kayit.question_count if kayit.question_count else -1.0
    )
    if yeni_oran >= eski_oran:
        kayit.correct_count = payload.correct_count
        kayit.question_count = payload.question_count

    if kayit.passed and kayit.completed_at is None:
        kayit.completed_at = dt.datetime.now(dt.UTC)

    await session.commit()
    await session.refresh(kayit)
    return _cikti(kayit)


class EkipSatiri(BaseModel):
    user_id: int
    username: str
    full_name: str
    roles: list[str]
    tamamlanan: int
    denenen: int


@router.get("/team", response_model=list[EkipSatiri], summary="Ekip eğitim durumu")
async def ekip_durumu(session: SessionDep, _user: OkuKullanici) -> list[EkipSatiri]:
    """Kimin hangi eğitimi tamamladığı — denetim ve gıda güvenliği için."""
    kullanicilar = (
        (await session.execute(select(User).where(User.is_active.is_(True))))
        .scalars()
        .all()
    )
    kayitlar = (await session.execute(select(EgitimIlerleme))).scalars().all()

    gruplu: dict[int, list[EgitimIlerleme]] = {}
    for k in kayitlar:
        gruplu.setdefault(k.user_id, []).append(k)

    return [
        EkipSatiri(
            user_id=u.id,
            username=u.username,
            full_name=u.full_name,
            roles=list(u.roles or []),
            tamamlanan=sum(1 for k in gruplu.get(u.id, []) if k.passed),
            denenen=len(gruplu.get(u.id, [])),
        )
        for u in kullanicilar
    ]
