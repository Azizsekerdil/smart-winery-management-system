"""Parola karmasi (Argon2id) ve JWT oturum belirteci islemleri."""

from __future__ import annotations

import datetime as dt
import re
import secrets
import uuid
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

# Argon2id - OWASP Password Storage Cheat Sheet ile uyumlu parametreler
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

TokenType = Literal["access", "refresh"]

# HTTP Authorization semasinin adi; gizli bir deger DEGILDIR.
BEARER_SCHEME = "bearer"


# --------------------------------------------------------------------- parola
def hash_password(plain: str) -> str:
    """Duz parolayi Argon2id ile karmalar."""
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Parolayi dogrular. Hatali karma degeri istisna firlatmaz, False doner."""
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _hasher.check_needs_rehash(hashed)
    except InvalidHashError:
        return True


PASSWORD_RULES_TR = (
    "Parola en az {n} karakter olmali; en az bir buyuk harf, bir kucuk harf "
    "ve bir rakam icermelidir."
)


def validate_password_strength(plain: str) -> list[str]:
    """Parola politikasini denetler; sorun listesi (Turkce) doner."""
    problems: list[str] = []
    if len(plain) < settings.PASSWORD_MIN_LENGTH:
        problems.append(
            f"Parola en az {settings.PASSWORD_MIN_LENGTH} karakter olmalidir."
        )
    if not re.search(r"[a-zçğıöşü]", plain):
        problems.append("Parola en az bir kucuk harf icermelidir.")
    if not re.search(r"[A-ZÇĞİÖŞÜ]", plain):
        problems.append("Parola en az bir buyuk harf icermelidir.")
    if not re.search(r"\d", plain):
        problems.append("Parola en az bir rakam icermelidir.")
    return problems


# ---------------------------------------------------------------------- JWT
def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def create_token(
    subject: str,
    token_type: TokenType,
    *,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: dt.timedelta | None = None,
) -> tuple[str, dt.datetime, str]:
    """JWT uretir. (token, son_kullanma, jti) doner."""
    if expires_delta is None:
        expires_delta = (
            dt.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            if token_type == "access"
            else dt.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
    now = _now()
    expire = now + expires_delta
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": jti,
        "iss": "saraphane-yonetim",
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expire, jti


class TokenError(Exception):
    """Gecersiz / suresi dolmus belirtec."""


def decode_token(token: str, *, expected_type: TokenType | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer="saraphane-yonetim",
            options={"require": ["exp", "sub", "jti", "typ"]},
        )
    except jwt.ExpiredSignatureError as exc:  # pragma: no cover - trivial
        raise TokenError("Oturum suresi dolmus.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Gecersiz oturum belirteci.") from exc

    if expected_type and payload.get("typ") != expected_type:
        raise TokenError("Beklenen belirtec turu ile uyusmuyor.")
    return payload


def generate_api_token(prefix: str = "swm") -> str:
    """Makine erisimi icin okunabilir onekli rastgele belirtec."""
    return f"{prefix}_{secrets.token_urlsafe(32)}"
