"""Kimlik dogrulama uc noktalari."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import or_, select

from app.core.audit import record_audit
from app.core.config import settings
from app.core.deps import CurrentUser, SessionDep
from app.core.i18n import dil_sec
from app.core.permissions import permissions_for, rol_etiketleri
from app.core.security import (
    TokenError,
    create_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.models.ops import AuditAction
from app.models.user import User, UserSession
from app.schemas.auth import (
    AccessToken,
    LoginRequest,
    PasswordChange,
    PreferencesUpdate,
    RefreshRequest,
    TokenPair,
    UserDetail,
    UserOut,
)
from app.schemas.common import Message


def _kurulum_parola_dosyasini_sil() -> None:
    """Ilk giris parolasinin yazildigi dosyayi siler (artik gecersiz)."""
    from contextlib import suppress

    from app.db.ilk_kurulum import ILK_GIRIS_DOSYASI

    with suppress(OSError):
        ILK_GIRIS_DOSYASI.unlink(missing_ok=True)

router = APIRouter(prefix="/auth", tags=["Kimlik Doğrulama"])

# Ilk kurulum hesabinin giris yapabilecegi adresler. Kurulum parolasi bir kez
# diske yazildigi icin bu hesap ag uzerinden ERISILEBILIR OLMAMALIDIR.
_YEREL_ADRESLER = frozenset({"127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1"})


def _yerel_istemci_mi(request: Request) -> bool:
    """Istek gercekten bu makineden mi geliyor?

    `X-Forwarded-For` BILEREK dikkate alinmaz: istemcinin gonderdigi bir baslik
    guven kaynagi olamaz, aksi halde uzak bir saldirgan basligi 127.0.0.1 yazip
    kurulum hesabina ag uzerinden girebilirdi.
    """
    if request.client is None:
        return False
    return request.client.host in _YEREL_ADRESLER


def _user_detail(user: User, request: Request | None = None) -> UserDetail:
    perms = sorted(permissions_for(user.roles or []))
    # Rol adlari `Accept-Language` basligina gore secilir; arayuz Ingilizce
    # secildiginde bu etiketler Turkce kalirsa ekran yarim cevrilmis gorunur.
    etiketler = rol_etiketleri(dil_sec(request))
    return UserDetail(
        **UserOut.model_validate(user).model_dump(),
        permissions=perms,
        role_labels=[etiketler.get(r, r) for r in (user.roles or [])],
    )


@router.post("/login", response_model=TokenPair, summary="Oturum aç")
async def login(payload: LoginRequest, request: Request, session: SessionDep) -> TokenPair:
    ident = payload.username.strip().lower()
    stmt = select(User).where(
        or_(User.username == ident, User.email == ident)
    )
    user = (await session.execute(stmt)).scalar_one_or_none()

    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kullanıcı adı veya parola hatalı.",
    )

    if user is None:
        # Kullanici numaralandirmasini engellemek icin ayni hata ve benzer sure
        verify_password(payload.password, "$argon2id$v=19$m=65536,t=3,p=4$" + "A" * 22)
        await record_audit(
            session,
            action=AuditAction.GIRIS_BASARISIZ,
            entity_type="users",
            summary=f"Bilinmeyen kullanıcı ile giriş denemesi: {ident[:64]}",
            request=request,
            severity="uyari",
            commit=True,
        )
        raise generic_error

    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=(
                f"Hesap {settings.LOGIN_LOCKOUT_MINUTES} dakika süreyle kilitlendi. "
                "Lütfen daha sonra tekrar deneyin."
            ),
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Hesap pasif durumda."
        )

    # --------------------------------------- ILK KURULUM HESABI: YALNIZCA YEREL
    # Parola degistirilene kadar bu hesaba ag uzerinden giris yapilamaz.
    # Parola dogrulanmadan ONCE reddedilir; boylece uzaktan kaba kuvvet
    # denemesi hicbir bilgi (dogru/yanlis ayrimi) sizdirmaz.
    if getattr(user, "bootstrap_pending", False) and not _yerel_istemci_mi(request):
        await record_audit(
            session,
            action=AuditAction.GIRIS_BASARISIZ,
            entity_type="users",
            entity_id=user.id,
            summary=(
                "Kurulum hesabina AG UZERINDEN giris denemesi reddedildi "
                "(parola degistirilene kadar yalnizca yerel giris)"
            ),
            user=user,
            request=request,
            severity="uyari",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Kurulum yönetici hesabı yalnızca kurulumun yapıldığı bilgisayardan "
                "(localhost) açılabilir. Sunucu başında oturum açıp parolayı "
                "değiştirdikten sonra ağ üzerinden giriş yapabilirsiniz."
            ),
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.MAX_LOGIN_ATTEMPTS:
            user.locked_until = dt.datetime.now(dt.UTC) + dt.timedelta(
                minutes=settings.LOGIN_LOCKOUT_MINUTES
            )
            user.failed_login_count = 0
        await record_audit(
            session,
            action=AuditAction.GIRIS_BASARISIZ,
            entity_type="users",
            entity_id=user.id,
            summary="Hatalı parola ile giriş denemesi",
            user=user,
            request=request,
            severity="uyari",
            commit=True,
        )
        raise generic_error

    # Basarili giris
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = dt.datetime.now(dt.UTC)

    access, access_exp, _ = create_token(
        str(user.id), "access", extra_claims={"roles": user.roles or []}
    )
    refresh, refresh_exp, refresh_jti = create_token(str(user.id), "refresh")

    session.add(
        UserSession(
            user_id=user.id,
            refresh_jti=refresh_jti,
            expires_at=refresh_exp,
            user_agent=request.headers.get("user-agent", "")[:255] or None,
            ip_address=(request.client.host[:64] if request.client else None),
        )
    )
    await record_audit(
        session,
        action=AuditAction.GIRIS,
        entity_type="users",
        entity_id=user.id,
        entity_code=user.username,
        summary="Oturum açıldı",
        user=user,
        request=request,
    )
    await session.commit()

    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_at=access_exp,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=AccessToken, summary="Erişim belirtecini yenile")
async def refresh_token(payload: RefreshRequest, session: SessionDep) -> AccessToken:
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    jti = claims.get("jti", "")
    stmt = select(UserSession).where(UserSession.refresh_jti == jti)
    sess = (await session.execute(stmt)).scalar_one_or_none()
    if sess is None or not sess.is_valid:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Oturum sonlandırılmış. Tekrar giriş yapın."
        )

    user = await session.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Kullanıcı erişimi kapalı.")

    access, access_exp, _ = create_token(
        str(user.id), "access", extra_claims={"roles": user.roles or []}
    )
    return AccessToken(access_token=access, expires_at=access_exp)


@router.post("/logout", response_model=Message, summary="Oturumu kapat")
async def logout(
    payload: RefreshRequest, request: Request, session: SessionDep, user: CurrentUser
) -> Message:
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
        jti = claims.get("jti", "")
    except TokenError:
        jti = ""

    if jti:
        stmt = select(UserSession).where(UserSession.refresh_jti == jti)
        sess = (await session.execute(stmt)).scalar_one_or_none()
        if sess is not None and sess.user_id == user.id:
            sess.revoked_at = dt.datetime.now(dt.UTC)

    await record_audit(
        session,
        action=AuditAction.CIKIS,
        entity_type="users",
        entity_id=user.id,
        entity_code=user.username,
        summary="Oturum kapatıldı",
        user=user,
        request=request,
    )
    await session.commit()
    return Message(detail="Oturum kapatıldı.")


@router.get("/me", response_model=UserDetail, summary="Oturumdaki kullanıcı")
async def me(request: Request, user: CurrentUser) -> UserDetail:
    return _user_detail(user, request)


@router.post("/change-password", response_model=Message, summary="Parola değiştir")
async def change_password(
    payload: PasswordChange, request: Request, session: SessionDep, user: CurrentUser
) -> Message:
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mevcut parola hatalı.")
    if payload.old_password == payload.new_password:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Yeni parola eskisiyle aynı olamaz."
        )

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    # Kurulum durumu KALICI olarak kapanir. Eski (kurulum) parolasi artik
    # hicbir kosulda calismaz: karma degeri uzerine yazildi. Yonetici parola
    # sifirlamasi da bu bayragi geri getirmez (bkz. users.reset_password).
    if getattr(user, "bootstrap_pending", False):
        user.bootstrap_pending = False
        _kurulum_parola_dosyasini_sil()

    # Tum yenileme oturumlarini iptal et
    stmt = select(UserSession).where(
        UserSession.user_id == user.id, UserSession.revoked_at.is_(None)
    )
    for s in (await session.execute(stmt)).scalars().all():
        s.revoked_at = dt.datetime.now(dt.UTC)

    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="users",
        entity_id=user.id,
        entity_code=user.username,
        summary="Parola değiştirildi",
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    return Message(detail="Parola güncellendi. Diğer oturumlar kapatıldı.")


@router.patch("/preferences", response_model=UserDetail, summary="Dil / tema tercihi")
async def update_preferences(
    payload: PreferencesUpdate, request: Request, session: SessionDep, user: CurrentUser
) -> UserDetail:
    if payload.locale:
        user.locale = payload.locale
    if payload.theme:
        user.theme = payload.theme
    await session.commit()
    await session.refresh(user)
    return _user_detail(user, request)
