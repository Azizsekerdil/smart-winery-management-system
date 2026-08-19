"""Fıçı / mahzen ve şişeleme-paketleme uç noktaları."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.crud import build_crud_router, get_or_404, label_map
from app.api.v1.production import _recalc_tank, add_lot_event
from app.core.audit import record_audit
from app.core.deps import SessionDep, require_perms
from app.core.permissions import Perm
from app.models.cellar import (
    Barrel,
    BarrelMovement,
    BarrelMovementType,
    BarrelStatus,
    BottlingOrder,
    BottlingStatus,
    TastingNote,
)
from app.models.inventory import InventoryItem, ItemCategory, MovementType, Warehouse
from app.models.ops import AuditAction
from app.models.production import Lot, LotStage, LotStatus, Tank
from app.models.user import User
from app.schemas.cellar import (
    BarrelCreate,
    BarrelMovementCreate,
    BarrelMovementOut,
    BarrelOut,
    BarrelUpdate,
    BottlingCreate,
    BottlingFinish,
    BottlingOut,
    BottlingStart,
    BottlingUpdate,
    LabelPreview,
    TastingNoteCreate,
    TastingNoteOut,
)
from app.schemas.common import Message
from app.services.codes import make_lot_number, next_code, qr_payload
from app.services.inventory import StockError, stock_in, stock_out
from app.services.qr import qr_png

ReadBarrel = Annotated[User, Depends(require_perms(Perm.BARREL_READ))]
WriteBarrel = Annotated[User, Depends(require_perms(Perm.BARREL_WRITE))]
ReadBottling = Annotated[User, Depends(require_perms(Perm.BOTTLING_READ))]
WriteBottling = Annotated[User, Depends(require_perms(Perm.BOTTLING_WRITE))]


async def _enrich_barrels(session: AsyncSession, rows: Sequence[Any]) -> None:
    lotmap = await label_map(session, Lot, (r.current_lot_id for r in rows), field="code")
    for r in rows:
        r.current_lot_code = lotmap.get(r.current_lot_id) if r.current_lot_id else None


async def _enrich_bottling(session: AsyncSession, rows: Sequence[Any]) -> None:
    lotmap = await label_map(session, Lot, (r.lot_id for r in rows), field="code")
    for r in rows:
        r.lot_code = lotmap.get(r.lot_id)


# ------------------------------------------------------------------ FICI
barrels_crud = build_crud_router(
    model=Barrel,
    create_schema=BarrelCreate,
    update_schema=BarrelUpdate,
    out_schema=BarrelOut,
    read_perm=Perm.BARREL_READ,
    write_perm=Perm.BARREL_WRITE,
    entity_label="Fıçı",
    tags=["Fıçı ve Mahzen"],
    prefix="/barrels",
    search_fields=("code", "cooper", "cellar_zone", "rack_code"),
    enrich=_enrich_barrels,
    filters={
        "status": "status",
        "oak_type": "oak_type",
        "cellar_zone": "cellar_zone",
        "is_active": "is_active",
    },
)

barrels_extra = APIRouter(prefix="/barrels", tags=["Fıçı ve Mahzen"])


@barrels_extra.get("/{barrel_id}/qr.png", summary="Fıçı QR kodu", response_class=Response)
async def barrel_qr(barrel_id: int, session: SessionDep, _user: ReadBarrel) -> Response:
    b = await get_or_404(session, Barrel, barrel_id, "Fıçı")
    return Response(
        content=qr_png(b.qr_payload or qr_payload("fici", b.code)), media_type="image/png"
    )


@barrels_extra.get(
    "/{barrel_id}/movements", response_model=list[BarrelMovementOut], summary="Fıçı geçmişi"
)
async def barrel_movements(
    barrel_id: int, session: SessionDep, _user: ReadBarrel
) -> list[BarrelMovementOut]:
    await get_or_404(session, Barrel, barrel_id, "Fıçı")
    rows = (
        (
            await session.execute(
                select(BarrelMovement)
                .where(BarrelMovement.barrel_id == barrel_id)
                .order_by(BarrelMovement.occurred_at.desc())
            )
        )
        .scalars()
        .all()
    )
    out = []
    for r in rows:
        item = BarrelMovementOut.model_validate(r)
        if r.lot_id:
            lot = await session.get(Lot, r.lot_id)
            item.lot_code = lot.code if lot else None
        out.append(item)
    return out


@barrels_extra.post(
    "/{barrel_id}/movements",
    response_model=BarrelMovementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Fıçı hareketi (dolum/boşaltım/topping/temizlik)",
)
async def create_barrel_movement(
    barrel_id: int,
    payload: BarrelMovementCreate,
    request: Request,
    session: SessionDep,
    user: WriteBarrel,
) -> BarrelMovementOut:
    barrel = await get_or_404(session, Barrel, barrel_id, "Fıçı")
    mtype = payload.movement_type
    volume = float(payload.volume_l)
    loss = float(payload.loss_l)
    when = payload.occurred_at or dt.datetime.now(dt.UTC)

    lot: Lot | None = None
    if payload.lot_id:
        lot = await get_or_404(session, Lot, payload.lot_id, "Parti")

    if mtype == BarrelMovementType.DOLUM:
        if barrel.status not in (BarrelStatus.BOS, BarrelStatus.DOLU):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{barrel.code} fıçısı '{barrel.status}' durumunda; dolum yapılamaz.",
            )
        free = float(barrel.capacity_l) - float(barrel.current_volume_l)
        if free + 1e-6 < volume:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{barrel.code} fıçısında yeterli boş hacim yok "
                f"(boş {free:.1f} L, gelen {volume:.1f} L).",
            )
        if lot is not None:
            if float(lot.volume_l) + 1e-6 < volume:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"{lot.code} partisinde yeterli hacim yok ({lot.volume_l} L).",
                )
            source_tank_id = lot.current_tank_id
            lot.volume_l = float(lot.volume_l) - loss
            lot.stage = LotStage.OLGUNLASTIRMA
            if source_tank_id:
                tank = await session.get(Tank, source_tank_id)
                if tank is not None and float(lot.volume_l) <= 0.01:
                    lot.current_tank_id = None
                    await _recalc_tank(session, tank)
        barrel.current_volume_l = float(barrel.current_volume_l) + volume
        barrel.current_lot_id = payload.lot_id
        barrel.status = BarrelStatus.DOLU
        barrel.filled_at = when
        barrel.fill_count += 1

    elif mtype == BarrelMovementType.BOSALTIM:
        if float(barrel.current_volume_l) + 1e-6 < volume:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{barrel.code} fıçısında {volume:.1f} L yok "
                f"(mevcut {barrel.current_volume_l} L).",
            )
        barrel.current_volume_l = float(barrel.current_volume_l) - volume
        if barrel.current_volume_l <= 0.01:
            barrel.current_volume_l = 0
            barrel.current_lot_id = None
            barrel.status = BarrelStatus.BOS
            barrel.filled_at = None

    elif mtype == BarrelMovementType.TOPPING:
        barrel.current_volume_l = min(
            float(barrel.capacity_l), float(barrel.current_volume_l) + volume
        )
        barrel.last_topped_at = when

    elif mtype == BarrelMovementType.TEMIZLIK:
        if float(barrel.current_volume_l) > 0.01:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Dolu fıçıda temizlik kaydı girilemez."
            )
        barrel.last_cleaned_at = when
        barrel.status = BarrelStatus.BOS

    elif mtype == BarrelMovementType.ONARIM:
        barrel.status = BarrelStatus.ONARIMDA

    if loss > 0:
        barrel.total_loss_l = float(barrel.total_loss_l) + loss
        if mtype != BarrelMovementType.DOLUM:
            barrel.current_volume_l = max(0.0, float(barrel.current_volume_l) - loss)

    mv = BarrelMovement(
        barrel_id=barrel.id,
        lot_id=payload.lot_id,
        movement_type=mtype,
        volume_l=volume,
        loss_l=loss,
        occurred_at=when,
        performed_by_id=user.id,
        notes=payload.notes,
        created_by_id=user.id,
    )
    session.add(mv)
    await session.flush()

    if payload.lot_id:
        await add_lot_event(
            session,
            payload.lot_id,
            event_type="fici",
            title=f"Fıçı {barrel.code}: {mtype} {volume:.0f} L",
            ref_table="barrel_movements",
            ref_id=mv.id,
            occurred_at=when,
            user_id=user.id,
        )

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="barrel_movements",
        entity_id=mv.id,
        entity_code=barrel.code,
        summary=f"Fıçı hareketi: {mtype} {volume:.0f} L ({barrel.code})",
        after=mv.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(mv)
    out = BarrelMovementOut.model_validate(mv)
    if lot is not None:
        out.lot_code = lot.code
    return out


@barrels_extra.get("/cellar/map", summary="Mahzen yerleşim haritası")
async def cellar_map(session: SessionDep, _user: ReadBarrel) -> dict:
    rows = (
        (await session.execute(select(Barrel).where(Barrel.is_active.is_(True)).order_by(Barrel.code)))
        .scalars()
        .all()
    )
    await _enrich_barrels(session, rows)
    zones: dict[str, list[dict]] = {}
    for b in rows:
        zone = b.cellar_zone or "Genel"
        zones.setdefault(zone, []).append(
            {
                "id": b.id,
                "code": b.code,
                "oak_type": b.oak_type,
                "toast_level": b.toast_level,
                "capacity_l": float(b.capacity_l),
                "current_volume_l": float(b.current_volume_l),
                "status": b.status,
                "lot_code": getattr(b, "current_lot_code", None),
                "aging_days": b.aging_days,
                "age_years": b.age_years,
                "rack_code": b.rack_code,
                "row_no": b.row_no,
                "level_no": b.level_no,
                "total_loss_l": float(b.total_loss_l),
            }
        )
    return {
        "zones": [{"name": k, "barrels": v} for k, v in sorted(zones.items())],
        "total_barrels": len(rows),
        "filled_barrels": sum(1 for b in rows if b.status == BarrelStatus.DOLU),
        "total_volume_l": sum(float(b.current_volume_l) for b in rows),
        "total_loss_l": sum(float(b.total_loss_l) for b in rows),
    }


# ---------------------------------------------------------- TADIM NOTLARI
tasting_router = APIRouter(prefix="/tasting-notes", tags=["Fıçı ve Mahzen"])


@tasting_router.get("", response_model=list[TastingNoteOut], summary="Tadım notları")
async def list_tasting_notes(
    session: SessionDep,
    _user: ReadBarrel,
    barrel_id: int | None = None,
    lot_id: int | None = None,
    limit: int = Query(100, le=500),
) -> list[TastingNoteOut]:
    stmt = select(TastingNote).order_by(TastingNote.tasted_at.desc()).limit(limit)
    if barrel_id:
        stmt = stmt.where(TastingNote.barrel_id == barrel_id)
    if lot_id:
        stmt = stmt.where(TastingNote.lot_id == lot_id)
    rows = (await session.execute(stmt)).scalars().all()
    out = []
    for r in rows:
        item = TastingNoteOut.model_validate(r)
        if r.taster_id:
            u = await session.get(User, r.taster_id)
            item.taster_name = u.full_name if u else None
        out.append(item)
    return out


@tasting_router.post(
    "", response_model=TastingNoteOut, status_code=status.HTTP_201_CREATED,
    summary="Tadım notu ekle",
)
async def create_tasting_note(
    payload: TastingNoteCreate, request: Request, session: SessionDep, user: WriteBarrel
) -> TastingNoteOut:
    note = TastingNote(
        barrel_id=payload.barrel_id,
        lot_id=payload.lot_id,
        tasted_at=payload.tasted_at or dt.datetime.now(dt.UTC),
        taster_id=user.id,
        appearance=payload.appearance,
        aroma=payload.aroma,
        palate=payload.palate,
        finish=payload.finish,
        score=payload.score,
        conclusion=payload.conclusion,
        created_by_id=user.id,
    )
    session.add(note)
    await session.flush()
    if payload.lot_id:
        await add_lot_event(
            session, payload.lot_id, event_type="tadim",
            title=f"Tadım notu eklendi (puan: {payload.score or '—'})",
            ref_table="tasting_notes", ref_id=note.id, user_id=user.id,
        )
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="tasting_notes",
        entity_id=note.id,
        summary="Tadım notu eklendi",
        after=note.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(note)
    out = TastingNoteOut.model_validate(note)
    out.taster_name = user.full_name
    return out


# -------------------------------------------------------------- SISELEME
bottling_crud = build_crud_router(
    model=BottlingOrder,
    create_schema=BottlingCreate,
    update_schema=BottlingUpdate,
    out_schema=BottlingOut,
    read_perm=Perm.BOTTLING_READ,
    write_perm=Perm.BOTTLING_WRITE,
    entity_label="Şişeleme emri",
    tags=["Şişeleme"],
    prefix="/bottling",
    search_fields=("code", "product_name", "lot_number", "barcode"),
    default_sort="id",
    enrich=_enrich_bottling,
    filters={"status": "status", "lot_id": "lot_id", "vintage_year": "vintage_year"},
    soft_delete_field=None,
)

bottling_extra = APIRouter(prefix="/bottling", tags=["Şişeleme"])


@bottling_extra.post(
    "/orders",
    response_model=BottlingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Şişeleme emri oluştur (LOT numarası ve QR üretir)",
)
async def create_order(
    payload: BottlingCreate, request: Request, session: SessionDep, user: WriteBottling
) -> BottlingOut:
    lot = await get_or_404(session, Lot, payload.lot_id, "Parti")
    code = payload.code or await next_code(session, BottlingOrder)
    planned_volume = payload.planned_bottles * payload.bottle_volume_ml / 1000.0

    if planned_volume > float(lot.volume_l) + 1e-6:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Planlanan hacim ({planned_volume:.1f} L) parti hacmini "
            f"({lot.volume_l} L) aşıyor.",
        )

    order = BottlingOrder(
        code=code,
        lot_id=lot.id,
        source_tank_id=payload.source_tank_id or lot.current_tank_id,
        product_name=payload.product_name,
        vintage_year=payload.vintage_year or lot.vintage_year,
        lot_number=payload.lot_number
        or make_lot_number(lot.code.replace("-", ""), dt.date.today(), code),
        bottle_volume_ml=payload.bottle_volume_ml,
        planned_bottles=payload.planned_bottles,
        bottles_per_case=payload.bottles_per_case,
        planned_volume_l=planned_volume,
        line_code=payload.line_code,
        planned_at=payload.planned_at,
        bottle_item_id=payload.bottle_item_id,
        closure_item_id=payload.closure_item_id,
        capsule_item_id=payload.capsule_item_id,
        label_item_id=payload.label_item_id,
        case_item_id=payload.case_item_id,
        barcode=payload.barcode,
        notes=payload.notes,
        created_by_id=user.id,
    )
    order.qr_payload = qr_payload("siseleme", code)
    session.add(order)
    await session.flush()

    await add_lot_event(
        session, lot.id, event_type="siseleme",
        title=f"Şişeleme emri oluşturuldu: {code} ({payload.planned_bottles} şişe)",
        ref_table="bottling_orders", ref_id=order.id, user_id=user.id,
    )
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="bottling_orders",
        entity_id=order.id,
        entity_code=code,
        summary=f"Şişeleme emri: {payload.product_name} ({payload.planned_bottles} şişe)",
        after=order.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(order)
    await _enrich_bottling(session, [order])
    return BottlingOut.model_validate(order)


@bottling_extra.post("/{order_id}/start", response_model=BottlingOut, summary="Hattı başlat")
async def start_bottling(
    order_id: int,
    payload: BottlingStart,
    request: Request,
    session: SessionDep,
    user: WriteBottling,
) -> BottlingOut:
    order = await get_or_404(session, BottlingOrder, order_id, "Şişeleme emri")
    if order.status not in (BottlingStatus.PLANLANDI, BottlingStatus.HAZIRLIK):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Emir '{order.status}' durumunda; başlatılamaz."
        )
    before = order.to_dict()
    order.status = BottlingStatus.DEVAM_EDIYOR
    order.started_at = payload.started_at or dt.datetime.now(dt.UTC)
    if payload.line_code:
        order.line_code = payload.line_code
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="bottling_orders",
        entity_id=order.id,
        entity_code=order.code,
        summary="Şişeleme hattı başlatıldı",
        before=before,
        after=order.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(order)
    await _enrich_bottling(session, [order])
    return BottlingOut.model_validate(order)


@bottling_extra.post(
    "/{order_id}/finish",
    response_model=BottlingOut,
    summary="Şişelemeyi bitir (stok hareketlerini üretir)",
)
async def finish_bottling(
    order_id: int,
    payload: BottlingFinish,
    request: Request,
    session: SessionDep,
    user: WriteBottling,
) -> BottlingOut:
    order = await get_or_404(session, BottlingOrder, order_id, "Şişeleme emri")
    if order.status == BottlingStatus.TAMAMLANDI:
        raise HTTPException(status.HTTP_409_CONFLICT, "Şişeleme zaten tamamlanmış.")
    if order.status != BottlingStatus.DEVAM_EDIYOR:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Önce hattı başlatın (/start)."
        )

    lot = await get_or_404(session, Lot, order.lot_id, "Parti")
    before = order.to_dict()

    used_l = payload.produced_bottles * order.bottle_volume_ml / 1000.0
    total_out = used_l + float(payload.loss_l)
    if total_out > float(lot.volume_l) + 1e-6:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Kullanılan hacim ({total_out:.1f} L) parti hacmini aşıyor "
            f"({lot.volume_l} L).",
        )

    finished_at = payload.finished_at or dt.datetime.now(dt.UTC)
    warehouse_id = payload.target_warehouse_id
    if warehouse_id is None:
        wh = (
            await session.execute(
                select(Warehouse).where(Warehouse.is_active.is_(True)).order_by(Warehouse.id)
            )
        ).scalar_one_or_none()
        warehouse_id = wh.id if wh else None

    # --- ambalaj tuketimi ------------------------------------------------
    consumed: list[str] = []
    if warehouse_id is not None:
        packaging = [
            (order.bottle_item_id, payload.produced_bottles + payload.rejected_bottles, "şişe"),
            (order.closure_item_id, payload.produced_bottles + payload.rejected_bottles, "mantar/kapak"),
            (order.capsule_item_id, payload.produced_bottles, "kapsül"),
            (order.label_item_id, payload.produced_bottles, "etiket"),
            (
                order.case_item_id,
                -(-payload.produced_bottles // max(1, order.bottles_per_case)),
                "koli",
            ),
        ]
        for item_id, qty, label in packaging:
            if not item_id or qty <= 0:
                continue
            try:
                await stock_out(
                    session,
                    item_id=item_id,
                    warehouse_id=warehouse_id,
                    quantity=float(qty),
                    occurred_at=finished_at,
                    movement_type=MovementType.URETIM_TUKETIM,
                    ref_type="bottling_orders",
                    ref_id=order.id,
                    lot_id=lot.id,
                    user_id=user.id,
                    notes=f"Şişeleme {order.code} - {label}",
                )
                consumed.append(f"{label}: {qty}")
            except StockError as exc:
                raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    # --- bitmis urun girisi ----------------------------------------------
    finished_item = None
    if warehouse_id is not None and payload.produced_bottles > 0:
        finished_item = (
            await session.execute(
                select(InventoryItem).where(
                    InventoryItem.bottling_order_id == order.id,
                    InventoryItem.category == ItemCategory.BITMIS_URUN,
                )
            )
        ).scalar_one_or_none()
        if finished_item is None:
            finished_item = InventoryItem(
                code=f"BU-{order.code}",
                name=f"{order.product_name} {order.vintage_year} "
                f"({order.bottle_volume_ml} ml)",
                category=ItemCategory.BITMIS_URUN,
                unit="şişe",
                barcode=order.barcode,
                bottling_order_id=order.id,
                lot_id=lot.id,
                created_by_id=user.id,
            )
            session.add(finished_item)
            await session.flush()
        order.finished_item_id = finished_item.id
        await stock_in(
            session,
            item_id=finished_item.id,
            warehouse_id=warehouse_id,
            quantity=float(payload.produced_bottles),
            unit_cost=0.0,
            batch_code=order.lot_number,
            occurred_at=finished_at,
            movement_type=MovementType.URETIM_GIRIS,
            ref_type="bottling_orders",
            ref_id=order.id,
            lot_id=lot.id,
            user_id=user.id,
            notes=f"Şişeleme {order.code}",
        )

    # --- emir ve parti guncellemesi --------------------------------------
    order.produced_bottles = payload.produced_bottles
    order.rejected_bottles = payload.rejected_bottles
    order.used_volume_l = used_l
    order.loss_l = payload.loss_l
    order.status = BottlingStatus.TAMAMLANDI
    order.finished_at = finished_at
    order.qc_passed = payload.qc_passed
    order.qc_notes = payload.qc_notes

    lot.volume_l = max(0.0, float(lot.volume_l) - total_out)
    lot.stage = LotStage.SISELEME
    if lot.volume_l <= 0.01:
        lot.stage = LotStage.TAMAMLANDI
        lot.status = LotStatus.KAPANDI
        lot.closed_at = dt.date.today()
        if lot.current_tank_id:
            tank = await session.get(Tank, lot.current_tank_id)
            lot.current_tank_id = None
            if tank is not None:
                await session.flush()
                await _recalc_tank(session, tank)

    await add_lot_event(
        session, lot.id, event_type="siseleme",
        title=f"Şişeleme tamamlandı: {payload.produced_bottles} şişe (LOT {order.lot_number})",
        description=f"Fire {payload.loss_l:.1f} L, red {payload.rejected_bottles} şişe. "
        + ("Tüketilen ambalaj — " + ", ".join(consumed) if consumed else ""),
        ref_table="bottling_orders", ref_id=order.id, occurred_at=finished_at,
        user_id=user.id,
    )
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="bottling_orders",
        entity_id=order.id,
        entity_code=order.code,
        summary=f"Şişeleme tamamlandı: {payload.produced_bottles} şişe, LOT {order.lot_number}",
        before=before,
        after=order.to_dict(),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(order)
    await _enrich_bottling(session, [order])
    return BottlingOut.model_validate(order)


@bottling_extra.get(
    "/{order_id}/label-preview", response_model=LabelPreview, summary="Etiket önizleme verisi"
)
async def label_preview(
    order_id: int, session: SessionDep, _user: ReadBottling
) -> LabelPreview:
    order = await get_or_404(session, BottlingOrder, order_id, "Şişeleme emri")
    lot = await session.get(Lot, order.lot_id)
    variety = None
    if lot and lot.variety_id:
        from app.models.vineyard import GrapeVariety

        v = await session.get(GrapeVariety, lot.variety_id)
        variety = v.name if v else None
    return LabelPreview(
        product_name=order.product_name,
        vintage_year=order.vintage_year,
        lot_number=order.lot_number,
        bottle_volume_ml=order.bottle_volume_ml,
        alcohol=float(lot.current_alcohol) if lot and lot.current_alcohol is not None else None,
        variety=variety,
        barcode=order.barcode,
        qr_payload=order.qr_payload or qr_payload("siseleme", order.code),
    )


@bottling_extra.get("/{order_id}/qr.png", summary="Şişeleme QR kodu", response_class=Response)
async def bottling_qr(order_id: int, session: SessionDep, _user: ReadBottling) -> Response:
    order = await get_or_404(session, BottlingOrder, order_id, "Şişeleme emri")
    return Response(
        content=qr_png(order.qr_payload or qr_payload("siseleme", order.code)),
        media_type="image/png",
    )


@bottling_extra.post("/{order_id}/cancel", response_model=Message, summary="Emri iptal et")
async def cancel_bottling(
    order_id: int, request: Request, session: SessionDep, user: WriteBottling
) -> Message:
    order = await get_or_404(session, BottlingOrder, order_id, "Şişeleme emri")
    if order.status == BottlingStatus.TAMAMLANDI:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Tamamlanmış şişeleme emri iptal edilemez."
        )
    before = order.to_dict()
    order.status = BottlingStatus.IPTAL
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="bottling_orders",
        entity_id=order.id,
        entity_code=order.code,
        summary="Şişeleme emri iptal edildi",
        before=before,
        after=order.to_dict(),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    return Message(detail="Şişeleme emri iptal edildi.")


routers = [barrels_crud, barrels_extra, tasting_router, bottling_crud, bottling_extra]
