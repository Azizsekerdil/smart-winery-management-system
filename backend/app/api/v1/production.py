"""Parti, tank, transfer ve fermantasyon uç noktaları."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.crud import build_crud_router, get_or_404, label_map
from app.core.audit import record_audit
from app.core.deps import SessionDep, require_perms
from app.core.permissions import Perm
from app.models.ops import AuditAction
from app.models.production import (
    CleaningStatus,
    Fermentation,
    FermentationAdditive,
    FermentationReading,
    FermentationStatus,
    Lot,
    LotEvent,
    LotLink,
    LotLinkType,
    LotSource,
    LotStage,
    LotStatus,
    Tank,
    TankStatus,
    TankTransfer,
    TransferType,
)
from app.models.user import User
from app.models.vineyard import GrapeVariety, HarvestIntake
from app.schemas.common import Message
from app.schemas.production import (
    FermentationAdditiveCreate,
    FermentationAdditiveOut,
    FermentationCreate,
    FermentationCurve,
    FermentationOut,
    FermentationReadingCreate,
    FermentationReadingOut,
    FermentationUpdate,
    LotCreate,
    LotEventOut,
    LotOut,
    LotUpdate,
    TankCreate,
    TankOut,
    TankTransferCreate,
    TankTransferOut,
    TankUpdate,
    TraceGraph,
)
from app.schemas.quality import LotSplitRequest
from app.services.ai_features import (
    detect_reading_anomaly,
    predict_fermentation_end,
)
from app.services.alerts import raise_alert
from app.services.codes import next_code, qr_payload
from app.services.qr import qr_png
from app.services.traceability import build_trace

ReadLot = Annotated[User, Depends(require_perms(Perm.LOT_READ))]
WriteLot = Annotated[User, Depends(require_perms(Perm.LOT_WRITE))]
ReadTank = Annotated[User, Depends(require_perms(Perm.TANK_READ))]
WriteTank = Annotated[User, Depends(require_perms(Perm.TANK_WRITE))]
TransferPerm = Annotated[User, Depends(require_perms(Perm.TANK_TRANSFER))]
ReadFerm = Annotated[User, Depends(require_perms(Perm.FERMENTATION_READ))]
WriteFerm = Annotated[User, Depends(require_perms(Perm.FERMENTATION_WRITE))]


# ------------------------------------------------------------ yardimcilar
async def add_lot_event(
    session: AsyncSession,
    lot_id: int,
    *,
    event_type: str,
    title: str,
    description: str | None = None,
    ref_table: str | None = None,
    ref_id: int | None = None,
    occurred_at: dt.datetime | None = None,
    user_id: int | None = None,
) -> LotEvent:
    ev = LotEvent(
        lot_id=lot_id,
        occurred_at=occurred_at or dt.datetime.now(dt.UTC),
        event_type=event_type,
        title=title[:200],
        description=description,
        ref_table=ref_table,
        ref_id=ref_id,
        created_by_id=user_id,
    )
    session.add(ev)
    return ev


async def _recalc_tank(session: AsyncSession, tank: Tank) -> None:
    """Tank doluluk ve durumunu icindeki partilerden yeniden hesaplar."""
    total = (
        await session.execute(
            select(func.coalesce(func.sum(Lot.volume_l), 0)).where(
                Lot.current_tank_id == tank.id,
                Lot.status.notin_([LotStatus.KAPANDI, LotStatus.IPTAL]),
            )
        )
    ).scalar_one()
    tank.current_volume_l = float(total or 0)
    if tank.status not in (TankStatus.BAKIMDA, TankStatus.TEMIZLIKTE, TankStatus.DEVRE_DISI):
        if tank.current_volume_l <= 0.001:
            tank.status = TankStatus.BOS
        elif tank.current_volume_l >= float(tank.capacity_l) * 0.98:
            tank.status = TankStatus.DOLU
        else:
            tank.status = TankStatus.KISMEN_DOLU
    if tank.current_volume_l > 0:
        tank.cleaning_status = CleaningStatus.KIRLI


async def _enrich_lots(session: AsyncSession, rows: Sequence[Any]) -> None:
    varmap = await label_map(session, GrapeVariety, (r.variety_id for r in rows))
    tankmap = await label_map(session, Tank, (r.current_tank_id for r in rows), field="code")
    for r in rows:
        r.variety_name = varmap.get(r.variety_id) if r.variety_id else None
        r.tank_code = tankmap.get(r.current_tank_id) if r.current_tank_id else None


async def _enrich_tanks(session: AsyncSession, rows: Sequence[Any]) -> None:
    ids = [r.id for r in rows]
    lotmap: dict[int, tuple[int, str]] = {}  # tank_id -> (lot_id, lot_code)
    if ids:
        lot_rows = (
            (
                await session.execute(
                    select(Lot.current_tank_id, Lot.id, Lot.code)
                    .where(
                        Lot.current_tank_id.in_(ids),
                        Lot.status.notin_([LotStatus.KAPANDI, LotStatus.IPTAL]),
                    )
                    .order_by(Lot.volume_l.desc())
                )
            )
            .all()
        )
        for tank_id, lot_id, lot_code in lot_rows:
            lotmap.setdefault(tank_id, (lot_id, lot_code))
    for r in rows:
        pair = lotmap.get(r.id)
        r.current_lot_id = pair[0] if pair else None
        r.current_lot_code = pair[1] if pair else None


async def _enrich_ferms(session: AsyncSession, rows: Sequence[Any]) -> None:
    lotmap = await label_map(session, Lot, (r.lot_id for r in rows), field="code")
    tankmap = await label_map(session, Tank, (r.tank_id for r in rows), field="code")
    for r in rows:
        r.lot_code = lotmap.get(r.lot_id)
        r.tank_code = tankmap.get(r.tank_id) if r.tank_id else None

        last = (
            await session.execute(
                select(FermentationReading)
                .where(FermentationReading.fermentation_id == r.id)
                .order_by(FermentationReading.measured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        count = (
            await session.execute(
                select(func.count())
                .select_from(FermentationReading)
                .where(FermentationReading.fermentation_id == r.id)
            )
        ).scalar_one()
        r.reading_count = count
        r.last_brix = float(last.brix) if last and last.brix is not None else None
        r.last_temperature_c = (
            float(last.temperature_c) if last and last.temperature_c is not None else None
        )
        r.last_reading_at = last.measured_at if last else None

        start_brix = float(r.initial_brix) if r.initial_brix is not None else None
        target = float(r.target_brix or 0)
        if start_brix is not None and r.last_brix is not None and start_brix > target:
            pct = (start_brix - r.last_brix) / (start_brix - target) * 100
            r.progress_percent = round(max(0.0, min(100.0, pct)), 1)
        else:
            r.progress_percent = 100.0 if r.status == FermentationStatus.TAMAMLANDI else 0.0

        r.active_alerts = (
            await session.execute(
                select(func.count())
                .select_from(FermentationReading)
                .where(
                    FermentationReading.fermentation_id == r.id,
                    FermentationReading.is_anomaly.is_(True),
                )
            )
        ).scalar_one()


# ------------------------------------------------------------------ TANK
tanks_router = build_crud_router(
    model=Tank,
    create_schema=TankCreate,
    update_schema=TankUpdate,
    out_schema=TankOut,
    read_perm=Perm.TANK_READ,
    write_perm=Perm.TANK_WRITE,
    entity_label="Tank",
    tags=["Tanklar"],
    prefix="/tanks",
    search_fields=("code", "name", "location", "zone"),
    enrich=_enrich_tanks,
    filters={
        "status": "status",
        "tank_type": "tank_type",
        "zone": "zone",
        "is_active": "is_active",
    },
)

tanks_extra = APIRouter(prefix="/tanks", tags=["Tanklar"])


@tanks_extra.get("/{tank_id}/history", response_model=list[TankTransferOut], summary="Tank geçmişi")
async def tank_history(
    tank_id: int, session: SessionDep, _user: ReadTank, limit: int = Query(100, le=500)
) -> list[TankTransferOut]:
    await get_or_404(session, Tank, tank_id, "Tank")
    rows = (
        (
            await session.execute(
                select(TankTransfer)
                .where(
                    (TankTransfer.from_tank_id == tank_id)
                    | (TankTransfer.to_tank_id == tank_id)
                )
                .order_by(TankTransfer.occurred_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [await _transfer_out(session, r) for r in rows]


@tanks_extra.post("/{tank_id}/clean", response_model=TankOut, summary="Tank temizliğini kaydet")
async def clean_tank(
    tank_id: int, request: Request, session: SessionDep, user: WriteTank
) -> TankOut:
    tank = await get_or_404(session, Tank, tank_id, "Tank")
    if float(tank.current_volume_l or 0) > 0.001:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Tank dolu ({tank.current_volume_l} L). Temizlik için önce boşaltılmalıdır.",
        )
    before = tank.to_dict()
    tank.cleaning_status = CleaningStatus.TEMIZ
    tank.last_cleaned_at = dt.datetime.now(dt.UTC)
    tank.status = TankStatus.BOS
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="tanks",
        entity_id=tank.id,
        entity_code=tank.code,
        summary="Tank temizliği kaydedildi",
        before=before,
        after=tank.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(tank)
    await _enrich_tanks(session, [tank])
    return TankOut.model_validate(tank)


@tanks_extra.get("/layout/map", summary="Görsel tank yerleşimi")
async def tank_layout(session: SessionDep, _user: ReadTank) -> dict:
    rows = (
        (await session.execute(select(Tank).where(Tank.is_active.is_(True)).order_by(Tank.code)))
        .scalars()
        .all()
    )
    await _enrich_tanks(session, rows)
    zones: dict[str, list[dict]] = {}
    for t in rows:
        zone = t.zone or t.location or "Genel"
        zones.setdefault(zone, []).append(
            {
                "id": t.id,
                "code": t.code,
                "tank_type": t.tank_type,
                "capacity_l": float(t.capacity_l),
                "current_volume_l": float(t.current_volume_l),
                "fill_percent": t.fill_percent,
                "status": t.status,
                "cleaning_status": t.cleaning_status,
                "temperature_c": float(t.temperature_c) if t.temperature_c is not None else None,
                "target_temperature_c": (
                    float(t.target_temperature_c) if t.target_temperature_c is not None else None
                ),
                "lot_code": getattr(t, "current_lot_code", None),
                "position_x": t.position_x,
                "position_y": t.position_y,
            }
        )
    return {
        "zones": [{"name": k, "tanks": v} for k, v in sorted(zones.items())],
        "total_capacity_l": sum(float(t.capacity_l) for t in rows),
        "total_volume_l": sum(float(t.current_volume_l) for t in rows),
    }


# -------------------------------------------------------------- TRANSFER
transfers_router = APIRouter(prefix="/transfers", tags=["Tanklar"])


async def _transfer_out(session: AsyncSession, tr: TankTransfer) -> TankTransferOut:
    out = TankTransferOut.model_validate(tr)
    lot = await session.get(Lot, tr.lot_id)
    out.lot_code = lot.code if lot else None
    if tr.from_tank_id:
        t = await session.get(Tank, tr.from_tank_id)
        out.from_code = t.code if t else None
    if tr.to_tank_id:
        t = await session.get(Tank, tr.to_tank_id)
        out.to_code = t.code if t else None
    return out


@transfers_router.get("", response_model=list[TankTransferOut], summary="Transfer listesi")
async def list_transfers(
    session: SessionDep,
    _user: ReadTank,
    lot_id: int | None = None,
    limit: int = Query(100, le=500),
) -> list[TankTransferOut]:
    stmt = select(TankTransfer).order_by(TankTransfer.occurred_at.desc()).limit(limit)
    if lot_id:
        stmt = stmt.where(TankTransfer.lot_id == lot_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [await _transfer_out(session, r) for r in rows]


@transfers_router.post(
    "",
    response_model=TankTransferOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tank/fıçı transferi yap",
)
async def create_transfer(
    payload: TankTransferCreate,
    request: Request,
    session: SessionDep,
    user: TransferPerm,
) -> TankTransferOut:
    lot = await get_or_404(session, Lot, payload.lot_id, "Parti")
    from_tank = (
        await get_or_404(session, Tank, payload.from_tank_id, "Kaynak tank")
        if payload.from_tank_id
        else None
    )
    to_tank = (
        await get_or_404(session, Tank, payload.to_tank_id, "Hedef tank")
        if payload.to_tank_id
        else None
    )

    volume = float(payload.volume_l)
    loss = float(payload.loss_l)

    # --- is kurallari -----------------------------------------------------
    if from_tank is not None and float(from_tank.current_volume_l) + 1e-6 < volume:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{from_tank.code} tankında yeterli hacim yok "
            f"(mevcut {from_tank.current_volume_l} L, istenen {volume} L).",
        )
    if to_tank is not None:
        if to_tank.status == TankStatus.DEVRE_DISI:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"{to_tank.code} tankı devre dışı."
            )
        if to_tank.cleaning_status == CleaningStatus.KIRLI and float(to_tank.current_volume_l) <= 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{to_tank.code} tankı temizlenmemiş. Önce temizlik kaydı girin.",
            )
        arriving = volume - loss
        if to_tank.free_capacity_l + 1e-6 < arriving:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{to_tank.code} tankında yeterli boş kapasite yok "
                f"(boş {to_tank.free_capacity_l:.1f} L, gelen {arriving:.1f} L).",
            )

    if from_tank is None and to_tank is not None and float(lot.volume_l or 0) <= 0:
        # ilk dolum: parti hacmi transferle olusur
        lot.initial_volume_l = float(lot.initial_volume_l or 0) or volume

    occurred = payload.occurred_at or dt.datetime.now(dt.UTC)
    code = await next_code(session, TankTransfer)

    tr = TankTransfer(
        code=code,
        transfer_type=payload.transfer_type,
        lot_id=lot.id,
        from_tank_id=payload.from_tank_id,
        to_tank_id=payload.to_tank_id,
        from_barrel_id=payload.from_barrel_id,
        to_barrel_id=payload.to_barrel_id,
        volume_l=volume,
        loss_l=loss,
        occurred_at=occurred,
        performed_by_id=user.id,
        notes=payload.notes,
        created_by_id=user.id,
    )
    session.add(tr)

    # --- hacim guncellemeleri --------------------------------------------
    if from_tank is not None and to_tank is not None:
        lot.current_tank_id = to_tank.id
        lot.volume_l = max(0.0, float(lot.volume_l or 0) - loss)
    elif to_tank is not None:  # dolum
        lot.current_tank_id = to_tank.id
        lot.volume_l = float(lot.volume_l or 0) + volume - loss
        if not lot.initial_volume_l:
            lot.initial_volume_l = lot.volume_l
    elif from_tank is not None:  # bosaltim (siseleme/fici)
        lot.volume_l = max(0.0, float(lot.volume_l or 0) - volume)
        if payload.to_barrel_id is None and payload.transfer_type != TransferType.SISELEME:
            lot.current_tank_id = None

    await session.flush()
    for t in (from_tank, to_tank):
        if t is not None:
            await _recalc_tank(session, t)

    await add_lot_event(
        session,
        lot.id,
        event_type="transfer",
        title=f"Transfer {code}: {volume:.0f} L",
        description=(
            f"{from_tank.code if from_tank else '—'} → {to_tank.code if to_tank else '—'}"
            + (f" (fire {loss:.1f} L)" if loss else "")
        ),
        ref_table="tank_transfers",
        ref_id=tr.id,
        occurred_at=occurred,
        user_id=user.id,
    )
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="tank_transfers",
        entity_id=tr.id,
        entity_code=code,
        summary=f"Transfer: {volume:.0f} L, parti {lot.code}",
        after=tr.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(tr)
    return await _transfer_out(session, tr)


# ------------------------------------------------------------------ PARTI
lots_crud = build_crud_router(
    model=Lot,
    create_schema=LotCreate,
    update_schema=LotUpdate,
    out_schema=LotOut,
    read_perm=Perm.LOT_READ,
    write_perm=Perm.LOT_WRITE,
    entity_label="Parti",
    tags=["Partiler"],
    prefix="/lots",
    search_fields=("code", "name"),
    enrich=_enrich_lots,
    filters={
        "stage": "stage",
        "status": "status",
        "wine_type": "wine_type",
        "vintage_year": "vintage_year",
        "variety_id": "variety_id",
        "current_tank_id": "current_tank_id",
    },
    soft_delete_field=None,
)

lots_extra = APIRouter(prefix="/lots", tags=["Partiler"])


@lots_extra.post(
    "/with-sources",
    response_model=LotOut,
    status_code=status.HTTP_201_CREATED,
    summary="Üzüm kabullerinden parti oluştur",
)
async def create_lot_with_sources(
    payload: LotCreate, request: Request, session: SessionDep, user: WriteLot
) -> LotOut:
    if not payload.sources:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "En az bir üzüm kabul kaydı seçilmelidir."
        )

    intakes: list[HarvestIntake] = []
    for src in payload.sources:
        intake = await get_or_404(session, HarvestIntake, src.intake_id, "Üzüm kabul kaydı")
        intakes.append(intake)

    vintage = payload.vintage_year or max(i.vintage_year for i in intakes)
    variety_ids = {i.variety_id for i in intakes}
    code = payload.code or await next_code(session, Lot)

    lot = Lot(
        code=code,
        name=payload.name,
        vintage_year=vintage,
        wine_type=payload.wine_type,
        variety_id=payload.variety_id or (variety_ids.pop() if len(variety_ids) == 1 else None),
        is_blend=len(variety_ids) > 1,
        stage=payload.stage,
        volume_l=payload.volume_l,
        initial_volume_l=payload.volume_l,
        current_tank_id=payload.current_tank_id,
        notes=payload.notes,
        opened_at=dt.date.today(),
        created_by_id=user.id,
    )
    lot.qr_payload = qr_payload("parti", code)
    session.add(lot)
    await session.flush()

    total_kg = 0.0
    for src in payload.sources:
        session.add(
            LotSource(
                lot_id=lot.id,
                intake_id=src.intake_id,
                weight_kg=src.weight_kg,
                juice_yield_l=src.juice_yield_l,
            )
        )
        total_kg += float(src.weight_kg)

    await add_lot_event(
        session,
        lot.id,
        event_type="olusturma",
        title=f"Parti oluşturuldu ({len(payload.sources)} üzüm kabulü, {total_kg:.0f} kg)",
        description=", ".join(i.code for i in intakes),
        user_id=user.id,
    )
    if payload.current_tank_id:
        tank = await session.get(Tank, payload.current_tank_id)
        if tank is not None:
            await _recalc_tank(session, tank)

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="lots",
        entity_id=lot.id,
        entity_code=lot.code,
        summary=f"Parti oluşturuldu: {lot.name} ({total_kg:.0f} kg üzüm)",
        after=lot.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(lot)
    await _enrich_lots(session, [lot])
    return LotOut.model_validate(lot)


@lots_extra.get(
    "/{lot_id}/trace",
    response_model=TraceGraph,
    summary="İzlenebilirlik çizgesi (geri / ileri / tam)",
)
async def lot_trace(
    lot_id: int,
    session: SessionDep,
    _user: ReadLot,
    direction: str = Query("tam", pattern="^(geri|ileri|tam)$"),
) -> TraceGraph:
    try:
        return await build_trace(session, lot_id, direction=direction)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@lots_extra.get("/{lot_id}/timeline", response_model=list[LotEventOut], summary="Parti zaman çizelgesi")
async def lot_events(lot_id: int, session: SessionDep, _user: ReadLot) -> list[LotEventOut]:
    await get_or_404(session, Lot, lot_id, "Parti")
    rows = (
        (
            await session.execute(
                select(LotEvent).where(LotEvent.lot_id == lot_id).order_by(LotEvent.occurred_at)
            )
        )
        .scalars()
        .all()
    )
    return [LotEventOut.model_validate(r) for r in rows]


@lots_extra.get("/{lot_id}/qr.png", summary="Parti QR kodu (PNG)", response_class=Response)
async def lot_qr(lot_id: int, session: SessionDep, _user: ReadLot) -> Response:
    lot = await get_or_404(session, Lot, lot_id, "Parti")
    return Response(
        content=qr_png(lot.qr_payload or qr_payload("parti", lot.code)),
        media_type="image/png",
    )


@lots_extra.post("/{lot_id}/split", response_model=LotOut, summary="Partiyi böl")
async def split_lot(
    lot_id: int,
    payload: LotSplitRequest,
    request: Request,
    session: SessionDep,
    user: WriteLot,
) -> LotOut:
    parent = await get_or_404(session, Lot, lot_id, "Parti")
    volume = float(payload.volume_l)
    if volume >= float(parent.volume_l):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Bölünecek hacim parti hacminden küçük olmalıdır "
            f"(parti {parent.volume_l} L).",
        )

    code = payload.new_lot_code or await next_code(session, Lot)
    child = Lot(
        code=code,
        name=payload.new_lot_name,
        vintage_year=parent.vintage_year,
        wine_type=parent.wine_type,
        variety_id=parent.variety_id,
        is_blend=parent.is_blend,
        stage=parent.stage,
        volume_l=volume,
        initial_volume_l=volume,
        current_tank_id=payload.target_tank_id or parent.current_tank_id,
        current_brix=parent.current_brix,
        current_ph=parent.current_ph,
        current_alcohol=parent.current_alcohol,
        notes=payload.notes,
        opened_at=dt.date.today(),
        created_by_id=user.id,
    )
    child.qr_payload = qr_payload("parti", code)
    session.add(child)
    await session.flush()

    parent.volume_l = float(parent.volume_l) - volume
    session.add(
        LotLink(
            parent_lot_id=parent.id,
            child_lot_id=child.id,
            link_type=LotLinkType.BOLME,
            volume_l=volume,
            ratio_percent=round(volume / float(parent.initial_volume_l or volume) * 100, 3),
            occurred_at=dt.datetime.now(dt.UTC),
            created_by_id=user.id,
        )
    )
    await add_lot_event(
        session, parent.id, event_type="bolme",
        title=f"Parti bölündü: {volume:.0f} L → {code}", user_id=user.id,
    )
    await add_lot_event(
        session, child.id, event_type="olusturma",
        title=f"{parent.code} partisinden bölünerek oluşturuldu", user_id=user.id,
    )

    for tank_id in {parent.current_tank_id, child.current_tank_id}:
        if tank_id:
            tank = await session.get(Tank, tank_id)
            if tank is not None:
                await _recalc_tank(session, tank)

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="lots",
        entity_id=child.id,
        entity_code=child.code,
        summary=f"Parti bölündü: {parent.code} → {child.code} ({volume:.0f} L)",
        after=child.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(child)
    await _enrich_lots(session, [child])
    return LotOut.model_validate(child)


@lots_extra.post("/{lot_id}/stage", response_model=LotOut, summary="Parti aşamasını ilerlet")
async def change_stage(
    lot_id: int,
    request: Request,
    session: SessionDep,
    user: WriteLot,
    stage: LotStage = Query(..., description="Yeni aşama"),
) -> LotOut:
    lot = await get_or_404(session, Lot, lot_id, "Parti")
    before = lot.to_dict()
    old = lot.stage
    lot.stage = stage
    if stage == LotStage.TAMAMLANDI:
        lot.status = LotStatus.KAPANDI
        lot.closed_at = dt.date.today()
    await add_lot_event(
        session, lot.id, event_type="asama",
        title=f"Aşama değişti: {old} → {stage}", user_id=user.id,
    )
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="lots",
        entity_id=lot.id,
        entity_code=lot.code,
        summary=f"Parti aşaması: {old} → {stage}",
        before=before,
        after=lot.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(lot)
    await _enrich_lots(session, [lot])
    return LotOut.model_validate(lot)


# ---------------------------------------------------------- FERMANTASYON
ferms_crud = build_crud_router(
    model=Fermentation,
    create_schema=FermentationCreate,
    update_schema=FermentationUpdate,
    out_schema=FermentationOut,
    read_perm=Perm.FERMENTATION_READ,
    write_perm=Perm.FERMENTATION_WRITE,
    entity_label="Fermantasyon",
    tags=["Fermantasyon"],
    prefix="/fermentations",
    search_fields=("code", "yeast_strain"),
    default_sort="start_date",
    enrich=_enrich_ferms,
    filters={"status": "status", "ferm_type": "ferm_type", "lot_id": "lot_id", "tank_id": "tank_id"},
    soft_delete_field=None,
)

ferms_extra = APIRouter(prefix="/fermentations", tags=["Fermantasyon"])


@ferms_extra.post(
    "/start",
    response_model=FermentationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Fermantasyon başlat",
)
async def start_fermentation(
    payload: FermentationCreate, request: Request, session: SessionDep, user: WriteFerm
) -> FermentationOut:
    lot = await get_or_404(session, Lot, payload.lot_id, "Parti")
    tank = await session.get(Tank, payload.tank_id) if payload.tank_id else None

    active = (
        await session.execute(
            select(func.count())
            .select_from(Fermentation)
            .where(
                Fermentation.lot_id == lot.id,
                Fermentation.ferm_type == payload.ferm_type,
                Fermentation.status.in_(
                    [FermentationStatus.DEVAM_EDIYOR, FermentationStatus.PLANLANDI]
                ),
            )
        )
    ).scalar_one()
    if active:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{lot.code} partisi için zaten devam eden bir {payload.ferm_type} "
            "fermantasyonu var.",
        )

    code = payload.code or await next_code(session, Fermentation)
    ferm = Fermentation(
        code=code,
        lot_id=lot.id,
        tank_id=payload.tank_id or lot.current_tank_id,
        ferm_type=payload.ferm_type,
        status=FermentationStatus.DEVAM_EDIYOR,
        start_date=payload.start_date or dt.datetime.now(dt.UTC),
        target_end_date=payload.target_end_date,
        yeast_strain=payload.yeast_strain,
        yeast_dose_g_hl=payload.yeast_dose_g_hl,
        initial_brix=payload.initial_brix if payload.initial_brix is not None else lot.current_brix,
        target_brix=payload.target_brix,
        initial_ph=payload.initial_ph if payload.initial_ph is not None else lot.current_ph,
        temp_min_c=payload.temp_min_c,
        temp_max_c=payload.temp_max_c,
        volume_l=payload.volume_l or float(lot.volume_l or 0),
        notes=payload.notes,
        created_by_id=user.id,
    )
    session.add(ferm)
    lot.stage = LotStage.FERMANTASYON if payload.ferm_type == "alkol" else LotStage.MALOLAKTIK
    await session.flush()

    await add_lot_event(
        session, lot.id, event_type="fermantasyon",
        title=f"Fermantasyon başladı: {code}",
        description=f"Maya: {payload.yeast_strain or '—'}, tank: {tank.code if tank else '—'}",
        ref_table="fermentations", ref_id=ferm.id, user_id=user.id,
    )
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="fermentations",
        entity_id=ferm.id,
        entity_code=code,
        summary=f"Fermantasyon başlatıldı: {lot.code}",
        after=ferm.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(ferm)
    await _enrich_ferms(session, [ferm])
    return FermentationOut.model_validate(ferm)


@ferms_extra.post(
    "/{ferm_id}/readings",
    response_model=FermentationReadingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ölçüm gir (manuel veya sensör)",
)
async def add_reading(
    ferm_id: int,
    payload: FermentationReadingCreate,
    request: Request,
    session: SessionDep,
    user: WriteFerm,
) -> FermentationReadingOut:
    ferm = await get_or_404(session, Fermentation, ferm_id, "Fermantasyon")
    if ferm.status in (FermentationStatus.TAMAMLANDI, FermentationStatus.IPTAL):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Tamamlanmış veya iptal edilmiş fermantasyona ölçüm girilemez.",
        )

    previous = (
        (
            await session.execute(
                select(FermentationReading)
                .where(FermentationReading.fermentation_id == ferm_id)
                .order_by(FermentationReading.measured_at)
            )
        )
        .scalars()
        .all()
    )

    reading = FermentationReading(
        fermentation_id=ferm_id,
        measured_at=payload.measured_at or dt.datetime.now(dt.UTC),
        source=payload.source,
        temperature_c=payload.temperature_c,
        brix=payload.brix,
        density=payload.density,
        ph=payload.ph,
        total_acidity=payload.total_acidity,
        volatile_acidity=payload.volatile_acidity,
        free_so2=payload.free_so2,
        alcohol=payload.alcohol,
        cap_management=payload.cap_management,
        notes=payload.notes,
        created_by_id=user.id,
    )

    anomaly, reason = detect_reading_anomaly(ferm, list(previous), reading)
    reading.is_anomaly = anomaly
    reading.anomaly_reason = reason
    session.add(reading)
    await session.flush()

    # Parti ozet degerlerini guncelle
    lot = await session.get(Lot, ferm.lot_id)
    if lot is not None:
        if reading.brix is not None:
            lot.current_brix = reading.brix
        if reading.ph is not None:
            lot.current_ph = reading.ph
        if reading.alcohol is not None:
            lot.current_alcohol = reading.alcohol
        if reading.volatile_acidity is not None:
            lot.current_va = reading.volatile_acidity
        if reading.free_so2 is not None:
            lot.current_free_so2 = reading.free_so2
    if reading.temperature_c is not None and ferm.tank_id:
        tank = await session.get(Tank, ferm.tank_id)
        if tank is not None:
            tank.temperature_c = reading.temperature_c

    # Esik tabanli alarm
    if reading.temperature_c is not None:
        temp = float(reading.temperature_c)
        if temp > float(ferm.temp_max_c) or temp < float(ferm.temp_min_c):
            await raise_alert(
                session,
                category="fermantasyon",
                severity="kritik" if temp > float(ferm.temp_max_c) + 3 else "uyari",
                title=f"{ferm.code}: sıcaklık aralık dışı ({temp:.1f} °C)",
                message=(
                    f"Hedef aralık {ferm.temp_min_c}–{ferm.temp_max_c} °C. "
                    f"Ölçülen: {temp:.1f} °C. Soğutma/ısıtma kontrol edilmeli."
                ),
                ref_type="fermentations",
                ref_id=ferm.id,
                ref_code=ferm.code,
                dedupe_key=f"ferm-temp-{ferm.id}-{reading.measured_at:%Y%m%d%H}",
            )
    if anomaly and reason:
        await raise_alert(
            session,
            category="fermantasyon",
            severity="uyari",
            title=f"{ferm.code}: fermantasyon anomalisi",
            message=reason,
            ref_type="fermentations",
            ref_id=ferm.id,
            ref_code=ferm.code,
            dedupe_key=f"ferm-anom-{ferm.id}-{reading.measured_at:%Y%m%d}",
        )

    # Tahmini bitis
    all_readings = [*previous, reading]
    predicted, _note = predict_fermentation_end(ferm, all_readings)
    ferm.predicted_end_date = predicted

    # Hedefe ulasildi mi?
    if reading.brix is not None and float(reading.brix) <= float(ferm.target_brix):
        ferm.status = FermentationStatus.TAMAMLANDI
        ferm.actual_end_date = reading.measured_at
        if lot is not None:
            lot.stage = LotStage.DINLENDIRME
        await add_lot_event(
            session, ferm.lot_id, event_type="fermantasyon",
            title=f"Fermantasyon tamamlandı: {ferm.code} (Brix {reading.brix})",
            ref_table="fermentations", ref_id=ferm.id, user_id=user.id,
        )

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="fermentation_readings",
        entity_id=reading.id,
        entity_code=ferm.code,
        summary=(
            f"Ölçüm: {ferm.code} "
            f"(Brix {reading.brix if reading.brix is not None else '—'}, "
            f"{reading.temperature_c if reading.temperature_c is not None else '—'} °C)"
        ),
        after=reading.to_dict(),
        user=user,
        request=request,
        severity="uyari" if anomaly else "bilgi",
    )
    await session.commit()
    await session.refresh(reading)
    return FermentationReadingOut.model_validate(reading)


@ferms_extra.get(
    "/{ferm_id}/readings",
    response_model=list[FermentationReadingOut],
    summary="Ölçüm listesi",
)
async def list_readings(
    ferm_id: int, session: SessionDep, _user: ReadFerm
) -> list[FermentationReadingOut]:
    await get_or_404(session, Fermentation, ferm_id, "Fermantasyon")
    rows = (
        (
            await session.execute(
                select(FermentationReading)
                .where(FermentationReading.fermentation_id == ferm_id)
                .order_by(FermentationReading.measured_at)
            )
        )
        .scalars()
        .all()
    )
    return [FermentationReadingOut.model_validate(r) for r in rows]


@ferms_extra.get("/{ferm_id}/curve", response_model=FermentationCurve, summary="Fermantasyon eğrisi")
async def fermentation_curve(
    ferm_id: int, session: SessionDep, _user: ReadFerm
) -> FermentationCurve:
    ferm = await get_or_404(session, Fermentation, ferm_id, "Fermantasyon")
    rows = (
        (
            await session.execute(
                select(FermentationReading)
                .where(FermentationReading.fermentation_id == ferm_id)
                .order_by(FermentationReading.measured_at)
            )
        )
        .scalars()
        .all()
    )
    lot = await session.get(Lot, ferm.lot_id)
    predicted, note = predict_fermentation_end(ferm, list(rows))
    return FermentationCurve(
        fermentation_id=ferm.id,
        code=ferm.code,
        lot_code=lot.code if lot else None,
        labels=[r.measured_at for r in rows],
        temperature=[float(r.temperature_c) if r.temperature_c is not None else None for r in rows],
        brix=[float(r.brix) if r.brix is not None else None for r in rows],
        density=[float(r.density) if r.density is not None else None for r in rows],
        ph=[float(r.ph) if r.ph is not None else None for r in rows],
        temp_min_c=float(ferm.temp_min_c),
        temp_max_c=float(ferm.temp_max_c),
        target_brix=float(ferm.target_brix),
        anomalies=[i for i, r in enumerate(rows) if r.is_anomaly],
        predicted_end_date=predicted,
        prediction_note=note,
    )


@ferms_extra.post(
    "/{ferm_id}/additives",
    response_model=FermentationAdditiveOut,
    status_code=status.HTTP_201_CREATED,
    summary="Katkı maddesi ekle",
)
async def add_additive(
    ferm_id: int,
    payload: FermentationAdditiveCreate,
    request: Request,
    session: SessionDep,
    user: WriteFerm,
) -> FermentationAdditiveOut:
    ferm = await get_or_404(session, Fermentation, ferm_id, "Fermantasyon")
    add = FermentationAdditive(
        fermentation_id=ferm_id,
        additive_name=payload.additive_name,
        additive_type=payload.additive_type,
        amount=payload.amount,
        unit=payload.unit,
        added_at=payload.added_at or dt.datetime.now(dt.UTC),
        inventory_item_id=payload.inventory_item_id,
        notes=payload.notes,
        created_by_id=user.id,
    )
    session.add(add)
    await session.flush()
    await add_lot_event(
        session, ferm.lot_id, event_type="katki",
        title=f"Katkı: {payload.additive_name} {payload.amount} {payload.unit}",
        ref_table="fermentation_additives", ref_id=add.id, user_id=user.id,
    )
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="fermentation_additives",
        entity_id=add.id,
        entity_code=ferm.code,
        summary=f"Katkı eklendi: {payload.additive_name}",
        after=add.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(add)
    return FermentationAdditiveOut.model_validate(add)


@ferms_extra.get(
    "/{ferm_id}/additives",
    response_model=list[FermentationAdditiveOut],
    summary="Katkı listesi",
)
async def list_additives(
    ferm_id: int, session: SessionDep, _user: ReadFerm
) -> list[FermentationAdditiveOut]:
    rows = (
        (
            await session.execute(
                select(FermentationAdditive).where(
                    FermentationAdditive.fermentation_id == ferm_id
                )
            )
        )
        .scalars()
        .all()
    )
    return [FermentationAdditiveOut.model_validate(r) for r in rows]


@ferms_extra.post("/{ferm_id}/complete", response_model=FermentationOut, summary="Fermantasyonu bitir")
async def complete_fermentation(
    ferm_id: int, request: Request, session: SessionDep, user: WriteFerm
) -> FermentationOut:
    ferm = await get_or_404(session, Fermentation, ferm_id, "Fermantasyon")
    if ferm.status == FermentationStatus.TAMAMLANDI:
        raise HTTPException(status.HTTP_409_CONFLICT, "Fermantasyon zaten tamamlanmış.")
    before = ferm.to_dict()
    ferm.status = FermentationStatus.TAMAMLANDI
    ferm.actual_end_date = dt.datetime.now(dt.UTC)
    lot = await session.get(Lot, ferm.lot_id)
    if lot is not None and lot.stage in (LotStage.FERMANTASYON, LotStage.MALOLAKTIK):
        lot.stage = LotStage.DINLENDIRME
    await add_lot_event(
        session, ferm.lot_id, event_type="fermantasyon",
        title=f"Fermantasyon manuel olarak tamamlandı: {ferm.code}", user_id=user.id,
    )
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="fermentations",
        entity_id=ferm.id,
        entity_code=ferm.code,
        summary="Fermantasyon tamamlandı",
        before=before,
        after=ferm.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(ferm)
    await _enrich_ferms(session, [ferm])
    return FermentationOut.model_validate(ferm)


@ferms_extra.delete("/readings/{reading_id}", response_model=Message, summary="Ölçümü sil")
async def delete_reading(
    reading_id: int, request: Request, session: SessionDep, user: WriteFerm
) -> Message:
    reading = await get_or_404(session, FermentationReading, reading_id, "Ölçüm")
    before = reading.to_dict()
    await session.delete(reading)
    await record_audit(
        session,
        action=AuditAction.SIL,
        entity_type="fermentation_readings",
        entity_id=reading_id,
        summary="Fermantasyon ölçümü silindi",
        before=before,
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    return Message(detail="Ölçüm silindi.")


routers = [
    tanks_router,
    tanks_extra,
    transfers_router,
    lots_crud,
    lots_extra,
    ferms_crud,
    ferms_extra,
]
