"""Stok, depo, satin alma ve sevkiyat modelleri (FIFO/FEFO destekli)."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuthorMixin, Base, TimestampMixin


class ItemCategory(StrEnum):
    HAMMADDE = "hammadde"          # üzüm, şıra
    KATKI = "katki"                # maya, enzim, SO2, bentonit
    SARF = "sarf"                  # filtre, kimyasal, temizlik
    AMBALAJ = "ambalaj"            # şişe, mantar, kapsül, etiket, koli
    BITMIS_URUN = "bitmis_urun"    # şişelenmiş şarap
    YEDEK_PARCA = "yedek_parca"


class ValuationMethod(StrEnum):
    FIFO = "fifo"
    FEFO = "fefo"
    ORTALAMA = "ortalama"


class Warehouse(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_cold_storage: Mapped[bool] = mapped_column(Boolean, default=False)
    temperature_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryItem(Base, TimestampMixin, AuthorMixin):
    """Stok kartı."""

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(24), default=ItemCategory.SARF, index=True)
    unit: Mapped[str] = mapped_column(String(16), default="adet")

    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    default_supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )

    min_stock: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    reorder_qty: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    valuation_method: Mapped[str] = mapped_column(String(12), default=ValuationMethod.FIFO)
    last_unit_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="TRY")
    has_expiry: Mapped[bool] = mapped_column(Boolean, default=False)
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Bitmis urun ise ilgili siseleme emri.
    # NOT: Burada bilincli olarak ForeignKey KULLANILMAZ. `bottling_orders` tablosu
    # ambalaj kalemleri icin `inventory_items`e bes ayri FK ile bagli oldugundan
    # cift yonlu FK dairesel bagimlilik olusturur; SQLite ALTER ile kisit ekleyemedigi
    # icin tablolar olusturulamaz/silinemez hale gelir. Bu alan mantiksal referanstir
    # ve butunluk uygulama katmaninda korunur (bkz. ARCHITECTURE.md).
    bottling_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("lots.id", ondelete="SET NULL"), nullable=True, index=True
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    batches: Mapped[list[StockBatch]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class StockBatch(Base, TimestampMixin, AuthorMixin):
    """Parti bazli stok yigini. FIFO/FEFO tuketimi bu kayitlar uzerinden yapilir."""

    __tablename__ = "stock_batches"
    __table_args__ = (
        Index("ix_stock_batches_item_wh", "item_id", "warehouse_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    batch_code: Mapped[str] = mapped_column(String(64), index=True)

    quantity: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    unit_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    received_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    expiry_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True, index=True)
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    item: Mapped[InventoryItem] = relationship(back_populates="batches")

    @property
    def value(self) -> float:
        return round(float(self.quantity) * float(self.unit_cost), 2)


class MovementType(StrEnum):
    GIRIS = "giris"
    CIKIS = "cikis"
    TRANSFER = "transfer"
    SAYIM = "sayim"
    FIRE = "fire"
    URETIM_TUKETIM = "uretim_tuketim"
    URETIM_GIRIS = "uretim_giris"
    IADE = "iade"


class StockMovement(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "stock_movements"
    __table_args__ = (
        Index("ix_stock_moves_item_time", "item_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), index=True
    )
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("stock_batches.id", ondelete="SET NULL"), nullable=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    target_warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True
    )

    movement_type: Mapped[str] = mapped_column(String(20), index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Kaynak belge iliskisi
    ref_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("lots.id", ondelete="SET NULL"), nullable=True, index=True
    )

    performed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def value(self) -> float:
        return round(float(self.quantity) * float(self.unit_cost), 2)


# ---------------------------------------------------------------- SATINALMA
class PurchaseStatus(StrEnum):
    TASLAK = "taslak"
    SIPARIS_VERILDI = "siparis_verildi"
    KISMEN_TESLIM = "kismen_teslim"
    TESLIM_ALINDI = "teslim_alindi"
    IPTAL = "iptal"


class PurchaseOrder(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default=PurchaseStatus.TASLAK, index=True)
    order_date: Mapped[dt.date] = mapped_column(Date, index=True)
    expected_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    received_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="TRY")
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=20)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list[PurchaseOrderLine]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    @property
    def subtotal(self) -> float:
        return round(sum(line_.line_total for line_ in self.lines), 2)

    @property
    def total(self) -> float:
        return round(self.subtotal * (1 + float(self.tax_rate) / 100), 2)


class PurchaseOrderLine(Base, TimestampMixin):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    received_quantity: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[PurchaseOrder] = relationship(back_populates="lines")

    @property
    def line_total(self) -> float:
        return round(float(self.quantity) * float(self.unit_price), 2)


# ----------------------------------------------------------------- SEVKIYAT
class Customer(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    customer_type: Mapped[str] = mapped_column(String(32), default="bayi")
    tax_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    country: Mapped[str] = mapped_column(String(80), default="Türkiye")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ShipmentStatus(StrEnum):
    TASLAK = "taslak"
    HAZIRLANIYOR = "hazirlaniyor"
    SEVK_EDILDI = "sevk_edildi"
    TESLIM_EDILDI = "teslim_edildi"
    IPTAL = "iptal"


class Shipment(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=ShipmentStatus.TASLAK, index=True)

    order_date: Mapped[dt.date] = mapped_column(Date, index=True)
    shipped_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    carrier: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tracking_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="TRY")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list[ShipmentLine]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan"
    )

    @property
    def total(self) -> float:
        return round(sum(line_.line_total for line_ in self.lines), 2)


class ShipmentLine(Base, TimestampMixin):
    __tablename__ = "shipment_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(
        ForeignKey("shipments.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), index=True
    )
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("stock_batches.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(14, 4), default=0)

    shipment: Mapped[Shipment] = relationship(back_populates="lines")

    @property
    def line_total(self) -> float:
        return round(float(self.quantity) * float(self.unit_price), 2)
