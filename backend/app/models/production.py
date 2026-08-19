"""Parti (lot), tank, transfer ve fermantasyon modelleri.

Izlenebilirlik cekirdegi: `LotSource` (uzum -> parti) ve `LotLink` (parti -> parti)
tablolari birlikte yonlu bir cizge olusturur; geriye ve ileriye izleme bu cizge
uzerinde yurutulur (bkz. app.services.traceability).
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:  # dairesel ithalati onlemek icin yalnizca tip denetiminde
    from app.models.vineyard import GrapeVariety, HarvestIntake


class LotStage(StrEnum):
    UZUM_KABUL = "uzum_kabul"
    SIRA = "sira"  # must / şıra
    FERMANTASYON = "fermantasyon"
    MALOLAKTIK = "malolaktik"
    DINLENDIRME = "dinlendirme"
    OLGUNLASTIRMA = "olgunlastirma"
    KUPAJ = "kupaj"
    STABILIZASYON = "stabilizasyon"
    SISELEME = "siseleme"
    TAMAMLANDI = "tamamlandi"


class WineType(StrEnum):
    KIRMIZI = "kirmizi"
    BEYAZ = "beyaz"
    ROSE = "rose"
    KOPUKLU = "kopuklu"
    TATLI = "tatli"


class LotStatus(StrEnum):
    AKTIF = "aktif"
    BEKLEMEDE = "beklemede"
    KARANTINA = "karantina"
    KAPANDI = "kapandi"
    IPTAL = "iptal"


class Lot(Base, TimestampMixin, AuthorMixin):
    """Uretim partisi. Uzumden siseye kadar tasinan izlenebilirlik birimi."""

    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))

    vintage_year: Mapped[int] = mapped_column(Integer, index=True)
    wine_type: Mapped[str] = mapped_column(String(16), default=WineType.KIRMIZI)
    variety_id: Mapped[int | None] = mapped_column(
        ForeignKey("grape_varieties.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_blend: Mapped[bool] = mapped_column(Boolean, default=False)

    stage: Mapped[str] = mapped_column(String(24), default=LotStage.UZUM_KABUL, index=True)
    status: Mapped[str] = mapped_column(String(16), default=LotStatus.AKTIF, index=True)

    volume_l: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    initial_volume_l: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    current_tank_id: Mapped[int | None] = mapped_column(
        ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Guncel ozet analiz degerleri (son laboratuvar/fermantasyon olcumunden)
    current_brix: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    current_ph: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    current_alcohol: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    current_ta: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    current_va: Mapped[float | None] = mapped_column(Numeric(5, 3), nullable=True)
    current_free_so2: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    qr_payload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    opened_at: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    closed_at: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    variety: Mapped[GrapeVariety | None] = relationship()
    current_tank: Mapped[Tank | None] = relationship(
        foreign_keys=[current_tank_id], back_populates="current_lots"
    )
    sources: Mapped[list[LotSource]] = relationship(
        back_populates="lot", cascade="all, delete-orphan"
    )
    events: Mapped[list[LotEvent]] = relationship(
        back_populates="lot", cascade="all, delete-orphan",
        order_by="LotEvent.occurred_at",
    )


class LotSource(Base, TimestampMixin):
    """Uzum kabul partisi -> uretim partisi baglantisi."""

    __tablename__ = "lot_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(
        ForeignKey("lots.id", ondelete="CASCADE"), index=True
    )
    intake_id: Mapped[int] = mapped_column(
        ForeignKey("harvest_intakes.id", ondelete="RESTRICT"), index=True
    )
    weight_kg: Mapped[float] = mapped_column(Numeric(12, 2))
    juice_yield_l: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    lot: Mapped[Lot] = relationship(back_populates="sources")
    intake: Mapped[HarvestIntake] = relationship()


class LotLinkType(StrEnum):
    TRANSFER = "transfer"
    KUPAJ = "kupaj"
    BOLME = "bolme"
    SISELEME = "siseleme"
    RACKING = "aktarma"


class LotLink(Base, TimestampMixin, AuthorMixin):
    """Parti -> parti yonlu baglanti (kupaj, bolme, siseleme)."""

    __tablename__ = "lot_links"
    __table_args__ = (Index("ix_lot_links_pair", "parent_lot_id", "child_lot_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_lot_id: Mapped[int] = mapped_column(
        ForeignKey("lots.id", ondelete="CASCADE"), index=True
    )
    child_lot_id: Mapped[int] = mapped_column(
        ForeignKey("lots.id", ondelete="CASCADE"), index=True
    )
    link_type: Mapped[str] = mapped_column(String(16), default=LotLinkType.KUPAJ)
    volume_l: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    ratio_percent: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent_lot: Mapped[Lot] = relationship(foreign_keys=[parent_lot_id])
    child_lot: Mapped[Lot] = relationship(foreign_keys=[child_lot_id])


class LotEvent(Base, TimestampMixin, AuthorMixin):
    """Parti zaman cizelgesi girdisi (islem gecmisi)."""

    __tablename__ = "lot_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(
        ForeignKey("lots.id", ondelete="CASCADE"), index=True
    )
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ref_table: Mapped[str | None] = mapped_column(String(48), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    lot: Mapped[Lot] = relationship(back_populates="events")


# ------------------------------------------------------------------- TANKLAR
class TankType(StrEnum):
    PASLANMAZ = "paslanmaz_celik"
    BETON = "beton"
    AHSAP = "ahsap"
    AMFORA = "amfora"
    FIBERGLAS = "fiberglas"


class TankStatus(StrEnum):
    BOS = "bos"
    DOLU = "dolu"
    KISMEN_DOLU = "kismen_dolu"
    TEMIZLIKTE = "temizlikte"
    BAKIMDA = "bakimda"
    DEVRE_DISI = "devre_disi"


class CleaningStatus(StrEnum):
    TEMIZ = "temiz"
    KIRLI = "kirli"
    CIP_BEKLIYOR = "cip_bekliyor"
    STERIL = "steril"


class Tank(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "tanks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tank_type: Mapped[str] = mapped_column(String(24), default=TankType.PASLANMAZ)
    capacity_l: Mapped[float] = mapped_column(Numeric(12, 2))
    current_volume_l: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_y: Mapped[int | None] = mapped_column(Integer, nullable=True)

    has_cooling: Mapped[bool] = mapped_column(Boolean, default=True)
    has_sensor: Mapped[bool] = mapped_column(Boolean, default=False)
    temperature_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    target_temperature_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=TankStatus.BOS, index=True)
    cleaning_status: Mapped[str] = mapped_column(String(20), default=CleaningStatus.TEMIZ)
    last_cleaned_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    commissioned_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    current_lots: Mapped[list[Lot]] = relationship(
        back_populates="current_tank", foreign_keys=[Lot.current_tank_id]
    )

    @property
    def fill_percent(self) -> float:
        if not self.capacity_l:
            return 0.0
        return round(float(self.current_volume_l) / float(self.capacity_l) * 100, 1)

    @property
    def free_capacity_l(self) -> float:
        return max(0.0, float(self.capacity_l) - float(self.current_volume_l))


class TransferType(StrEnum):
    DOLUM = "dolum"
    BOSALTIM = "bosaltim"
    TANK_ARASI = "tank_arasi"
    FICIYA = "ficiya"
    FICIDAN = "ficidan"
    AKTARMA = "aktarma"  # racking
    SISELEME = "siseleme"


class TankTransfer(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "tank_transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    transfer_type: Mapped[str] = mapped_column(String(20), default=TransferType.TANK_ARASI)

    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="RESTRICT"), index=True)
    from_tank_id: Mapped[int | None] = mapped_column(
        ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    to_tank_id: Mapped[int | None] = mapped_column(
        ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    from_barrel_id: Mapped[int | None] = mapped_column(
        ForeignKey("barrels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    to_barrel_id: Mapped[int | None] = mapped_column(
        ForeignKey("barrels.id", ondelete="SET NULL"), nullable=True, index=True
    )

    volume_l: Mapped[float] = mapped_column(Numeric(12, 2))
    loss_l: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    performed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lot: Mapped[Lot] = relationship()
    from_tank: Mapped[Tank | None] = relationship(foreign_keys=[from_tank_id])
    to_tank: Mapped[Tank | None] = relationship(foreign_keys=[to_tank_id])


# ------------------------------------------------------------- FERMANTASYON
class FermentationType(StrEnum):
    ALKOL = "alkol"
    MALOLAKTIK = "malolaktik"
    IKINCIL = "ikincil"


class FermentationStatus(StrEnum):
    PLANLANDI = "planlandi"
    DEVAM_EDIYOR = "devam_ediyor"
    DURAKLADI = "durakladi"
    TAMAMLANDI = "tamamlandi"
    IPTAL = "iptal"


class Fermentation(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "fermentations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), index=True)
    tank_id: Mapped[int | None] = mapped_column(
        ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True
    )

    ferm_type: Mapped[str] = mapped_column(String(16), default=FermentationType.ALKOL)
    status: Mapped[str] = mapped_column(
        String(16), default=FermentationStatus.PLANLANDI, index=True
    )

    start_date: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    target_end_date: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    predicted_end_date: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_end_date: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    yeast_strain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    yeast_dose_g_hl: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    initial_brix: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    target_brix: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    initial_ph: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)

    temp_min_c: Mapped[float] = mapped_column(Numeric(5, 2), default=18)
    temp_max_c: Mapped[float] = mapped_column(Numeric(5, 2), default=28)

    volume_l: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lot: Mapped[Lot] = relationship()
    tank: Mapped[Tank | None] = relationship()
    readings: Mapped[list[FermentationReading]] = relationship(
        back_populates="fermentation",
        cascade="all, delete-orphan",
        order_by="FermentationReading.measured_at",
    )
    additives: Mapped[list[FermentationAdditive]] = relationship(
        back_populates="fermentation", cascade="all, delete-orphan"
    )


class ReadingSource(StrEnum):
    MANUEL = "manuel"
    SENSOR = "sensor"
    ICE_AKTARIM = "ice_aktarim"


class FermentationReading(Base, TimestampMixin, AuthorMixin):
    """Gunluk / sensor olcumu."""

    __tablename__ = "fermentation_readings"
    __table_args__ = (
        Index("ix_ferm_readings_ferm_time", "fermentation_id", "measured_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fermentation_id: Mapped[int] = mapped_column(
        ForeignKey("fermentations.id", ondelete="CASCADE"), index=True
    )
    measured_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(16), default=ReadingSource.MANUEL)

    temperature_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    brix: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    density: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    ph: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    total_acidity: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    volatile_acidity: Mapped[float | None] = mapped_column(Numeric(5, 3), nullable=True)
    free_so2: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    alcohol: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    cap_management: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    anomaly_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    fermentation: Mapped[Fermentation] = relationship(back_populates="readings")


class FermentationAdditive(Base, TimestampMixin, AuthorMixin):
    """Fermantasyon sirasinda eklenen maya/enzim/katki."""

    __tablename__ = "fermentation_additives"

    id: Mapped[int] = mapped_column(primary_key=True)
    fermentation_id: Mapped[int] = mapped_column(
        ForeignKey("fermentations.id", ondelete="CASCADE"), index=True
    )
    additive_name: Mapped[str] = mapped_column(String(160))
    additive_type: Mapped[str] = mapped_column(String(48), default="katki")
    amount: Mapped[float] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(16), default="g")
    added_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    inventory_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    fermentation: Mapped[Fermentation] = relationship(back_populates="additives")
