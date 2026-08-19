"""Kullanici ve rol yonetimi."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.audit import record_audit
from app.core.deps import CurrentUser, SessionDep, require_perms
from app.core.i18n import dil_sec
from app.core.permissions import (
    Perm,
    permissions_for,
    rol_etiketleri,
    role_catalog,
    yetki_etiketleri,
)
from app.core.security import hash_password
from app.models.ops import AuditAction
from app.models.user import User, UserSession
from app.schemas.auth import (
    PasswordReset,
    RoleInfo,
    UserCreate,
    UserDetail,
    UserOut,
    UserUpdate,
)
from app.schemas.common import Message, Page

router = APIRouter(prefix="/users", tags=["Kullanıcılar"])

ReadUsers = Annotated[User, Depends(require_perms(Perm.USER_READ))]
WriteUsers = Annotated[User, Depends(require_perms(Perm.USER_WRITE))]


def _detail(user: User, request: Request | None = None) -> UserDetail:
    etiketler = rol_etiketleri(dil_sec(request))
    return UserDetail(
        **UserOut.model_validate(user).model_dump(),
        permissions=sorted(permissions_for(user.roles or [])),
        role_labels=[etiketler.get(r, r) for r in (user.roles or [])],
    )


@router.get("/roles", response_model=list[RoleInfo], summary="Rol ve yetki kataloğu")
async def list_roles(_user: CurrentUser) -> list[RoleInfo]:
    return [RoleInfo(**r) for r in role_catalog()]  # type: ignore[arg-type]


@router.get("/permissions", response_model=dict, summary="Yetki etiketleri")
async def list_permissions(request: Request, _user: CurrentUser) -> dict:
    return yetki_etiketleri(dil_sec(request))


@router.get("", response_model=Page[UserOut], summary="Kullanıcı listesi")
async def list_users(
    session: SessionDep,
    _user: ReadUsers,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, max_length=120),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
) -> Page[UserOut]:
    stmt = select(User)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(User.username.ilike(like), User.full_name.ilike(like), User.email.ilike(like))
        )
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(total_stmt)).scalar_one()
    rows = list(
        (
            await session.execute(
                stmt.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    # Rol filtresi JSON alan uzerinde uygulama katmaninda yapilir (tasinabilirlik)
    if role:
        rows = [r for r in rows if role in (r.roles or [])]

    return Page[UserOut](
        items=[UserOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}", response_model=UserDetail, summary="Kullanıcı detayı")
async def get_user(
    user_id: int, request: Request, session: SessionDep, _user: ReadUsers
) -> UserDetail:
    obj = await session.get(User, user_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kullanıcı bulunamadı.")
    return _detail(obj, request)


@router.post(
    "", response_model=UserDetail, status_code=status.HTTP_201_CREATED,
    summary="Kullanıcı oluştur",
)
async def create_user(
    payload: UserCreate, request: Request, session: SessionDep, user: WriteUsers
) -> UserDetail:
    obj = User(
        username=payload.username.strip().lower(),
        email=str(payload.email).strip().lower(),
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        roles=[str(r) for r in payload.roles],
        department=payload.department,
        phone=payload.phone,
        locale=payload.locale,
        theme=payload.theme,
        is_active=payload.is_active,
        must_change_password=True,
    )
    session.add(obj)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Bu kullanıcı adı veya e-posta zaten kayıtlı."
        ) from exc

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="users",
        entity_id=obj.id,
        entity_code=obj.username,
        summary=f"Kullanıcı oluşturuldu: {obj.username}",
        after=obj.to_dict(exclude={"password_hash"}),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(obj)
    return _detail(obj, request)


@router.patch("/{user_id}", response_model=UserDetail, summary="Kullanıcı güncelle")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    session: SessionDep,
    user: WriteUsers,
) -> UserDetail:
    obj = await session.get(User, user_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kullanıcı bulunamadı.")

    before = obj.to_dict(exclude={"password_hash"})
    data = payload.model_dump(exclude_unset=True)

    # Son aktif sistem yoneticisi yetkisiz birakilamaz / kapatilamaz
    if "sistem_yoneticisi" in (obj.roles or []) and (
        "roles" in data or data.get("is_active") is False
    ):
        new_roles = [str(r) for r in (data.get("roles") or obj.roles or [])]
        losing_admin = (
            "sistem_yoneticisi" not in new_roles or data.get("is_active") is False
        )
        if losing_admin:
            actives = (
                (await session.execute(select(User).where(User.is_active.is_(True))))
                .scalars()
                .all()
            )
            admins = [u for u in actives if "sistem_yoneticisi" in (u.roles or [])]
            if len(admins) <= 1:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Sistemde en az bir aktif sistem yöneticisi kalmalıdır.",
                )

    for k, v in data.items():
        if k == "roles" and v is not None:
            obj.roles = [str(r) for r in v]
        elif k == "email" and v is not None:
            obj.email = str(v).strip().lower()
        elif hasattr(obj, k):
            setattr(obj, k, v)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "E-posta zaten kullanılıyor.") from exc

    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="users",
        entity_id=obj.id,
        entity_code=obj.username,
        summary=f"Kullanıcı güncellendi: {obj.username}",
        before=before,
        after=obj.to_dict(exclude={"password_hash"}),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(obj)
    return _detail(obj, request)


@router.post("/{user_id}/reset-password", response_model=Message, summary="Parola sıfırla")
async def reset_password(
    user_id: int,
    payload: PasswordReset,
    request: Request,
    session: SessionDep,
    user: WriteUsers,
) -> Message:
    obj = await session.get(User, user_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kullanıcı bulunamadı.")

    obj.password_hash = hash_password(payload.new_password)
    obj.must_change_password = payload.must_change
    # Kurulum bayragi ASLA geri getirilmez. Parola sifirlama, bir kez
    # degistirilmis kurulum hesabini tekrar "kurulum modu"na dusuremez;
    # aksi halde varsayilan durum sifirlama yoluyla canlandirilabilirdi.
    obj.bootstrap_pending = False
    obj.failed_login_count = 0
    obj.locked_until = None

    stmt = select(UserSession).where(
        UserSession.user_id == obj.id, UserSession.revoked_at.is_(None)
    )
    for s in (await session.execute(stmt)).scalars().all():
        s.revoked_at = dt.datetime.now(dt.UTC)

    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="users",
        entity_id=obj.id,
        entity_code=obj.username,
        summary=f"Parola yönetici tarafından sıfırlandı: {obj.username}",
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    return Message(
        detail=f"{obj.username} kullanıcısının parolası sıfırlandı ve oturumları kapatıldı."
    )


@router.delete("/{user_id}", response_model=Message, summary="Kullanıcıyı pasife al")
async def deactivate_user(
    user_id: int, request: Request, session: SessionDep, user: WriteUsers
) -> Message:
    obj = await session.get(User, user_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kullanıcı bulunamadı.")
    if obj.id == user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Kendi hesabınızı pasife alamazsınız."
        )

    before = obj.to_dict(exclude={"password_hash"})
    obj.is_active = False
    await record_audit(
        session,
        action=AuditAction.SIL,
        entity_type="users",
        entity_id=obj.id,
        entity_code=obj.username,
        summary=f"Kullanıcı pasife alındı: {obj.username}",
        before=before,
        after=obj.to_dict(exclude={"password_hash"}),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    return Message(detail="Kullanıcı pasife alındı.")
