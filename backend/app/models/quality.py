"""Laboratuvar, numune, recete ve kupaj modelleri."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuthorMixin, Base, TimestampMixin


# ------------------------------------------------------------- LABORATUVAR
class SampleStatus(StrEnum):
    ALINDI = "alindi"
    ANALIZDE = "analizde"
    TAMAMLANDI = "tamamlandi"
    IPTAL = "iptal"


class ApprovalStatus(StrEnum):
    BEKLIYOR = "bekliyor"
    ONAYLANDI = "onaylandi"
    REDDEDILDI = "reddedildi"


class LabSample(Base, TimestampMixin, AuthorMixin):
    """Numune kaydi."""

    __tablename__ = "lab_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)

    lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("lots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tank_id: Mapped[int | None] = mapped_column(
        ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    barrel_id: Mapped[int | None] = mapped_column(
        ForeignKey("barrels.id", ondelete="SET NULL"), nullable=True, index=True
    )

    sampled_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    sampled_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    sample_type: Mapped[str] = mapped_column(String(48), default="rutin")
    status: Mapped[str] = mapped_column(String(16), default=SampleStatus.ALINDI, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    results: Mapped[list[LabResult]] = relationship(
        back_populates="sample", cascade="all, delete-orphan"
    )


class LabResult(Base, TimestampMixin, AuthorMixin):
    """Laboratuvar analiz sonucu. Tum parametreler tek satirda tutulur."""

    __tablename__ = "lab_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    sample_id: Mapped[int] = mapped_column(
        ForeignKey("lab_samples.id", ondelete="CASCADE"), index=True
    )
    lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("lots.id", ondelete="SET NULL"), nullable=True, index=True
    )

    analyzed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    analyzed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Temel kimya
    ph: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    total_acidity: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)  # g/L
    volatile_acidity: Mapped[float | None] = mapped_column(Numeric(5, 3), nullable=True)  # g/L
    free_so2: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)  # mg/L
    total_so2: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)  # mg/L
    alcohol: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)  # %vol
    residual_sugar: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)  # g/L
    density: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    malic_acid: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    lactic_acid: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    dry_extract: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    turbidity_ntu: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    # Mikrobiyoloji
    micro_yeast_cfu: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    micro_bacteria_cfu: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    micro_brettanomyces: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    micro_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ek serbest parametreler {"parametre": {"deger": .., "birim": ".."}}
    extra_parameters: Mapped[dict] = mapped_column(JSON, default=dict)

    # Onay is akisi
    approval_status: Mapped[str] = mapped_column(
        String(16), default=ApprovalStatus.BEKLIYOR, index=True
    )
    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    out_of_spec: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    out_of_spec_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    sample: Mapped[LabSample] = relationship(back_populates="results")


class LabSpec(Base, TimestampMixin, AuthorMixin):
    """Parametre bazli kabul araliklari (spesifikasyon)."""

    __tablename__ = "lab_specs"

    id: Mapped[int] = mapped_column(primary_key=True)
    parameter: Mapped[str] = mapped_column(String(48), index=True)
    wine_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    min_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), default="")
    severity: Mapped[str] = mapped_column(String(16), default="uyari")  # uyari|kritik
    label_tr: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# --------------------------------------------------------- RECETE / KUPAJ
class RecipeStatus(StrEnum):
    TASLAK = "taslak"
    ONAY_BEKLIYOR = "onay_bekliyor"
    ONAYLANDI = "onaylandi"
    ARSIV = "arsiv"


class Recipe(Base, TimestampMixin, AuthorMixin):
    """Urun recetesi. Versiyonludur; `parent_recipe_id` onceki surumu isaret eder."""

    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )

    wine_type: Mapped[str] = mapped_column(String(16), default="kirmizi")
    target_volume_l: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    vintage_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(16), default=RecipeStatus.TASLAK, index=True)
    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    target_alcohol: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    target_ph: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    target_ta: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    aging_months: Mapped[int | None] = mapped_column(Integer, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    process_steps: Mapped[list] = mapped_column(JSON, default=list)

    items: Mapped[list[RecipeItem]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )

    @property
    def estimated_cost(self) -> float:
        return round(sum(i.line_cost for i in self.items), 2)


class RecipeItem(Base, TimestampMixin):
    """Recete bileseni: uzum cesidi orani veya katki maddesi dozu."""

    __tablename__ = "recipe_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), index=True
    )
    item_kind: Mapped[str] = mapped_column(String(24), default="uzum")  # uzum|maya|enzim|katki|ambalaj
    variety_id: Mapped[int | None] = mapped_column(
        ForeignKey("grape_varieties.id", ondelete="SET NULL"), nullable=True
    )
    inventory_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(160))
    percentage: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), default="%")
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    recipe: Mapped[Recipe] = relationship(back_populates="items")

    @property
    def line_cost(self) -> float:
        return round(float(self.amount or 0) * float(self.unit_cost or 0), 4)


class BlendStatus(StrEnum):
    SENARYO = "senaryo"
    ONAY_BEKLIYOR = "onay_bekliyor"
    ONAYLANDI = "onaylandi"
    UYGULANDI = "uygulandi"
    IPTAL = "iptal"


class BlendOperation(Base, TimestampMixin, AuthorMixin):
    """Kupaj senaryosu / uygulamasi."""

    __tablename__ = "blend_operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )
    result_lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("lots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_tank_id: Mapped[int | None] = mapped_column(
        ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), default=BlendStatus.SENARYO, index=True)
    planned_volume_l: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    actual_volume_l: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    planned_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    executed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Hesaplanan tahmini karisim degerleri
    predicted_alcohol: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    predicted_ph: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    predicted_ta: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    components: Mapped[list[BlendComponent]] = relationship(
        back_populates="blend", cascade="all, delete-orphan"
    )


class BlendComponent(Base, TimestampMixin):
    __tablename__ = "blend_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    blend_id: Mapped[int] = mapped_column(
        ForeignKey("blend_operations.id", ondelete="CASCADE"), index=True
    )
    source_lot_id: Mapped[int] = mapped_column(
        ForeignKey("lots.id", ondelete="RESTRICT"), index=True
    )
    volume_l: Mapped[float] = mapped_column(Numeric(12, 2))
    percentage: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    unit_cost_l: Mapped[float] = mapped_column(Numeric(12, 4), default=0)

    blend: Mapped[BlendOperation] = relationship(back_populates="components")
