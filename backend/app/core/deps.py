"""FastAPI bagimliliklari: oturum, gecerli kullanici ve yetki kontrolu."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.permissions import Perm, permissions_for
from app.core.security import TokenError, decode_token
from app.db.session import get_session
from app.models.ops import AuditAction
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False, description="JWT erişim belirteci")

# Parola degistirmesi ZORUNLU olan bir kullanicinin erisebilecegi TEK yollar.
# Bunlarin disinda hicbir uc nokta - pano, musteri/personel verisi, mali kayit,
# AI/API ayarlari, disa aktarma, yedekleme, yonetim islemleri - acilmaz.
PAROLA_DEGISIMI_SERBEST_YOLLARI: tuple[str, ...] = (
    "/auth/me",
    "/auth/change-password",
    "/auth/logout",
)


def parola_degisimi_bekliyor_mu(path: str) -> bool:
    """Yol, zorunlu parola degisimi sirasinda serbest birakilanlardan mi?"""
    return any(path.endswith(uc) for uc in PAROLA_DEGISIMI_SERBEST_YOLLARI)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    request: Request,
    session: SessionDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum açmanız gerekiyor.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz belirteç."
        ) from exc

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı veya pasif durumda.",
        )
    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Hesap geçici olarak kilitli.",
        )

    # ------------------------------------------- ZORUNLU PAROLA DEGISIMI KAPISI
    # Gecerli bir belirtec tek basina yeterli DEGILDIR. Ilk kurulum parolasi
    # (veya yonetici sifirlamasi) hala gecerliyken korumali hicbir uc nokta
    # acilmaz. Bu kontrol arayuzde degil, sunucuda yapilir; API'yi dogrudan
    # cagiran bir istemci de atlayamaz.
    if user.must_change_password and not parola_degisimi_bekliyor_mu(
        request.url.path
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Parolanızı değiştirmeden bu işlemi yapamazsınız. "
                "Önce /auth/change-password ile yeni bir parola belirleyin."
            ),
            headers={"X-Password-Change-Required": "true"},
        )

    request.state.user = user
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_perms(
    *perms: Perm | str, mode: str = "all"
) -> Callable[..., Coroutine[Any, Any, User]]:
    """Verilen yetkilerin tamamini (veya `mode='any'` ile en az birini) sart kosar.

    Yetkisiz erisim denemesi denetim gunlugune yazilir (madde 15).
    """
    required = {str(p) for p in perms}

    async def _dep(
        request: Request,
        session: SessionDep,
        user: CurrentUser,
    ) -> User:
        granted = permissions_for(user.roles or [])
        ok = required <= granted if mode == "all" else bool(required & granted)
        if not ok:
            missing = sorted(required - granted)
            await record_audit(
                session,
                action=AuditAction.IZINSIZ_ERISIM,
                entity_type="yetki",
                summary=f"Yetkisiz erişim denemesi: {', '.join(missing)}",
                after={"gerekli": sorted(required), "eksik": missing},
                user=user,
                request=request,
                severity="uyari",
                commit=True,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem için yetkiniz yok. Gerekli yetki: {', '.join(missing)}",
            )
        return user

    return _dep


def require_any(*perms: Perm | str) -> Callable[..., Coroutine[Any, Any, User]]:
    return require_perms(*perms, mode="any")


async def get_optional_user(
    request: Request,
    session: SessionDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User | None:
    if credentials is None:
        return None
    try:
        return await get_current_user(request, session, credentials)
    except HTTPException:
        return None
