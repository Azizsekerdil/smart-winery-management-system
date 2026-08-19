"""Parti, tank, transfer ve fermantasyon semalari."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator

from app.models.production import (
    CleaningStatus,
    FermentationStatus,
    FermentationType,
    LotStage,
    LotStatus,
    ReadingSource,
    TankStatus,
    TankType,
    TransferType,
    WineType,
)
from app.schemas.common import ORMModel


# ------------------------------------------------------------------ PARTI
class LotSourceIn(BaseModel):
    intake_id: int
    weight_kg: float = Field(gt=0)
    juice_yield_l: float | None = Field(default=None, ge=0)


class LotCreate(BaseModel):
    code: str | None = Field(default=None, max_length=48)
    name: str = Field(min_length=2, max_length=200)
    vintage_year: int | None = Field(default=None, ge=1900, le=2200)
    wine_type: WineType = WineType.KIRMIZI
    variety_id: int | None = None
    stage: LotStage = LotStage.UZUM_KABUL
    volume_l: float = Field(default=0, ge=0)
    current_tank_id: int | None = None
    notes: str | None = None
    sources: list[LotSourceIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _fill_defaults(self):
        if self.vintage_year is None:
            self.vintage_year = dt.date.today().year
        return self


class LotUpdate(BaseModel):
    name: str | None = None
    wine_type: WineType | None = None
    variety_id: int | None = None
    stage: LotStage | None = None
    status: LotStatus | None = None
    volume_l: float | None = Field(default=None, ge=0)
    current_tank_id: int | None = None
    notes: str | None = None


class LotOut(ORMModel):
    id: int
    code: str
    name: str
    vintage_year: int
    wine_type: str
    variety_id: int | None = None
    is_blend: bool
    stage: str
    status: str
    volume_l: float
    initial_volume_l: float
    current_tank_id: int | None = None
    current_brix: float | None = None
    current_ph: float | None = None
    current_alcohol: float | None = None
    current_ta: float | None = None
    current_va: float | None = None
    current_free_so2: float | None = None
    qr_payload: str | None = None
    notes: str | None = None
    created_at: dt.datetime
    variety_name: str | None = None
    tank_code: str | None = None


class LotEventOut(ORMModel):
    id: int
    occurred_at: dt.datetime
    event_type: str
    title: str
    description: str | None = None
    ref_table: str | None = None
    ref_id: int | None = None


class TraceNode(BaseModel):
    """Izlenebilirlik cizgesi dugumu."""

    kind: str  # uzum_kabul | parti | tank | fici | siseleme
    id: int
    code: str
    label: str
    detail: dict = Field(default_factory=dict)


class TraceEdge(BaseModel):
    from_key: str
    to_key: str
    relation: str
    volume_l: float | None = None
    occurred_at: dt.datetime | None = None


class TraceGraph(BaseModel):
    root: str
    direction: str  # geri | ileri | tam
    nodes: list[TraceNode]
    edges: list[TraceEdge]
    warnings: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------ TANK
class TankBase(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    tank_type: TankType = TankType.PASLANMAZ
    capacity_l: float = Field(gt=0)
    location: str | None = Field(default=None, max_length=120)
    zone: str | None = Field(default=None, max_length=64)
    position_x: int | None = None
    position_y: int | None = None
    has_cooling: bool = True
    has_sensor: bool = False
    target_temperature_c: float | None = Field(default=None, ge=-10, le=60)
    commissioned_year: int | None = Field(default=None, ge=1900, le=2200)
    notes: str | None = None
    is_active: bool = True


class TankCreate(TankBase):
    code: str | None = Field(default=None, max_length=32)


class TankUpdate(BaseModel):
    name: str | None = None
    tank_type: TankType | None = None
    capacity_l: float | None = Field(default=None, gt=0)
    location: str | None = None
    zone: str | None = None
    position_x: int | None = None
    position_y: int | None = None
    has_cooling: bool | None = None
    has_sensor: bool | None = None
    temperature_c: float | None = Field(default=None, ge=-20, le=80)
    target_temperature_c: float | None = Field(default=None, ge=-10, le=60)
    status: TankStatus | None = None
    cleaning_status: CleaningStatus | None = None
    notes: str | None = None
    is_active: bool | None = None


class TankOut(ORMModel, TankBase):
    id: int
    code: str
    current_volume_l: float
    temperature_c: float | None = None
    status: str
    cleaning_status: str
    last_cleaned_at: dt.datetime | None = None
    fill_percent: float = 0.0
    free_capacity_l: float = 0.0
    current_lot_code: str | None = None
    current_lot_id: int | None = None


class TankTransferCreate(BaseModel):
    transfer_type: TransferType = TransferType.TANK_ARASI
    lot_id: int
    from_tank_id: int | None = None
    to_tank_id: int | None = None
    from_barrel_id: int | None = None
    to_barrel_id: int | None = None
    volume_l: float = Field(gt=0)
    loss_l: float = Field(default=0, ge=0)
    occurred_at: dt.datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _endpoints(self):
        src = self.from_tank_id or self.from_barrel_id
        dst = self.to_tank_id or self.to_barrel_id
        if src is None and dst is None:
            raise ValueError("En az bir kaynak veya hedef kap belirtilmelidir.")
        if (
            self.from_tank_id is not None
            and self.to_tank_id is not None
            and self.from_tank_id == self.to_tank_id
        ):
            raise ValueError("Kaynak ve hedef tank aynı olamaz.")
        return self


class TankTransferOut(ORMModel):
    id: int
    code: str
    transfer_type: str
    lot_id: int
    from_tank_id: int | None = None
    to_tank_id: int | None = None
    from_barrel_id: int | None = None
    to_barrel_id: int | None = None
    volume_l: float
    loss_l: float
    occurred_at: dt.datetime
    notes: str | None = None
    lot_code: str | None = None
    from_code: str | None = None
    to_code: str | None = None


# ---------------------------------------------------------- FERMANTASYON
class FermentationCreate(BaseModel):
    code: str | None = Field(default=None, max_length=48)
    lot_id: int
    tank_id: int | None = None
    ferm_type: FermentationType = FermentationType.ALKOL
    start_date: dt.datetime | None = None
    target_end_date: dt.datetime | None = None
    yeast_strain: str | None = Field(default=None, max_length=120)
    yeast_dose_g_hl: float | None = Field(default=None, ge=0)
    initial_brix: float | None = Field(default=None, ge=0, le=40)
    target_brix: float = Field(default=0, ge=-5, le=40)
    initial_ph: float | None = Field(default=None, ge=0, le=14)
    temp_min_c: float = Field(default=18, ge=-5, le=60)
    temp_max_c: float = Field(default=28, ge=-5, le=60)
    volume_l: float = Field(default=0, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def _temps(self):
        if self.temp_min_c > self.temp_max_c:
            raise ValueError("Minimum sıcaklık maksimumdan büyük olamaz.")
        if self.start_date is None:
            self.start_date = dt.datetime.now(dt.UTC)
        return self


class FermentationUpdate(BaseModel):
    tank_id: int | None = None
    status: FermentationStatus | None = None
    target_end_date: dt.datetime | None = None
    actual_end_date: dt.datetime | None = None
    yeast_strain: str | None = None
    yeast_dose_g_hl: float | None = Field(default=None, ge=0)
    target_brix: float | None = None
    temp_min_c: float | None = Field(default=None, ge=-5, le=60)
    temp_max_c: float | None = Field(default=None, ge=-5, le=60)
    volume_l: float | None = Field(default=None, ge=0)
    notes: str | None = None


class FermentationOut(ORMModel):
    id: int
    code: str
    lot_id: int
    tank_id: int | None = None
    ferm_type: str
    status: str
    start_date: dt.datetime
    target_end_date: dt.datetime | None = None
    predicted_end_date: dt.datetime | None = None
    actual_end_date: dt.datetime | None = None
    yeast_strain: str | None = None
    yeast_dose_g_hl: float | None = None
    initial_brix: float | None = None
    target_brix: float
    initial_ph: float | None = None
    temp_min_c: float
    temp_max_c: float
    volume_l: float
    notes: str | None = None
    created_at: dt.datetime
    lot_code: str | None = None
    tank_code: str | None = None
    last_brix: float | None = None
    last_temperature_c: float | None = None
    last_reading_at: dt.datetime | None = None
    reading_count: int = 0
    progress_percent: float = 0.0
    active_alerts: int = 0


class FermentationReadingCreate(BaseModel):
    measured_at: dt.datetime | None = None
    source: ReadingSource = ReadingSource.MANUEL
    temperature_c: float | None = Field(default=None, ge=-20, le=80)
    brix: float | None = Field(default=None, ge=-10, le=40)
    density: float | None = Field(default=None, ge=0.9, le=1.3)
    ph: float | None = Field(default=None, ge=0, le=14)
    total_acidity: float | None = Field(default=None, ge=0, le=50)
    volatile_acidity: float | None = Field(default=None, ge=0, le=10)
    free_so2: float | None = Field(default=None, ge=0, le=500)
    alcohol: float | None = Field(default=None, ge=0, le=25)
    cap_management: str | None = Field(default=None, max_length=64)
    notes: str | None = None

    @model_validator(mode="after")
    def _at_least_one(self):
        if all(
            getattr(self, f) is None
            for f in (
                "temperature_c",
                "brix",
                "density",
                "ph",
                "total_acidity",
                "volatile_acidity",
                "free_so2",
                "alcohol",
            )
        ):
            raise ValueError("En az bir ölçüm değeri girilmelidir.")
        return self


class FermentationReadingOut(ORMModel):
    id: int
    fermentation_id: int
    measured_at: dt.datetime
    source: str
    temperature_c: float | None = None
    brix: float | None = None
    density: float | None = None
    ph: float | None = None
    total_acidity: float | None = None
    volatile_acidity: float | None = None
    free_so2: float | None = None
    alcohol: float | None = None
    cap_management: str | None = None
    notes: str | None = None
    is_anomaly: bool = False
    anomaly_reason: str | None = None


class FermentationAdditiveCreate(BaseModel):
    additive_name: str = Field(min_length=1, max_length=160)
    additive_type: str = Field(default="katki", max_length=48)
    amount: float = Field(gt=0)
    unit: str = Field(default="g", max_length=16)
    added_at: dt.datetime | None = None
    inventory_item_id: int | None = None
    notes: str | None = None


class FermentationAdditiveOut(ORMModel):
    id: int
    additive_name: str
    additive_type: str
    amount: float
    unit: str
    added_at: dt.datetime
    inventory_item_id: int | None = None
    notes: str | None = None


class FermentationCurve(BaseModel):
    """Grafik icin duzlestirilmis egri verisi."""

    fermentation_id: int
    code: str
    lot_code: str | None = None
    labels: list[dt.datetime]
    temperature: list[float | None]
    brix: list[float | None]
    density: list[float | None]
    ph: list[float | None]
    temp_min_c: float
    temp_max_c: float
    target_brix: float
    anomalies: list[int] = Field(default_factory=list)
    predicted_end_date: dt.datetime | None = None
    prediction_note: str | None = None
