"""Stok, satin alma ve sevkiyat semalari."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.inventory import (
    ItemCategory,
    MovementType,
    PurchaseStatus,
    ShipmentStatus,
    ValuationMethod,
)
from app.schemas.common import ORMModel


# ------------------------------------------------------------------ DEPO
class WarehouseBase(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    location: str | None = Field(default=None, max_length=200)
    is_cold_storage: bool = False
    temperature_c: float | None = Field(default=None, ge=-40, le=60)
    notes: str | None = None
    is_active: bool = True


class WarehouseCreate(WarehouseBase):
    code: str | None = Field(default=None, max_length=32)


class WarehouseUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    is_cold_storage: bool | None = None
    temperature_c: float | None = None
    notes: str | None = None
    is_active: bool | None = None


class WarehouseOut(ORMModel, WarehouseBase):
    id: int
    code: str
    item_count: int = 0
    total_value: float = 0.0


# ------------------------------------------------------------ STOK KARTI
class ItemBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    category: ItemCategory = ItemCategory.SARF
    unit: str = Field(default="adet", max_length=16)
    barcode: str | None = Field(default=None, max_length=64)
    default_supplier_id: int | None = None
    min_stock: float = Field(default=0, ge=0)
    reorder_qty: float = Field(default=0, ge=0)
    valuation_method: ValuationMethod = ValuationMethod.FIFO
    currency: str = Field(default="TRY", max_length=8)
    has_expiry: bool = False
    shelf_life_days: int | None = Field(default=None, ge=0)
    description: str | None = None
    is_active: bool = True


class ItemCreate(ItemBase):
    code: str | None = Field(default=None, max_length=48)


class ItemUpdate(BaseModel):
    name: str | None = None
    category: ItemCategory | None = None
    unit: str | None = None
    barcode: str | None = None
    default_supplier_id: int | None = None
    min_stock: float | None = Field(default=None, ge=0)
    reorder_qty: float | None = Field(default=None, ge=0)
    valuation_method: ValuationMethod | None = None
    has_expiry: bool | None = None
    shelf_life_days: int | None = None
    description: str | None = None
    is_active: bool | None = None


class ItemOut(ORMModel, ItemBase):
    id: int
    code: str
    last_unit_cost: float = 0.0
    bottling_order_id: int | None = None
    lot_id: int | None = None
    created_at: dt.datetime
    # hesaplanan
    on_hand: float = 0.0
    stock_value: float = 0.0
    below_min: bool = False
    nearest_expiry: dt.date | None = None


class StockBatchOut(ORMModel):
    id: int
    item_id: int
    warehouse_id: int
    batch_code: str
    quantity: float
    unit_cost: float
    received_at: dt.datetime
    expiry_date: dt.date | None = None
    supplier_id: int | None = None
    notes: str | None = None
    value: float = 0.0
    item_name: str | None = None
    warehouse_code: str | None = None
    days_to_expiry: int | None = None


class StockInRequest(BaseModel):
    """Stok girisi (satin alma disi manuel giris dahil)."""

    item_id: int
    warehouse_id: int
    quantity: float = Field(gt=0)
    unit_cost: float = Field(default=0, ge=0)
    batch_code: str | None = Field(default=None, max_length=64)
    expiry_date: dt.date | None = None
    supplier_id: int | None = None
    occurred_at: dt.datetime | None = None
    ref_type: str | None = None
    ref_id: int | None = None
    notes: str | None = None


class StockOutRequest(BaseModel):
    """Stok cikisi. FIFO/FEFO'ya gore parti secimi otomatiktir."""

    item_id: int
    warehouse_id: int
    quantity: float = Field(gt=0)
    movement_type: MovementType = MovementType.CIKIS
    occurred_at: dt.datetime | None = None
    lot_id: int | None = None
    ref_type: str | None = None
    ref_id: int | None = None
    notes: str | None = None


class StockTransferRequest(BaseModel):
    item_id: int
    from_warehouse_id: int
    to_warehouse_id: int
    quantity: float = Field(gt=0)
    occurred_at: dt.datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _different(self):
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError("Kaynak ve hedef depo aynı olamaz.")
        return self


class StockCountRequest(BaseModel):
    """Sayim duzeltmesi."""

    item_id: int
    warehouse_id: int
    counted_quantity: float = Field(ge=0)
    occurred_at: dt.datetime | None = None
    notes: str | None = None


class StockMovementOut(ORMModel):
    id: int
    code: str
    item_id: int
    batch_id: int | None = None
    warehouse_id: int
    target_warehouse_id: int | None = None
    movement_type: str
    quantity: float
    unit_cost: float
    occurred_at: dt.datetime
    ref_type: str | None = None
    ref_id: int | None = None
    lot_id: int | None = None
    notes: str | None = None
    value: float = 0.0
    item_name: str | None = None
    item_code: str | None = None
    warehouse_code: str | None = None
    performed_by_name: str | None = None


class StockLevel(BaseModel):
    item_id: int
    item_code: str
    item_name: str
    category: str
    unit: str
    on_hand: float
    min_stock: float
    below_min: bool
    stock_value: float
    warehouses: dict[str, float] = Field(default_factory=dict)
    nearest_expiry: dt.date | None = None
    days_of_cover: float | None = None


# -------------------------------------------------------------- SATINALMA
class PurchaseLineIn(BaseModel):
    item_id: int
    quantity: float = Field(gt=0)
    unit_price: float = Field(default=0, ge=0)
    notes: str | None = None


class PurchaseLineOut(ORMModel, PurchaseLineIn):
    id: int
    received_quantity: float = 0
    line_total: float = 0.0
    item_name: str | None = None


class PurchaseCreate(BaseModel):
    code: str | None = Field(default=None, max_length=48)
    supplier_id: int
    warehouse_id: int | None = None
    order_date: dt.date | None = None
    expected_date: dt.date | None = None
    currency: str = "TRY"
    tax_rate: float = Field(default=20, ge=0, le=100)
    notes: str | None = None
    lines: list[PurchaseLineIn] = Field(min_length=1)


class PurchaseUpdate(BaseModel):
    supplier_id: int | None = None
    warehouse_id: int | None = None
    status: PurchaseStatus | None = None
    expected_date: dt.date | None = None
    tax_rate: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = None
    lines: list[PurchaseLineIn] | None = None


class PurchaseReceiveLine(BaseModel):
    line_id: int
    quantity: float = Field(gt=0)
    unit_cost: float | None = Field(default=None, ge=0)
    batch_code: str | None = None
    expiry_date: dt.date | None = None


class PurchaseReceive(BaseModel):
    warehouse_id: int
    received_date: dt.date | None = None
    lines: list[PurchaseReceiveLine] = Field(min_length=1)


class PurchaseOut(ORMModel):
    id: int
    code: str
    supplier_id: int
    warehouse_id: int | None = None
    status: str
    order_date: dt.date
    expected_date: dt.date | None = None
    received_date: dt.date | None = None
    currency: str
    tax_rate: float
    notes: str | None = None
    created_at: dt.datetime
    lines: list[PurchaseLineOut] = Field(default_factory=list)
    subtotal: float = 0.0
    total: float = 0.0
    supplier_name: str | None = None


# --------------------------------------------------------------- MUSTERI
class CustomerBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    customer_type: str = Field(default="bayi", max_length=32)
    tax_number: str | None = Field(default=None, max_length=40)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = None
    city: str | None = Field(default=None, max_length=80)
    country: str = "Türkiye"
    is_active: bool = True


class CustomerCreate(CustomerBase):
    code: str | None = Field(default=None, max_length=32)


class CustomerUpdate(BaseModel):
    name: str | None = None
    customer_type: str | None = None
    tax_number: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    is_active: bool | None = None


class CustomerOut(ORMModel, CustomerBase):
    id: int
    code: str


# -------------------------------------------------------------- SEVKIYAT
class ShipmentLineIn(BaseModel):
    item_id: int
    quantity: float = Field(gt=0)
    unit_price: float = Field(default=0, ge=0)


class ShipmentLineOut(ORMModel, ShipmentLineIn):
    id: int
    batch_id: int | None = None
    line_total: float = 0.0
    item_name: str | None = None


class ShipmentCreate(BaseModel):
    code: str | None = Field(default=None, max_length=48)
    customer_id: int
    warehouse_id: int
    order_date: dt.date | None = None
    carrier: str | None = Field(default=None, max_length=120)
    tracking_no: str | None = Field(default=None, max_length=80)
    destination: str | None = None
    currency: str = "TRY"
    notes: str | None = None
    lines: list[ShipmentLineIn] = Field(min_length=1)


class ShipmentUpdate(BaseModel):
    customer_id: int | None = None
    warehouse_id: int | None = None
    status: ShipmentStatus | None = None
    carrier: str | None = None
    tracking_no: str | None = None
    destination: str | None = None
    notes: str | None = None
    lines: list[ShipmentLineIn] | None = None


class ShipmentOut(ORMModel):
    id: int
    code: str
    customer_id: int
    warehouse_id: int
    status: str
    order_date: dt.date
    shipped_at: dt.datetime | None = None
    delivered_at: dt.datetime | None = None
    carrier: str | None = None
    tracking_no: str | None = None
    destination: str | None = None
    currency: str
    notes: str | None = None
    created_at: dt.datetime
    lines: list[ShipmentLineOut] = Field(default_factory=list)
    total: float = 0.0
    customer_name: str | None = None
