"""Denetim gunlugu yardimcilari.

Kritik kayit degisikliklerinde once/sonra degerleri saklanir; hassas alanlar
`app.core.logging.SENSITIVE_FIELD_NAMES` uyarinca maskelenir.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import SENSITIVE_FIELD_NAMES, scrub
from app.models.ops import AuditAction, AuditLog

_MASK = "***GIZLI***"


def _sanitize(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    out: dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_FIELD_NAMES:
            out[k] = _MASK
        else:
            out[k] = scrub(v)
    return out


def diff_fields(
    before: dict[str, Any] | None, after: dict[str, Any] | None
) -> list[str]:
    if not before or not after:
        return []
    return sorted(
        k
        for k in set(before) | set(after)
        if k not in {"updated_at", "created_at"} and before.get(k) != after.get(k)
    )


async def record_audit(
    session: AsyncSession,
    *,
    action: AuditAction | str,
    entity_type: str,
    entity_id: int | None = None,
    entity_code: str | None = None,
    summary: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    user: Any | None = None,
    request: Request | None = None,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    agent_task_id: int | None = None,
    severity: str = "bilgi",
    commit: bool = False,
) -> AuditLog:
    """Denetim kaydi olusturur. Cagirici islemi ayni islem (transaction) icinde
    tutabilmesi icin varsayilan olarak commit ETMEZ."""
    before_s = _sanitize(before)
    after_s = _sanitize(after)

    log = AuditLog(
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
        action=str(action),
        entity_type=entity_type,
        entity_id=entity_id,
        entity_code=entity_code,
        summary=summary[:400],
        before_data=before_s,
        after_data=after_s,
        changed_fields=diff_fields(before_s, after_s) or None,
        ip_address=_client_ip(request),
        user_agent=(request.headers.get("user-agent", "")[:255] if request else None),
        request_path=(str(request.url.path)[:255] if request else None),
        request_method=(request.method if request else None),
        ai_provider=ai_provider,
        ai_model=ai_model,
        agent_task_id=agent_task_id,
        severity=severity,
    )
    session.add(log)
    if commit:
        await session.commit()
    else:
        await session.flush()
    return log


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    # Ters vekil arkasindaysa X-Forwarded-For ilk degeri
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host[:64] if request.client else None
