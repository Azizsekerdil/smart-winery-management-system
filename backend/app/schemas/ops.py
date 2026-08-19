"""Bakim, uyari, denetim, pano ve rapor semalari."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator

from app.models.ops import (
    AlertSeverity,
    AlertStatus,
    EquipmentStatus,
    EquipmentType,
    MaintenanceKind,
)
from app.schemas.common import ORMModel


# --------------------------------------------------------------- EKIPMAN
class EquipmentBase(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    equipment_type: EquipmentType = EquipmentType.DIGER
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_no: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    tank_id: int | None = None
    install_date: dt.date | None = None
    maintenance_interval_days: int | None = Field(default=None, ge=1, le=3650)
    notes: str | None = None
    is_active: bool = True


class EquipmentCreate(EquipmentBase):
    code: str | None = Field(default=None, max_length=32)


class EquipmentUpdate(BaseModel):
    name: str | None = None
    equipment_type: EquipmentType | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_no: str | None = None
    location: str | None = None
    tank_id: int | None = None
    status: EquipmentStatus | None = None
    install_date: dt.date | None = None
    maintenance_interval_days: int | None = None
    next_maintenance_at: dt.date | None = None
    notes: str | None = None
    is_active: bool | None = None


class EquipmentOut(ORMModel, EquipmentBase):
    id: int
    code: str
    status: str
    last_maintenance_at: dt.date | None = None
    next_maintenance_at: dt.date | None = None
    maintenance_due_days: int | None = None
    created_at: dt.datetime


class MaintenanceCreate(BaseModel):
    code: str | None = Field(default=None, max_length=48)
    equipment_id: int | None = None
    tank_id: int | None = None
    barrel_id: int | None = None
    kind: MaintenanceKind = MaintenanceKind.PERIYODIK
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    started_at: dt.datetime | None = None
    finished_at: dt.datetime | None = None
    downtime_minutes: int | None = Field(default=None, ge=0)
    responsible_id: int | None = None
    cost: float = Field(default=0, ge=0)
    cip_chemical: str | None = Field(default=None, max_length=120)
    cip_temperature_c: float | None = Field(default=None, ge=0, le=150)
    cip_duration_min: int | None = Field(default=None, ge=0)
    cip_verified: bool | None = None

    @model_validator(mode="after")
    def _fill_defaults(self):
        if self.started_at is None:
            self.started_at = dt.datetime.now(dt.UTC)
        return self


class MaintenanceUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    finished_at: dt.datetime | None = None
    downtime_minutes: int | None = None
    responsible_id: int | None = None
    cost: float | None = Field(default=None, ge=0)
    cip_verified: bool | None = None


class MaintenanceOut(ORMModel):
    id: int
    code: str
    equipment_id: int | None = None
    tank_id: int | None = None
    barrel_id: int | None = None
    kind: str
    title: str
    description: str | None = None
    started_at: dt.datetime
    finished_at: dt.datetime | None = None
    downtime_minutes: int | None = None
    responsible_id: int | None = None
    cost: float
    cip_chemical: str | None = None
    cip_temperature_c: float | None = None
    cip_duration_min: int | None = None
    cip_verified: bool | None = None
    created_at: dt.datetime
    equipment_name: str | None = None
    tank_code: str | None = None
    responsible_name: str | None = None


# ----------------------------------------------------------------- UYARI
class AlertOut(ORMModel):
    id: int
    category: str
    severity: str
    status: str
    title: str
    message: str
    ref_type: str | None = None
    ref_id: int | None = None
    ref_code: str | None = None
    ai_generated: bool = False
    ai_provider: str | None = None
    acknowledged_by_id: int | None = None
    acknowledged_at: dt.datetime | None = None
    resolved_at: dt.datetime | None = None
    resolution_note: str | None = None
    created_at: dt.datetime


class AlertCreate(BaseModel):
    category: str = Field(max_length=32)
    severity: AlertSeverity = AlertSeverity.UYARI
    title: str = Field(min_length=2, max_length=220)
    message: str
    ref_type: str | None = None
    ref_id: int | None = None
    ref_code: str | None = None
    dedupe_key: str | None = None


class AlertUpdate(BaseModel):
    status: AlertStatus
    resolution_note: str | None = None


# ----------------------------------------------------- DENETIM GUNLUGU
class AuditOut(ORMModel):
    id: int
    created_at: dt.datetime
    user_id: int | None = None
    username: str | None = None
    action: str
    entity_type: str
    entity_id: int | None = None
    entity_code: str | None = None
    summary: str
    before_data: dict | None = None
    after_data: dict | None = None
    changed_fields: list | None = None
    ip_address: str | None = None
    request_path: str | None = None
    request_method: str | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    agent_task_id: int | None = None
    severity: str


# ------------------------------------------------------------------ PANO
class KpiCard(BaseModel):
    key: str
    label: str
    value: float | int | str
    unit: str = ""
    trend: float | None = None
    trend_label: str | None = None
    severity: str = "bilgi"
    icon: str | None = None


class TankFillSummary(BaseModel):
    id: int
    code: str
    tank_type: str
    capacity_l: float
    current_volume_l: float
    fill_percent: float
    status: str
    temperature_c: float | None = None
    target_temperature_c: float | None = None
    lot_code: str | None = None
    lot_name: str | None = None
    zone: str | None = None
    position_x: int | None = None
    position_y: int | None = None
    temp_alert: bool = False


class UpcomingTask(BaseModel):
    kind: str
    title: str
    due_date: dt.date | None = None
    days_left: int | None = None
    ref_type: str | None = None
    ref_id: int | None = None
    ref_code: str | None = None
    severity: str = "bilgi"


class ActivityItem(BaseModel):
    at: dt.datetime
    username: str | None = None
    action: str
    entity_type: str
    entity_code: str | None = None
    summary: str


class SeriesPoint(BaseModel):
    label: str
    value: float


class DashboardOut(BaseModel):
    generated_at: dt.datetime
    kpis: list[KpiCard]
    active_fermentations: list[dict]
    critical_alerts: list[AlertOut]
    tank_fills: list[TankFillSummary]
    upcoming_tasks: list[UpcomingTask]
    daily_production: list[SeriesPoint]
    stock_summary: list[SeriesPoint]
    low_stock_items: list[dict]
    recent_activity: list[ActivityItem]
    ai_suggestions: list[dict] = Field(default_factory=list)
    lot_stage_distribution: list[SeriesPoint] = Field(default_factory=list)


# --------------------------------------------------------------- RAPORLAR
class CostBreakdown(BaseModel):
    lot_id: int
    lot_code: str
    lot_name: str
    vintage_year: int
    volume_l: float
    grape_cost: float = 0.0
    additive_cost: float = 0.0
    packaging_cost: float = 0.0
    labor_cost: float = 0.0
    energy_cost: float = 0.0
    overhead_cost: float = 0.0
    total_cost: float = 0.0
    cost_per_liter: float = 0.0
    cost_per_bottle: float | None = None
    bottles_produced: int = 0
    loss_l: float = 0.0
    loss_percent: float = 0.0
    currency: str = "TRY"
    details: list[dict] = Field(default_factory=list)


class ProductionSummary(BaseModel):
    period_start: dt.date
    period_end: dt.date
    intake_kg: float = 0.0
    intake_count: int = 0
    juice_l: float = 0.0
    bottles_produced: int = 0
    bottles_rejected: int = 0
    active_lots: int = 0
    completed_lots: int = 0
    total_loss_l: float = 0.0
    yield_l_per_kg: float | None = None
    by_variety: list[SeriesPoint] = Field(default_factory=list)
    by_month: list[SeriesPoint] = Field(default_factory=list)


class ExportRequest(BaseModel):
    report: str = Field(description="uretim|maliyet|stok|laboratuvar|izlenebilirlik|fermantasyon")
    fmt: str = Field(default="xlsx", pattern=r"^(xlsx|csv|pdf)$")
    start: dt.date | None = None
    end: dt.date | None = None
    lot_id: int | None = None
    variety_id: int | None = None
    department: str | None = None
