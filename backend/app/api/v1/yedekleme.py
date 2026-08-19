"""Veritabani yedekleme uc noktalari.

Yetki ayrimi bilinclidir:

  * ``backup:manage``   — yedek al, listele, sil, eskileri temizle
  * ``backup:download`` — yedek dosyasini makine disina cikar

Yedek dosyasi TUM veritabaninin kopyasidir: parola ozetleri, sifreli API
anahtarlari, denetim gunlugu ve kullanici e-postalari icerir. Bu yuzden yedek
ALMAK isletme sorumlulugu, yedegi DISARI CIKARMAK sistem yoneticisi
sorumlulugudur ve ikisi ayri yetkilerdir.

Geri yukleme ucu BILEREK YOKTUR; gerekcesi `services/yedekleme.py` icinde.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.core.audit import record_audit
from app.core.deps import SessionDep, require_perms
from app.core.permissions import Perm
from app.models.ops import AuditAction
from app.models.user import User
from app.services import yedekleme

router = APIRouter(prefix="/backups", tags=["Yedekleme"])

Yonet = Annotated[User, Depends(require_perms(Perm.BACKUP_MANAGE))]
Indir = Annotated[User, Depends(require_perms(Perm.BACKUP_DOWNLOAD))]


@router.get("", summary="Yedek listesi ve disk durumu")
async def yedekleri_listele(_user: Yonet) -> dict:
    return {
        "yedekler": [y.to_dict() for y in yedekleme.yedekleri_listele()],
        "disk": yedekleme.disk_durumu(),
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Yeni yedek al")
async def yedek_al(
    request: Request,
    session: SessionDep,
    user: Yonet,
    yuklemeler: bool = Query(False, description="Yüklenen belgeleri de arşivle"),
) -> dict:
    try:
        sonuc = await yedekleme.yedek_al(yuklemeler=yuklemeler)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, str(exc)) from exc
    except OSError as exc:
        # Disk dolu, izin yok vb. — kullaniciya anlasilir mesaj
        raise HTTPException(
            status.HTTP_507_INSUFFICIENT_STORAGE,
            f"Yedek yazılamadı: {exc}. Disk alanını ve klasör iznini kontrol edin.",
        ) from exc

    await record_audit(
        session,
        action=AuditAction.OLUSTUR,
        entity_type="backups",
        summary=f"Yedek alındı: {', '.join(y.ad for y in sonuc)}",
        after={"dosyalar": [y.to_dict() for y in sonuc]},
        user=user,
        request=request,
        commit=True,
    )
    return {"yedekler": [y.to_dict() for y in sonuc]}


@router.post("/temizle", summary="Eski yedekleri sil (saklama politikası)")
async def eskileri_temizle(
    request: Request,
    session: SessionDep,
    user: Yonet,
    saklanan: int = Query(
        yedekleme.VARSAYILAN_SAKLANAN, ge=1, le=500, description="Saklanacak yedek sayısı"
    ),
) -> dict:
    silinen = yedekleme.eskileri_temizle(saklanan)
    if silinen:
        await record_audit(
            session,
            action=AuditAction.SIL,
            entity_type="backups",
            summary=f"{len(silinen)} eski yedek silindi (saklanan: {saklanan})",
            after={"silinen": silinen},
            user=user,
            request=request,
            severity="uyari",
            commit=True,
        )
    return {"silinen": silinen, "saklanan": saklanan}


@router.get("/indir/{ad}", summary="Yedek dosyasını indir")
async def yedek_indir(
    ad: str, request: Request, session: SessionDep, user: Indir
) -> FileResponse:
    try:
        yol = yedekleme.yedek_yolu(ad)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not yol.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Yedek bulunamadı: {ad}")

    # Yedegin makine disina cikmasi denetlenebilir olmali: kim, ne zaman,
    # hangi dosyayi indirdi.
    await record_audit(
        session,
        action=AuditAction.DISA_AKTAR,
        entity_type="backups",
        entity_code=ad,
        summary=f"Yedek indirildi: {ad}",
        user=user,
        request=request,
        severity="uyari",
        commit=True,
    )
    return FileResponse(yol, filename=ad, media_type="application/octet-stream")


@router.delete("/{ad}", summary="Yedek sil")
async def yedek_sil(ad: str, request: Request, session: SessionDep, user: Yonet) -> dict:
    try:
        yol = yedekleme.yedek_yolu(ad)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not yol.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Yedek bulunamadı: {ad}")

    yedekleme.yedek_sil(ad)
    await record_audit(
        session,
        action=AuditAction.SIL,
        entity_type="backups",
        entity_code=ad,
        summary=f"Yedek silindi: {ad}",
        user=user,
        request=request,
        severity="uyari",
        commit=True,
    )
    return {"silinen": ad}
