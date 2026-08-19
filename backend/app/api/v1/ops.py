"""Bakım/temizlik, uyarı ve denetim günlüğü uç noktaları."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.crud import build_crud_router, get_or_404
from app.core.audit import record_audit
from app.core.deps import SessionDep, require_perms
from app.core.permissions import Perm
from app.models.cellar import Barrel
from app.models.ops import (
    Alert,
    AlertStatus,
    AuditAction,
    AuditLog,
    Equipment,
    MaintenanceKind,
    MaintenanceLog,
)
from app.models.production import CleaningStatus, Tank
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.ops import (
    AlertCreate,
    AlertOut,
    AlertUpdate,
    AuditOut,
    EquipmentCreate,
    EquipmentOut,
    EquipmentUpdate,
    MaintenanceCreate,
    MaintenanceOut,
    MaintenanceUpdate,
)
from app.services.ai_features import next_maintenance_date
from app.services.alerts import raise_alert
from app.services.codes import next_code

ReadMaint = Annotated[User, Depends(require_perms(Perm.MAINTENANCE_READ))]
WriteMaint = Annotated[User, Depends(require_perms(Perm.MAINTENANCE_WRITE))]
ReadAudit = Annotated[User, Depends(require_perms(Perm.AUDIT_READ))]


async def _enrich_maintenance(session: AsyncSession, rows: Sequence[Any]) -> None:
    for r in rows:
        if r.equipment_id:
            eq = await session.get(Equipment, r.equipment_id)
            r.equipment_name = eq.name if eq else None
        else:
            r.equipment_name = None
        if r.tank_id:
            t = await session.get(Tank, r.tank_id)
            r.tank_code = t.code if t else None
        else:
            r.tank_code = None
        if r.responsible_id:
            u = await session.get(User, r.responsible_id)
            r.responsible_name = u.full_name if u else None
        else:
            r.responsible_name = None


equipment_crud = build_crud_router(
    model=Equipment,
    create_schema=EquipmentCreate,
    update_schema=EquipmentUpdate,
    out_schema=EquipmentOut,
    read_perm=Perm.MAINTENANCE_READ,
    write_perm=Perm.MAINTENANCE_WRITE,
    entity_label="Ekipman",
    tags=["Bakım ve Temizlik"],
    prefix="/equipment",
    search_fields=("code", "name", "manufacturer", "model", "serial_no"),
    filters={"equipment_type": "equipment_type", "status": "status", "is_active": "is_active"},
)

maintenance_crud = build_crud_router(
    model=MaintenanceLog,
    create_schema=MaintenanceCreate,
    update_schema=MaintenanceUpdate,
    out_schema=MaintenanceOut,
    read_perm=Perm.MAINTENANCE_READ,
    write_perm=Perm.MAINTENANCE_WRITE,
    entity_label="Bakım kaydı",
    tags=["Bakım ve Temizlik"],
    prefix="/maintenance",
    search_fields=("code", "title"),
    default_sort="started_at",
    enrich=_enrich_maintenance,
    filters={"kind": "kind", "equipment_id": "equipment_id", "tank_id": "tank_id"},
    soft_delete_field=None,
)

maint_extra = APIRouter(prefix="/maintenance", tags=["Bakım ve Temizlik"])


@maint_extra.post(
    "/log",
    response_model=MaintenanceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Bakım / CIP kaydı gir (ekipman ve tank durumunu günceller)",
)
async def create_maintenance(
    payload: MaintenanceCreate, request: Request, session: SessionDep, user: WriteMaint
) -> MaintenanceOut:
    if not any((payload.equipment_id, payload.tank_id, payload.barrel_id)):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Bakım kaydı için ekipman, tank veya fıçı belirtilmelidir.",
        )

    log = MaintenanceLog(
        code=payload.code or await next_code(session, MaintenanceLog),
        equipment_id=payload.equipment_id,
        tank_id=payload.tank_id,
        barrel_id=payload.barrel_id,
        kind=payload.kind,
        title=payload.title,
        description=payload.description,
        started_at=payload.started_at or dt.datetime.now(dt.UTC),
        finished_at=payload.finished_at,
        downtime_minutes=payload.downtime_minutes,
        responsible_id=payload.responsible_id or user.id,
        cost=payload.cost,
        cip_chemical=payload.cip_chemical,
        cip_temperature_c=payload.cip_temperature_c,
        cip_duration_min=payload.cip_duration_min,
        cip_verified=payload.cip_verified,
        created_by_id=user.id,
    )
    session.add(log)
    await session.flush()

    # Yalnizca TAMAMLANMIS bakim, ekipman/tank durumunu gunceller.
    finished_at = log.finished_at
    temizlik_turu = payload.kind in (MaintenanceKind.CIP, MaintenanceKind.TEMIZLIK)

    if payload.equipment_id and finished_at is not None:
        eq = await session.get(Equipment, payload.equipment_id)
        if eq is not None:
            eq.last_maintenance_at = finished_at.date()
            eq.next_maintenance_at = next_maintenance_date(
                eq.last_maintenance_at, eq.maintenance_interval_days
            )
            if payload.kind != MaintenanceKind.ARIZA:
                eq.status = "calisiyor"

    if payload.tank_id and temizlik_turu and finished_at is not None:
        tank = await session.get(Tank, payload.tank_id)
        if tank is not None:
            tank.cleaning_status = (
                CleaningStatus.STERIL if payload.cip_verified else CleaningStatus.TEMIZ
            )
            tank.last_cleaned_at = finished_at

    if payload.barrel_id and temizlik_turu and finished_at is not None:
        barrel = await session.get(Barrel, payload.barrel_id)
        if barrel is not None:
            barrel.last_cleaned_at = finished_at

    if payload.kind == MaintenanceKind.ARIZA and payload.equipment_id:
        eq = await session.get(Equipment, payload.equipment_id)
        if eq is not None and finished_at is None:
            eq.status = "arizali"
            await raise_alert(
                session,
                category="bakim",
                severity="kritik",
                title=f"Ekipman arızası: {eq.name}",
                message=payload.description or payload.title,
                ref_type="equipment",
                ref_id=eq.id,
                ref_code=eq.code,
                dedupe_key=f"ariza-{eq.id}-{dt.date.today():%Y%m%d}",
            )

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="maintenance_logs",
        entity_id=log.id,
        entity_code=log.code,
        summary=f"{payload.kind}: {payload.title}",
        after=log.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(log)
    await _enrich_maintenance(session, [log])
    return MaintenanceOut.model_validate(log)


@maint_extra.get("/due", summary="Yaklaşan / geciken bakımlar")
async def due_maintenance(
    session: SessionDep, _user: ReadMaint, days: int = Query(30, ge=1, le=365)
) -> list[dict]:
    limit = dt.date.today() + dt.timedelta(days=days)
    rows = (
        (
            await session.execute(
                select(Equipment)
                .where(
                    Equipment.is_active.is_(True),
                    Equipment.next_maintenance_at.is_not(None),
                    Equipment.next_maintenance_at <= limit,
                )
                .order_by(Equipment.next_maintenance_at)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "equipment_id": e.id,
            "code": e.code,
            "name": e.name,
            "equipment_type": e.equipment_type,
            "next_maintenance_at": e.next_maintenance_at.isoformat()
            if e.next_maintenance_at
            else None,
            "days_left": e.maintenance_due_days,
            "overdue": (e.maintenance_due_days or 0) < 0,
            "status": e.status,
        }
        for e in rows
    ]


# ----------------------------------------------------------------- UYARI
alerts_router = APIRouter(prefix="/alerts", tags=["Uyarılar"])


@alerts_router.get("", response_model=Page[AlertOut], summary="Uyarı listesi")
async def list_alerts(
    session: SessionDep,
    user: Annotated[User, Depends(require_perms(Perm.LOT_READ))],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = None,
    category: str | None = None,
) -> Page[AlertOut]:
    stmt = select(Alert)
    if status_filter:
        stmt = stmt.where(Alert.status == status_filter)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if category:
        stmt = stmt.where(Alert.category == category)
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(Alert.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return Page[AlertOut](
        items=[AlertOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@alerts_router.post(
    "", response_model=AlertOut, status_code=status.HTTP_201_CREATED, summary="Uyarı oluştur"
)
async def create_alert(
    payload: AlertCreate,
    request: Request,
    session: SessionDep,
    user: Annotated[User, Depends(require_perms(Perm.LOT_WRITE))],
) -> AlertOut:
    alert = await raise_alert(
        session,
        category=payload.category,
        severity=payload.severity,
        title=payload.title,
        message=payload.message,
        ref_type=payload.ref_type,
        ref_id=payload.ref_id,
        ref_code=payload.ref_code,
        dedupe_key=payload.dedupe_key,
    )
    if alert is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Bu uyarı zaten açık durumda (tekilleştirildi)."
        )
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="alerts",
        summary=f"Uyarı oluşturuldu: {payload.title}",
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(alert)
    return AlertOut.model_validate(alert)


@alerts_router.patch("/{alert_id}", response_model=AlertOut, summary="Uyarı durumunu güncelle")
async def update_alert(
    alert_id: int,
    payload: AlertUpdate,
    request: Request,
    session: SessionDep,
    user: Annotated[User, Depends(require_perms(Perm.LOT_READ))],
) -> AlertOut:
    alert = await get_or_404(session, Alert, alert_id, "Uyarı")
    before = alert.to_dict()
    alert.status = payload.status
    now = dt.datetime.now(dt.UTC)
    if payload.status == AlertStatus.OKUNDU:
        alert.acknowledged_by_id = user.id
        alert.acknowledged_at = now
    elif payload.status in (AlertStatus.COZULDU, AlertStatus.YOKSAYILDI):
        alert.resolved_at = now
        alert.resolution_note = payload.resolution_note
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="alerts",
        entity_id=alert.id,
        summary=f"Uyarı durumu: {payload.status}",
        before=before,
        after=alert.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(alert)
    return AlertOut.model_validate(alert)


@alerts_router.get("/summary", summary="Uyarı özeti")
async def alert_summary(
    session: SessionDep, _user: Annotated[User, Depends(require_perms(Perm.LOT_READ))]
) -> dict:
    rows = (
        await session.execute(
            select(Alert.severity, Alert.category, func.count())
            .where(Alert.status.in_([AlertStatus.ACIK, AlertStatus.OKUNDU]))
            .group_by(Alert.severity, Alert.category)
        )
    ).all()
    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for severity, category, count in rows:
        by_severity[severity] = by_severity.get(severity, 0) + count
        by_category[category] = by_category.get(category, 0) + count
    return {
        "acik_toplam": sum(by_severity.values()),
        "seviyeye_gore": by_severity,
        "kategoriye_gore": by_category,
    }


# ------------------------------------------------------- DENETIM GUNLUGU
audit_router = APIRouter(prefix="/audit", tags=["Denetim Günlüğü"])


@audit_router.get("", response_model=Page[AuditOut], summary="Denetim kayıtları")
async def list_audit(
    session: SessionDep,
    _user: ReadAudit,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    entity_type: str | None = None,
    entity_id: int | None = None,
    action: str | None = None,
    username: str | None = None,
    severity: str | None = None,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> Page[AuditOut]:
    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if username:
        stmt = stmt.where(AuditLog.username.ilike(f"%{username}%"))
    if severity:
        stmt = stmt.where(AuditLog.severity == severity)
    if start:
        stmt = stmt.where(
            AuditLog.created_at >= dt.datetime.combine(start, dt.time.min, dt.UTC)
        )
    if end:
        stmt = stmt.where(
            AuditLog.created_at <= dt.datetime.combine(end, dt.time.max, dt.UTC)
        )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(AuditLog.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return Page[AuditOut](
        items=[AuditOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@audit_router.get("/{audit_id}", response_model=AuditOut, summary="Denetim kaydı detayı")
async def get_audit(audit_id: int, session: SessionDep, _user: ReadAudit) -> AuditOut:
    row = await get_or_404(session, AuditLog, audit_id, "Denetim kaydı")
    return AuditOut.model_validate(row)


@audit_router.get("/entity/{entity_type}/{entity_id}", response_model=list[AuditOut],
                  summary="Bir kaydın tüm denetim geçmişi")
async def entity_audit(
    entity_type: str, entity_id: int, session: SessionDep, _user: ReadAudit
) -> list[AuditOut]:
    rows = (
        (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
                .order_by(AuditLog.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [AuditOut.model_validate(r) for r in rows]


@audit_router.delete("/{audit_id}", response_model=Message, summary="Denetim kaydı silinemez")
async def delete_audit(audit_id: int, _user: ReadAudit) -> Message:
    raise HTTPException(
        status.HTTP_405_METHOD_NOT_ALLOWED,
        "Denetim kayıtları değiştirilemez ve silinemez (değişmezlik ilkesi).",
    )


# SIRA ONEMLI: `maint_extra` sabit yollar icerir (`/maintenance/due`,
# `/maintenance/log`). CRUD router'i `/maintenance/{item_id}` tanimladigi icin
# ondan SONRA kaydedilirse "due" bir tamsayi sanilir ve istek 422 doner.
# Bu kural `tests/test_route_ordering.py` tarafindan zorunlu tutulur.
routers = [equipment_crud, maint_extra, maintenance_crud, alerts_router, audit_router]
