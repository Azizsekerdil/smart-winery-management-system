"""Laboratuvar, reçete ve kupaj uç noktaları."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.crud import build_crud_router, get_or_404, label_map
from app.api.v1.production import _enrich_lots, _recalc_tank, add_lot_event
from app.core.audit import record_audit
from app.core.deps import SessionDep, require_perms
from app.core.permissions import Perm
from app.models.ops import AuditAction
from app.models.production import (
    Lot,
    LotLink,
    LotLinkType,
    LotStage,
    LotStatus,
    Tank,
)
from app.models.quality import (
    ApprovalStatus,
    BlendComponent,
    BlendOperation,
    BlendStatus,
    LabResult,
    LabSample,
    LabSpec,
    Recipe,
    RecipeItem,
    RecipeStatus,
    SampleStatus,
)
from app.models.user import User
from app.schemas.common import Message
from app.schemas.production import LotOut
from app.schemas.quality import (
    BlendApproval,
    BlendComponentOut,
    BlendCreate,
    BlendExecute,
    BlendOut,
    BlendUpdate,
    LabApproval,
    LabResultCreate,
    LabResultOut,
    LabResultUpdate,
    LabSampleCreate,
    LabSampleOut,
    LabSampleUpdate,
    LabSpecCreate,
    LabSpecOut,
    LabSpecUpdate,
    RecipeCreate,
    RecipeItemOut,
    RecipeOut,
    RecipeUpdate,
)
from app.services.ai_features import blend_prediction
from app.services.alerts import raise_alert
from app.services.codes import next_code, qr_payload

ReadLab = Annotated[User, Depends(require_perms(Perm.LAB_READ))]
WriteLab = Annotated[User, Depends(require_perms(Perm.LAB_WRITE))]
ApproveLab = Annotated[User, Depends(require_perms(Perm.LAB_APPROVE))]
ReadRecipe = Annotated[User, Depends(require_perms(Perm.RECIPE_READ))]
WriteRecipe = Annotated[User, Depends(require_perms(Perm.RECIPE_WRITE))]
ApproveRecipe = Annotated[User, Depends(require_perms(Perm.RECIPE_APPROVE))]


# ------------------------------------------------------------ spesifikasyon
async def evaluate_specs(
    session: AsyncSession, result: LabResult, wine_type: str | None = None
) -> tuple[bool, list[str]]:
    """Sonucu aktif spesifikasyonlara gore degerlendirir."""
    specs = (
        (await session.execute(select(LabSpec).where(LabSpec.is_active.is_(True))))
        .scalars()
        .all()
    )
    problems: list[str] = []
    for spec in specs:
        if spec.wine_type and wine_type and spec.wine_type != wine_type:
            continue
        value = getattr(result, spec.parameter, None)
        if value is None:
            continue
        val = float(value)
        label = spec.label_tr or spec.parameter
        if spec.min_value is not None and val < float(spec.min_value):
            problems.append(
                f"{label}: {val:g} {spec.unit} < alt sınır {float(spec.min_value):g}"
            )
        if spec.max_value is not None and val > float(spec.max_value):
            problems.append(
                f"{label}: {val:g} {spec.unit} > üst sınır {float(spec.max_value):g}"
            )
    return (bool(problems), problems)


# ---------------------------------------------------------------- NUMUNE
async def _enrich_samples(session: AsyncSession, rows: Sequence[Any]) -> None:
    lotmap = await label_map(session, Lot, (r.lot_id for r in rows), field="code")
    tankmap = await label_map(session, Tank, (r.tank_id for r in rows), field="code")
    for r in rows:
        r.lot_code = lotmap.get(r.lot_id) if r.lot_id else None
        r.tank_code = tankmap.get(r.tank_id) if r.tank_id else None
        r.result_count = (
            await session.execute(
                select(func.count()).select_from(LabResult).where(LabResult.sample_id == r.id)
            )
        ).scalar_one()


samples_crud = build_crud_router(
    model=LabSample,
    create_schema=LabSampleCreate,
    update_schema=LabSampleUpdate,
    out_schema=LabSampleOut,
    read_perm=Perm.LAB_READ,
    write_perm=Perm.LAB_WRITE,
    entity_label="Numune",
    tags=["Laboratuvar"],
    prefix="/lab/samples",
    search_fields=("code", "sample_type"),
    default_sort="sampled_at",
    enrich=_enrich_samples,
    filters={"status": "status", "lot_id": "lot_id", "tank_id": "tank_id"},
    soft_delete_field=None,
)

specs_crud = build_crud_router(
    model=LabSpec,
    create_schema=LabSpecCreate,
    update_schema=LabSpecUpdate,
    out_schema=LabSpecOut,
    read_perm=Perm.LAB_READ,
    write_perm=Perm.SETTINGS_WRITE,
    entity_label="Laboratuvar spesifikasyonu",
    tags=["Laboratuvar"],
    prefix="/lab/specs",
    search_fields=("parameter", "label_tr"),
    generate_code=False,
    filters={"parameter": "parameter", "is_active": "is_active"},
)

lab_extra = APIRouter(prefix="/lab", tags=["Laboratuvar"])


async def _result_out(session: AsyncSession, r: LabResult) -> LabResultOut:
    out = LabResultOut.model_validate(r)
    if r.lot_id:
        lot = await session.get(Lot, r.lot_id)
        out.lot_code = lot.code if lot else None
    sample = await session.get(LabSample, r.sample_id)
    out.sample_code = sample.code if sample else None
    return out


@lab_extra.post(
    "/samples/{sample_id}/results",
    response_model=LabResultOut,
    status_code=status.HTTP_201_CREATED,
    summary="Analiz sonucu gir",
)
async def create_result(
    sample_id: int,
    payload: LabResultCreate,
    request: Request,
    session: SessionDep,
    user: WriteLab,
) -> LabResultOut:
    sample = await get_or_404(session, LabSample, sample_id, "Numune")
    lot = await session.get(Lot, sample.lot_id) if sample.lot_id else None

    result = LabResult(
        code=payload.code or await next_code(session, LabResult),
        sample_id=sample.id,
        lot_id=sample.lot_id,
        analyzed_at=payload.analyzed_at or dt.datetime.now(dt.UTC),
        analyzed_by_id=user.id,
        created_by_id=user.id,
        **payload.model_dump(exclude={"code", "analyzed_at"}),
    )
    out_of_spec, problems = await evaluate_specs(
        session, result, lot.wine_type if lot else None
    )
    result.out_of_spec = out_of_spec
    result.out_of_spec_details = "; ".join(problems) if problems else None
    session.add(result)
    sample.status = SampleStatus.TAMAMLANDI
    await session.flush()

    if lot is not None:
        for src, dst in (
            ("ph", "current_ph"),
            ("total_acidity", "current_ta"),
            ("volatile_acidity", "current_va"),
            ("free_so2", "current_free_so2"),
            ("alcohol", "current_alcohol"),
        ):
            val = getattr(result, src)
            if val is not None:
                setattr(lot, dst, val)
        await add_lot_event(
            session, lot.id, event_type="laboratuvar",
            title=f"Laboratuvar sonucu: {result.code}",
            description=result.out_of_spec_details or "Tüm parametreler spesifikasyon içinde.",
            ref_table="lab_results", ref_id=result.id, user_id=user.id,
        )

    if out_of_spec:
        await raise_alert(
            session,
            category="lab",
            severity="kritik" if len(problems) > 2 else "uyari",
            title=f"Spesifikasyon dışı analiz: {result.code}",
            message="; ".join(problems),
            ref_type="lab_results",
            ref_id=result.id,
            ref_code=result.code,
            dedupe_key=f"lab-oos-{result.id}",
        )

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="lab_results",
        entity_id=result.id,
        entity_code=result.code,
        summary=f"Analiz sonucu girildi ({sample.code})"
        + (" — SPESİFİKASYON DIŞI" if out_of_spec else ""),
        after=result.to_dict(),
        user=user,
        request=request,
        severity="uyari" if out_of_spec else "bilgi",
    )
    await session.commit()
    await session.refresh(result)
    return await _result_out(session, result)


@lab_extra.get("/results", response_model=list[LabResultOut], summary="Analiz sonuçları")
async def list_results(
    session: SessionDep,
    _user: ReadLab,
    lot_id: int | None = None,
    approval_status: str | None = None,
    out_of_spec: bool | None = None,
    limit: int = Query(100, le=500),
) -> list[LabResultOut]:
    stmt = select(LabResult).order_by(LabResult.analyzed_at.desc()).limit(limit)
    if lot_id:
        stmt = stmt.where(LabResult.lot_id == lot_id)
    if approval_status:
        stmt = stmt.where(LabResult.approval_status == approval_status)
    if out_of_spec is not None:
        stmt = stmt.where(LabResult.out_of_spec.is_(out_of_spec))
    rows = (await session.execute(stmt)).scalars().all()
    return [await _result_out(session, r) for r in rows]


@lab_extra.get("/results/{result_id}", response_model=LabResultOut, summary="Analiz detayı")
async def get_result(result_id: int, session: SessionDep, _user: ReadLab) -> LabResultOut:
    r = await get_or_404(session, LabResult, result_id, "Analiz sonucu")
    return await _result_out(session, r)


@lab_extra.patch("/results/{result_id}", response_model=LabResultOut, summary="Analiz güncelle")
async def update_result(
    result_id: int,
    payload: LabResultUpdate,
    request: Request,
    session: SessionDep,
    user: WriteLab,
) -> LabResultOut:
    r = await get_or_404(session, LabResult, result_id, "Analiz sonucu")
    if r.approval_status == ApprovalStatus.ONAYLANDI:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Onaylanmış analiz sonucu değiştirilemez. Yeni analiz kaydı oluşturun.",
        )
    before = r.to_dict()
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    lot = await session.get(Lot, r.lot_id) if r.lot_id else None
    oos, problems = await evaluate_specs(session, r, lot.wine_type if lot else None)
    r.out_of_spec = oos
    r.out_of_spec_details = "; ".join(problems) if problems else None

    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="lab_results",
        entity_id=r.id,
        entity_code=r.code,
        summary="Analiz sonucu güncellendi",
        before=before,
        after=r.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(r)
    return await _result_out(session, r)


@lab_extra.post(
    "/results/{result_id}/approval",
    response_model=LabResultOut,
    summary="Analizi onayla / reddet",
)
async def approve_result(
    result_id: int,
    payload: LabApproval,
    request: Request,
    session: SessionDep,
    user: ApproveLab,
) -> LabResultOut:
    r = await get_or_404(session, LabResult, result_id, "Analiz sonucu")
    if r.approval_status != ApprovalStatus.BEKLIYOR:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Bu analiz zaten '{r.approval_status}' durumunda.",
        )
    if r.analyzed_by_id == user.id and payload.approve:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Analizi yapan kişi kendi sonucunu onaylayamaz (görevler ayrılığı).",
        )

    before = r.to_dict()
    r.approval_status = (
        ApprovalStatus.ONAYLANDI if payload.approve else ApprovalStatus.REDDEDILDI
    )
    r.approved_by_id = user.id
    r.approved_at = dt.datetime.now(dt.UTC)
    r.rejection_reason = None if payload.approve else payload.reason

    if r.lot_id:
        await add_lot_event(
            session, r.lot_id, event_type="lab_onay",
            title=f"Analiz {r.code} {'onaylandı' if payload.approve else 'reddedildi'}",
            description=payload.reason, ref_table="lab_results", ref_id=r.id,
            user_id=user.id,
        )
        if not payload.approve:
            lot = await session.get(Lot, r.lot_id)
            if lot is not None:
                lot.status = LotStatus.KARANTINA

    await record_audit(
        session,
        action=AuditAction.ONAY if payload.approve else AuditAction.RED,
        entity_type="lab_results",
        entity_id=r.id,
        entity_code=r.code,
        summary=f"Analiz {'onaylandı' if payload.approve else 'reddedildi'}"
        + (f": {payload.reason}" if payload.reason else ""),
        before=before,
        after=r.to_dict(),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(r)
    return await _result_out(session, r)


# ---------------------------------------------------------------- RECETE
recipes_router = APIRouter(prefix="/recipes", tags=["Reçete ve Kupaj"])


async def _recipe_out(session: AsyncSession, r: Recipe) -> RecipeOut:
    items = (
        (await session.execute(select(RecipeItem).where(RecipeItem.recipe_id == r.id)))
        .scalars()
        .all()
    )
    payload = [
        RecipeItemOut(**{**RecipeItemOut.model_validate(i).model_dump(), "line_cost": i.line_cost})
        for i in items
    ]
    return RecipeOut.model_validate(
        {
            **r.to_dict(),
            "items": payload,
            "estimated_cost": round(sum(i.line_cost for i in items), 2),
        }
    )


@recipes_router.get("", response_model=list[RecipeOut], summary="Reçete listesi")
async def list_recipes(
    session: SessionDep,
    _user: ReadRecipe,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(100, le=500),
) -> list[RecipeOut]:
    stmt = select(Recipe).order_by(Recipe.name, Recipe.version.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(Recipe.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [await _recipe_out(session, r) for r in rows]


@recipes_router.get("/{recipe_id}", response_model=RecipeOut, summary="Reçete detayı")
async def get_recipe(recipe_id: int, session: SessionDep, _user: ReadRecipe) -> RecipeOut:
    r = await get_or_404(session, Recipe, recipe_id, "Reçete")
    return await _recipe_out(session, r)


@recipes_router.post(
    "", response_model=RecipeOut, status_code=status.HTTP_201_CREATED, summary="Reçete oluştur"
)
async def create_recipe(
    payload: RecipeCreate, request: Request, session: SessionDep, user: WriteRecipe
) -> RecipeOut:
    recipe = Recipe(
        code=payload.code or await next_code(session, Recipe),
        name=payload.name,
        wine_type=payload.wine_type,
        target_volume_l=payload.target_volume_l,
        vintage_year=payload.vintage_year,
        target_alcohol=payload.target_alcohol,
        target_ph=payload.target_ph,
        target_ta=payload.target_ta,
        aging_months=payload.aging_months,
        description=payload.description,
        process_steps=payload.process_steps,
        created_by_id=user.id,
    )
    session.add(recipe)
    await session.flush()
    for item in payload.items:
        session.add(RecipeItem(recipe_id=recipe.id, **item.model_dump()))
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="recipes",
        entity_id=recipe.id,
        entity_code=recipe.code,
        summary=f"Reçete oluşturuldu: {recipe.name}",
        after=recipe.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(recipe)
    return await _recipe_out(session, recipe)


@recipes_router.post(
    "/{recipe_id}/new-version",
    response_model=RecipeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Reçetenin yeni sürümünü oluştur",
)
async def new_recipe_version(
    recipe_id: int,
    payload: RecipeUpdate,
    request: Request,
    session: SessionDep,
    user: WriteRecipe,
) -> RecipeOut:
    parent = await get_or_404(session, Recipe, recipe_id, "Reçete")
    data = payload.model_dump(exclude_unset=True, exclude={"items", "status"})

    child = Recipe(
        code=f"{parent.code}-v{parent.version + 1}",
        name=data.get("name", parent.name),
        version=parent.version + 1,
        parent_recipe_id=parent.id,
        wine_type=data.get("wine_type", parent.wine_type),
        target_volume_l=data.get("target_volume_l", parent.target_volume_l),
        vintage_year=data.get("vintage_year", parent.vintage_year),
        target_alcohol=data.get("target_alcohol", parent.target_alcohol),
        target_ph=data.get("target_ph", parent.target_ph),
        target_ta=data.get("target_ta", parent.target_ta),
        aging_months=data.get("aging_months", parent.aging_months),
        description=data.get("description", parent.description),
        process_steps=data.get("process_steps", parent.process_steps),
        status=RecipeStatus.TASLAK,
        created_by_id=user.id,
    )
    session.add(child)
    await session.flush()

    source_items = payload.items
    if source_items is None:
        old = (
            (await session.execute(select(RecipeItem).where(RecipeItem.recipe_id == parent.id)))
            .scalars()
            .all()
        )
        for i in old:
            session.add(
                RecipeItem(
                    recipe_id=child.id,
                    item_kind=i.item_kind,
                    variety_id=i.variety_id,
                    inventory_item_id=i.inventory_item_id,
                    name=i.name,
                    percentage=i.percentage,
                    amount=i.amount,
                    unit=i.unit,
                    unit_cost=i.unit_cost,
                    notes=i.notes,
                )
            )
    else:
        for item in source_items:
            session.add(RecipeItem(recipe_id=child.id, **item.model_dump()))

    parent.status = RecipeStatus.ARSIV
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="recipes",
        entity_id=child.id,
        entity_code=child.code,
        summary=f"Reçete yeni sürüm: {parent.code} → v{child.version}",
        after=child.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(child)
    return await _recipe_out(session, child)


@recipes_router.post("/{recipe_id}/approve", response_model=RecipeOut, summary="Reçeteyi onayla")
async def approve_recipe(
    recipe_id: int, request: Request, session: SessionDep, user: ApproveRecipe
) -> RecipeOut:
    r = await get_or_404(session, Recipe, recipe_id, "Reçete")
    if r.status == RecipeStatus.ONAYLANDI:
        raise HTTPException(status.HTTP_409_CONFLICT, "Reçete zaten onaylanmış.")
    before = r.to_dict()
    r.status = RecipeStatus.ONAYLANDI
    r.approved_by_id = user.id
    r.approved_at = dt.datetime.now(dt.UTC)
    await record_audit(
        session,
        action=AuditAction.ONAY,
        entity_type="recipes",
        entity_id=r.id,
        entity_code=r.code,
        summary=f"Reçete onaylandı: {r.name} v{r.version}",
        before=before,
        after=r.to_dict(),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(r)
    return await _recipe_out(session, r)


@recipes_router.delete("/{recipe_id}", response_model=Message, summary="Reçeteyi arşivle")
async def archive_recipe(
    recipe_id: int, request: Request, session: SessionDep, user: WriteRecipe
) -> Message:
    r = await get_or_404(session, Recipe, recipe_id, "Reçete")
    before = r.to_dict()
    r.status = RecipeStatus.ARSIV
    await record_audit(
        session,
        action=AuditAction.SIL,
        entity_type="recipes",
        entity_id=r.id,
        entity_code=r.code,
        summary="Reçete arşivlendi",
        before=before,
        after=r.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    return Message(detail="Reçete arşivlendi.")


# ----------------------------------------------------------------- KUPAJ
blends_router = APIRouter(prefix="/blends", tags=["Reçete ve Kupaj"])


async def _blend_out(session: AsyncSession, b: BlendOperation) -> BlendOut:
    comps = (
        (
            await session.execute(
                select(BlendComponent).where(BlendComponent.blend_id == b.id)
            )
        )
        .scalars()
        .all()
    )
    items: list[BlendComponentOut] = []
    for c in comps:
        lot = await session.get(Lot, c.source_lot_id)
        item = BlendComponentOut.model_validate(c)
        item.source_lot_code = lot.code if lot else None
        item.source_lot_name = lot.name if lot else None
        items.append(item)
    # ORM nesnesinden dogrulamak `components` tembel iliskisini tetikler ve
    # async baglamda senkron IO hatasi verir; bu yuzden acik sozlukten dogrularız.
    return BlendOut.model_validate({**b.to_dict(), "components": items})


async def _compute_blend(session: AsyncSession, b: BlendOperation) -> None:
    comps = (
        (await session.execute(select(BlendComponent).where(BlendComponent.blend_id == b.id)))
        .scalars()
        .all()
    )
    payload = []
    total = 0.0
    for c in comps:
        lot = await session.get(Lot, c.source_lot_id)
        vol = float(c.volume_l)
        total += vol
        payload.append(
            {
                "volume_l": vol,
                "alcohol": float(lot.current_alcohol) if lot and lot.current_alcohol is not None else None,
                "ph": float(lot.current_ph) if lot and lot.current_ph is not None else None,
                "ta": float(lot.current_ta) if lot and lot.current_ta is not None else None,
                "cost_l": float(c.unit_cost_l or 0),
            }
        )
    pred = blend_prediction(payload)
    b.planned_volume_l = pred["volume_l"] or 0.0
    b.predicted_alcohol = pred["alcohol"]
    b.predicted_ph = pred["ph"]
    b.predicted_ta = pred["ta"]
    b.estimated_cost = pred["cost"]
    for c in comps:
        c.percentage = round(float(c.volume_l) / total * 100, 3) if total else None


@blends_router.get("", response_model=list[BlendOut], summary="Kupaj senaryoları")
async def list_blends(
    session: SessionDep,
    _user: ReadRecipe,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(100, le=500),
) -> list[BlendOut]:
    stmt = select(BlendOperation).order_by(BlendOperation.id.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(BlendOperation.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [await _blend_out(session, b) for b in rows]


@blends_router.get("/{blend_id}", response_model=BlendOut, summary="Kupaj detayı")
async def get_blend(blend_id: int, session: SessionDep, _user: ReadRecipe) -> BlendOut:
    b = await get_or_404(session, BlendOperation, blend_id, "Kupaj")
    return await _blend_out(session, b)


@blends_router.post(
    "", response_model=BlendOut, status_code=status.HTTP_201_CREATED,
    summary="Kupaj senaryosu oluştur",
)
async def create_blend(
    payload: BlendCreate, request: Request, session: SessionDep, user: WriteRecipe
) -> BlendOut:
    for comp in payload.components:
        lot = await get_or_404(session, Lot, comp.source_lot_id, "Kaynak parti")
        if float(lot.volume_l) + 1e-6 < float(comp.volume_l):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{lot.code} partisinde yeterli hacim yok "
                f"(mevcut {lot.volume_l} L, istenen {comp.volume_l} L).",
            )

    blend = BlendOperation(
        code=payload.code or await next_code(session, BlendOperation),
        name=payload.name,
        recipe_id=payload.recipe_id,
        target_tank_id=payload.target_tank_id,
        planned_at=payload.planned_at,
        notes=payload.notes,
        created_by_id=user.id,
    )
    session.add(blend)
    await session.flush()
    for comp in payload.components:
        session.add(
            BlendComponent(
                blend_id=blend.id,
                source_lot_id=comp.source_lot_id,
                volume_l=comp.volume_l,
            )
        )
    await session.flush()
    await _compute_blend(session, blend)

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="blend_operations",
        entity_id=blend.id,
        entity_code=blend.code,
        summary=f"Kupaj senaryosu: {blend.name} ({len(payload.components)} bileşen)",
        after=blend.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(blend)
    return await _blend_out(session, blend)


@blends_router.patch("/{blend_id}", response_model=BlendOut, summary="Kupaj güncelle")
async def update_blend(
    blend_id: int,
    payload: BlendUpdate,
    request: Request,
    session: SessionDep,
    user: WriteRecipe,
) -> BlendOut:
    b = await get_or_404(session, BlendOperation, blend_id, "Kupaj")
    if b.status == BlendStatus.UYGULANDI:
        raise HTTPException(status.HTTP_409_CONFLICT, "Uygulanmış kupaj değiştirilemez.")
    before = b.to_dict()
    data = payload.model_dump(exclude_unset=True, exclude={"components"})
    for k, v in data.items():
        setattr(b, k, v)
    if payload.components is not None:
        for c in (
            (await session.execute(select(BlendComponent).where(BlendComponent.blend_id == b.id)))
            .scalars()
            .all()
        ):
            await session.delete(c)
        await session.flush()
        for comp in payload.components:
            session.add(
                BlendComponent(
                    blend_id=b.id, source_lot_id=comp.source_lot_id, volume_l=comp.volume_l
                )
            )
        await session.flush()
    await _compute_blend(session, b)
    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="blend_operations",
        entity_id=b.id,
        entity_code=b.code,
        summary="Kupaj güncellendi",
        before=before,
        after=b.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(b)
    return await _blend_out(session, b)


@blends_router.post("/{blend_id}/approval", response_model=BlendOut, summary="Kupajı onayla/reddet")
async def approve_blend(
    blend_id: int,
    payload: BlendApproval,
    request: Request,
    session: SessionDep,
    user: ApproveRecipe,
) -> BlendOut:
    b = await get_or_404(session, BlendOperation, blend_id, "Kupaj")
    if b.status in (BlendStatus.UYGULANDI, BlendStatus.IPTAL):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Kupaj '{b.status}' durumunda.")
    before = b.to_dict()
    b.status = BlendStatus.ONAYLANDI if payload.approve else BlendStatus.IPTAL
    b.approved_by_id = user.id
    b.approved_at = dt.datetime.now(dt.UTC)
    if not payload.approve:
        b.notes = f"{b.notes or ''}\nRed gerekçesi: {payload.reason or '—'}".strip()
    await record_audit(
        session,
        action=AuditAction.ONAY if payload.approve else AuditAction.RED,
        entity_type="blend_operations",
        entity_id=b.id,
        entity_code=b.code,
        summary=f"Kupaj {'onaylandı' if payload.approve else 'reddedildi'}: {b.name}",
        before=before,
        after=b.to_dict(),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(b)
    return await _blend_out(session, b)


@blends_router.post("/{blend_id}/execute", response_model=LotOut, summary="Kupajı uygula")
async def execute_blend(
    blend_id: int,
    payload: BlendExecute,
    request: Request,
    session: SessionDep,
    user: WriteRecipe,
) -> LotOut:
    b = await get_or_404(session, BlendOperation, blend_id, "Kupaj")
    if b.status != BlendStatus.ONAYLANDI:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Kupaj uygulanmadan önce yetkili onayı gereklidir.",
        )

    comps = (
        (await session.execute(select(BlendComponent).where(BlendComponent.blend_id == b.id)))
        .scalars()
        .all()
    )
    if len(comps) < 2:
        raise HTTPException(status.HTTP_409_CONFLICT, "Kupaj en az iki bileşen içermelidir.")

    source_lots: list[tuple[BlendComponent, Lot]] = []
    for c in comps:
        lot = await get_or_404(session, Lot, c.source_lot_id, "Kaynak parti")
        if float(lot.volume_l) + 1e-6 < float(c.volume_l):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{lot.code} partisinde yeterli hacim kalmamış "
                f"({lot.volume_l} L < {c.volume_l} L).",
            )
        source_lots.append((c, lot))

    target_tank_id = payload.target_tank_id or b.target_tank_id
    total_volume = sum(float(c.volume_l) for c, _ in source_lots)
    if target_tank_id:
        tank = await get_or_404(session, Tank, target_tank_id, "Hedef tank")
        if tank.free_capacity_l + 1e-6 < total_volume:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{tank.code} tankında yeterli kapasite yok "
                f"(boş {tank.free_capacity_l:.0f} L < {total_volume:.0f} L).",
            )

    first_lot = source_lots[0][1]
    code = payload.result_lot_code or await next_code(session, Lot)
    result_lot = Lot(
        code=code,
        name=payload.result_lot_name,
        vintage_year=max(lot.vintage_year for _, lot in source_lots),
        wine_type=first_lot.wine_type,
        is_blend=True,
        stage=LotStage.KUPAJ,
        volume_l=total_volume,
        initial_volume_l=total_volume,
        current_tank_id=target_tank_id,
        current_alcohol=b.predicted_alcohol,
        current_ph=b.predicted_ph,
        current_ta=b.predicted_ta,
        opened_at=dt.date.today(),
        created_by_id=user.id,
    )
    result_lot.qr_payload = qr_payload("parti", code)
    session.add(result_lot)
    await session.flush()

    executed = payload.executed_at or dt.datetime.now(dt.UTC)
    touched_tanks: set[int] = {target_tank_id} if target_tank_id else set()

    for c, lot in source_lots:
        lot.volume_l = float(lot.volume_l) - float(c.volume_l)
        if lot.volume_l <= 0.01:
            lot.status = LotStatus.KAPANDI
            lot.closed_at = dt.date.today()
        if lot.current_tank_id:
            touched_tanks.add(lot.current_tank_id)
        session.add(
            LotLink(
                parent_lot_id=lot.id,
                child_lot_id=result_lot.id,
                link_type=LotLinkType.KUPAJ,
                volume_l=c.volume_l,
                ratio_percent=c.percentage,
                occurred_at=executed,
                created_by_id=user.id,
            )
        )
        await add_lot_event(
            session, lot.id, event_type="kupaj",
            title=f"Kupaja katıldı: {c.volume_l} L → {code}",
            ref_table="blend_operations", ref_id=b.id, occurred_at=executed,
            user_id=user.id,
        )

    await add_lot_event(
        session, result_lot.id, event_type="olusturma",
        title=f"Kupaj sonucu oluşturuldu ({len(comps)} bileşen, {total_volume:.0f} L)",
        description=b.name, ref_table="blend_operations", ref_id=b.id,
        occurred_at=executed, user_id=user.id,
    )

    b.status = BlendStatus.UYGULANDI
    b.result_lot_id = result_lot.id
    b.actual_volume_l = total_volume
    b.executed_at = executed
    b.target_tank_id = target_tank_id

    await session.flush()
    for tid in touched_tanks:
        tank = await session.get(Tank, tid)
        if tank is not None:
            await _recalc_tank(session, tank)

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="lots",
        entity_id=result_lot.id,
        entity_code=result_lot.code,
        summary=f"Kupaj uygulandı: {b.code} → {result_lot.code} ({total_volume:.0f} L)",
        after=result_lot.to_dict(),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(result_lot)
    await _enrich_lots(session, [result_lot])
    return LotOut.model_validate(result_lot)


routers = [samples_crud, specs_crud, lab_extra, recipes_router, blends_router]
