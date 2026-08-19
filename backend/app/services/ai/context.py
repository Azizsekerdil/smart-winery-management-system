"""Modele gonderilecek saraphane veri baglaminin hazirlanmasi.

Gizlilik ilkesi (madde 11): Dis saglayiciya veri gonderilmeden ONCE kullaniciya
"hangi saglayiciya, hangi veriler gidecek" ozeti gosterilir ve onayi alinir.
`build_context` hem metni hem de bu ozeti uretir.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ops import Alert, AlertStatus
from app.models.production import (
    Fermentation,
    FermentationReading,
    Lot,
    LotStatus,
    Tank,
)
from app.models.quality import LabResult
from app.models.vineyard import GrapeVariety

MAX_READINGS = 40


@dataclass(slots=True)
class WineryContext:
    text: str
    items: list[dict[str, Any]] = field(default_factory=list)

    @property
    def approx_chars(self) -> int:
        return len(self.text)


def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:g}{suffix}"
    return f"{value}{suffix}"


async def build_context(
    session: AsyncSession,
    *,
    lot_ids: list[int] | None = None,
    fermentation_ids: list[int] | None = None,
    include_dashboard: bool = False,
) -> WineryContext:
    """Secilen kayitlardan modele verilecek metni ve veri kapsami listesini uretir."""
    blocks: list[str] = []
    items: list[dict[str, Any]] = []

    # ------------------------------------------------------------- partiler
    for lot_id in lot_ids or []:
        lot = await session.get(Lot, lot_id)
        if lot is None:
            continue
        variety = await session.get(GrapeVariety, lot.variety_id) if lot.variety_id else None
        tank = await session.get(Tank, lot.current_tank_id) if lot.current_tank_id else None

        lines = [
            f"### Parti {lot.code} — {lot.name}",
            f"- Rekolte: {lot.vintage_year}, Şarap tipi: {lot.wine_type}",
            f"- Çeşit: {variety.name if variety else '—'}"
            + (" (kupaj)" if lot.is_blend else ""),
            f"- Aşama: {lot.stage}, Durum: {lot.status}",
            f"- Hacim: {_fmt(float(lot.volume_l or 0), ' L')} "
            f"(başlangıç {_fmt(float(lot.initial_volume_l or 0), ' L')})",
            f"- Bulunduğu tank: {tank.code if tank else '—'}",
            "- Güncel analiz: "
            + ", ".join(
                [
                    f"Brix {_fmt(float(lot.current_brix) if lot.current_brix is not None else None)}",
                    f"pH {_fmt(float(lot.current_ph) if lot.current_ph is not None else None)}",
                    f"Alkol {_fmt(float(lot.current_alcohol) if lot.current_alcohol is not None else None, ' %vol')}",
                    f"TA {_fmt(float(lot.current_ta) if lot.current_ta is not None else None, ' g/L')}",
                    f"UA {_fmt(float(lot.current_va) if lot.current_va is not None else None, ' g/L')}",
                    f"Serbest SO₂ {_fmt(float(lot.current_free_so2) if lot.current_free_so2 is not None else None, ' mg/L')}",
                ]
            ),
        ]

        labs = (
            (
                await session.execute(
                    select(LabResult)
                    .where(LabResult.lot_id == lot.id)
                    .order_by(LabResult.analyzed_at.desc())
                    .limit(3)
                )
            )
            .scalars()
            .all()
        )
        if labs:
            lines.append("- Son laboratuvar sonuçları:")
            for r in labs:
                lines.append(
                    f"  * {r.analyzed_at:%Y-%m-%d} · pH {_fmt(float(r.ph) if r.ph is not None else None)}"
                    f" · TA {_fmt(float(r.total_acidity) if r.total_acidity is not None else None)}"
                    f" · UA {_fmt(float(r.volatile_acidity) if r.volatile_acidity is not None else None)}"
                    f" · SO₂ {_fmt(float(r.free_so2) if r.free_so2 is not None else None)}/"
                    f"{_fmt(float(r.total_so2) if r.total_so2 is not None else None)}"
                    f" · Alkol {_fmt(float(r.alcohol) if r.alcohol is not None else None)}"
                    + (" · SPEK. DIŞI" if r.out_of_spec else "")
                )

        blocks.append("\n".join(lines))
        items.append(
            {
                "tur": "Parti",
                "kod": lot.code,
                "ad": lot.name,
                "alanlar": "aşama, hacim, tank, güncel analiz değerleri, son 3 lab sonucu",
            }
        )

    # -------------------------------------------------------- fermantasyonlar
    for ferm_id in fermentation_ids or []:
        ferm = await session.get(Fermentation, ferm_id)
        if ferm is None:
            continue
        lot = await session.get(Lot, ferm.lot_id)
        readings = (
            (
                await session.execute(
                    select(FermentationReading)
                    .where(FermentationReading.fermentation_id == ferm.id)
                    .order_by(FermentationReading.measured_at.desc())
                    .limit(MAX_READINGS)
                )
            )
            .scalars()
            .all()
        )
        readings = list(reversed(readings))

        lines = [
            f"### Fermantasyon {ferm.code}",
            f"- Parti: {lot.code if lot else '—'}, Tür: {ferm.ferm_type}, Durum: {ferm.status}",
            f"- Başlangıç: {ferm.start_date:%Y-%m-%d}, Hacim: {_fmt(float(ferm.volume_l or 0), ' L')}",
            f"- Maya: {ferm.yeast_strain or '—'}"
            + (f" ({_fmt(float(ferm.yeast_dose_g_hl))} g/hL)" if ferm.yeast_dose_g_hl else ""),
            f"- Başlangıç Brix: {_fmt(float(ferm.initial_brix) if ferm.initial_brix is not None else None)}, "
            f"Hedef Brix: {_fmt(float(ferm.target_brix))}",
            f"- Sıcaklık aralığı: {_fmt(float(ferm.temp_min_c))}–{_fmt(float(ferm.temp_max_c))} °C",
            f"- Ölçümler (son {len(readings)}):",
            "  | Tarih | Sıc. °C | Brix | Yoğunluk | pH | Anomali |",
            "  |---|---|---|---|---|---|",
        ]
        for reading in readings:
            lines.append(
                f"  | {reading.measured_at:%d.%m %H:%M} "
                f"| {_fmt(float(reading.temperature_c) if reading.temperature_c is not None else None)} "
                f"| {_fmt(float(reading.brix) if reading.brix is not None else None)} "
                f"| {_fmt(float(reading.density) if reading.density is not None else None)} "
                f"| {_fmt(float(reading.ph) if reading.ph is not None else None)} "
                f"| {'EVET' if reading.is_anomaly else ''} |"
            )
        blocks.append("\n".join(lines))
        items.append(
            {
                "tur": "Fermantasyon",
                "kod": ferm.code,
                "ad": f"{lot.code if lot else ''} fermantasyonu",
                "alanlar": f"parametreler + son {len(readings)} ölçüm (sıcaklık, Brix, yoğunluk, pH)",
            }
        )

    # ----------------------------------------------------------------- pano
    if include_dashboard:
        active_lots = (
            await session.execute(
                select(func.count()).select_from(Lot).where(Lot.status == LotStatus.AKTIF)
            )
        ).scalar_one()
        total_volume = (
            await session.execute(
                select(func.coalesce(func.sum(Lot.volume_l), 0)).where(
                    Lot.status == LotStatus.AKTIF
                )
            )
        ).scalar_one()
        active_ferms = (
            await session.execute(
                select(func.count())
                .select_from(Fermentation)
                .where(Fermentation.status == "devam_ediyor")
            )
        ).scalar_one()
        alerts = (
            (
                await session.execute(
                    select(Alert)
                    .where(Alert.status == AlertStatus.ACIK)
                    .order_by(Alert.severity.desc())
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )
        tanks = (await session.execute(select(Tank).where(Tank.is_active.is_(True)))).scalars().all()
        capacity = sum(float(t.capacity_l) for t in tanks) or 1
        used = sum(float(t.current_volume_l) for t in tanks)

        lines = [
            "### İşletme genel durumu",
            f"- Aktif parti: {active_lots}, toplam hacim: {float(total_volume or 0):.0f} L",
            f"- Devam eden fermantasyon: {active_ferms}",
            f"- Tank doluluk: %{used / capacity * 100:.1f} ({len(tanks)} tank)",
            f"- Açık uyarı: {len(alerts)}",
        ]
        for a in alerts:
            lines.append(f"  * [{a.severity}] {a.title}")
        blocks.append("\n".join(lines))
        items.append(
            {
                "tur": "Pano özeti",
                "kod": "—",
                "ad": "İşletme genel durumu",
                "alanlar": "parti/tank/fermantasyon sayıları ve açık uyarı başlıkları",
            }
        )

    if not blocks:
        return WineryContext(text="", items=[])

    header = (
        "## ŞARAPHANE VERİLERİ\n"
        f"(Oluşturma: {dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M} UTC. "
        "Aşağıdaki veriler dışında bilgi uydurma.)\n"
    )
    return WineryContext(text=header + "\n\n".join(blocks), items=items)


PRIVACY_WARNINGS: dict[str, str] = {
    "yerel_only": (
        "Bu sağlayıcı bilgisayarınızda çalışır; veriler makineden çıkmaz."
    ),
    "dahili": (
        "Bu sağlayıcı kurum içi/sözleşmeli bir servistir. Yine de gönderilecek "
        "veri kapsamını kontrol edin."
    ),
    "herkese_acik": (
        "DİKKAT: Bu sağlayıcı harici bir bulut servisidir. Aşağıdaki veriler "
        "şaraphanenizin dışına gönderilecektir. Hassas veriler için yerel modeli "
        "(LM Studio) tercih edin."
    ),
}
