"""Parti bazli maliyet hesabi.

Maliyet bilesenleri:
  * Uzum: LotSource -> HarvestIntake.unit_price * weight_kg
  * Katki: FermentationAdditive -> stok kalemi son birim maliyeti
  * Ambalaj: siseleme emrine bagli URETIM_TUKETIM stok hareketleri
  * Iscilik/enerji/genel gider: hacim bazli varsayilan oranlar (ayarlanabilir)
  * Kupaj: ust partilerden gelen maliyet oranli olarak tasinir
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cellar import BottlingOrder
from app.models.inventory import InventoryItem, MovementType, StockMovement
from app.models.production import (
    Fermentation,
    FermentationAdditive,
    Lot,
    LotLink,
    LotSource,
    TankTransfer,
)
from app.models.vineyard import HarvestIntake
from app.schemas.ops import CostBreakdown

# Varsayilan dolayli maliyet oranlari (TRY / litre). Uretimde ayarlar
# ekranindan yonetilebilir hale getirilmelidir.
DEFAULT_LABOR_PER_L = 3.50
DEFAULT_ENERGY_PER_L = 1.20
DEFAULT_OVERHEAD_PER_L = 2.00

MAX_DEPTH = 8


async def compute_lot_cost(
    session: AsyncSession,
    lot_id: int,
    *,
    labor_per_l: float = DEFAULT_LABOR_PER_L,
    energy_per_l: float = DEFAULT_ENERGY_PER_L,
    overhead_per_l: float = DEFAULT_OVERHEAD_PER_L,
    _depth: int = 0,
) -> CostBreakdown:
    lot = await session.get(Lot, lot_id)
    if lot is None:
        raise ValueError(f"Parti bulunamadı: {lot_id}")

    details: list[dict] = []
    grape_cost = 0.0
    additive_cost = 0.0
    packaging_cost = 0.0

    # --------------------------------------------------------------- uzum
    sources = (
        (await session.execute(select(LotSource).where(LotSource.lot_id == lot_id)))
        .scalars()
        .all()
    )
    for src in sources:
        intake = await session.get(HarvestIntake, src.intake_id)
        if intake is None or intake.unit_price is None:
            continue
        cost = float(intake.unit_price) * float(src.weight_kg)
        grape_cost += cost
        details.append(
            {
                "kalem": "Üzüm",
                "aciklama": f"{intake.code} — {float(src.weight_kg):.0f} kg",
                "birim_fiyat": float(intake.unit_price),
                "miktar": float(src.weight_kg),
                "tutar": round(cost, 2),
            }
        )

    # ------------------------------------------ ust partilerden gelen maliyet
    if _depth < MAX_DEPTH:
        parents = (
            (await session.execute(select(LotLink).where(LotLink.child_lot_id == lot_id)))
            .scalars()
            .all()
        )
        for link in parents:
            parent_cost = await compute_lot_cost(
                session,
                link.parent_lot_id,
                labor_per_l=labor_per_l,
                energy_per_l=energy_per_l,
                overhead_per_l=overhead_per_l,
                _depth=_depth + 1,
            )
            share = float(link.volume_l or 0) * parent_cost.cost_per_liter
            grape_cost += share
            details.append(
                {
                    "kalem": "Kaynak parti",
                    "aciklama": (
                        f"{parent_cost.lot_code} — {float(link.volume_l):.0f} L "
                        f"× {parent_cost.cost_per_liter:.2f} TRY/L"
                    ),
                    "birim_fiyat": parent_cost.cost_per_liter,
                    "miktar": float(link.volume_l or 0),
                    "tutar": round(share, 2),
                }
            )

    # -------------------------------------------------------------- katkilar
    ferm_ids = [
        f.id
        for f in (
            (await session.execute(select(Fermentation).where(Fermentation.lot_id == lot_id)))
            .scalars()
            .all()
        )
    ]
    if ferm_ids:
        additives = (
            (
                await session.execute(
                    select(FermentationAdditive).where(
                        FermentationAdditive.fermentation_id.in_(ferm_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        for add in additives:
            unit_cost = 0.0
            if add.inventory_item_id:
                item = await session.get(InventoryItem, add.inventory_item_id)
                unit_cost = float(item.last_unit_cost) if item else 0.0
            cost = unit_cost * float(add.amount)
            additive_cost += cost
            details.append(
                {
                    "kalem": "Katkı",
                    "aciklama": f"{add.additive_name} — {float(add.amount):g} {add.unit}",
                    "birim_fiyat": unit_cost,
                    "miktar": float(add.amount),
                    "tutar": round(cost, 2),
                }
            )

    # -------------------------------------------------------------- ambalaj
    orders = (
        (await session.execute(select(BottlingOrder).where(BottlingOrder.lot_id == lot_id)))
        .scalars()
        .all()
    )
    bottles = sum(o.produced_bottles for o in orders)
    for order in orders:
        moves = (
            (
                await session.execute(
                    select(StockMovement).where(
                        StockMovement.ref_type == "bottling_orders",
                        StockMovement.ref_id == order.id,
                        StockMovement.movement_type == MovementType.URETIM_TUKETIM,
                    )
                )
            )
            .scalars()
            .all()
        )
        for mv in moves:
            item = await session.get(InventoryItem, mv.item_id)
            cost = abs(float(mv.quantity)) * float(mv.unit_cost)
            packaging_cost += cost
            if cost > 0:
                details.append(
                    {
                        "kalem": "Ambalaj",
                        "aciklama": f"{item.name if item else mv.item_id} — "
                        f"{abs(float(mv.quantity)):g} {item.unit if item else ''}",
                        "birim_fiyat": float(mv.unit_cost),
                        "miktar": abs(float(mv.quantity)),
                        "tutar": round(cost, 2),
                    }
                )

    # ------------------------------------------------------ dolayli giderler
    base_volume = float(lot.initial_volume_l or lot.volume_l or 0)
    labor_cost = base_volume * labor_per_l
    energy_cost = base_volume * energy_per_l
    overhead_cost = base_volume * overhead_per_l

    total = grape_cost + additive_cost + packaging_cost + labor_cost + energy_cost + overhead_cost

    # ------------------------------------------------------------ fire/verim
    transfer_loss = (
        (
            await session.execute(
                select(TankTransfer.loss_l).where(TankTransfer.lot_id == lot_id)
            )
        )
        .scalars()
        .all()
    )
    loss_l = sum(float(x or 0) for x in transfer_loss) + sum(float(o.loss_l or 0) for o in orders)
    loss_percent = round(loss_l / base_volume * 100, 2) if base_volume else 0.0

    denom = base_volume if base_volume > 0 else 1.0
    cost_per_liter = round(total / denom, 4)

    return CostBreakdown(
        lot_id=lot.id,
        lot_code=lot.code,
        lot_name=lot.name,
        vintage_year=lot.vintage_year,
        volume_l=round(base_volume, 2),
        grape_cost=round(grape_cost, 2),
        additive_cost=round(additive_cost, 2),
        packaging_cost=round(packaging_cost, 2),
        labor_cost=round(labor_cost, 2),
        energy_cost=round(energy_cost, 2),
        overhead_cost=round(overhead_cost, 2),
        total_cost=round(total, 2),
        cost_per_liter=cost_per_liter,
        cost_per_bottle=round(total / bottles, 4) if bottles else None,
        bottles_produced=bottles,
        loss_l=round(loss_l, 2),
        loss_percent=loss_percent,
        details=details,
    )
