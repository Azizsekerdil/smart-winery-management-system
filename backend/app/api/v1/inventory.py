"""Stok, satın alma, müşteri ve sevkiyat uç noktaları."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.crud import build_crud_router, get_or_404
from app.core.audit import record_audit
from app.core.deps import SessionDep, require_perms
from app.core.permissions import Perm
from app.models.inventory import (
    Customer,
    InventoryItem,
    MovementType,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseStatus,
    Shipment,
    ShipmentLine,
    ShipmentStatus,
    StockBatch,
    StockMovement,
    Warehouse,
)
from app.models.ops import AuditAction
from app.models.user import User
from app.models.vineyard import Supplier
from app.schemas.common import Message
from app.schemas.inventory import (
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    ItemCreate,
    ItemOut,
    ItemUpdate,
    PurchaseCreate,
    PurchaseLineOut,
    PurchaseOut,
    PurchaseReceive,
    PurchaseUpdate,
    ShipmentCreate,
    ShipmentLineOut,
    ShipmentOut,
    ShipmentUpdate,
    StockBatchOut,
    StockCountRequest,
    StockInRequest,
    StockLevel,
    StockMovementOut,
    StockOutRequest,
    StockTransferRequest,
    WarehouseCreate,
    WarehouseOut,
    WarehouseUpdate,
)
from app.services import inventory as inv
from app.services.alerts import raise_alert
from app.services.codes import next_code

ReadInv = Annotated[User, Depends(require_perms(Perm.INVENTORY_READ))]
WriteInv = Annotated[User, Depends(require_perms(Perm.INVENTORY_WRITE))]
ReadPurchase = Annotated[User, Depends(require_perms(Perm.PURCHASE_READ))]
WritePurchase = Annotated[User, Depends(require_perms(Perm.PURCHASE_WRITE))]
ReadShip = Annotated[User, Depends(require_perms(Perm.SHIPMENT_READ))]
WriteShip = Annotated[User, Depends(require_perms(Perm.SHIPMENT_WRITE))]


async def _enrich_items(session: AsyncSession, rows: Sequence[Any]) -> None:
    for r in rows:
        r.on_hand = await inv.on_hand(session, r.id)
        r.stock_value = await inv.stock_value(session, r.id)
        r.below_min = float(r.min_stock or 0) > 0 and r.on_hand < float(r.min_stock)
        nearest = (
            await session.execute(
                select(StockBatch.expiry_date)
                .where(
                    StockBatch.item_id == r.id,
                    StockBatch.quantity > 0,
                    StockBatch.expiry_date.is_not(None),
                )
                .order_by(StockBatch.expiry_date)
                .limit(1)
            )
        ).scalar_one_or_none()
        r.nearest_expiry = nearest


async def _enrich_warehouses(session: AsyncSession, rows: Sequence[Any]) -> None:
    for r in rows:
        batches = (
            (await session.execute(select(StockBatch).where(StockBatch.warehouse_id == r.id)))
            .scalars()
            .all()
        )
        r.item_count = len({b.item_id for b in batches if float(b.quantity) > 0})
        r.total_value = round(
            sum(float(b.quantity) * float(b.unit_cost) for b in batches), 2
        )


warehouses_crud = build_crud_router(
    model=Warehouse,
    create_schema=WarehouseCreate,
    update_schema=WarehouseUpdate,
    out_schema=WarehouseOut,
    read_perm=Perm.INVENTORY_READ,
    write_perm=Perm.INVENTORY_WRITE,
    entity_label="Depo",
    tags=["Stok"],
    prefix="/warehouses",
    search_fields=("code", "name", "location"),
    enrich=_enrich_warehouses,
    filters={"is_active": "is_active"},
)

items_crud = build_crud_router(
    model=InventoryItem,
    create_schema=ItemCreate,
    update_schema=ItemUpdate,
    out_schema=ItemOut,
    read_perm=Perm.INVENTORY_READ,
    write_perm=Perm.INVENTORY_WRITE,
    entity_label="Stok kartı",
    tags=["Stok"],
    prefix="/items",
    search_fields=("code", "name", "barcode"),
    enrich=_enrich_items,
    filters={"category": "category", "is_active": "is_active"},
)

customers_crud = build_crud_router(
    model=Customer,
    create_schema=CustomerCreate,
    update_schema=CustomerUpdate,
    out_schema=CustomerOut,
    read_perm=Perm.SHIPMENT_READ,
    write_perm=Perm.SHIPMENT_WRITE,
    entity_label="Müşteri",
    tags=["Sevkiyat"],
    prefix="/customers",
    search_fields=("code", "name", "city", "tax_number"),
    filters={"customer_type": "customer_type", "is_active": "is_active"},
)


# ------------------------------------------------------------ STOK HAREKET
stock_router = APIRouter(prefix="/stock", tags=["Stok"])


async def _move_out(session: AsyncSession, m: StockMovement) -> StockMovementOut:
    out = StockMovementOut.model_validate(m)
    item = await session.get(InventoryItem, m.item_id)
    out.item_name = item.name if item else None
    out.item_code = item.code if item else None
    wh = await session.get(Warehouse, m.warehouse_id)
    out.warehouse_code = wh.code if wh else None
    if m.performed_by_id:
        u = await session.get(User, m.performed_by_id)
        out.performed_by_name = u.full_name if u else None
    return out


async def _check_min_stock(session: AsyncSession, item_id: int) -> None:
    item = await session.get(InventoryItem, item_id)
    if item is None or float(item.min_stock or 0) <= 0:
        return
    qty = await inv.on_hand(session, item_id)
    if qty < float(item.min_stock):
        await raise_alert(
            session,
            category="stok",
            severity="kritik" if qty <= 0 else "uyari",
            title=f"Minimum stok altında: {item.name}",
            message=(
                f"{item.code} — mevcut {qty:g} {item.unit}, "
                f"minimum {float(item.min_stock):g} {item.unit}. "
                f"Önerilen sipariş: {float(item.reorder_qty):g} {item.unit}."
            ),
            ref_type="inventory_items",
            ref_id=item.id,
            ref_code=item.code,
            dedupe_key=f"minstock-{item.id}-{dt.date.today():%Y%m%d}",
        )


@stock_router.get("/levels", response_model=list[StockLevel], summary="Stok seviyeleri")
async def stock_levels(
    session: SessionDep,
    _user: ReadInv,
    category: str | None = None,
    only_below_min: bool = False,
) -> list[StockLevel]:
    stmt = select(InventoryItem).where(InventoryItem.is_active.is_(True))
    if category:
        stmt = stmt.where(InventoryItem.category == category)
    items = (await session.execute(stmt.order_by(InventoryItem.name))).scalars().all()

    out: list[StockLevel] = []
    for item in items:
        qty = await inv.on_hand(session, item.id)
        below = float(item.min_stock or 0) > 0 and qty < float(item.min_stock)
        if only_below_min and not below:
            continue
        batches = (
            (
                await session.execute(
                    select(StockBatch).where(
                        StockBatch.item_id == item.id, StockBatch.quantity > 0
                    )
                )
            )
            .scalars()
            .all()
        )
        per_wh: dict[str, float] = {}
        for b in batches:
            wh = await session.get(Warehouse, b.warehouse_id)
            key = wh.code if wh else str(b.warehouse_id)
            per_wh[key] = round(per_wh.get(key, 0) + float(b.quantity), 3)
        expiries = [b.expiry_date for b in batches if b.expiry_date]
        out.append(
            StockLevel(
                item_id=item.id,
                item_code=item.code,
                item_name=item.name,
                category=item.category,
                unit=item.unit,
                on_hand=round(qty, 3),
                min_stock=float(item.min_stock or 0),
                below_min=below,
                stock_value=await inv.stock_value(session, item.id),
                warehouses=per_wh,
                nearest_expiry=min(expiries) if expiries else None,
            )
        )
    return out


@stock_router.get("/movements", response_model=list[StockMovementOut], summary="Stok hareketleri")
async def list_movements(
    session: SessionDep,
    _user: ReadInv,
    item_id: int | None = None,
    warehouse_id: int | None = None,
    movement_type: str | None = None,
    limit: int = Query(200, le=1000),
) -> list[StockMovementOut]:
    stmt = select(StockMovement).order_by(StockMovement.occurred_at.desc()).limit(limit)
    if item_id:
        stmt = stmt.where(StockMovement.item_id == item_id)
    if warehouse_id:
        stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
    if movement_type:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
    rows = (await session.execute(stmt)).scalars().all()
    return [await _move_out(session, m) for m in rows]


@stock_router.get("/batches", response_model=list[StockBatchOut], summary="Stok partileri")
async def list_batches(
    session: SessionDep,
    _user: ReadInv,
    item_id: int | None = None,
    warehouse_id: int | None = None,
    only_positive: bool = True,
) -> list[StockBatchOut]:
    stmt = select(StockBatch).order_by(StockBatch.received_at)
    if item_id:
        stmt = stmt.where(StockBatch.item_id == item_id)
    if warehouse_id:
        stmt = stmt.where(StockBatch.warehouse_id == warehouse_id)
    if only_positive:
        stmt = stmt.where(StockBatch.quantity > 0)
    rows = (await session.execute(stmt)).scalars().all()
    out = []
    for b in rows:
        item = await session.get(InventoryItem, b.item_id)
        wh = await session.get(Warehouse, b.warehouse_id)
        o = StockBatchOut.model_validate(b)
        o.item_name = item.name if item else None
        o.warehouse_code = wh.code if wh else None
        o.days_to_expiry = (
            (b.expiry_date - dt.date.today()).days if b.expiry_date else None
        )
        out.append(o)
    return out


@stock_router.post(
    "/in", response_model=list[StockMovementOut], status_code=status.HTTP_201_CREATED,
    summary="Stok girişi",
)
async def do_stock_in(
    payload: StockInRequest, request: Request, session: SessionDep, user: WriteInv
) -> list[StockMovementOut]:
    try:
        move = await inv.stock_in(
            session,
            item_id=payload.item_id,
            warehouse_id=payload.warehouse_id,
            quantity=payload.quantity,
            unit_cost=payload.unit_cost,
            batch_code=payload.batch_code,
            expiry_date=payload.expiry_date,
            supplier_id=payload.supplier_id,
            occurred_at=payload.occurred_at,
            ref_type=payload.ref_type,
            ref_id=payload.ref_id,
            user_id=user.id,
            notes=payload.notes,
        )
    except inv.StockError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="stock_movements",
        entity_id=move.id,
        entity_code=move.code,
        summary=f"Stok girişi: {payload.quantity:g} (kalem #{payload.item_id})",
        after=move.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(move)
    return [await _move_out(session, move)]


@stock_router.post(
    "/out", response_model=list[StockMovementOut], status_code=status.HTTP_201_CREATED,
    summary="Stok çıkışı (FIFO/FEFO)",
)
async def do_stock_out(
    payload: StockOutRequest, request: Request, session: SessionDep, user: WriteInv
) -> list[StockMovementOut]:
    try:
        moves = await inv.stock_out(
            session,
            item_id=payload.item_id,
            warehouse_id=payload.warehouse_id,
            quantity=payload.quantity,
            movement_type=payload.movement_type,
            occurred_at=payload.occurred_at,
            lot_id=payload.lot_id,
            ref_type=payload.ref_type,
            ref_id=payload.ref_id,
            user_id=user.id,
            notes=payload.notes,
        )
    except inv.StockError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await _check_min_stock(session, payload.item_id)
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="stock_movements",
        entity_id=moves[0].id if moves else None,
        summary=f"Stok çıkışı: {payload.quantity:g} (kalem #{payload.item_id})",
        after={"quantity": payload.quantity, "batches": len(moves)},
        user=user,
        request=request,
    )
    await session.commit()
    return [await _move_out(session, m) for m in moves]


@stock_router.post(
    "/transfer", response_model=list[StockMovementOut], summary="Depolar arası transfer"
)
async def do_transfer(
    payload: StockTransferRequest, request: Request, session: SessionDep, user: WriteInv
) -> list[StockMovementOut]:
    try:
        moves = await inv.stock_transfer(
            session,
            item_id=payload.item_id,
            from_warehouse_id=payload.from_warehouse_id,
            to_warehouse_id=payload.to_warehouse_id,
            quantity=payload.quantity,
            occurred_at=payload.occurred_at,
            user_id=user.id,
            notes=payload.notes,
        )
    except inv.StockError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="stock_movements",
        summary=(
            f"Depo transferi: {payload.quantity:g} "
            f"(#{payload.from_warehouse_id} → #{payload.to_warehouse_id})"
        ),
        after={"quantity": payload.quantity},
        user=user,
        request=request,
    )
    await session.commit()
    return [await _move_out(session, m) for m in moves]


@stock_router.post("/count", response_model=list[StockMovementOut], summary="Sayım düzeltmesi")
async def do_count(
    payload: StockCountRequest, request: Request, session: SessionDep, user: WriteInv
) -> list[StockMovementOut]:
    try:
        result = await inv.stock_count(
            session,
            item_id=payload.item_id,
            warehouse_id=payload.warehouse_id,
            counted_quantity=payload.counted_quantity,
            occurred_at=payload.occurred_at,
            user_id=user.id,
            notes=payload.notes,
        )
    except inv.StockError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    moves = [] if result is None else (result if isinstance(result, list) else [result])
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="stock_movements",
        summary=f"Sayım: kalem #{payload.item_id} → {payload.counted_quantity:g}",
        after={"counted": payload.counted_quantity},
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    return [await _move_out(session, m) for m in moves]


@stock_router.get("/alerts/low", summary="Minimum stok altındaki kalemler")
async def low_stock(session: SessionDep, _user: ReadInv) -> list[dict]:
    return await inv.low_stock_items(session)


@stock_router.get("/alerts/expiring", summary="Son kullanma tarihi yaklaşanlar")
async def expiring(
    session: SessionDep, _user: ReadInv, days: int = Query(60, ge=1, le=365)
) -> list[dict]:
    return await inv.expiring_batches(session, days)


# --------------------------------------------------------------- SATINALMA
purchase_router = APIRouter(prefix="/purchases", tags=["Satın Alma"])


async def _purchase_out(session: AsyncSession, po: PurchaseOrder) -> PurchaseOut:
    lines = (
        (
            await session.execute(
                select(PurchaseOrderLine).where(PurchaseOrderLine.order_id == po.id)
            )
        )
        .scalars()
        .all()
    )
    items = []
    for line in lines:
        item = await session.get(InventoryItem, line.item_id)
        lo = PurchaseLineOut.model_validate(line)
        lo.line_total = line.line_total
        lo.item_name = item.name if item else None
        items.append(lo)

    sup = await session.get(Supplier, po.supplier_id)
    subtotal = round(sum(x.line_total for x in items), 2)
    # `lines` tembel iliskisini tetiklememek icin acik sozlukten dogrulanir.
    return PurchaseOut.model_validate(
        {
            **po.to_dict(),
            "lines": items,
            "subtotal": subtotal,
            "total": round(subtotal * (1 + float(po.tax_rate) / 100), 2),
            "supplier_name": sup.name if sup else None,
        }
    )


@purchase_router.get("", response_model=list[PurchaseOut], summary="Satın alma siparişleri")
async def list_purchases(
    session: SessionDep,
    _user: ReadPurchase,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(100, le=500),
) -> list[PurchaseOut]:
    stmt = select(PurchaseOrder).order_by(PurchaseOrder.order_date.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(PurchaseOrder.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [await _purchase_out(session, p) for p in rows]


@purchase_router.get("/{order_id}", response_model=PurchaseOut, summary="Sipariş detayı")
async def get_purchase(order_id: int, session: SessionDep, _user: ReadPurchase) -> PurchaseOut:
    po = await get_or_404(session, PurchaseOrder, order_id, "Satın alma siparişi")
    return await _purchase_out(session, po)


@purchase_router.post(
    "", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED, summary="Sipariş oluştur"
)
async def create_purchase(
    payload: PurchaseCreate, request: Request, session: SessionDep, user: WritePurchase
) -> PurchaseOut:
    po = PurchaseOrder(
        code=payload.code or await next_code(session, PurchaseOrder),
        supplier_id=payload.supplier_id,
        warehouse_id=payload.warehouse_id,
        order_date=payload.order_date or dt.date.today(),
        expected_date=payload.expected_date,
        currency=payload.currency,
        tax_rate=payload.tax_rate,
        notes=payload.notes,
        created_by_id=user.id,
    )
    session.add(po)
    await session.flush()
    for line in payload.lines:
        session.add(PurchaseOrderLine(order_id=po.id, **line.model_dump()))
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="purchase_orders",
        entity_id=po.id,
        entity_code=po.code,
        summary=f"Satın alma siparişi oluşturuldu ({len(payload.lines)} kalem)",
        after=po.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(po)
    return await _purchase_out(session, po)


@purchase_router.patch("/{order_id}", response_model=PurchaseOut, summary="Sipariş güncelle")
async def update_purchase(
    order_id: int,
    payload: PurchaseUpdate,
    request: Request,
    session: SessionDep,
    user: WritePurchase,
) -> PurchaseOut:
    po = await get_or_404(session, PurchaseOrder, order_id, "Satın alma siparişi")
    if po.status in (PurchaseStatus.TESLIM_ALINDI, PurchaseStatus.IPTAL):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Sipariş '{po.status}' durumunda.")
    before = po.to_dict()
    for k, v in payload.model_dump(exclude_unset=True, exclude={"lines"}).items():
        setattr(po, k, v)
    if payload.lines is not None:
        for line in (
            (
                await session.execute(
                    select(PurchaseOrderLine).where(PurchaseOrderLine.order_id == po.id)
                )
            )
            .scalars()
            .all()
        ):
            await session.delete(line)
        await session.flush()
        for line_in in payload.lines:
            session.add(PurchaseOrderLine(order_id=po.id, **line_in.model_dump()))
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="purchase_orders",
        entity_id=po.id,
        entity_code=po.code,
        summary="Satın alma siparişi güncellendi",
        before=before,
        after=po.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(po)
    return await _purchase_out(session, po)


@purchase_router.post(
    "/{order_id}/receive", response_model=PurchaseOut, summary="Mal kabul (stok girişi üretir)"
)
async def receive_purchase(
    order_id: int,
    payload: PurchaseReceive,
    request: Request,
    session: SessionDep,
    user: WritePurchase,
) -> PurchaseOut:
    po = await get_or_404(session, PurchaseOrder, order_id, "Satın alma siparişi")
    if po.status == PurchaseStatus.IPTAL:
        raise HTTPException(status.HTTP_409_CONFLICT, "İptal edilmiş sipariş teslim alınamaz.")
    before = po.to_dict()

    for rl in payload.lines:
        line = await session.get(PurchaseOrderLine, rl.line_id)
        if line is None or line.order_id != po.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Sipariş satırı bulunamadı: {rl.line_id}"
            )
        remaining = float(line.quantity) - float(line.received_quantity)
        if rl.quantity > remaining + 1e-6:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Satır #{rl.line_id} için kalan miktar {remaining:g}; "
                f"{rl.quantity:g} teslim alınamaz.",
            )
        try:
            await inv.stock_in(
                session,
                item_id=line.item_id,
                warehouse_id=payload.warehouse_id,
                quantity=rl.quantity,
                unit_cost=rl.unit_cost if rl.unit_cost is not None else float(line.unit_price),
                batch_code=rl.batch_code,
                expiry_date=rl.expiry_date,
                supplier_id=po.supplier_id,
                ref_type="purchase_orders",
                ref_id=po.id,
                user_id=user.id,
                notes=f"Mal kabul {po.code}",
            )
        except inv.StockError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        line.received_quantity = float(line.received_quantity) + rl.quantity

    lines = (
        (
            await session.execute(
                select(PurchaseOrderLine).where(PurchaseOrderLine.order_id == po.id)
            )
        )
        .scalars()
        .all()
    )
    fully = all(float(x.received_quantity) + 1e-6 >= float(x.quantity) for x in lines)
    po.status = PurchaseStatus.TESLIM_ALINDI if fully else PurchaseStatus.KISMEN_TESLIM
    po.received_date = payload.received_date or dt.date.today()
    po.warehouse_id = payload.warehouse_id

    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="purchase_orders",
        entity_id=po.id,
        entity_code=po.code,
        summary=f"Mal kabul yapıldı ({len(payload.lines)} satır) → {po.status}",
        before=before,
        after=po.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(po)
    return await _purchase_out(session, po)


# ---------------------------------------------------------------- SEVKIYAT
shipment_router = APIRouter(prefix="/shipments", tags=["Sevkiyat"])


async def _shipment_out(session: AsyncSession, sh: Shipment) -> ShipmentOut:
    lines = (
        (await session.execute(select(ShipmentLine).where(ShipmentLine.shipment_id == sh.id)))
        .scalars()
        .all()
    )
    items = []
    for line in lines:
        item = await session.get(InventoryItem, line.item_id)
        lo = ShipmentLineOut.model_validate(line)
        lo.line_total = line.line_total
        lo.item_name = item.name if item else None
        items.append(lo)
    cust = await session.get(Customer, sh.customer_id)
    return ShipmentOut.model_validate(
        {
            **sh.to_dict(),
            "lines": items,
            "total": round(sum(x.line_total for x in items), 2),
            "customer_name": cust.name if cust else None,
        }
    )


@shipment_router.get("", response_model=list[ShipmentOut], summary="Sevkiyat listesi")
async def list_shipments(
    session: SessionDep,
    _user: ReadShip,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(100, le=500),
) -> list[ShipmentOut]:
    stmt = select(Shipment).order_by(Shipment.order_date.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(Shipment.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [await _shipment_out(session, s) for s in rows]


@shipment_router.get("/{shipment_id}", response_model=ShipmentOut, summary="Sevkiyat detayı")
async def get_shipment(shipment_id: int, session: SessionDep, _user: ReadShip) -> ShipmentOut:
    sh = await get_or_404(session, Shipment, shipment_id, "Sevkiyat")
    return await _shipment_out(session, sh)


@shipment_router.post(
    "", response_model=ShipmentOut, status_code=status.HTTP_201_CREATED, summary="Sevkiyat oluştur"
)
async def create_shipment(
    payload: ShipmentCreate, request: Request, session: SessionDep, user: WriteShip
) -> ShipmentOut:
    await get_or_404(session, Customer, payload.customer_id, "Müşteri")
    await get_or_404(session, Warehouse, payload.warehouse_id, "Depo")

    for line in payload.lines:
        available = await inv.on_hand(session, line.item_id, payload.warehouse_id)
        if available + 1e-6 < line.quantity:
            item = await session.get(InventoryItem, line.item_id)
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{item.name if item else line.item_id} için yeterli stok yok "
                f"(mevcut {available:g}, istenen {line.quantity:g}).",
            )

    sh = Shipment(
        code=payload.code or await next_code(session, Shipment),
        customer_id=payload.customer_id,
        warehouse_id=payload.warehouse_id,
        order_date=payload.order_date or dt.date.today(),
        carrier=payload.carrier,
        tracking_no=payload.tracking_no,
        destination=payload.destination,
        currency=payload.currency,
        notes=payload.notes,
        created_by_id=user.id,
    )
    session.add(sh)
    await session.flush()
    for line in payload.lines:
        session.add(ShipmentLine(shipment_id=sh.id, **line.model_dump()))
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="shipments",
        entity_id=sh.id,
        entity_code=sh.code,
        summary=f"Sevkiyat oluşturuldu ({len(payload.lines)} kalem)",
        after=sh.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(sh)
    return await _shipment_out(session, sh)


@shipment_router.patch("/{shipment_id}", response_model=ShipmentOut, summary="Sevkiyat güncelle")
async def update_shipment(
    shipment_id: int,
    payload: ShipmentUpdate,
    request: Request,
    session: SessionDep,
    user: WriteShip,
) -> ShipmentOut:
    sh = await get_or_404(session, Shipment, shipment_id, "Sevkiyat")
    if sh.status in (ShipmentStatus.SEVK_EDILDI, ShipmentStatus.TESLIM_EDILDI):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Sevk edilmiş kayıt değiştirilemez."
        )
    before = sh.to_dict()
    for k, v in payload.model_dump(exclude_unset=True, exclude={"lines"}).items():
        setattr(sh, k, v)
    if payload.lines is not None:
        for line in (
            (await session.execute(select(ShipmentLine).where(ShipmentLine.shipment_id == sh.id)))
            .scalars()
            .all()
        ):
            await session.delete(line)
        await session.flush()
        for line_in in payload.lines:
            session.add(ShipmentLine(shipment_id=sh.id, **line_in.model_dump()))
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="shipments",
        entity_id=sh.id,
        entity_code=sh.code,
        summary="Sevkiyat güncellendi",
        before=before,
        after=sh.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(sh)
    return await _shipment_out(session, sh)


@shipment_router.post(
    "/{shipment_id}/ship", response_model=ShipmentOut, summary="Sevk et (stok çıkışı üretir)"
)
async def ship(
    shipment_id: int, request: Request, session: SessionDep, user: WriteShip
) -> ShipmentOut:
    sh = await get_or_404(session, Shipment, shipment_id, "Sevkiyat")
    if sh.status in (ShipmentStatus.SEVK_EDILDI, ShipmentStatus.TESLIM_EDILDI):
        raise HTTPException(status.HTTP_409_CONFLICT, "Sevkiyat zaten yapılmış.")
    if sh.status == ShipmentStatus.IPTAL:
        raise HTTPException(status.HTTP_409_CONFLICT, "İptal edilmiş sevkiyat gönderilemez.")

    before = sh.to_dict()
    lines = (
        (await session.execute(select(ShipmentLine).where(ShipmentLine.shipment_id == sh.id)))
        .scalars()
        .all()
    )
    if not lines:
        raise HTTPException(status.HTTP_409_CONFLICT, "Sevkiyat satırı yok.")

    now = dt.datetime.now(dt.UTC)
    for line in lines:
        try:
            moves = await inv.stock_out(
                session,
                item_id=line.item_id,
                warehouse_id=sh.warehouse_id,
                quantity=float(line.quantity),
                occurred_at=now,
                movement_type=MovementType.CIKIS,
                ref_type="shipments",
                ref_id=sh.id,
                user_id=user.id,
                notes=f"Sevkiyat {sh.code}",
            )
        except inv.StockError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        if moves:
            line.batch_id = moves[0].batch_id
        await _check_min_stock(session, line.item_id)

    sh.status = ShipmentStatus.SEVK_EDILDI
    sh.shipped_at = now
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="shipments",
        entity_id=sh.id,
        entity_code=sh.code,
        summary=f"Sevk edildi ({len(lines)} kalem)",
        before=before,
        after=sh.to_dict(),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(sh)
    return await _shipment_out(session, sh)


@shipment_router.post("/{shipment_id}/deliver", response_model=ShipmentOut, summary="Teslim edildi")
async def deliver(
    shipment_id: int, request: Request, session: SessionDep, user: WriteShip
) -> ShipmentOut:
    sh = await get_or_404(session, Shipment, shipment_id, "Sevkiyat")
    if sh.status != ShipmentStatus.SEVK_EDILDI:
        raise HTTPException(status.HTTP_409_CONFLICT, "Önce sevk işlemi yapılmalıdır.")
    before = sh.to_dict()
    sh.status = ShipmentStatus.TESLIM_EDILDI
    sh.delivered_at = dt.datetime.now(dt.UTC)
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="shipments",
        entity_id=sh.id,
        entity_code=sh.code,
        summary="Sevkiyat teslim edildi",
        before=before,
        after=sh.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(sh)
    return await _shipment_out(session, sh)


@shipment_router.delete("/{shipment_id}", response_model=Message, summary="Sevkiyatı iptal et")
async def cancel_shipment(
    shipment_id: int, request: Request, session: SessionDep, user: WriteShip
) -> Message:
    sh = await get_or_404(session, Shipment, shipment_id, "Sevkiyat")
    if sh.status in (ShipmentStatus.SEVK_EDILDI, ShipmentStatus.TESLIM_EDILDI):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Sevk edilmiş kayıt iptal edilemez; iade hareketi girin.",
        )
    before = sh.to_dict()
    sh.status = ShipmentStatus.IPTAL
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="shipments",
        entity_id=sh.id,
        entity_code=sh.code,
        summary="Sevkiyat iptal edildi",
        before=before,
        after=sh.to_dict(),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    return Message(detail="Sevkiyat iptal edildi.")


routers = [
    warehouses_crud,
    items_crud,
    customers_crud,
    stock_router,
    purchase_router,
    shipment_router,
]
