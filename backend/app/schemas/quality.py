"""Laboratuvar, recete ve kupaj semalari."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator

from app.models.quality import ApprovalStatus, BlendStatus, RecipeStatus, SampleStatus
from app.schemas.common import ORMModel


# ------------------------------------------------------------ LABORATUVAR
class LabSampleCreate(BaseModel):
    code: str | None = Field(default=None, max_length=48)
    lot_id: int | None = None
    tank_id: int | None = None
    barrel_id: int | None = None
    sampled_at: dt.datetime | None = None
    sample_type: str = Field(default="rutin", max_length=48)
    notes: str | None = None

    @model_validator(mode="after")
    def _source(self):
        if not any((self.lot_id, self.tank_id, self.barrel_id)):
            raise ValueError("Numune için parti, tank veya fıçı belirtilmelidir.")
        if self.sampled_at is None:
            self.sampled_at = dt.datetime.now(dt.UTC)
        return self


class LabSampleUpdate(BaseModel):
    status: SampleStatus | None = None
    sample_type: str | None = None
    notes: str | None = None


class LabSampleOut(ORMModel):
    id: int
    code: str
    lot_id: int | None = None
    tank_id: int | None = None
    barrel_id: int | None = None
    sampled_at: dt.datetime
    sampled_by_id: int | None = None
    sample_type: str
    status: str
    notes: str | None = None
    created_at: dt.datetime
    lot_code: str | None = None
    tank_code: str | None = None
    result_count: int = 0


class LabResultCreate(BaseModel):
    code: str | None = Field(default=None, max_length=48)
    analyzed_at: dt.datetime | None = None
    ph: float | None = Field(default=None, ge=0, le=14)
    total_acidity: float | None = Field(default=None, ge=0, le=50)
    volatile_acidity: float | None = Field(default=None, ge=0, le=10)
    free_so2: float | None = Field(default=None, ge=0, le=500)
    total_so2: float | None = Field(default=None, ge=0, le=1000)
    alcohol: float | None = Field(default=None, ge=0, le=25)
    residual_sugar: float | None = Field(default=None, ge=0, le=500)
    density: float | None = Field(default=None, ge=0.9, le=1.3)
    malic_acid: float | None = Field(default=None, ge=0, le=20)
    lactic_acid: float | None = Field(default=None, ge=0, le=20)
    dry_extract: float | None = Field(default=None, ge=0, le=100)
    turbidity_ntu: float | None = Field(default=None, ge=0)
    micro_yeast_cfu: float | None = Field(default=None, ge=0)
    micro_bacteria_cfu: float | None = Field(default=None, ge=0)
    micro_brettanomyces: bool | None = None
    micro_notes: str | None = None
    extra_parameters: dict = Field(default_factory=dict)
    notes: str | None = None

    @model_validator(mode="after")
    def _so2_consistency(self):
        if (
            self.free_so2 is not None
            and self.total_so2 is not None
            and self.free_so2 > self.total_so2
        ):
            raise ValueError("Serbest SO₂, toplam SO₂ değerinden büyük olamaz.")
        return self


class LabResultUpdate(LabResultCreate):
    pass


class LabApproval(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _reason_required(self):
        if not self.approve and not (self.reason or "").strip():
            raise ValueError("Red işlemi için gerekçe zorunludur.")
        return self


class LabResultOut(ORMModel):
    id: int
    code: str
    sample_id: int
    lot_id: int | None = None
    analyzed_at: dt.datetime
    analyzed_by_id: int | None = None
    ph: float | None = None
    total_acidity: float | None = None
    volatile_acidity: float | None = None
    free_so2: float | None = None
    total_so2: float | None = None
    alcohol: float | None = None
    residual_sugar: float | None = None
    density: float | None = None
    malic_acid: float | None = None
    lactic_acid: float | None = None
    dry_extract: float | None = None
    turbidity_ntu: float | None = None
    micro_yeast_cfu: float | None = None
    micro_bacteria_cfu: float | None = None
    micro_brettanomyces: bool | None = None
    micro_notes: str | None = None
    extra_parameters: dict = Field(default_factory=dict)
    approval_status: str
    approved_by_id: int | None = None
    approved_at: dt.datetime | None = None
    rejection_reason: str | None = None
    out_of_spec: bool = False
    out_of_spec_details: str | None = None
    notes: str | None = None
    created_at: dt.datetime
    lot_code: str | None = None
    sample_code: str | None = None


class LabSpecOut(ORMModel):
    id: int
    parameter: str
    wine_type: str | None = None
    stage: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    unit: str
    severity: str
    label_tr: str
    is_active: bool


class LabSpecCreate(BaseModel):
    parameter: str = Field(max_length=48)
    wine_type: str | None = None
    stage: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    unit: str = ""
    severity: str = "uyari"
    label_tr: str = ""
    is_active: bool = True


class LabSpecUpdate(BaseModel):
    min_value: float | None = None
    max_value: float | None = None
    unit: str | None = None
    severity: str | None = None
    label_tr: str | None = None
    is_active: bool | None = None


# --------------------------------------------------------------- RECETE
class RecipeItemIn(BaseModel):
    item_kind: str = Field(default="uzum", max_length=24)
    variety_id: int | None = None
    inventory_item_id: int | None = None
    name: str = Field(min_length=1, max_length=160)
    percentage: float | None = Field(default=None, ge=0, le=100)
    amount: float | None = Field(default=None, ge=0)
    unit: str = Field(default="%", max_length=16)
    unit_cost: float = Field(default=0, ge=0)
    notes: str | None = None


class RecipeItemOut(ORMModel, RecipeItemIn):
    id: int
    line_cost: float = 0.0


class RecipeCreate(BaseModel):
    code: str | None = Field(default=None, max_length=48)
    name: str = Field(min_length=2, max_length=200)
    wine_type: str = "kirmizi"
    target_volume_l: float = Field(default=0, ge=0)
    vintage_year: int | None = Field(default=None, ge=1900, le=2200)
    target_alcohol: float | None = Field(default=None, ge=0, le=25)
    target_ph: float | None = Field(default=None, ge=0, le=14)
    target_ta: float | None = Field(default=None, ge=0, le=50)
    aging_months: int | None = Field(default=None, ge=0, le=600)
    description: str | None = None
    process_steps: list[dict] = Field(default_factory=list)
    items: list[RecipeItemIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _grape_percent(self):
        grapes = [i for i in self.items if i.item_kind == "uzum"]
        if grapes:
            total = sum(i.percentage or 0 for i in grapes)
            if abs(total - 100) > 0.5:
                raise ValueError(
                    f"Üzüm bileşenlerinin oranları toplamı %100 olmalıdır (şu an %{total:.1f})."
                )
        return self


class RecipeUpdate(BaseModel):
    name: str | None = None
    wine_type: str | None = None
    target_volume_l: float | None = Field(default=None, ge=0)
    vintage_year: int | None = None
    target_alcohol: float | None = None
    target_ph: float | None = None
    target_ta: float | None = None
    aging_months: int | None = None
    description: str | None = None
    process_steps: list[dict] | None = None
    items: list[RecipeItemIn] | None = None
    status: RecipeStatus | None = None


class RecipeOut(ORMModel):
    id: int
    code: str
    name: str
    version: int
    parent_recipe_id: int | None = None
    wine_type: str
    target_volume_l: float
    vintage_year: int | None = None
    status: str
    approved_by_id: int | None = None
    approved_at: dt.datetime | None = None
    target_alcohol: float | None = None
    target_ph: float | None = None
    target_ta: float | None = None
    aging_months: int | None = None
    description: str | None = None
    process_steps: list = Field(default_factory=list)
    created_at: dt.datetime
    items: list[RecipeItemOut] = Field(default_factory=list)
    estimated_cost: float = 0.0


# ---------------------------------------------------------------- KUPAJ
class BlendComponentIn(BaseModel):
    source_lot_id: int
    volume_l: float = Field(gt=0)


class BlendComponentOut(ORMModel):
    id: int
    source_lot_id: int
    volume_l: float
    percentage: float | None = None
    unit_cost_l: float = 0
    source_lot_code: str | None = None
    source_lot_name: str | None = None


class BlendCreate(BaseModel):
    code: str | None = Field(default=None, max_length=48)
    name: str = Field(min_length=2, max_length=200)
    recipe_id: int | None = None
    target_tank_id: int | None = None
    planned_at: dt.datetime | None = None
    notes: str | None = None
    components: list[BlendComponentIn] = Field(min_length=2)


class BlendUpdate(BaseModel):
    name: str | None = None
    recipe_id: int | None = None
    target_tank_id: int | None = None
    planned_at: dt.datetime | None = None
    notes: str | None = None
    components: list[BlendComponentIn] | None = None
    status: BlendStatus | None = None


class BlendOut(ORMModel):
    id: int
    code: str
    name: str
    recipe_id: int | None = None
    result_lot_id: int | None = None
    target_tank_id: int | None = None
    status: str
    planned_volume_l: float
    actual_volume_l: float | None = None
    planned_at: dt.datetime | None = None
    executed_at: dt.datetime | None = None
    approved_by_id: int | None = None
    approved_at: dt.datetime | None = None
    predicted_alcohol: float | None = None
    predicted_ph: float | None = None
    predicted_ta: float | None = None
    estimated_cost: float | None = None
    notes: str | None = None
    created_at: dt.datetime
    components: list[BlendComponentOut] = Field(default_factory=list)


class BlendApproval(BaseModel):
    approve: bool
    reason: str | None = None


class BlendExecute(BaseModel):
    result_lot_name: str = Field(min_length=2, max_length=200)
    result_lot_code: str | None = None
    target_tank_id: int | None = None
    executed_at: dt.datetime | None = None


class LotSplitRequest(BaseModel):
    """Parti bolme."""

    volume_l: float = Field(gt=0)
    new_lot_name: str = Field(min_length=2, max_length=200)
    new_lot_code: str | None = None
    target_tank_id: int | None = None
    notes: str | None = None


class ApprovalOut(BaseModel):
    id: int
    approval_status: ApprovalStatus
    detail: str
