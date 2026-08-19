"""Genel CRUD yonlendirici fabrikasi.

Amac: 12 modulde tekrarlanan liste/getir/olustur/guncelle/sil uc noktalarini tek
yerde, denetim gunlugu ve yetki kontrolu dahil olacak sekilde uretmek. Modullere
ozgu is mantigi (transfer, onay, izlenebilirlik) kendi yonlendiricilerinde kalir.
"""

# NOT: Bu modulde bilincli olarak `from __future__ import annotations` KULLANILMAZ.
# Fabrika fonksiyonu ic ice tanimlanan uc noktalarda YEREL degiskenleri
# (create_schema, ReadDep ...) tip acikamasi olarak kullanir; ertelenmis
# (string) acikamalar bu yerel adlari cozemez ve FastAPI sema uretimi patlar.

from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.audit import record_audit
from app.core.deps import CurrentUser, SessionDep, require_perms
from app.core.permissions import Perm
from app.models.ops import AuditAction
from app.models.user import User
from app.schemas.common import Message, Page, PageParams
from app.services.codes import next_code

ModelT = TypeVar("ModelT")
Enricher = Callable[[AsyncSession, Sequence[Any]], Awaitable[None]]


def _apply_search(
    stmt: Select[Any], model: Any, fields: Sequence[str], term: str
) -> Select[Any]:
    like = f"%{term.strip()}%"
    clauses = []
    for f in fields:
        attr = getattr(model, f, None)
        if isinstance(attr, InstrumentedAttribute):
            clauses.append(attr.ilike(like))
    return stmt.where(or_(*clauses)) if clauses else stmt


def build_crud_router(
    *,
    model: Any,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    out_schema: type[BaseModel],
    read_perm: Perm,
    write_perm: Perm,
    entity_label: str,
    tags: list[str],
    prefix: str,
    search_fields: Sequence[str] = ("code", "name"),
    default_sort: str = "id",
    code_prefix: str | None = None,
    generate_code: bool = True,
    enrich: Enricher | None = None,
    filters: dict[str, str] | None = None,
    allow_delete: bool = True,
    soft_delete_field: str | None = "is_active",
) -> APIRouter:
    """Bir model icin standart CRUD yonlendiricisi uretir.

    `filters`: sorgu parametresi adi -> model alan adi eslemesi.
    `soft_delete_field`: doluysa DELETE kaydi silmez, alani False yapar.
    """
    router = APIRouter(prefix=prefix, tags=tags)
    filters = filters or {}
    ReadDep = Annotated[User, Depends(require_perms(read_perm))]
    WriteDep = Annotated[User, Depends(require_perms(write_perm))]

    async def _enrich(session: AsyncSession, rows: Sequence[Any]) -> None:
        if enrich is not None and rows:
            await enrich(session, rows)

    # ------------------------------------------------------------- LISTE
    @router.get("", response_model=Page[out_schema], summary=f"{entity_label} listesi")
    async def list_items(  # type: ignore[no-untyped-def]
        request: Request,
        session: SessionDep,
        _user: ReadDep,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
        q: str | None = Query(None, max_length=200),
        sort: str | None = Query(None, max_length=64),
        desc: bool = Query(False),
    ):
        params = PageParams(page=page, page_size=page_size, q=q, sort=sort, desc=desc)
        stmt: Select[Any] = select(model)

        if params.q:
            stmt = _apply_search(stmt, model, search_fields, params.q)

        # Dinamik alan filtreleri (?status=aktif gibi)
        for param, field in filters.items():
            raw = request.query_params.get(param)
            if raw in (None, ""):
                continue
            attr = getattr(model, field, None)
            if attr is None:
                continue
            if "," in raw:
                stmt = stmt.where(attr.in_([v.strip() for v in raw.split(",")]))
            elif raw.lower() in ("true", "false"):
                stmt = stmt.where(attr.is_(raw.lower() == "true"))
            else:
                stmt = stmt.where(attr == raw)

        total = (
            await session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()

        sort_field = params.sort or default_sort
        sort_attr = getattr(model, sort_field, None) or model.id
        stmt = stmt.order_by(sort_attr.desc() if params.desc else sort_attr.asc())
        stmt = stmt.offset(params.offset).limit(params.page_size)

        rows = list((await session.execute(stmt)).scalars().unique().all())
        await _enrich(session, rows)
        return Page[out_schema](
            items=[out_schema.model_validate(r) for r in rows],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    # --------------------------------------------------------------- TEK
    @router.get("/{item_id}", response_model=out_schema, summary=f"{entity_label} detayı")
    async def get_item(item_id: int, session: SessionDep, _user: ReadDep):  # type: ignore[no-untyped-def]
        obj = await session.get(model, item_id)
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{entity_label} bulunamadı.")
        await _enrich(session, [obj])
        return out_schema.model_validate(obj)

    # ---------------------------------------------------------- OLUSTUR
    @router.post(
        "",
        response_model=out_schema,
        status_code=status.HTTP_201_CREATED,
        summary=f"{entity_label} oluştur",
    )
    async def create_item(  # type: ignore[no-untyped-def]
        payload: create_schema,  # type: ignore[valid-type]
        request: Request,
        session: SessionDep,
        user: WriteDep,
    ):
        data = payload.model_dump(exclude_unset=False, exclude_none=False)
        # Alt nesne listeleri bu genel katmanda islenmez
        data = {k: v for k, v in data.items() if hasattr(model, k)}
        # NOT NULL sutunlara None gondermek sunucu varsayilanlarini ezer;
        # bu alanlari tamamen atlayarak modeldeki varsayilanin gecerli olmasini saglar.
        columns = model.__table__.columns
        data = {
            k: v
            for k, v in data.items()
            if not (v is None and k in columns and not columns[k].nullable)
        }

        if generate_code and not data.get("code"):
            data["code"] = await next_code(session, model, prefix=code_prefix)

        obj = model(**data)
        if hasattr(obj, "created_by_id"):
            obj.created_by_id = user.id
        session.add(obj)
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{entity_label} kaydedilemedi: benzersiz alan çakışması "
                "(kod veya ad zaten kullanılıyor).",
            ) from exc

        await record_audit(
            session,
            action=AuditAction.OLUSTUR,
            entity_type=model.__tablename__,
            entity_id=obj.id,
            entity_code=getattr(obj, "code", None),
            summary=f"{entity_label} oluşturuldu",
            after=obj.to_dict(),
            user=user,
            request=request,
        )
        await session.commit()
        await session.refresh(obj)
        await _enrich(session, [obj])
        return out_schema.model_validate(obj)

    # --------------------------------------------------------- GUNCELLE
    @router.patch("/{item_id}", response_model=out_schema, summary=f"{entity_label} güncelle")
    async def update_item(  # type: ignore[no-untyped-def]
        item_id: int,
        payload: update_schema,  # type: ignore[valid-type]
        request: Request,
        session: SessionDep,
        user: WriteDep,
    ):
        obj = await session.get(model, item_id)
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{entity_label} bulunamadı.")

        before = obj.to_dict()
        changes = payload.model_dump(exclude_unset=True)
        for k, v in changes.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        if hasattr(obj, "updated_by_id"):
            obj.updated_by_id = user.id

        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"{entity_label} güncellenemedi: alan çakışması."
            ) from exc

        await record_audit(
            session,
            action=AuditAction.GUNCELLE,
            entity_type=model.__tablename__,
            entity_id=obj.id,
            entity_code=getattr(obj, "code", None),
            summary=f"{entity_label} güncellendi",
            before=before,
            after=obj.to_dict(),
            user=user,
            request=request,
        )
        await session.commit()
        await session.refresh(obj)
        await _enrich(session, [obj])
        return out_schema.model_validate(obj)

    # --------------------------------------------------------------- SIL
    if allow_delete:

        @router.delete("/{item_id}", response_model=Message, summary=f"{entity_label} sil")
        async def delete_item(  # type: ignore[no-untyped-def]
            item_id: int,
            request: Request,
            session: SessionDep,
            user: WriteDep,
            hard: bool = Query(False, description="Kalıcı sil (yalnızca gerekliyse)"),
        ):
            obj = await session.get(model, item_id)
            if obj is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, f"{entity_label} bulunamadı."
                )
            before = obj.to_dict()

            use_soft = bool(soft_delete_field) and hasattr(obj, soft_delete_field or "")
            if use_soft and not hard:
                setattr(obj, soft_delete_field, False)  # type: ignore[arg-type]
                summary = f"{entity_label} pasife alındı"
            else:
                try:
                    await session.delete(obj)
                    await session.flush()
                except IntegrityError as exc:
                    await session.rollback()
                    raise HTTPException(
                        status.HTTP_409_CONFLICT,
                        f"{entity_label} silinemedi: bağlı kayıtlar var. "
                        "Önce ilişkili kayıtları kaldırın veya pasife alın.",
                    ) from exc
                summary = f"{entity_label} silindi"

            await record_audit(
                session,
                action=AuditAction.SIL,
                entity_type=model.__tablename__,
                entity_id=item_id,
                entity_code=before.get("code"),
                summary=summary,
                before=before,
                user=user,
                request=request,
                severity="uyari",
            )
            await session.commit()
            return Message(detail=summary + ".")

    return router


async def get_or_404(session: AsyncSession, model: Any, item_id: int, label: str) -> Any:
    obj = await session.get(model, item_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} bulunamadı (id={item_id}).")
    return obj


async def label_map(
    session: AsyncSession,
    model: Any,
    ids: Iterable[int | None],
    *,
    field: str = "name",
) -> dict[int, str]:
    """`{id: etiket}` sozlugu uretir; liste yanitlarini zenginlestirmek icin.

    N+1 sorgusunu onlemek amaciyla tek IN sorgusu kullanir. `None` kimlikler
    yok sayilir; kume bossa sorgu HIC calistirilmaz.
    """
    clean = {int(i) for i in ids if i is not None}
    if not clean:
        return {}
    rows = (
        await session.execute(
            select(model.id, getattr(model, field)).where(model.id.in_(clean))
        )
    ).all()
    return {int(row[0]): str(row[1]) for row in rows}


__all__ = ["CurrentUser", "build_crud_router", "get_or_404", "label_map"]
