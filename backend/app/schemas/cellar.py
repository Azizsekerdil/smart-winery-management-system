"""Fici/mahzen ve siseleme semalari."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator

from app.models.cellar import (
    BarrelMovementType,
    BarrelStatus,
    BottlingStatus,
    OakType,
    ToastLevel,
)
from app.schemas.common import ORMModel


# ------------------------------------------------------------------ FICI
class BarrelBase(BaseModel):
    oak_type: OakType = OakType.FRANSIZ
    cooper: str | None = Field(default=None, max_length=120)
    toast_level: ToastLevel = ToastLevel.ORTA
    capacity_l: float = Field(default=225, gt=0, le=10000)
    production_year: int | None = Field(default=None, ge=1900, le=2200)
    cellar_zone: str | None = Field(default=None, max_length=64)
    rack_code: str | None = Field(default=None, max_length=32)
    row_no: int | None = None
    level_no: int | None = None
    notes: str | None = None
    is_active: bool = True


class BarrelCreate(BarrelBase):
    code: str | None = Field(default=None, max_length=32)


class BarrelUpdate(BaseModel):
    oak_type: OakType | None = None
    cooper: str | None = None
    toast_level: ToastLevel | None = None
    capacity_l: float | None = Field(default=None, gt=0)
    production_year: int | None = None
    cellar_zone: str | None = None
    rack_code: str | None = None
    row_no: int | None = None
    level_no: int | None = None
    status: BarrelStatus | None = None
    planned_empty_at: dt.date | None = None
    notes: str | None = None
    is_active: bool | None = None


class BarrelOut(ORMModel, BarrelBase):
    id: int
    code: str
    qr_payload: str | None = None
    current_volume_l: float
    fill_count: int
    status: str
    current_lot_id: int | None = None
    filled_at: dt.datetime | None = None
    planned_empty_at: dt.date | None = None
    last_topped_at: dt.datetime | None = None
    last_cleaned_at: dt.datetime | None = None
    total_loss_l: float
    created_at: dt.datetime
    age_years: int | None = None
    aging_days: int | None = None
    current_lot_code: str | None = None


class BarrelMovementCreate(BaseModel):
    movement_type: BarrelMovementType
    lot_id: int | None = None
    volume_l: float = Field(default=0, ge=0)
    loss_l: float = Field(default=0, ge=0)
    occurred_at: dt.datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _needs_lot(self):
        if self.movement_type == BarrelMovementType.DOLUM:
            if self.lot_id is None:
                raise ValueError("Dolum işlemi için parti seçilmelidir.")
            if self.volume_l <= 0:
                raise ValueError("Dolum hacmi sıfırdan büyük olmalıdır.")
        return self


class BarrelMovementOut(ORMModel):
    id: int
    barrel_id: int
    lot_id: int | None = None
    movement_type: str
    volume_l: float
    loss_l: float
    occurred_at: dt.datetime
    notes: str | None = None
    lot_code: str | None = None


class TastingNoteCreate(BaseModel):
    barrel_id: int | None = None
    lot_id: int | None = None
    tasted_at: dt.datetime | None = None
    appearance: str | None = None
    aroma: str | None = None
    palate: str | None = None
    finish: str | None = None
    score: float | None = Field(default=None, ge=0, le=100)
    conclusion: str | None = None

    @model_validator(mode="after")
    def _target(self):
        if self.barrel_id is None and self.lot_id is None:
            raise ValueError("Tadım notu için fıçı veya parti belirtilmelidir.")
        return self


class TastingNoteOut(ORMModel):
    id: int
    barrel_id: int | None = None
    lot_id: int | None = None
    tasted_at: dt.datetime
    taster_id: int | None = None
    appearance: str | None = None
    aroma: str | None = None
    palate: str | None = None
    finish: str | None = None
    score: float | None = None
    conclusion: str | None = None
    taster_name: str | None = None


# -------------------------------------------------------------- SISELEME
class BottlingCreate(BaseModel):
    code: str | None = Field(default=None, max_length=48)
    lot_id: int
    source_tank_id: int | None = None
    product_name: str = Field(min_length=2, max_length=200)
    vintage_year: int | None = Field(default=None, ge=1900, le=2200)
    lot_number: str | None = Field(default=None, max_length=48)
    bottle_volume_ml: int = Field(default=750, gt=0, le=20000)
    planned_bottles: int = Field(default=0, ge=0)
    bottles_per_case: int = Field(default=6, gt=0, le=100)
    line_code: str | None = Field(default=None, max_length=32)
    planned_at: dt.datetime | None = None
    bottle_item_id: int | None = None
    closure_item_id: int | None = None
    capsule_item_id: int | None = None
    label_item_id: int | None = None
    case_item_id: int | None = None
    barcode: str | None = Field(default=None, max_length=64)
    notes: str | None = None

    @model_validator(mode="after")
    def _fill_defaults(self):
        """NOT NULL alanlarin gecici degerleri. Adanmis `/bottling/orders` uc
        noktasi bunlari parti ve emir koduna gore yeniden hesaplar."""
        if self.vintage_year is None:
            self.vintage_year = dt.date.today().year
        if not self.lot_number:
            self.lot_number = f"GECICI-{dt.datetime.now(dt.UTC):%y%m%d%H%M%S}"
        return self


class BottlingUpdate(BaseModel):
    product_name: str | None = None
    source_tank_id: int | None = None
    status: BottlingStatus | None = None
    planned_bottles: int | None = Field(default=None, ge=0)
    bottles_per_case: int | None = Field(default=None, gt=0)
    line_code: str | None = None
    planned_at: dt.datetime | None = None
    bottle_item_id: int | None = None
    closure_item_id: int | None = None
    capsule_item_id: int | None = None
    label_item_id: int | None = None
    case_item_id: int | None = None
    barcode: str | None = None
    qc_passed: bool | None = None
    qc_notes: str | None = None
    notes: str | None = None


class BottlingStart(BaseModel):
    started_at: dt.datetime | None = None
    line_code: str | None = None


class BottlingFinish(BaseModel):
    produced_bottles: int = Field(ge=0)
    rejected_bottles: int = Field(default=0, ge=0)
    loss_l: float = Field(default=0, ge=0)
    finished_at: dt.datetime | None = None
    qc_passed: bool = True
    qc_notes: str | None = None
    target_warehouse_id: int | None = None


class BottlingOut(ORMModel):
    id: int
    code: str
    lot_id: int
    source_tank_id: int | None = None
    product_name: str
    vintage_year: int
    lot_number: str
    status: str
    bottle_volume_ml: int
    planned_bottles: int
    produced_bottles: int
    rejected_bottles: int
    bottles_per_case: int
    planned_volume_l: float
    used_volume_l: float
    loss_l: float
    line_code: str | None = None
    started_at: dt.datetime | None = None
    finished_at: dt.datetime | None = None
    planned_at: dt.datetime | None = None
    barcode: str | None = None
    qr_payload: str | None = None
    qc_passed: bool | None = None
    qc_notes: str | None = None
    notes: str | None = None
    created_at: dt.datetime
    lot_code: str | None = None
    yield_percent: float = 0.0
    scrap_percent: float = 0.0


class LabelPreview(BaseModel):
    """Etiket onizleme verisi (arayuzde SVG olarak cizilir)."""

    product_name: str
    vintage_year: int
    lot_number: str
    bottle_volume_ml: int
    alcohol: float | None = None
    variety: str | None = None
    producer: str = "Şaraphane"
    barcode: str | None = None
    qr_payload: str
    ingredients_tr: str = "Üzüm, sülfit içerir"
    warning_tr: str = "18 yaşından küçüklere satılamaz. Alkollü içki zararlıdır."
