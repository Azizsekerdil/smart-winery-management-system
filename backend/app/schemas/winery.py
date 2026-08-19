"""Bag, parsel, cesit, tedarikci ve uzum kabul semalari."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.vineyard import GrapeColor, QualityGrade
from app.schemas.common import ORMModel


# ------------------------------------------------------------------- BAG
class VineyardBase(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    region: str | None = Field(default=None, max_length=120)
    village: str | None = Field(default=None, max_length=120)
    altitude_m: int | None = Field(default=None, ge=-500, le=5000)
    soil_type: str | None = Field(default=None, max_length=120)
    total_area_da: float | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_owned: bool = True
    notes: str | None = None
    is_active: bool = True


class VineyardCreate(VineyardBase):
    code: str | None = Field(default=None, max_length=32)


class VineyardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    region: str | None = None
    village: str | None = None
    altitude_m: int | None = None
    soil_type: str | None = None
    total_area_da: float | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_owned: bool | None = None
    notes: str | None = None
    is_active: bool | None = None


class VineyardOut(ORMModel, VineyardBase):
    id: int
    code: str
    created_at: dt.datetime
    parcel_count: int = 0


# ---------------------------------------------------------------- CESIT
class GrapeVarietyBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    color: GrapeColor = GrapeColor.KIRMIZI
    origin: str | None = Field(default=None, max_length=120)
    target_brix_min: float | None = Field(default=None, ge=0, le=40)
    target_brix_max: float | None = Field(default=None, ge=0, le=40)
    target_ph_min: float | None = Field(default=None, ge=0, le=14)
    target_ph_max: float | None = Field(default=None, ge=0, le=14)
    description: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _ranges(self):
        if (
            self.target_brix_min is not None
            and self.target_brix_max is not None
            and self.target_brix_min > self.target_brix_max
        ):
            raise ValueError("Brix alt sınırı üst sınırdan büyük olamaz.")
        if (
            self.target_ph_min is not None
            and self.target_ph_max is not None
            and self.target_ph_min > self.target_ph_max
        ):
            raise ValueError("pH alt sınırı üst sınırdan büyük olamaz.")
        return self


class GrapeVarietyCreate(GrapeVarietyBase):
    code: str | None = Field(default=None, max_length=32)


class GrapeVarietyUpdate(BaseModel):
    name: str | None = None
    color: GrapeColor | None = None
    origin: str | None = None
    target_brix_min: float | None = None
    target_brix_max: float | None = None
    target_ph_min: float | None = None
    target_ph_max: float | None = None
    description: str | None = None
    is_active: bool | None = None


class GrapeVarietyOut(ORMModel, GrapeVarietyBase):
    id: int
    code: str


# ---------------------------------------------------------------- PARSEL
class ParcelBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    vineyard_id: int
    variety_id: int | None = None
    area_da: float | None = Field(default=None, ge=0)
    planting_year: int | None = Field(default=None, ge=1800, le=2100)
    vine_count: int | None = Field(default=None, ge=0)
    rootstock: str | None = Field(default=None, max_length=80)
    training_system: str | None = Field(default=None, max_length=80)
    notes: str | None = None
    is_active: bool = True


class ParcelCreate(ParcelBase):
    code: str | None = Field(default=None, max_length=32)


class ParcelUpdate(BaseModel):
    name: str | None = None
    vineyard_id: int | None = None
    variety_id: int | None = None
    area_da: float | None = Field(default=None, ge=0)
    planting_year: int | None = Field(default=None, ge=1800, le=2100)
    vine_count: int | None = Field(default=None, ge=0)
    rootstock: str | None = None
    training_system: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class ParcelOut(ORMModel, ParcelBase):
    id: int
    code: str
    vineyard_name: str | None = None
    variety_name: str | None = None


# ------------------------------------------------------------ TEDARIKCI
class SupplierBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    supplier_type: str = Field(default="uzum", max_length=32)
    tax_number: str | None = Field(default=None, max_length=40)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
    is_active: bool = True


class SupplierCreate(SupplierBase):
    code: str | None = Field(default=None, max_length=32)


class SupplierUpdate(BaseModel):
    name: str | None = None
    supplier_type: str | None = None
    tax_number: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
    is_active: bool | None = None


class SupplierOut(ORMModel, SupplierBase):
    id: int
    code: str


# --------------------------------------------------------- UZUM KABULU
class HarvestIntakeBase(BaseModel):
    vineyard_id: int | None = None
    parcel_id: int | None = None
    variety_id: int
    supplier_id: int | None = None

    harvest_date: dt.date
    received_at: dt.datetime | None = None
    vintage_year: int | None = Field(default=None, ge=1900, le=2200)

    gross_weight_kg: float | None = Field(default=None, ge=0)
    tare_weight_kg: float | None = Field(default=None, ge=0)
    net_weight_kg: float = Field(gt=0, description="Net üzüm miktarı (kg)")
    vehicle_plate: str | None = Field(default=None, max_length=24)
    weighbridge_ticket: str | None = Field(default=None, max_length=48)

    brix: float | None = Field(default=None, ge=0, le=40)
    ph: float | None = Field(default=None, ge=0, le=14)
    total_acidity: float | None = Field(default=None, ge=0, le=50)
    temperature_c: float | None = Field(default=None, ge=-20, le=60)
    rot_percent: float | None = Field(default=None, ge=0, le=100)
    quality_grade: QualityGrade = QualityGrade.A

    unit_price: float | None = Field(default=None, ge=0)
    currency: str = Field(default="TRY", max_length=8)
    notes: str | None = None

    @model_validator(mode="after")
    def _weights(self):
        if self.gross_weight_kg is not None and self.tare_weight_kg is not None:
            expected = self.gross_weight_kg - self.tare_weight_kg
            if expected <= 0:
                raise ValueError("Brüt ağırlık dara ağırlığından büyük olmalıdır.")
            if abs(expected - self.net_weight_kg) > 1.0:
                raise ValueError(
                    f"Net ağırlık (brüt - dara) ile uyuşmuyor. Beklenen: {expected:.2f} kg"
                )
        return self


class HarvestIntakeCreate(HarvestIntakeBase):
    code: str | None = Field(default=None, max_length=48)

    @model_validator(mode="after")
    def _fill_defaults(self):
        """Zorunlu (NOT NULL) alanlari hasat tarihinden turet."""
        if self.received_at is None:
            self.received_at = dt.datetime.combine(self.harvest_date, dt.time(9, 0), dt.UTC)
        if self.vintage_year is None:
            self.vintage_year = self.harvest_date.year
        return self


class HarvestIntakeUpdate(BaseModel):
    vineyard_id: int | None = None
    parcel_id: int | None = None
    variety_id: int | None = None
    supplier_id: int | None = None
    harvest_date: dt.date | None = None
    received_at: dt.datetime | None = None
    gross_weight_kg: float | None = Field(default=None, ge=0)
    tare_weight_kg: float | None = Field(default=None, ge=0)
    net_weight_kg: float | None = Field(default=None, gt=0)
    vehicle_plate: str | None = None
    weighbridge_ticket: str | None = None
    brix: float | None = Field(default=None, ge=0, le=40)
    ph: float | None = Field(default=None, ge=0, le=14)
    total_acidity: float | None = Field(default=None, ge=0, le=50)
    temperature_c: float | None = Field(default=None, ge=-20, le=60)
    rot_percent: float | None = Field(default=None, ge=0, le=100)
    quality_grade: QualityGrade | None = None
    unit_price: float | None = Field(default=None, ge=0)
    notes: str | None = None


class HarvestIntakeOut(ORMModel):
    id: int
    code: str
    vineyard_id: int | None = None
    parcel_id: int | None = None
    variety_id: int
    supplier_id: int | None = None
    harvest_date: dt.date
    received_at: dt.datetime
    vintage_year: int
    gross_weight_kg: float | None = None
    tare_weight_kg: float | None = None
    net_weight_kg: float
    vehicle_plate: str | None = None
    weighbridge_ticket: str | None = None
    brix: float | None = None
    ph: float | None = None
    total_acidity: float | None = None
    temperature_c: float | None = None
    rot_percent: float | None = None
    quality_grade: str
    unit_price: float | None = None
    currency: str
    qr_payload: str | None = None
    notes: str | None = None
    created_at: dt.datetime
    # zenginlestirilmis alanlar
    variety_name: str | None = None
    vineyard_name: str | None = None
    supplier_name: str | None = None
    total_cost: float = 0.0


class AttachmentOut(ORMModel):
    id: int
    filename: str
    content_type: str
    size_bytes: int
    description: str | None = None
    created_at: dt.datetime
    url: str | None = None
