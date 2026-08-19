"""Insan tarafindan okunabilir benzersiz kod uretimi (PRT-2026-0007 gibi)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Modul basina kod onekleri
PREFIXES: dict[str, str] = {
    "vineyards": "BAG",
    "parcels": "PRS",
    "grape_varieties": "CST",
    "suppliers": "TED",
    "harvest_intakes": "UZK",
    "lots": "PRT",
    "tanks": "TNK",
    "tank_transfers": "TRF",
    "fermentations": "FRM",
    "lab_samples": "NMN",
    "lab_results": "LAB",
    "recipes": "RCT",
    "blend_operations": "KPJ",
    "barrels": "FIC",
    "bottling_orders": "SSL",
    "warehouses": "DPO",
    "inventory_items": "STK",
    "stock_movements": "HRK",
    "purchase_orders": "SAT",
    "customers": "MST",
    "shipments": "SVK",
    "equipment": "EKP",
    "maintenance_logs": "BKM",
    "agent_tasks": "GRV",
}


def _sequence_of(code: str, base: str) -> int | None:
    if not code or not code.startswith(base):
        return None
    try:
        return int(code[len(base) :])
    except ValueError:
        return None


async def next_code(
    session: AsyncSession,
    model: Any,
    *,
    prefix: str | None = None,
    with_year: bool = True,
    width: int = 4,
) -> str:
    """Ayni onek/yil icin bir sonraki sirali kodu uretir.

    Veritabanindaki kayitlarin YANI SIRA oturumda bekleyen (henuz flush
    edilmemis) nesneler de dikkate alinir; aksi halde tek bir islem icinde
    uretilen coklu kayitlar (ornegin FIFO stok cikisinda birden fazla hareket)
    ayni kodu alir ve benzersizlik kisiti ihlal edilir.

    Es zamanli istekler icin son savunma hatti yine veritabani benzersizlik
    kisitidir; cagirici IntegrityError yakalayip yeniden deneyebilir.
    """
    table = model.__tablename__
    pfx = prefix or PREFIXES.get(table, table[:3].upper())
    year = dt.date.today().year
    base = f"{pfx}-{year}-" if with_year else f"{pfx}-"

    count_stmt = select(func.count()).select_from(model).where(model.code.like(f"{base}%"))
    existing = (await session.execute(count_stmt)).scalar_one()

    max_stmt = (
        select(model.code)
        .where(model.code.like(f"{base}%"))
        .order_by(model.code.desc())
        .limit(1)
    )
    last = (await session.execute(max_stmt)).scalar_one_or_none()

    seq = existing + 1
    if last:
        last_seq = _sequence_of(last, base)
        if last_seq is not None:
            seq = max(seq, last_seq + 1)

    # Oturumda bekleyen ayni turden nesneler
    pending = [
        obj
        for obj in session.new
        if isinstance(obj, model) and getattr(obj, "code", None)
    ]
    for obj in pending:
        pending_seq = _sequence_of(obj.code, base)
        if pending_seq is not None:
            seq = max(seq, pending_seq + 1)

    return f"{base}{seq:0{width}d}"


def qr_payload(kind: str, code: str) -> str:
    """QR/barkod icerigi. Dis sisteme veri sizdirmayan sade sema."""
    return f"saraphane://{kind}/{code}"


def make_lot_number(product_code: str, bottled_on: dt.date, order_code: str) -> str:
    """Sise uzerindeki LOT numarasi: URUN-YYJJJ-SIRA (JJJ = yilin gunu)."""
    seq = order_code.rsplit("-", 1)[-1]
    return f"{product_code}-{bottled_on:%y}{bottled_on.timetuple().tm_yday:03d}-{seq}"
