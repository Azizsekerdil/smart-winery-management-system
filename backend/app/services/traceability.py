"""Parti izlenebilirligi: uzumden siseye geriye ve ileriye dogru izleme.

Cizge dugumleri `tur:id` anahtariyla adreslenir (orn. `parti:12`, `uzum_kabul:3`).
Dongulere karsi ziyaret kumesi tutulur; derinlik sinirlidir.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cellar import Barrel, BarrelMovement, BottlingOrder
from app.models.production import Lot, LotLink, LotSource, Tank, TankTransfer
from app.models.vineyard import GrapeVariety, HarvestIntake, Vineyard
from app.schemas.production import TraceEdge, TraceGraph, TraceNode

MAX_DEPTH = 12


def _key(kind: str, item_id: int) -> str:
    return f"{kind}:{item_id}"


async def _lot_node(session: AsyncSession, lot: Lot) -> TraceNode:
    variety = None
    if lot.variety_id:
        variety = await session.get(GrapeVariety, lot.variety_id)
    tank = await session.get(Tank, lot.current_tank_id) if lot.current_tank_id else None
    return TraceNode(
        kind="parti",
        id=lot.id,
        code=lot.code,
        label=f"{lot.code} · {lot.name}",
        detail={
            "asama": lot.stage,
            "durum": lot.status,
            "hacim_l": float(lot.volume_l or 0),
            "sarap_tipi": lot.wine_type,
            "rekolte": lot.vintage_year,
            "cesit": variety.name if variety else None,
            "tank": tank.code if tank else None,
            "kupaj_mi": lot.is_blend,
        },
    )


async def _intake_node(session: AsyncSession, intake: HarvestIntake) -> TraceNode:
    variety = await session.get(GrapeVariety, intake.variety_id)
    vineyard = (
        await session.get(Vineyard, intake.vineyard_id) if intake.vineyard_id else None
    )
    return TraceNode(
        kind="uzum_kabul",
        id=intake.id,
        code=intake.code,
        label=f"{intake.code} · {variety.name if variety else 'Üzüm'}",
        detail={
            "hasat_tarihi": intake.harvest_date.isoformat(),
            "net_kg": float(intake.net_weight_kg or 0),
            "brix": float(intake.brix) if intake.brix is not None else None,
            "ph": float(intake.ph) if intake.ph is not None else None,
            "kalite": intake.quality_grade,
            "bag": vineyard.name if vineyard else None,
            "rekolte": intake.vintage_year,
        },
    )


def _bottling_node(order: BottlingOrder) -> TraceNode:
    return TraceNode(
        kind="siseleme",
        id=order.id,
        code=order.code,
        label=f"{order.code} · {order.product_name}",
        detail={
            "lot_no": order.lot_number,
            "durum": order.status,
            "uretilen_sise": order.produced_bottles,
            "sise_hacmi_ml": order.bottle_volume_ml,
            "tarih": order.finished_at.isoformat() if order.finished_at else None,
        },
    )


def _barrel_node(barrel: Barrel) -> TraceNode:
    return TraceNode(
        kind="fici",
        id=barrel.id,
        code=barrel.code,
        label=f"{barrel.code} · {barrel.oak_type}",
        detail={
            "mese": barrel.oak_type,
            "kavurma": barrel.toast_level,
            "hacim_l": float(barrel.current_volume_l or 0),
            "bolge": barrel.cellar_zone,
        },
    )


async def build_trace(
    session: AsyncSession, lot_id: int, *, direction: str = "tam"
) -> TraceGraph:
    """`direction`: 'geri' (kaynaklara), 'ileri' (urune) veya 'tam'."""
    root_lot = await session.get(Lot, lot_id)
    if root_lot is None:
        raise ValueError(f"Parti bulunamadı: {lot_id}")

    nodes: dict[str, TraceNode] = {}
    edges: list[TraceEdge] = []
    warnings: list[str] = []

    nodes[_key("parti", root_lot.id)] = await _lot_node(session, root_lot)

    go_back = direction in ("geri", "tam")
    go_fwd = direction in ("ileri", "tam")

    # ------------------------------------------------------------- GERIYE
    if go_back:
        visited: set[int] = set()
        queue: deque[tuple[int, int]] = deque([(root_lot.id, 0)])
        while queue:
            current_id, depth = queue.popleft()
            if current_id in visited:
                continue
            visited.add(current_id)
            if depth >= MAX_DEPTH:
                warnings.append(
                    f"Geriye izleme derinlik sınırına ({MAX_DEPTH}) ulaştı; "
                    "daha eski bağlantılar gösterilmiyor."
                )
                continue

            # Uzum kabul kaynaklari
            src_rows = (
                (await session.execute(select(LotSource).where(LotSource.lot_id == current_id)))
                .scalars()
                .all()
            )
            for src in src_rows:
                intake = await session.get(HarvestIntake, src.intake_id)
                if intake is None:
                    continue
                k = _key("uzum_kabul", intake.id)
                if k not in nodes:
                    nodes[k] = await _intake_node(session, intake)
                edges.append(
                    TraceEdge(
                        from_key=k,
                        to_key=_key("parti", current_id),
                        relation="uzum_girisi",
                        volume_l=float(src.juice_yield_l) if src.juice_yield_l else None,
                    )
                )

            # Ust partiler (kupaj/bolme kaynaklari)
            parent_rows = (
                (await session.execute(select(LotLink).where(LotLink.child_lot_id == current_id)))
                .scalars()
                .all()
            )
            for link in parent_rows:
                parent = await session.get(Lot, link.parent_lot_id)
                if parent is None:
                    continue
                pk = _key("parti", parent.id)
                if pk not in nodes:
                    nodes[pk] = await _lot_node(session, parent)
                edges.append(
                    TraceEdge(
                        from_key=pk,
                        to_key=_key("parti", current_id),
                        relation=link.link_type,
                        volume_l=float(link.volume_l or 0),
                        occurred_at=link.occurred_at,
                    )
                )
                queue.append((parent.id, depth + 1))

    # -------------------------------------------------------------- ILERI
    if go_fwd:
        visited_f: set[int] = set()
        queue_f: deque[tuple[int, int]] = deque([(root_lot.id, 0)])
        while queue_f:
            current_id, depth = queue_f.popleft()
            if current_id in visited_f:
                continue
            visited_f.add(current_id)
            if depth >= MAX_DEPTH:
                warnings.append(
                    f"İleriye izleme derinlik sınırına ({MAX_DEPTH}) ulaştı."
                )
                continue

            child_rows = (
                (await session.execute(select(LotLink).where(LotLink.parent_lot_id == current_id)))
                .scalars()
                .all()
            )
            for link in child_rows:
                child = await session.get(Lot, link.child_lot_id)
                if child is None:
                    continue
                ck = _key("parti", child.id)
                if ck not in nodes:
                    nodes[ck] = await _lot_node(session, child)
                edges.append(
                    TraceEdge(
                        from_key=_key("parti", current_id),
                        to_key=ck,
                        relation=link.link_type,
                        volume_l=float(link.volume_l or 0),
                        occurred_at=link.occurred_at,
                    )
                )
                queue_f.append((child.id, depth + 1))

            # Siseleme emirleri
            orders = (
                (
                    await session.execute(
                        select(BottlingOrder).where(BottlingOrder.lot_id == current_id)
                    )
                )
                .scalars()
                .all()
            )
            for order in orders:
                ok = _key("siseleme", order.id)
                if ok not in nodes:
                    nodes[ok] = _bottling_node(order)
                edges.append(
                    TraceEdge(
                        from_key=_key("parti", current_id),
                        to_key=ok,
                        relation="siseleme",
                        volume_l=float(order.used_volume_l or 0),
                        occurred_at=order.finished_at or order.started_at,
                    )
                )

    # ------------------------------------- kaplar (tank/fici) - her iki yon
    lot_ids = [int(k.split(":")[1]) for k in nodes if k.startswith("parti:")]
    if lot_ids:
        transfers = (
            (
                await session.execute(
                    select(TankTransfer)
                    .where(TankTransfer.lot_id.in_(lot_ids))
                    .order_by(TankTransfer.occurred_at)
                )
            )
            .scalars()
            .all()
        )
        for tr in transfers:
            for tank_id, relation, reverse in (
                (tr.from_tank_id, "cikis_tank", True),
                (tr.to_tank_id, "giris_tank", False),
            ):
                if not tank_id:
                    continue
                tank = await session.get(Tank, tank_id)
                if tank is None:
                    continue
                tk = _key("tank", tank.id)
                if tk not in nodes:
                    nodes[tk] = TraceNode(
                        kind="tank",
                        id=tank.id,
                        code=tank.code,
                        label=f"{tank.code} · {tank.tank_type}",
                        detail={
                            "kapasite_l": float(tank.capacity_l or 0),
                            "doluluk_yuzde": tank.fill_percent,
                            "konum": tank.location,
                        },
                    )
                lot_key = _key("parti", tr.lot_id)
                edges.append(
                    TraceEdge(
                        from_key=tk if reverse else lot_key,
                        to_key=lot_key if reverse else tk,
                        relation=relation,
                        volume_l=float(tr.volume_l or 0),
                        occurred_at=tr.occurred_at,
                    )
                )

        movements = (
            (
                await session.execute(
                    select(BarrelMovement)
                    .where(BarrelMovement.lot_id.in_(lot_ids))
                    .order_by(BarrelMovement.occurred_at)
                )
            )
            .scalars()
            .all()
        )
        for mv in movements:
            barrel = await session.get(Barrel, mv.barrel_id)
            if barrel is None or mv.lot_id is None:
                continue
            bk = _key("fici", barrel.id)
            if bk not in nodes:
                nodes[bk] = _barrel_node(barrel)
            edges.append(
                TraceEdge(
                    from_key=_key("parti", mv.lot_id),
                    to_key=bk,
                    relation=f"fici_{mv.movement_type}",
                    volume_l=float(mv.volume_l or 0),
                    occurred_at=mv.occurred_at,
                )
            )

    # Yinelenen kenarlari temizle
    seen: set[tuple[str, str, str, str]] = set()
    unique_edges: list[TraceEdge] = []
    for e in edges:
        sig = (e.from_key, e.to_key, e.relation, str(e.occurred_at))
        if sig in seen:
            continue
        seen.add(sig)
        unique_edges.append(e)

    if not unique_edges:
        warnings.append("Bu parti için henüz bağlantı kaydı bulunmuyor.")

    return TraceGraph(
        root=_key("parti", root_lot.id),
        direction=direction,
        nodes=list(nodes.values()),
        edges=unique_edges,
        warnings=sorted(set(warnings)),
    )


async def lot_timeline(session: AsyncSession, lot_id: int) -> list[dict[str, Any]]:
    """Parti islem zaman cizelgesi (olaylar + transferler + siseleme)."""
    from app.models.production import LotEvent  # yerel ithal: dongu engelleme

    events = (
        (
            await session.execute(
                select(LotEvent).where(LotEvent.lot_id == lot_id).order_by(LotEvent.occurred_at)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "occurred_at": e.occurred_at,
            "event_type": e.event_type,
            "title": e.title,
            "description": e.description,
            "ref_table": e.ref_table,
            "ref_id": e.ref_id,
        }
        for e in events
    ]
