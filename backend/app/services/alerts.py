"""Uyari uretimi ve tekillestirme."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ops import Alert, AlertStatus


async def raise_alert(
    session: AsyncSession,
    *,
    category: str,
    severity: str,
    title: str,
    message: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
    ref_code: str | None = None,
    dedupe_key: str | None = None,
    ai_generated: bool = False,
    ai_provider: str | None = None,
) -> Alert | None:
    """Uyari olusturur. `dedupe_key` ile ayni uyarinin tekrari engellenir.

    Cagirici commit'ten sorumludur (islem butunlugu icin).
    """
    if dedupe_key:
        existing = (
            await session.execute(
                select(Alert).where(
                    Alert.dedupe_key == dedupe_key,
                    Alert.status.in_([AlertStatus.ACIK, AlertStatus.OKUNDU]),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return None

    alert = Alert(
        category=category,
        severity=severity,
        status=AlertStatus.ACIK,
        title=title[:220],
        message=message,
        ref_type=ref_type,
        ref_id=ref_id,
        ref_code=ref_code,
        dedupe_key=dedupe_key,
        ai_generated=ai_generated,
        ai_provider=ai_provider,
    )
    session.add(alert)
    return alert


async def resolve_alerts_for(
    session: AsyncSession, ref_type: str, ref_id: int, note: str = ""
) -> int:
    """Bir kaynaga bagli acik uyarilari cozuldu olarak isaretler."""
    rows = (
        (
            await session.execute(
                select(Alert).where(
                    Alert.ref_type == ref_type,
                    Alert.ref_id == ref_id,
                    Alert.status.in_([AlertStatus.ACIK, AlertStatus.OKUNDU]),
                )
            )
        )
        .scalars()
        .all()
    )
    now = dt.datetime.now(dt.UTC)
    for a in rows:
        a.status = AlertStatus.COZULDU
        a.resolved_at = now
        if note:
            a.resolution_note = note
    return len(rows)
