"""Bag, parsel, uzum cesidi, tedarikci ve uzum kabul modelleri."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuthorMixin, Base, TimestampMixin


class GrapeColor(StrEnum):
    KIRMIZI = "kirmizi"
    BEYAZ = "beyaz"
    ROSE = "rose"


class QualityGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    RED = "red"  # kabul edilmedi


class Vineyard(Base, TimestampMixin, AuthorMixin):
    """Bag."""

    __tablename__ = "vineyards"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    village: Mapped[str | None] = mapped_column(String(120), nullable=True)
    altitude_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    soil_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    total_area_da: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    is_owned: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    parcels: Mapped[list[Parcel]] = relationship(
        back_populates="vineyard", cascade="all, delete-orphan"
    )


class GrapeVariety(Base, TimestampMixin):
    """Uzum cesidi."""

    __tablename__ = "grape_varieties"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    color: Mapped[str] = mapped_column(String(16), default=GrapeColor.KIRMIZI)
    origin: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_brix_min: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    target_brix_max: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    target_ph_min: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    target_ph_max: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Parcel(Base, TimestampMixin, AuthorMixin):
    """Bag icindeki parsel."""

    __tablename__ = "parcels"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    vineyard_id: Mapped[int] = mapped_column(
        ForeignKey("vineyards.id", ondelete="CASCADE"), index=True
    )
    variety_id: Mapped[int | None] = mapped_column(
        ForeignKey("grape_varieties.id", ondelete="SET NULL"), nullable=True, index=True
    )
    area_da: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    planting_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vine_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rootstock: Mapped[str | None] = mapped_column(String(80), nullable=True)
    training_system: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    vineyard: Mapped[Vineyard] = relationship(back_populates="parcels")
    variety: Mapped[GrapeVariety | None] = relationship()


class Supplier(Base, TimestampMixin, AuthorMixin):
    """Tedarikci (uzum, ambalaj, sarf malzeme)."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    supplier_type: Mapped[str] = mapped_column(String(32), default="uzum")
    tax_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class HarvestIntake(Base, TimestampMixin, AuthorMixin):
    """Uzum kabul (kantar/teslimat) kaydi."""

    __tablename__ = "harvest_intakes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)

    vineyard_id: Mapped[int | None] = mapped_column(
        ForeignKey("vineyards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parcel_id: Mapped[int | None] = mapped_column(
        ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    variety_id: Mapped[int] = mapped_column(
        ForeignKey("grape_varieties.id", ondelete="RESTRICT"), index=True
    )
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    harvest_date: Mapped[dt.date] = mapped_column(Date, index=True)
    received_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    vintage_year: Mapped[int] = mapped_column(Integer, index=True)

    # Kantar
    gross_weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    tare_weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    net_weight_kg: Mapped[float] = mapped_column(Numeric(12, 2))
    vehicle_plate: Mapped[str | None] = mapped_column(String(24), nullable=True)
    weighbridge_ticket: Mapped[str | None] = mapped_column(String(48), nullable=True)

    # Kabul analizleri
    brix: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    ph: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    total_acidity: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    rot_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    quality_grade: Mapped[str] = mapped_column(String(8), default=QualityGrade.A)

    unit_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="TRY")

    qr_payload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    vineyard: Mapped[Vineyard | None] = relationship()
    parcel: Mapped[Parcel | None] = relationship()
    variety: Mapped[GrapeVariety] = relationship()
    supplier: Mapped[Supplier | None] = relationship()
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="intake", cascade="all, delete-orphan"
    )

    @property
    def total_cost(self) -> float:
        if self.unit_price is None or self.net_weight_kg is None:
            return 0.0
        return float(self.unit_price) * float(self.net_weight_kg)


class Attachment(Base, TimestampMixin, AuthorMixin):
    """Fotograf / belge eki. Dosyalar data/uploads altinda tutulur."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    intake_id: Mapped[int | None] = mapped_column(
        ForeignKey("harvest_intakes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(48), default="harvest_intake")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    intake: Mapped[HarvestIntake | None] = relationship(back_populates="attachments")
