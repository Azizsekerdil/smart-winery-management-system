"""Kimlik dogrulama ve kullanici semalari."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.permissions import Role
from app.core.security import validate_password_strength
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64, description="Kullanıcı adı veya e-posta")
    password: str = Field(min_length=1, max_length=256)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: dt.datetime
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: dt.datetime


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    roles: list[Role] = Field(default_factory=list)
    department: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    locale: str = "tr"
    theme: str = "dark"
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=10, max_length=256)

    @field_validator("password")
    @classmethod
    def _strength(cls, v: str) -> str:
        problems = validate_password_strength(v)
        if problems:
            raise ValueError(" ".join(problems))
        return v

    @field_validator("roles")
    @classmethod
    def _at_least_one_role(cls, v: list[Role]) -> list[Role]:
        if not v:
            raise ValueError("En az bir rol seçilmelidir.")
        return v


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    roles: list[Role] | None = None
    department: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    locale: str | None = None
    theme: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class UserOut(ORMModel):
    id: int
    username: str
    email: str
    full_name: str
    roles: list[str]
    department: str | None = None
    phone: str | None = None
    locale: str = "tr"
    theme: str = "dark"
    is_active: bool
    must_change_password: bool = False
    last_login_at: dt.datetime | None = None
    created_at: dt.datetime


class UserDetail(UserOut):
    permissions: list[str] = Field(default_factory=list)
    role_labels: list[str] = Field(default_factory=list)


class PasswordChange(BaseModel):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=10, max_length=256)

    @field_validator("new_password")
    @classmethod
    def _strength(cls, v: str) -> str:
        problems = validate_password_strength(v)
        if problems:
            raise ValueError(" ".join(problems))
        return v


class PasswordReset(BaseModel):
    """Yonetici tarafindan parola sifirlama."""

    new_password: str = Field(min_length=10, max_length=256)
    must_change: bool = True

    @field_validator("new_password")
    @classmethod
    def _strength(cls, v: str) -> str:
        problems = validate_password_strength(v)
        if problems:
            raise ValueError(" ".join(problems))
        return v


class PreferencesUpdate(BaseModel):
    locale: str | None = Field(default=None, pattern=r"^(tr|en)$")
    theme: str | None = Field(default=None, pattern=r"^(dark|light|system)$")


class RoleInfo(BaseModel):
    kod: str
    ad: str
    yetkiler: list[str]


TokenPair.model_rebuild()
