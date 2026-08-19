"""Stok hareket motoru: giris, cikis (FIFO/FEFO), transfer, sayim.

Tum miktar degisiklikleri `StockBatch` yiginlari uzerinden yurutulur; boylece
maliyet (agirlikli) ve son kullanma tarihi izlenebilir kalir.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import (
    InventoryItem,
    MovementType,
    StockBatch,
    StockMovement,
    ValuationMethod,
    Warehouse,
)
from app.services.codes import next_code


class StockError(Exception):
    """Stok is kurali ihlali (yetersiz stok, gecersiz depo vb.)."""


async def on_hand(
    session: AsyncSession, item_id: int, warehouse_id: int | None = None
) -> float:
    stmt = select(func.coalesce(func.sum(StockBatch.quantity), 0)).where(
        StockBatch.item_id == item_id
    )
    if warehouse_id is not None:
        stmt = stmt.where(StockBatch.warehouse_id == warehouse_id)
    return float((await session.execute(stmt)).scalar_one() or 0)


async def stock_value(session: AsyncSession, item_id: int) -> float:
    rows = (
        (await session.execute(select(StockBatch).where(StockBatch.item_id == item_id)))
        .scalars()
        .all()
    )
    return round(sum(float(b.quantity) * float(b.unit_cost) for b in rows), 2)


async def _pick_batches(
    session: AsyncSession, item: InventoryItem, warehouse_id: int, quantity: float
) -> list[tuple[StockBatch, float]]:
    """Cikis icin tuketilecek yiginlari degerleme yontemine gore secer."""
    stmt = select(StockBatch).where(
        StockBatch.item_id == item.id,
        StockBatch.warehouse_id == warehouse_id,
        StockBatch.quantity > 0,
    )
    if item.valuation_method == ValuationMethod.FEFO:
        # Once son kullanma tarihi yakin olan; tarihi olmayanlar en sona
        stmt = stmt.order_by(
            StockBatch.expiry_date.is_(None), StockBatch.expiry_date, StockBatch.received_at
        )
    else:  # FIFO ve ortalama icin giris sirasi
        stmt = stmt.order_by(StockBatch.received_at, StockBatch.id)

    batches = (await session.execute(stmt)).scalars().all()
    available = sum(float(b.quantity) for b in batches)
    if available + 1e-9 < quantity:
        raise StockError(
            f"{item.code} ({item.name}) için yeterli stok yok: "
            f"mevcut {available:g} {item.unit}, istenen {quantity:g} {item.unit}."
        )

    picked: list[tuple[StockBatch, float]] = []
    remaining = quantity
    for b in batches:
        if remaining <= 1e-9:
            break
        take = min(float(b.quantity), remaining)
        picked.append((b, take))
        remaining -= take
    return picked


async def stock_in(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
    quantity: float,
    unit_cost: float = 0.0,
    batch_code: str | None = None,
    expiry_date: dt.date | None = None,
    supplier_id: int | None = None,
    occurred_at: dt.datetime | None = None,
    movement_type: str = MovementType.GIRIS,
    ref_type: str | None = None,
    ref_id: int | None = None,
    lot_id: int | None = None,
    user_id: int | None = None,
    notes: str | None = None,
) -> StockMovement:
    if quantity <= 0:
        raise StockError("Giriş miktarı sıfırdan büyük olmalıdır.")

    item = await session.get(InventoryItem, item_id)
    if item is None:
        raise StockError(f"Stok kartı bulunamadı (id={item_id}).")
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise StockError(f"Depo bulunamadı (id={warehouse_id}).")

    when = occurred_at or dt.datetime.now(dt.UTC)
    if expiry_date is None and item.has_expiry and item.shelf_life_days:
        expiry_date = when.date() + dt.timedelta(days=item.shelf_life_days)

    code = batch_code or f"{item.code}-{when:%Y%m%d}-{warehouse.code}"
    existing = (
        await session.execute(
            select(StockBatch).where(
                StockBatch.item_id == item_id,
                StockBatch.warehouse_id == warehouse_id,
                StockBatch.batch_code == code,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        old_qty = float(existing.quantity)
        new_qty = old_qty + quantity
        # Agirlikli ortalama maliyet
        if new_qty > 0:
            existing.unit_cost = round(
                (old_qty * float(existing.unit_cost) + quantity * unit_cost) / new_qty, 4
            )
        existing.quantity = new_qty
        batch = existing
    else:
        batch = StockBatch(
            item_id=item_id,
            warehouse_id=warehouse_id,
            batch_code=code,
            quantity=quantity,
            unit_cost=unit_cost,
            received_at=when,
            expiry_date=expiry_date,
            supplier_id=supplier_id,
            created_by_id=user_id,
        )
        session.add(batch)
        await session.flush()

    if unit_cost > 0:
        item.last_unit_cost = unit_cost

    move = StockMovement(
        code=await next_code(session, StockMovement),
        item_id=item_id,
        batch_id=batch.id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost=unit_cost,
        occurred_at=when,
        ref_type=ref_type,
        ref_id=ref_id,
        lot_id=lot_id,
        performed_by_id=user_id,
        notes=notes,
        created_by_id=user_id,
    )
    session.add(move)
    await session.flush()
    return move


async def stock_out(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
    quantity: float,
    occurred_at: dt.datetime | None = None,
    movement_type: str = MovementType.CIKIS,
    ref_type: str | None = None,
    ref_id: int | None = None,
    lot_id: int | None = None,
    user_id: int | None = None,
    notes: str | None = None,
) -> list[StockMovement]:
    """FIFO/FEFO'ya gore stok cikisi. Her tuketilen yigin icin bir hareket uretir."""
    if quantity <= 0:
        raise StockError("Çıkış miktarı sıfırdan büyük olmalıdır.")

    item = await session.get(InventoryItem, item_id)
    if item is None:
        raise StockError(f"Stok kartı bulunamadı (id={item_id}).")

    when = occurred_at or dt.datetime.now(dt.UTC)
    picked = await _pick_batches(session, item, warehouse_id, quantity)

    moves: list[StockMovement] = []
    for batch, take in picked:
        batch.quantity = float(batch.quantity) - take
        move = StockMovement(
            code=await next_code(session, StockMovement),
            item_id=item_id,
            batch_id=batch.id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            quantity=-take,
            unit_cost=float(batch.unit_cost),
            occurred_at=when,
            ref_type=ref_type,
            ref_id=ref_id,
            lot_id=lot_id,
            performed_by_id=user_id,
            notes=notes,
            created_by_id=user_id,
        )
        session.add(move)
        moves.append(move)
    await session.flush()
    return moves


async def stock_transfer(
    session: AsyncSession,
    *,
    item_id: int,
    from_warehouse_id: int,
    to_warehouse_id: int,
    quantity: float,
    occurred_at: dt.datetime | None = None,
    user_id: int | None = None,
    notes: str | None = None,
) -> list[StockMovement]:
    when = occurred_at or dt.datetime.now(dt.UTC)
    out_moves = await stock_out(
        session,
        item_id=item_id,
        warehouse_id=from_warehouse_id,
        quantity=quantity,
        occurred_at=when,
        movement_type=MovementType.TRANSFER,
        user_id=user_id,
        notes=notes,
    )
    total_cost = sum(abs(float(m.quantity)) * float(m.unit_cost) for m in out_moves)
    avg_cost = round(total_cost / quantity, 4) if quantity else 0.0

    in_move = await stock_in(
        session,
        item_id=item_id,
        warehouse_id=to_warehouse_id,
        quantity=quantity,
        unit_cost=avg_cost,
        occurred_at=when,
        movement_type=MovementType.TRANSFER,
        user_id=user_id,
        notes=notes,
    )
    in_move.target_warehouse_id = to_warehouse_id
    for m in out_moves:
        m.target_warehouse_id = to_warehouse_id
    return [*out_moves, in_move]


async def stock_count(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
    counted_quantity: float,
    occurred_at: dt.datetime | None = None,
    user_id: int | None = None,
    notes: str | None = None,
) -> StockMovement | list[StockMovement] | None:
    """Sayim farkini duzeltir. Fazlaysa giris, eksikse cikis hareketi uretir."""
    current = await on_hand(session, item_id, warehouse_id)
    diff = round(counted_quantity - current, 6)
    if abs(diff) < 1e-9:
        return None

    item = await session.get(InventoryItem, item_id)
    cost = float(item.last_unit_cost) if item else 0.0
    note = (notes or "") + f" (Sayım farkı: {diff:+g}, sistem {current:g})"

    if diff > 0:
        return await stock_in(
            session,
            item_id=item_id,
            warehouse_id=warehouse_id,
            quantity=diff,
            unit_cost=cost,
            occurred_at=occurred_at,
            movement_type=MovementType.SAYIM,
            batch_code=f"SAYIM-{dt.date.today():%Y%m%d}",
            user_id=user_id,
            notes=note.strip(),
        )
    return await stock_out(
        session,
        item_id=item_id,
        warehouse_id=warehouse_id,
        quantity=abs(diff),
        occurred_at=occurred_at,
        movement_type=MovementType.SAYIM,
        user_id=user_id,
        notes=note.strip(),
    )


async def low_stock_items(session: AsyncSession) -> list[dict]:
    """Minimum stok altina dusen kalemler."""
    items = (
        (
            await session.execute(
                select(InventoryItem).where(
                    InventoryItem.is_active.is_(True), InventoryItem.min_stock > 0
                )
            )
        )
        .scalars()
        .all()
    )
    out: list[dict] = []
    for item in items:
        qty = await on_hand(session, item.id)
        if qty < float(item.min_stock):
            out.append(
                {
                    "item_id": item.id,
                    "code": item.code,
                    "name": item.name,
                    "category": item.category,
                    "unit": item.unit,
                    "on_hand": round(qty, 3),
                    "min_stock": float(item.min_stock),
                    "eksik": round(float(item.min_stock) - qty, 3),
                    "reorder_qty": float(item.reorder_qty),
                }
            )
    return sorted(out, key=lambda x: x["eksik"], reverse=True)


async def expiring_batches(session: AsyncSession, days: int = 60) -> list[dict]:
    limit = dt.date.today() + dt.timedelta(days=days)
    rows = (
        (
            await session.execute(
                select(StockBatch)
                .where(
                    StockBatch.expiry_date.is_not(None),
                    StockBatch.expiry_date <= limit,
                    StockBatch.quantity > 0,
                )
                .order_by(StockBatch.expiry_date)
            )
        )
        .scalars()
        .all()
    )
    out = []
    for b in rows:
        item = await session.get(InventoryItem, b.item_id)
        out.append(
            {
                "batch_id": b.id,
                "batch_code": b.batch_code,
                "item_code": item.code if item else None,
                "item_name": item.name if item else None,
                "quantity": float(b.quantity),
                "expiry_date": b.expiry_date.isoformat() if b.expiry_date else None,
                "days_left": (b.expiry_date - dt.date.today()).days if b.expiry_date else None,
            }
        )
    return out
