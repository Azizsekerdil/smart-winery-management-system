"""Ana kontrol paneli."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.deps import CurrentUser, SessionDep, require_perms
from app.core.permissions import Perm
from app.models.cellar import Barrel, BarrelStatus, BottlingOrder, BottlingStatus
from app.models.inventory import InventoryItem, ItemCategory
from app.models.ops import Alert, AlertStatus, AuditLog, Equipment
from app.models.production import (
    Fermentation,
    FermentationReading,
    FermentationStatus,
    Lot,
    LotStage,
    LotStatus,
    Tank,
    TankStatus,
)
from app.models.quality import ApprovalStatus, LabResult
from app.models.user import User
from app.models.vineyard import HarvestIntake, Vineyard
from app.schemas.ops import (
    ActivityItem,
    AlertOut,
    DashboardOut,
    KpiCard,
    SeriesPoint,
    TankFillSummary,
    UpcomingTask,
)
from app.services import inventory as inv
from app.services.ai_features import assess_lot_risk, predict_fermentation_end

router = APIRouter(prefix="/dashboard", tags=["Kontrol Paneli"])

STAGE_LABELS = {
    LotStage.UZUM_KABUL: "Üzüm kabul",
    LotStage.SIRA: "Şıra",
    LotStage.FERMANTASYON: "Fermantasyon",
    LotStage.MALOLAKTIK: "Malolaktik",
    LotStage.DINLENDIRME: "Dinlendirme",
    LotStage.OLGUNLASTIRMA: "Olgunlaştırma",
    LotStage.KUPAJ: "Kupaj",
    LotStage.STABILIZASYON: "Stabilizasyon",
    LotStage.SISELEME: "Şişeleme",
    LotStage.TAMAMLANDI: "Tamamlandı",
}


@router.get("", response_model=DashboardOut, summary="Kontrol paneli verileri")
async def dashboard(
    session: SessionDep,
    user: Annotated[User, Depends(require_perms(Perm.LOT_READ))],
    days: int = 30,
) -> DashboardOut:
    now = dt.datetime.now(dt.UTC)
    today = now.date()
    period_start = today - dt.timedelta(days=days)

    # ------------------------------------------------------- fermantasyonlar
    ferms = (
        (
            await session.execute(
                select(Fermentation)
                .where(Fermentation.status == FermentationStatus.DEVAM_EDIYOR)
                .order_by(Fermentation.start_date)
            )
        )
        .scalars()
        .all()
    )
    active_ferms: list[dict] = []
    for f in ferms:
        readings = (
            (
                await session.execute(
                    select(FermentationReading)
                    .where(FermentationReading.fermentation_id == f.id)
                    .order_by(FermentationReading.measured_at)
                )
            )
            .scalars()
            .all()
        )
        last = readings[-1] if readings else None
        predicted, note = predict_fermentation_end(f, list(readings))
        lot = await session.get(Lot, f.lot_id)
        tank = await session.get(Tank, f.tank_id) if f.tank_id else None

        start_brix = float(f.initial_brix) if f.initial_brix is not None else None
        last_brix = float(last.brix) if last and last.brix is not None else None
        target = float(f.target_brix or 0)
        progress = 0.0
        if start_brix is not None and last_brix is not None and start_brix > target:
            progress = round(
                max(0.0, min(100.0, (start_brix - last_brix) / (start_brix - target) * 100)), 1
            )

        temp = float(last.temperature_c) if last and last.temperature_c is not None else None
        temp_alert = temp is not None and (
            temp > float(f.temp_max_c) or temp < float(f.temp_min_c)
        )

        active_ferms.append(
            {
                "id": f.id,
                "code": f.code,
                "lot_id": f.lot_id,
                "lot_code": lot.code if lot else None,
                "lot_name": lot.name if lot else None,
                "tank_code": tank.code if tank else None,
                "ferm_type": f.ferm_type,
                "start_date": f.start_date,
                "day_no": (now - (f.start_date if f.start_date.tzinfo else f.start_date.replace(tzinfo=dt.UTC))).days + 1,
                "brix": last_brix,
                "target_brix": target,
                "temperature_c": temp,
                "temp_min_c": float(f.temp_min_c),
                "temp_max_c": float(f.temp_max_c),
                "temp_alert": temp_alert,
                "progress_percent": progress,
                "predicted_end_date": predicted,
                "prediction_note": note,
                "reading_count": len(readings),
                "last_reading_at": last.measured_at if last else None,
                "volume_l": float(f.volume_l or 0),
            }
        )

    # ---------------------------------------------------------------- uyarilar
    critical = (
        (
            await session.execute(
                select(Alert)
                .where(
                    Alert.status.in_([AlertStatus.ACIK, AlertStatus.OKUNDU]),
                    Alert.severity.in_(["kritik", "uyari"]),
                )
                .order_by(Alert.severity.desc(), Alert.created_at.desc())
                .limit(15)
            )
        )
        .scalars()
        .all()
    )

    # ------------------------------------------------------------------ tanklar
    tanks = (
        (
            await session.execute(
                select(Tank).where(Tank.is_active.is_(True)).order_by(Tank.code)
            )
        )
        .scalars()
        .all()
    )
    tank_fills: list[TankFillSummary] = []
    for t in tanks:
        lot = (
            await session.execute(
                select(Lot)
                .where(
                    Lot.current_tank_id == t.id,
                    Lot.status.notin_([LotStatus.KAPANDI, LotStatus.IPTAL]),
                )
                .order_by(Lot.volume_l.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        tank_temp = float(t.temperature_c) if t.temperature_c is not None else None
        tank_target = (
            float(t.target_temperature_c) if t.target_temperature_c is not None else None
        )
        tank_fills.append(
            TankFillSummary(
                id=t.id,
                code=t.code,
                tank_type=t.tank_type,
                capacity_l=float(t.capacity_l),
                current_volume_l=float(t.current_volume_l),
                fill_percent=t.fill_percent,
                status=t.status,
                temperature_c=tank_temp,
                target_temperature_c=tank_target,
                lot_code=lot.code if lot else None,
                lot_name=lot.name if lot else None,
                zone=t.zone or t.location,
                position_x=t.position_x,
                position_y=t.position_y,
                temp_alert=bool(
                    tank_temp is not None
                    and tank_target is not None
                    and abs(tank_temp - tank_target) > 3
                ),
            )
        )

    # ------------------------------------------------------------ yaklasanlar
    upcoming: list[UpcomingTask] = []
    for f in ferms:
        if f.predicted_end_date:
            end = f.predicted_end_date
            end_date = (end if end.tzinfo else end.replace(tzinfo=dt.UTC)).date()
            upcoming.append(
                UpcomingTask(
                    kind="fermantasyon_bitis",
                    title=f"{f.code} fermantasyonunun tahmini bitişi",
                    due_date=end_date,
                    days_left=(end_date - today).days,
                    ref_type="fermentations",
                    ref_id=f.id,
                    ref_code=f.code,
                    severity="bilgi",
                )
            )

    equipment_due = (
        (
            await session.execute(
                select(Equipment)
                .where(
                    Equipment.is_active.is_(True),
                    Equipment.next_maintenance_at.is_not(None),
                    Equipment.next_maintenance_at <= today + dt.timedelta(days=30),
                )
                .order_by(Equipment.next_maintenance_at)
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    for e in equipment_due:
        left = e.maintenance_due_days
        upcoming.append(
            UpcomingTask(
                kind="bakim",
                title=f"{e.name} bakımı",
                due_date=e.next_maintenance_at,
                days_left=left,
                ref_type="equipment",
                ref_id=e.id,
                ref_code=e.code,
                severity="uyari" if (left is not None and left < 0) else "bilgi",
            )
        )

    barrels_due = (
        (
            await session.execute(
                select(Barrel)
                .where(
                    Barrel.status == BarrelStatus.DOLU,
                    Barrel.planned_empty_at.is_not(None),
                    Barrel.planned_empty_at <= today + dt.timedelta(days=30),
                )
                .order_by(Barrel.planned_empty_at)
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    for b in barrels_due:
        upcoming.append(
            UpcomingTask(
                kind="fici_bosaltim",
                title=f"{b.code} fıçısının planlanan boşaltımı",
                due_date=b.planned_empty_at,
                days_left=(b.planned_empty_at - today).days if b.planned_empty_at else None,
                ref_type="barrels",
                ref_id=b.id,
                ref_code=b.code,
                severity="bilgi",
            )
        )

    pending_lab = (
        await session.execute(
            select(func.count())
            .select_from(LabResult)
            .where(LabResult.approval_status == ApprovalStatus.BEKLIYOR)
        )
    ).scalar_one()
    if pending_lab:
        upcoming.append(
            UpcomingTask(
                kind="lab_onay",
                title=f"{pending_lab} laboratuvar sonucu onay bekliyor",
                due_date=today,
                days_left=0,
                ref_type="lab_results",
                severity="uyari",
            )
        )

    upcoming.sort(key=lambda x: (x.days_left if x.days_left is not None else 999))

    # ---------------------------------------------------------- gunluk uretim
    intake_rows = (
        await session.execute(
            select(HarvestIntake.harvest_date, func.sum(HarvestIntake.net_weight_kg))
            .where(HarvestIntake.harvest_date >= period_start)
            .group_by(HarvestIntake.harvest_date)
            .order_by(HarvestIntake.harvest_date)
        )
    ).all()
    daily_production = [
        SeriesPoint(label=d.isoformat(), value=round(float(v or 0), 1)) for d, v in intake_rows
    ]

    # -------------------------------------------------------------- stok ozeti
    stock_summary: list[SeriesPoint] = []
    for category in ItemCategory:
        items = (
            (
                await session.execute(
                    select(InventoryItem).where(
                        InventoryItem.category == category, InventoryItem.is_active.is_(True)
                    )
                )
            )
            .scalars()
            .all()
        )
        total = 0.0
        for item in items:
            total += await inv.stock_value(session, item.id)
        if total > 0:
            stock_summary.append(SeriesPoint(label=str(category), value=round(total, 2)))

    low_stock = (await inv.low_stock_items(session))[:10]

    # -------------------------------------------------------------- faaliyetler
    activity_rows = (
        (
            await session.execute(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(20)
            )
        )
        .scalars()
        .all()
    )
    recent_activity = [
        ActivityItem(
            at=a.created_at,
            username=a.username,
            action=a.action,
            entity_type=a.entity_type,
            entity_code=a.entity_code,
            summary=a.summary,
        )
        for a in activity_rows
    ]

    # --------------------------------------------------------- parti dagilimi
    stage_rows = (
        await session.execute(
            select(Lot.stage, func.count())
            .where(Lot.status == LotStatus.AKTIF)
            .group_by(Lot.stage)
        )
    ).all()
    # HAM asama kodu gonderilir; ceviri istemcide yapilir. Sunucu Turkce etiket
    # gonderseydi Ingilizce arayuz bu etiketi geri ceviremezdi.
    lot_stage_distribution = [SeriesPoint(label=s, value=float(c)) for s, c in stage_rows]

    # ---------------------------------------------------------------- KPI'lar
    total_volume = (
        await session.execute(
            select(func.coalesce(func.sum(Lot.volume_l), 0)).where(Lot.status == LotStatus.AKTIF)
        )
    ).scalar_one()
    active_lots = (
        await session.execute(
            select(func.count()).select_from(Lot).where(Lot.status == LotStatus.AKTIF)
        )
    ).scalar_one()
    intake_total = (
        await session.execute(
            select(func.coalesce(func.sum(HarvestIntake.net_weight_kg), 0)).where(
                HarvestIntake.harvest_date >= period_start
            )
        )
    ).scalar_one()
    bottles = (
        await session.execute(
            select(func.coalesce(func.sum(BottlingOrder.produced_bottles), 0)).where(
                BottlingOrder.status == BottlingStatus.TAMAMLANDI
            )
        )
    ).scalar_one()
    open_alerts = (
        await session.execute(
            select(func.count()).select_from(Alert).where(Alert.status == AlertStatus.ACIK)
        )
    ).scalar_one()
    critical_alerts_count = (
        await session.execute(
            select(func.count())
            .select_from(Alert)
            .where(Alert.status == AlertStatus.ACIK, Alert.severity == "kritik")
        )
    ).scalar_one()
    tank_capacity = sum(float(t.capacity_l) for t in tanks) or 1.0
    tank_used = sum(float(t.current_volume_l) for t in tanks)
    empty_tanks = sum(1 for t in tanks if t.status == TankStatus.BOS)

    kpis = [
        KpiCard(key="aktif_parti", label="Aktif parti", value=active_lots, unit="adet", icon="grape"),
        KpiCard(
            key="toplam_hacim",
            label="Toplam şarap hacmi",
            value=round(float(total_volume or 0), 1),
            unit="L",
            icon="droplet",
        ),
        KpiCard(
            key="fermantasyon", label="Devam eden fermantasyon", value=len(ferms), unit="adet",
            severity="uyari" if any(f["temp_alert"] for f in active_ferms) else "bilgi",
            icon="activity",
        ),
        KpiCard(
            key="tank_doluluk",
            label="Tank doluluk oranı",
            value=round(tank_used / tank_capacity * 100, 1),
            unit="%",
            trend_label=f"{empty_tanks} boş tank",
            icon="cylinder",
        ),
        KpiCard(
            key="uzum_kabul",
            label=f"Son {days} gün üzüm kabulü",
            value=round(float(intake_total or 0), 0),
            unit="kg",
            icon="truck",
        ),
        KpiCard(key="sise", label="Toplam şişelenen", value=int(bottles or 0), unit="şişe", icon="wine"),
        KpiCard(
            key="uyari",
            label="Açık uyarı",
            value=open_alerts,
            unit="adet",
            severity="kritik" if critical_alerts_count else ("uyari" if open_alerts else "bilgi"),
            trend_label=f"{critical_alerts_count} kritik",
            icon="alert",
        ),
        KpiCard(
            key="lab_onay",
            label="Onay bekleyen analiz",
            value=pending_lab,
            unit="adet",
            severity="uyari" if pending_lab else "bilgi",
            icon="flask",
        ),
    ]

    # ------------------------------------------- yapay zeka onerileri (yerel)
    suggestions: list[dict] = []
    risky_lots = (
        (
            await session.execute(
                select(Lot).where(Lot.status == LotStatus.AKTIF).limit(60)
            )
        )
        .scalars()
        .all()
    )
    for lot in risky_lots:
        last_lab = (
            await session.execute(
                select(LabResult.analyzed_at)
                .where(LabResult.lot_id == lot.id)
                .order_by(LabResult.analyzed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        days_since = None
        if last_lab is not None:
            last_dt = last_lab if last_lab.tzinfo else last_lab.replace(tzinfo=dt.UTC)
            days_since = (now - last_dt).days
        anomalies = (
            await session.execute(
                select(func.count())
                .select_from(FermentationReading)
                .join(Fermentation, Fermentation.id == FermentationReading.fermentation_id)
                .where(
                    Fermentation.lot_id == lot.id, FermentationReading.is_anomaly.is_(True)
                )
            )
        ).scalar_one()

        level, reasons = assess_lot_risk(
            volatile_acidity=float(lot.current_va) if lot.current_va is not None else None,
            free_so2=float(lot.current_free_so2) if lot.current_free_so2 is not None else None,
            ph=float(lot.current_ph) if lot.current_ph is not None else None,
            days_since_last_lab=days_since,
            stage=lot.stage,
            anomaly_count=anomalies,
        )
        if level in ("orta", "yuksek"):
            suggestions.append(
                {
                    "tur": "riskli_parti",
                    "baslik": f"{lot.code} — {level} risk",
                    "aciklama": " ".join(reasons),
                    "risk": level,
                    "lot_id": lot.id,
                    "lot_code": lot.code,
                    "kaynak": "yerel_analiz",
                    "karar_destek": True,
                }
            )
    suggestions.sort(key=lambda s: 0 if s["risk"] == "yuksek" else 1)
    suggestions = suggestions[:8]

    return DashboardOut(
        generated_at=now,
        kpis=kpis,
        active_fermentations=active_ferms,
        critical_alerts=[AlertOut.model_validate(a) for a in critical],
        tank_fills=tank_fills,
        upcoming_tasks=upcoming[:15],
        daily_production=daily_production,
        stock_summary=stock_summary,
        low_stock_items=low_stock,
        recent_activity=recent_activity,
        ai_suggestions=suggestions,
        lot_stage_distribution=lot_stage_distribution,
    )


@router.get("/health-summary", summary="Sistem sağlık özeti")
async def health_summary(session: SessionDep, _user: CurrentUser) -> dict:
    counts: dict[str, int] = {}
    for label, model in (
        ("bag", Vineyard),
        ("parti", Lot),
        ("tank", Tank),
        ("fici", Barrel),
        ("kullanici", User),
    ):
        counts[label] = (
            await session.execute(select(func.count()).select_from(model))
        ).scalar_one()
    return {"kayit_sayilari": counts, "zaman": dt.datetime.now(dt.UTC)}
