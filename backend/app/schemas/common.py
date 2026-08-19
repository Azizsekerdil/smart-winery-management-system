"""Ortak sema tipleri."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Page[T](BaseModel):
    """Sayfalanmis liste yaniti (PEP 695 tip parametresi)."""

    items: list[T]
    total: int
    page: int = 1
    page_size: int = 50

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // max(1, self.page_size)))


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)
    q: str | None = Field(default=None, max_length=200, description="Serbest metin arama")
    sort: str | None = Field(default=None, max_length=64)
    desc: bool = False

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Message(BaseModel):
    detail: str
    ok: bool = True


class IdResponse(BaseModel):
    id: int
    code: str | None = None
    detail: str = "İşlem tamamlandı."


class DateRange(BaseModel):
    start: dt.date | None = None
    end: dt.date | None = None


class SelectOption(BaseModel):
    """Arayuz acilir listeleri icin."""

    value: str | int
    label: str
    group: str | None = None
    disabled: bool = False
