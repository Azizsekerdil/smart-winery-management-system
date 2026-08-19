"""Kullanici, rol atamasi ve oturum modelleri."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.permissions import permissions_for
from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))

    # Rol kodlari listesi (bkz. app.core.permissions.Role)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)

    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    locale: Mapped[str] = mapped_column(String(8), default="tr")
    theme: Mapped[str] = mapped_column(String(16), default="dark")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)

    # Ilk kurulumda uretilen TEK KULLANIMLIK yonetici hesabi mi?
    # True oldugu surece bu hesap YALNIZCA yerel makineden (loopback) giris
    # yapabilir. Parola degistirildigi anda kalici olarak False olur ve bir
    # daha asla True yapilmaz - yonetici parola sifirlamasi da geri getirmez.
    bootstrap_pending: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="0"
    )

    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # --------------------------------------------------------------- yardimci
    @property
    def permissions(self) -> set[str]:
        return permissions_for(self.roles or [])

    def has(self, perm: str) -> bool:
        return perm in self.permissions

    @property
    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        locked_until = self.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=dt.UTC)
        return locked_until > dt.datetime.now(dt.UTC)


class UserSession(Base, TimestampMixin):
    """Yenileme belirteci kaydi - iptal (revoke) edilebilir oturumlar."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Belirtecin kendisi degil, yalnizca JWT kimligi (jti) saklanir.
    refresh_jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")

    @property
    def is_valid(self) -> bool:
        if self.revoked_at is not None:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=dt.UTC)
        return expires > dt.datetime.now(dt.UTC)
