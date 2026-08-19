"""SQLAlchemy 2.x deklaratif temel siniflari ve ortak karisimlar (mixin)."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, MetaData, String, func
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Alembic'in isimsiz kisitlamalari (constraint) tutarli adlandirmasi icin.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def to_dict(self, *, exclude: set[str] | None = None) -> dict[str, Any]:
        """Denetim gunlugu ve serilestirme icin JSON'a uygun sozluk gosterimi.

        ONEMLI: Bu metot HICBIR ZAMAN veritabani IO'su tetiklemez. Sunucu tarafinda
        uretilen sutunlar (ornegin `onupdate=func.now()` olan `updated_at`) bir
        UPDATE flush'indan sonra 'expired' isaretlenir; bunlara erisim asenkron
        baglamda senkron SELECT baslatir ve SQLAlchemy `MissingGreenlet` firlatir.
        Denetim gunlugu is akisini kesmemelidir; bu nedenle yuklenmemis alanlar
        atlanir ve `_yuklenmemis_alanlar` anahtariyla belirtilir.

        Numeric sutunlar `Decimal` doner; JSON'a serilestirilemedigi icin float'a
        cevrilir. Tarih/saat degerleri ISO-8601 metnine donusturulur.
        """
        exclude = exclude or set()
        try:
            unloaded = set(sa_inspect(self).unloaded)
        except Exception:  # pragma: no cover - ORM'e bagli olmayan ornek
            unloaded = set()

        out: dict[str, Any] = {}
        skipped: list[str] = []
        for col in self.__table__.columns:
            if col.name in exclude:
                continue
            attr = self.__mapper__.get_property_by_column(col).key
            if attr in unloaded:
                skipped.append(col.name)
                continue
            value = getattr(self, col.name, None)
            if isinstance(value, dt.datetime | dt.date | dt.time):
                value = value.isoformat()
            elif isinstance(value, Decimal):
                value = float(value)
            elif isinstance(value, uuid.UUID):
                value = str(value)
            elif isinstance(value, bytes):
                value = f"<{len(value)} bayt ikili veri>"
            out[col.name] = value

        if skipped:
            out["_yuklenmemis_alanlar"] = skipped
        return out

    def __repr__(self) -> str:  # pragma: no cover - hata ayiklama kolayligi
        pk = getattr(self, "id", None)
        return f"<{type(self).__name__} id={pk}>"


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class TimestampMixin:
    """olusturma / guncelleme zaman damgalari."""

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuthorMixin:
    """Kaydi olusturan / son degistiren kullanici."""

    created_by_id: Mapped[int | None] = mapped_column(nullable=True)
    updated_by_id: Mapped[int | None] = mapped_column(nullable=True)


class CodeMixin:
    """Insan tarafindan okunabilir benzersiz kod (ornegin TNK-01, PRT-2025-0007)."""

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
