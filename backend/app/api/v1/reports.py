"""Maliyet, üretim raporları ve dışa aktarma."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select

from app.core.audit import record_audit
from app.core.deps import SessionDep, require_perms
from app.core.permissions import Perm
from app.models.cellar import BottlingOrder, BottlingStatus
from app.models.inventory import InventoryItem
from app.models.ops import AuditAction
from app.models.production import (
    Fermentation,
    FermentationReading,
    Lot,
    LotSource,
    LotStatus,
)
from app.models.quality import LabResult
from app.models.user import User
from app.models.vineyard import GrapeVariety, HarvestIntake
from app.schemas.ops import CostBreakdown, ProductionSummary, SeriesPoint
from app.services import exports
from app.services import inventory as inv
from app.services.costing import compute_lot_cost
from app.services.traceability import build_trace

router = APIRouter(prefix="/reports", tags=["Raporlar"])

ReadCost = Annotated[User, Depends(require_perms(Perm.COST_READ))]
ReadReport = Annotated[User, Depends(require_perms(Perm.REPORT_READ))]
ExportPerm = Annotated[User, Depends(require_perms(Perm.REPORT_EXPORT))]

MONTHS_TR = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]


@router.get("/cost/lot/{lot_id}", response_model=CostBreakdown, summary="Parti bazlı maliyet")
async def lot_cost(
    lot_id: int,
    session: SessionDep,
    _user: ReadCost,
    labor_per_l: float = Query(3.50, ge=0),
    energy_per_l: float = Query(1.20, ge=0),
    overhead_per_l: float = Query(2.00, ge=0),
) -> CostBreakdown:
    try:
        return await compute_lot_cost(
            session,
            lot_id,
            labor_per_l=labor_per_l,
            energy_per_l=energy_per_l,
            overhead_per_l=overhead_per_l,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/cost/summary", summary="Tüm partilerin maliyet özeti")
async def cost_summary(
    session: SessionDep,
    _user: ReadCost,
    vintage_year: int | None = None,
    limit: int = Query(100, le=300),
) -> list[dict]:
    stmt = select(Lot).order_by(Lot.id.desc()).limit(limit)
    if vintage_year:
        stmt = stmt.where(Lot.vintage_year == vintage_year)
    lots = (await session.execute(stmt)).scalars().all()
    out = []
    for lot in lots:
        cb = await compute_lot_cost(session, lot.id)
        out.append(
            {
                "lot_id": cb.lot_id,
                "lot_code": cb.lot_code,
                "lot_name": cb.lot_name,
                "vintage_year": cb.vintage_year,
                "volume_l": cb.volume_l,
                "total_cost": cb.total_cost,
                "cost_per_liter": cb.cost_per_liter,
                "cost_per_bottle": cb.cost_per_bottle,
                "bottles_produced": cb.bottles_produced,
                "loss_percent": cb.loss_percent,
            }
        )
    return out


@router.get("/production", response_model=ProductionSummary, summary="Üretim performansı")
async def production_summary(
    session: SessionDep,
    _user: ReadReport,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> ProductionSummary:
    end = end or dt.date.today()
    start = start or (end - dt.timedelta(days=365))

    intake_rows = (
        (
            await session.execute(
                select(HarvestIntake).where(
                    HarvestIntake.harvest_date >= start, HarvestIntake.harvest_date <= end
                )
            )
        )
        .scalars()
        .all()
    )
    intake_kg = sum(float(i.net_weight_kg or 0) for i in intake_rows)

    # Şıra hacmi AYNI üzüm kabullerinden hesaplanmalıdır. Daha önce filtre
    # yoktu: veritabanındaki TÜM partilerin şırası toplanıp, tarih filtreli
    # üzüm miktarına bölünüyordu. 30 günlük pencerede verim oranı 10 kata
    # kadar şişiyordu. `lot_sources` üzerinde tarih sütunu yoktur; bağlantı
    # kaynak üzüm kabulü üzerinden kurulur.
    juice_l = float(
        (
            await session.execute(
                select(func.coalesce(func.sum(LotSource.juice_yield_l), 0))
                .join(HarvestIntake, LotSource.intake_id == HarvestIntake.id)
                .where(
                    HarvestIntake.harvest_date >= start,
                    HarvestIntake.harvest_date <= end,
                )
            )
        ).scalar_one()
        or 0
    )

    orders = (
        (
            await session.execute(
                select(BottlingOrder).where(
                    BottlingOrder.status == BottlingStatus.TAMAMLANDI,
                    BottlingOrder.finished_at.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    orders = [
        o
        for o in orders
        if o.finished_at and start <= o.finished_at.date() <= end
    ]
    bottles = sum(o.produced_bottles for o in orders)
    rejected = sum(o.rejected_bottles for o in orders)
    bottling_loss = sum(float(o.loss_l or 0) for o in orders)

    active_lots = (
        await session.execute(
            select(func.count()).select_from(Lot).where(Lot.status == LotStatus.AKTIF)
        )
    ).scalar_one()
    completed_lots = (
        await session.execute(
            select(func.count()).select_from(Lot).where(Lot.status == LotStatus.KAPANDI)
        )
    ).scalar_one()

    # cesit bazli dagilim
    by_variety_rows = (
        await session.execute(
            select(GrapeVariety.name, func.sum(HarvestIntake.net_weight_kg))
            .join(GrapeVariety, GrapeVariety.id == HarvestIntake.variety_id)
            .where(HarvestIntake.harvest_date >= start, HarvestIntake.harvest_date <= end)
            .group_by(GrapeVariety.name)
            .order_by(func.sum(HarvestIntake.net_weight_kg).desc())
        )
    ).all()

    by_month: dict[str, float] = {}
    for i in intake_rows:
        key = f"{MONTHS_TR[i.harvest_date.month - 1]} {i.harvest_date.year}"
        by_month[key] = by_month.get(key, 0) + float(i.net_weight_kg or 0)

    return ProductionSummary(
        period_start=start,
        period_end=end,
        intake_kg=round(intake_kg, 1),
        intake_count=len(intake_rows),
        juice_l=round(juice_l, 1),
        bottles_produced=bottles,
        bottles_rejected=rejected,
        active_lots=active_lots,
        completed_lots=completed_lots,
        total_loss_l=round(bottling_loss, 1),
        yield_l_per_kg=round(juice_l / intake_kg, 3) if intake_kg else None,
        by_variety=[SeriesPoint(label=n, value=round(float(v or 0), 1)) for n, v in by_variety_rows],
        by_month=[SeriesPoint(label=k, value=round(v, 1)) for k, v in by_month.items()],
    )


# --------------------------------------------------------------- DISA AKTAR
async def _dataset(
    session: Any, report: str, start: dt.date | None, end: dt.date | None, lot_id: int | None
) -> tuple[str, list[str], list[list[Any]]]:
    """(baslik, sutunlar, satirlar)"""
    if report == "uretim":
        stmt = select(HarvestIntake).order_by(HarvestIntake.harvest_date.desc())
        if start:
            stmt = stmt.where(HarvestIntake.harvest_date >= start)
        if end:
            stmt = stmt.where(HarvestIntake.harvest_date <= end)
        rows = (await session.execute(stmt)).scalars().all()
        data = []
        for r in rows:
            v = await session.get(GrapeVariety, r.variety_id)
            data.append(
                [
                    r.code,
                    r.harvest_date.isoformat(),
                    v.name if v else "",
                    float(r.net_weight_kg or 0),
                    float(r.brix) if r.brix is not None else None,
                    float(r.ph) if r.ph is not None else None,
                    r.quality_grade,
                    round(r.total_cost, 2),
                ]
            )
        return (
            "Üzüm Kabul / Üretim Raporu",
            ["Kod", "Hasat tarihi", "Çeşit", "Net kg", "Brix", "pH", "Kalite", "Tutar (TRY)"],
            data,
        )

    if report == "maliyet":
        lots = (await session.execute(select(Lot).order_by(Lot.id.desc()).limit(200))).scalars().all()
        data = []
        for lot in lots:
            cb = await compute_lot_cost(session, lot.id)
            data.append(
                [
                    cb.lot_code,
                    cb.lot_name,
                    cb.vintage_year,
                    cb.volume_l,
                    cb.grape_cost,
                    cb.additive_cost,
                    cb.packaging_cost,
                    cb.labor_cost + cb.energy_cost + cb.overhead_cost,
                    cb.total_cost,
                    cb.cost_per_liter,
                    cb.cost_per_bottle,
                    cb.loss_percent,
                ]
            )
        return (
            "Parti Bazlı Maliyet Raporu",
            [
                "Parti", "Ad", "Rekolte", "Hacim (L)", "Üzüm", "Katkı", "Ambalaj",
                "Dolaylı", "Toplam", "TRY/L", "TRY/şişe", "Fire %",
            ],
            data,
        )

    if report == "stok":
        levels = []
        items = (
            (await session.execute(select(InventoryItem).order_by(InventoryItem.code)))
            .scalars()
            .all()
        )
        for item in items:
            qty = await inv.on_hand(session, item.id)
            levels.append(
                [
                    item.code,
                    item.name,
                    item.category,
                    item.unit,
                    round(qty, 3),
                    float(item.min_stock or 0),
                    "EVET" if float(item.min_stock or 0) > qty else "hayır",
                    await inv.stock_value(session, item.id),
                ]
            )
        return (
            "Stok Durum Raporu",
            ["Kod", "Ad", "Kategori", "Birim", "Mevcut", "Min. stok", "Kritik", "Değer (TRY)"],
            levels,
        )

    if report == "laboratuvar":
        lab_stmt = select(LabResult).order_by(LabResult.analyzed_at.desc()).limit(500)
        if lot_id:
            lab_stmt = lab_stmt.where(LabResult.lot_id == lot_id)
        rows = (await session.execute(lab_stmt)).scalars().all()
        data = []
        for r in rows:
            lot = await session.get(Lot, r.lot_id) if r.lot_id else None
            data.append(
                [
                    r.code,
                    lot.code if lot else "",
                    r.analyzed_at.strftime("%Y-%m-%d %H:%M"),
                    float(r.ph) if r.ph is not None else None,
                    float(r.total_acidity) if r.total_acidity is not None else None,
                    float(r.volatile_acidity) if r.volatile_acidity is not None else None,
                    float(r.free_so2) if r.free_so2 is not None else None,
                    float(r.total_so2) if r.total_so2 is not None else None,
                    float(r.alcohol) if r.alcohol is not None else None,
                    float(r.residual_sugar) if r.residual_sugar is not None else None,
                    r.approval_status,
                    "EVET" if r.out_of_spec else "hayır",
                ]
            )
        return (
            "Laboratuvar Analiz Raporu",
            [
                "Analiz", "Parti", "Tarih", "pH", "TA (g/L)", "UA (g/L)",
                "Serbest SO₂", "Toplam SO₂", "Alkol %", "Şeker (g/L)", "Onay", "Spek. dışı",
            ],
            data,
        )

    if report == "fermantasyon":
        ferm_stmt = select(Fermentation).order_by(Fermentation.start_date.desc()).limit(200)
        if lot_id:
            ferm_stmt = ferm_stmt.where(Fermentation.lot_id == lot_id)
        ferms = (await session.execute(ferm_stmt)).scalars().all()
        data = []
        for f in ferms:
            lot = await session.get(Lot, f.lot_id)
            count = (
                await session.execute(
                    select(func.count())
                    .select_from(FermentationReading)
                    .where(FermentationReading.fermentation_id == f.id)
                )
            ).scalar_one()
            data.append(
                [
                    f.code,
                    lot.code if lot else "",
                    f.ferm_type,
                    f.status,
                    f.start_date.strftime("%Y-%m-%d"),
                    f.actual_end_date.strftime("%Y-%m-%d") if f.actual_end_date else "",
                    float(f.initial_brix) if f.initial_brix is not None else None,
                    float(f.target_brix),
                    f.yeast_strain or "",
                    count,
                ]
            )
        return (
            "Fermantasyon Raporu",
            [
                "Kod", "Parti", "Tür", "Durum", "Başlangıç", "Bitiş",
                "Başl. Brix", "Hedef Brix", "Maya", "Ölçüm sayısı",
            ],
            data,
        )

    if report == "izlenebilirlik":
        if not lot_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "İzlenebilirlik raporu için lot_id gereklidir."
            )
        graph = await build_trace(session, lot_id, direction="tam")
        data = [
            [
                n.kind,
                n.code,
                n.label,
                "; ".join(f"{k}={v}" for k, v in n.detail.items() if v is not None),
            ]
            for n in graph.nodes
        ]
        lot = await session.get(Lot, lot_id)
        return (
            f"İzlenebilirlik Raporu — {lot.code if lot else lot_id}",
            ["Tür", "Kod", "Etiket", "Ayrıntı"],
            data,
        )

    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Bilinmeyen rapor türü: {report}")


@router.get("/export", summary="Rapor dışa aktar (xlsx / csv / pdf)")
async def export_report(
    request: Request,
    session: SessionDep,
    user: ExportPerm,
    report: str = Query(..., description="uretim|maliyet|stok|laboratuvar|fermantasyon|izlenebilirlik"),
    fmt: str = Query("xlsx", pattern="^(xlsx|csv|pdf)$"),
    start: dt.date | None = None,
    end: dt.date | None = None,
    lot_id: int | None = None,
) -> Response:
    title, headers, rows = await _dataset(session, report, start, end, lot_id)
    subtitle = (
        f"Oluşturma: {dt.datetime.now().strftime('%d.%m.%Y %H:%M')} · "
        f"Kullanıcı: {user.full_name} · Kayıt: {len(rows)}"
    )
    content, mime, ext = exports.render(fmt, title, headers, rows, subtitle=subtitle)

    await record_audit(
        session,
        action=AuditAction.DISA_AKTAR,
        entity_type="reports",
        summary=f"Rapor dışa aktarıldı: {report} ({fmt}, {len(rows)} kayıt)",
        after={"report": report, "format": fmt, "rows": len(rows)},
        user=user,
        request=request,
        commit=True,
    )

    filename = f"{report}-{dt.date.today():%Y%m%d}.{ext}"
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
