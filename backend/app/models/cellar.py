"""Fici / mahzen ve siseleme-paketleme modelleri."""

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


# ----------------------------------------------------------------- FICILAR
class OakType(StrEnum):
    FRANSIZ = "fransiz"
    AMERIKAN = "amerikan"
    MACAR = "macar"
    KAFKAS = "kafkas"
    SLAVONYA = "slavonya"


class ToastLevel(StrEnum):
    HAFIF = "hafif"
    ORTA = "orta"
    ORTA_PLUS = "orta_plus"
    AGIR = "agir"


class BarrelStatus(StrEnum):
    BOS = "bos"
    DOLU = "dolu"
    TEMIZLIKTE = "temizlikte"
    ONARIMDA = "onarimda"
    EMEKLI = "emekli"


class Barrel(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "barrels"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    qr_payload: Mapped[str | None] = mapped_column(String(255), nullable=True)

    oak_type: Mapped[str] = mapped_column(String(24), default=OakType.FRANSIZ)
    cooper: Mapped[str | None] = mapped_column(String(120), nullable=True)
    toast_level: Mapped[str] = mapped_column(String(16), default=ToastLevel.ORTA)
    capacity_l: Mapped[float] = mapped_column(Numeric(10, 2), default=225)
    current_volume_l: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    production_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fill_count: Mapped[int] = mapped_column(Integer, default=0)

    cellar_zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rack_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    row_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level_no: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(16), default=BarrelStatus.BOS, index=True)
    current_lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("lots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    filled_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    planned_empty_at: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    last_topped_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_cleaned_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    total_loss_l: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    movements: Mapped[list[BarrelMovement]] = relationship(
        back_populates="barrel", cascade="all, delete-orphan",
        order_by="BarrelMovement.occurred_at",
    )
    tasting_notes: Mapped[list[TastingNote]] = relationship(
        back_populates="barrel", cascade="all, delete-orphan"
    )

    @property
    def age_years(self) -> int | None:
        if self.production_year is None:
            return None
        return max(0, dt.date.today().year - self.production_year)

    @property
    def aging_days(self) -> int | None:
        if self.filled_at is None:
            return None
        filled = self.filled_at
        if filled.tzinfo is None:
            filled = filled.replace(tzinfo=dt.UTC)
        return (dt.datetime.now(dt.UTC) - filled).days


class BarrelMovementType(StrEnum):
    DOLUM = "dolum"
    BOSALTIM = "bosaltim"
    TOPPING = "topping"  # üst tamamlama
    AKTARMA = "aktarma"
    TEMIZLIK = "temizlik"
    ONARIM = "onarim"
    FIRE = "fire"


class BarrelMovement(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "barrel_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    barrel_id: Mapped[int] = mapped_column(
        ForeignKey("barrels.id", ondelete="CASCADE"), index=True
    )
    lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("lots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(16), default=BarrelMovementType.DOLUM)
    volume_l: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    loss_l: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    performed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    barrel: Mapped[Barrel] = relationship(back_populates="movements")


class TastingNote(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "tasting_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    barrel_id: Mapped[int | None] = mapped_column(
        ForeignKey("barrels.id", ondelete="CASCADE"), nullable=True, index=True
    )
    lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("lots.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tasted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    taster_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    aroma: Mapped[str | None] = mapped_column(Text, nullable=True)
    palate: Mapped[str | None] = mapped_column(Text, nullable=True)
    finish: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)  # 0-100
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)

    barrel: Mapped[Barrel | None] = relationship(back_populates="tasting_notes")


# --------------------------------------------------------------- SISELEME
class BottlingStatus(StrEnum):
    PLANLANDI = "planlandi"
    HAZIRLIK = "hazirlik"
    DEVAM_EDIYOR = "devam_ediyor"
    TAMAMLANDI = "tamamlandi"
    IPTAL = "iptal"


class BottlingOrder(Base, TimestampMixin, AuthorMixin):
    """Siseleme emri."""

    __tablename__ = "bottling_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="RESTRICT"), index=True)
    source_tank_id: Mapped[int | None] = mapped_column(
        ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True
    )

    product_name: Mapped[str] = mapped_column(String(200))
    vintage_year: Mapped[int] = mapped_column(Integer, index=True)
    lot_number: Mapped[str] = mapped_column(String(48), index=True)  # şişe üstü LOT
    status: Mapped[str] = mapped_column(
        String(16), default=BottlingStatus.PLANLANDI, index=True
    )

    bottle_volume_ml: Mapped[int] = mapped_column(Integer, default=750)
    planned_bottles: Mapped[int] = mapped_column(Integer, default=0)
    produced_bottles: Mapped[int] = mapped_column(Integer, default=0)
    rejected_bottles: Mapped[int] = mapped_column(Integer, default=0)
    bottles_per_case: Mapped[int] = mapped_column(Integer, default=6)

    planned_volume_l: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    used_volume_l: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    loss_l: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    line_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    planned_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Ambalaj bilesenleri (stok kalemi referanslari)
    bottle_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True
    )
    closure_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True
    )
    capsule_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True
    )
    label_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True
    )
    case_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True
    )
    finished_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True
    )

    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    qr_payload: Mapped[str | None] = mapped_column(String(255), nullable=True)

    qc_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    qc_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def yield_percent(self) -> float:
        if not self.planned_bottles:
            return 0.0
        return round(self.produced_bottles / self.planned_bottles * 100, 1)

    @property
    def scrap_percent(self) -> float:
        total = self.produced_bottles + self.rejected_bottles
        if not total:
            return 0.0
        return round(self.rejected_bottles / total * 100, 2)
