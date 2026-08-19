"""Bağ, parsel, üzüm çeşidi, tedarikçi ve üzüm kabul uç noktaları."""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import mimetypes
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.crud import build_crud_router, get_or_404, label_map
from app.core.audit import record_audit
from app.core.config import UPLOADS_DIR, settings
from app.core.deps import SessionDep, require_perms
from app.core.permissions import Perm
from app.models.ops import AuditAction
from app.models.user import User
from app.models.vineyard import (
    Attachment,
    GrapeVariety,
    HarvestIntake,
    Parcel,
    Supplier,
    Vineyard,
)
from app.schemas.common import Message
from app.schemas.winery import (
    AttachmentOut,
    GrapeVarietyCreate,
    GrapeVarietyOut,
    GrapeVarietyUpdate,
    HarvestIntakeCreate,
    HarvestIntakeOut,
    HarvestIntakeUpdate,
    ParcelCreate,
    ParcelOut,
    ParcelUpdate,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
    VineyardCreate,
    VineyardOut,
    VineyardUpdate,
)
from app.services.codes import qr_payload
from app.services.qr import qr_png


# ------------------------------------------------------------- zenginlestirme
async def _enrich_vineyards(session: AsyncSession, rows: Sequence[Any]) -> None:
    ids = [r.id for r in rows]
    if not ids:
        return
    stmt = (
        select(Parcel.vineyard_id, func.count())
        .where(Parcel.vineyard_id.in_(ids))
        .group_by(Parcel.vineyard_id)
    )
    counts: dict[int, int] = {
        int(row[0]): int(row[1]) for row in (await session.execute(stmt)).all()
    }
    for r in rows:
        r.parcel_count = counts.get(r.id, 0)


async def _enrich_parcels(session: AsyncSession, rows: Sequence[Any]) -> None:
    vmap = await label_map(session, Vineyard, (r.vineyard_id for r in rows))
    varmap = await label_map(session, GrapeVariety, (r.variety_id for r in rows))
    for r in rows:
        r.vineyard_name = vmap.get(r.vineyard_id)
        r.variety_name = varmap.get(r.variety_id) if r.variety_id else None


async def _enrich_intakes(session: AsyncSession, rows: Sequence[Any]) -> None:
    varmap = await label_map(session, GrapeVariety, (r.variety_id for r in rows))
    vmap = await label_map(session, Vineyard, (r.vineyard_id for r in rows))
    smap = await label_map(session, Supplier, (r.supplier_id for r in rows))
    for r in rows:
        r.variety_name = varmap.get(r.variety_id)
        r.vineyard_name = vmap.get(r.vineyard_id) if r.vineyard_id else None
        r.supplier_name = smap.get(r.supplier_id) if r.supplier_id else None


# --------------------------------------------------------------- CRUD yollari
vineyards_router = build_crud_router(
    model=Vineyard,
    create_schema=VineyardCreate,
    update_schema=VineyardUpdate,
    out_schema=VineyardOut,
    read_perm=Perm.VINEYARD_READ,
    write_perm=Perm.VINEYARD_WRITE,
    entity_label="Bağ",
    tags=["Bağ ve Üzüm Kabulü"],
    prefix="/vineyards",
    search_fields=("code", "name", "region", "village"),
    enrich=_enrich_vineyards,
    filters={"region": "region", "is_active": "is_active"},
)

parcels_router = build_crud_router(
    model=Parcel,
    create_schema=ParcelCreate,
    update_schema=ParcelUpdate,
    out_schema=ParcelOut,
    read_perm=Perm.VINEYARD_READ,
    write_perm=Perm.VINEYARD_WRITE,
    entity_label="Parsel",
    tags=["Bağ ve Üzüm Kabulü"],
    prefix="/parcels",
    search_fields=("code", "name"),
    enrich=_enrich_parcels,
    filters={"vineyard_id": "vineyard_id", "variety_id": "variety_id", "is_active": "is_active"},
)

varieties_router = build_crud_router(
    model=GrapeVariety,
    create_schema=GrapeVarietyCreate,
    update_schema=GrapeVarietyUpdate,
    out_schema=GrapeVarietyOut,
    read_perm=Perm.VINEYARD_READ,
    write_perm=Perm.VINEYARD_WRITE,
    entity_label="Üzüm çeşidi",
    tags=["Bağ ve Üzüm Kabulü"],
    prefix="/varieties",
    search_fields=("code", "name", "origin"),
    filters={"color": "color", "is_active": "is_active"},
)

suppliers_router = build_crud_router(
    model=Supplier,
    create_schema=SupplierCreate,
    update_schema=SupplierUpdate,
    out_schema=SupplierOut,
    read_perm=Perm.PURCHASE_READ,
    write_perm=Perm.PURCHASE_WRITE,
    entity_label="Tedarikçi",
    tags=["Tedarikçiler"],
    prefix="/suppliers",
    search_fields=("code", "name", "contact_person", "tax_number"),
    filters={"supplier_type": "supplier_type", "is_active": "is_active"},
)

intakes_router = build_crud_router(
    model=HarvestIntake,
    create_schema=HarvestIntakeCreate,
    update_schema=HarvestIntakeUpdate,
    out_schema=HarvestIntakeOut,
    read_perm=Perm.HARVEST_READ,
    write_perm=Perm.HARVEST_WRITE,
    entity_label="Üzüm kabul",
    tags=["Bağ ve Üzüm Kabulü"],
    prefix="/harvest-intakes",
    search_fields=("code", "vehicle_plate", "weighbridge_ticket"),
    default_sort="received_at",
    enrich=_enrich_intakes,
    filters={
        "variety_id": "variety_id",
        "vineyard_id": "vineyard_id",
        "supplier_id": "supplier_id",
        "vintage_year": "vintage_year",
        "quality_grade": "quality_grade",
    },
    soft_delete_field=None,
)


# -------------------------------------------------- uzum kabule ozel islemler
extra = APIRouter(tags=["Bağ ve Üzüm Kabulü"])

WriteHarvest = Annotated[User, Depends(require_perms(Perm.HARVEST_WRITE))]
ReadHarvest = Annotated[User, Depends(require_perms(Perm.HARVEST_READ))]


@extra.post(
    "/harvest-intakes/{intake_id}/finalize",
    response_model=HarvestIntakeOut,
    summary="Üzüm kabulünü tamamla (kod, yıl ve QR üret)",
)
async def finalize_intake(
    intake_id: int, request: Request, session: SessionDep, user: WriteHarvest
) -> HarvestIntakeOut:
    obj = await get_or_404(session, HarvestIntake, intake_id, "Üzüm kabul kaydı")
    before = obj.to_dict()

    if not obj.vintage_year:
        obj.vintage_year = obj.harvest_date.year
    if not obj.received_at:
        obj.received_at = dt.datetime.now(dt.UTC)
    obj.qr_payload = qr_payload("uzum-kabul", obj.code)

    await record_audit(
        session,
        action=AuditAction.GUNCELLE,
        entity_type="harvest_intakes",
        entity_id=obj.id,
        entity_code=obj.code,
        summary="Üzüm kabulü tamamlandı, QR üretildi",
        before=before,
        after=obj.to_dict(),
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(obj)
    await _enrich_intakes(session, [obj])
    return HarvestIntakeOut.model_validate(obj)


@extra.get(
    "/harvest-intakes/{intake_id}/qr.png",
    summary="Üzüm kabul QR kodu (PNG)",
    response_class=Response,
)
async def intake_qr(intake_id: int, session: SessionDep, _user: ReadHarvest) -> Response:
    obj = await get_or_404(session, HarvestIntake, intake_id, "Üzüm kabul kaydı")
    payload = obj.qr_payload or qr_payload("uzum-kabul", obj.code)
    return Response(content=qr_png(payload), media_type="image/png")


@extra.post(
    "/harvest-intakes/{intake_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Fotoğraf / belge ekle",
)
async def upload_attachment(
    intake_id: int,
    request: Request,
    session: SessionDep,
    user: WriteHarvest,
    file: Annotated[UploadFile, File(description="Yüklenecek dosya")],
    description: Annotated[str | None, Form()] = None,
) -> AttachmentOut:
    obj = await get_or_404(session, HarvestIntake, intake_id, "Üzüm kabul kaydı")

    filename = Path(file.filename or "dosya").name
    ext = Path(filename).suffix.lower()
    if ext not in settings.allowed_upload_extensions:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"İzin verilmeyen dosya türü: {ext or '(uzantısız)'}. "
            f"İzin verilenler: {', '.join(sorted(settings.allowed_upload_extensions))}",
        )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    buf = io.BytesIO()
    digest = hashlib.sha256()
    size = 0
    while chunk := await file.read(64 * 1024):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"Dosya boyutu {settings.MAX_UPLOAD_MB} MB sınırını aşıyor.",
            )
        digest.update(chunk)
        buf.write(chunk)

    if size == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Boş dosya yüklenemez.")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    target = UPLOADS_DIR / stored_name
    target.write_bytes(buf.getvalue())

    att = Attachment(
        intake_id=obj.id,
        entity_type="harvest_intake",
        entity_id=obj.id,
        filename=filename[:255],
        stored_name=stored_name,
        content_type=(file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream")[:120],
        size_bytes=size,
        sha256=digest.hexdigest(),
        description=description,
        created_by_id=user.id,
    )
    session.add(att)
    await session.flush()
    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="attachments",
        entity_id=att.id,
        summary=f"Ek yüklendi: {filename}",
        after={"filename": filename, "size_bytes": size, "intake": obj.code},
        user=user,
        request=request,
    )
    await session.commit()
    await session.refresh(att)
    out = AttachmentOut.model_validate(att)
    out.url = f"{settings.API_V1_PREFIX}/attachments/{att.id}/download"
    return out


@extra.get(
    "/harvest-intakes/{intake_id}/attachments",
    response_model=list[AttachmentOut],
    summary="Ekleri listele",
)
async def list_attachments(
    intake_id: int, session: SessionDep, _user: ReadHarvest
) -> list[AttachmentOut]:
    rows = (
        (await session.execute(select(Attachment).where(Attachment.intake_id == intake_id)))
        .scalars()
        .all()
    )
    out = []
    for r in rows:
        item = AttachmentOut.model_validate(r)
        item.url = f"{settings.API_V1_PREFIX}/attachments/{r.id}/download"
        out.append(item)
    return out


@extra.get("/attachments/{attachment_id}/download", summary="Ek indir")
async def download_attachment(
    attachment_id: int, session: SessionDep, _user: ReadHarvest
) -> Response:
    att = await get_or_404(session, Attachment, attachment_id, "Ek")
    path = UPLOADS_DIR / att.stored_name
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dosya diskte bulunamadı.")
    return Response(
        content=path.read_bytes(),
        media_type=att.content_type,
        headers={"Content-Disposition": f'attachment; filename="{att.filename}"'},
    )


@extra.delete("/attachments/{attachment_id}", response_model=Message, summary="Eki sil")
async def delete_attachment(
    attachment_id: int, request: Request, session: SessionDep, user: WriteHarvest
) -> Message:
    att = await get_or_404(session, Attachment, attachment_id, "Ek")
    path = UPLOADS_DIR / att.stored_name
    before = att.to_dict()
    await session.delete(att)
    await record_audit(
        session,
        action=AuditAction.SIL,
        entity_type="attachments",
        entity_id=attachment_id,
        summary=f"Ek silindi: {att.filename}",
        before=before,
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    if path.exists():
        path.unlink(missing_ok=True)
    return Message(detail="Ek silindi.")


routers = [
    vineyards_router,
    parcels_router,
    varieties_router,
    suppliers_router,
    intakes_router,
    extra,
]
