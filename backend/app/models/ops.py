"""Ekipman/bakim, temizlik (CIP), uyari ve denetim gunlugu modelleri."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    JSON,
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


# ---------------------------------------------------------------- EKIPMAN
class EquipmentType(StrEnum):
    TANK = "tank"
    POMPA = "pompa"
    PRES = "pres"
    SISELEME_HATTI = "siseleme_hatti"
    SOGUTMA = "sogutma"
    FILTRE = "filtre"
    DESTEMMER = "sap_ayirici"
    DIGER = "diger"


class EquipmentStatus(StrEnum):
    CALISIYOR = "calisiyor"
    BAKIMDA = "bakimda"
    ARIZALI = "arizali"
    DEVRE_DISI = "devre_disi"


class Equipment(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    equipment_type: Mapped[str] = mapped_column(String(24), default=EquipmentType.DIGER)
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tank_id: Mapped[int | None] = mapped_column(
        ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(16), default=EquipmentStatus.CALISIYOR, index=True
    )
    install_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    maintenance_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_maintenance_at: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    next_maintenance_at: Mapped[dt.date | None] = mapped_column(Date, nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    logs: Mapped[list[MaintenanceLog]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )

    @property
    def maintenance_due_days(self) -> int | None:
        if self.next_maintenance_at is None:
            return None
        return (self.next_maintenance_at - dt.date.today()).days


class MaintenanceKind(StrEnum):
    PERIYODIK = "periyodik"
    ARIZA = "ariza"
    KALIBRASYON = "kalibrasyon"
    TEMIZLIK = "temizlik"
    CIP = "cip"


class MaintenanceLog(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "maintenance_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tank_id: Mapped[int | None] = mapped_column(
        ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    barrel_id: Mapped[int | None] = mapped_column(
        ForeignKey("barrels.id", ondelete="SET NULL"), nullable=True, index=True
    )

    kind: Mapped[str] = mapped_column(String(16), default=MaintenanceKind.PERIYODIK, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    downtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsible_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # CIP / temizlik ayrintilari
    cip_chemical: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cip_temperature_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    cip_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cip_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    equipment: Mapped[Equipment | None] = relationship(back_populates="logs")


# ----------------------------------------------------------------- UYARI
class AlertSeverity(StrEnum):
    BILGI = "bilgi"
    UYARI = "uyari"
    KRITIK = "kritik"


class AlertStatus(StrEnum):
    ACIK = "acik"
    OKUNDU = "okundu"
    COZULDU = "cozuldu"
    YOKSAYILDI = "yoksayildi"


class Alert(Base, TimestampMixin):
    """Sicaklik, laboratuvar, stok, bakim vb. uyarilari."""

    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_status_sev", "status", "severity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(32), index=True)  # fermantasyon|lab|stok|bakim|ai
    severity: Mapped[str] = mapped_column(String(12), default=AlertSeverity.UYARI, index=True)
    status: Mapped[str] = mapped_column(String(12), default=AlertStatus.ACIK, index=True)

    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text)
    ref_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ref_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # AI tarafindan uretildiyse
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_provider: Mapped[str | None] = mapped_column(String(48), nullable=True)

    acknowledged_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    acknowledged_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ayni uyarinin tekrar uretilmesini engellemek icin
    dedupe_key: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)


# --------------------------------------------------------- DENETIM GUNLUGU
class AuditAction(StrEnum):
    OLUSTUR = "olustur"
    GUNCELLE = "guncelle"
    SIL = "sil"
    GIRIS = "giris"
    CIKIS = "cikis"
    GIRIS_BASARISIZ = "giris_basarisiz"
    ONAY = "onay"
    RED = "red"
    DISA_AKTAR = "disa_aktar"
    AI_ISTEK = "ai_istek"
    AI_ONERI = "ai_oneri"
    TERMINAL_KOMUT = "terminal_komut"
    TERMINAL_ONAY = "terminal_onay"
    TERMINAL_RED = "terminal_red"
    TERMINAL_GERI_AL = "terminal_geri_al"
    AYAR_DEGISIKLIGI = "ayar_degisikligi"
    IZINSIZ_ERISIM = "izinsiz_erisim"


class AuditLog(Base):
    """Degistirilemez denetim kaydi (kim, ne, ne zaman, once/sonra)."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_user_time", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), index=True
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entity_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    summary: Mapped[str] = mapped_column(String(400), default="")
    before_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    changed_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_method: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # AI / terminal baglantisi
    ai_provider: Mapped[str | None] = mapped_column(String(48), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    agent_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(12), default="bilgi")
