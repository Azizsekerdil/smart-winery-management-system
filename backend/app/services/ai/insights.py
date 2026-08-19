"""Yapay zeka destekli saraphane ozellikleri (sayisal cekirdek + istege bagli LLM yorumu).

Her ozellik once `app.services.ai_features` icindeki deterministik hesabi calistirir;
kullanici isterse ayni sonuc bir dil modeline yorumlatilir. Boylece saglayici
kapaliyken de ozellik CALISIR.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AITaskKind
from app.models.cellar import BottlingOrder
from app.models.inventory import InventoryItem, MovementType, StockMovement
from app.models.ops import Equipment
from app.models.production import (
    Fermentation,
    FermentationReading,
    Lot,
)
from app.models.quality import BlendComponent, BlendOperation, LabResult
from app.schemas.ai import InsightOut
from app.services.ai.base import ChatMessage, ProviderError
from app.services.ai.prompts import INSIGHT_PROMPTS, system_prompt
from app.services.ai.registry import chat_with_fallback
from app.services.ai_features import (
    assess_lot_risk,
    blend_prediction,
    detect_reading_anomaly,
    estimate_quality_score,
    forecast_depletion,
    next_maintenance_date,
    predict_fermentation_end,
)

DISCLAIMER = (
    "Karar destek amaçlıdır; üretim değerleri kullanıcı onayı olmadan değiştirilmez."
)


async def _add_llm_commentary(
    session: AsyncSession,
    insight: InsightOut,
    *,
    kind: str,
    payload: str,
    provider_key: str | None,
    user_id: int | None,
    confirm_external_share: bool = False,
) -> InsightOut:
    """Sayisal sonuca dil modeli yorumu ekler. Basarisiz olursa sessizce atlar.

    GIZLILIK: `payload` gercek saraphane verisidir (parti kodu, lab degerleri,
    hacim, maliyet). Kullanici harici paylasimi ONAYLAMADIYSA yalnizca yerel
    saglayici denenir; hicbir bulut saglayicisina veri gitmez. Sayisal cekirdek
    zaten calistigi icin ozellik onaysiz da tam sonuc uretir - yalnizca dil
    modeli yorumu eksilir.
    """
    instruction = INSIGHT_PROMPTS.get(kind, INSIGHT_PROMPTS["rapor"])
    messages = [
        ChatMessage("system", system_prompt(AITaskKind.SARAPHANE_DANISMANI)),
        ChatMessage("user", f"{instruction}\n\n{payload}"),
    ]
    try:
        result, resolved = await chat_with_fallback(
            session,
            messages,
            provider_key=provider_key,
            task_kind=AITaskKind.SARAPHANE_DANISMANI,
            temperature=0.3,
            max_tokens=700,
            user_id=user_id,
            allow_external=confirm_external_share,
        )
        insight.llm_commentary = result.content
        insight.provider_key = resolved.config.provider_key
        insight.model = result.model
    except ProviderError as exc:
        insight.llm_commentary = (
            "Dil modeli yorumu alınamadı; sayısal sonuç geçerlidir. "
            f"Sebep: {exc.safe_message}"
        )
    return insight


# ------------------------------------------------------ fermantasyon tahmini
async def fermentation_forecast(
    session: AsyncSession,
    ferm_id: int,
    *,
    use_llm: bool = False,
    provider_key: str | None = None,
    user_id: int | None = None,
    confirm_external_share: bool = False,
) -> InsightOut:
    ferm = await session.get(Fermentation, ferm_id)
    if ferm is None:
        raise ValueError(f"Fermantasyon bulunamadı: {ferm_id}")

    readings = list(
        (
            await session.execute(
                select(FermentationReading)
                .where(FermentationReading.fermentation_id == ferm_id)
                .order_by(FermentationReading.measured_at)
            )
        )
        .scalars()
        .all()
    )
    predicted, note = predict_fermentation_end(ferm, readings)
    lot = await session.get(Lot, ferm.lot_id)

    last = readings[-1] if readings else None
    numeric = {
        "olcum_sayisi": len(readings),
        "son_brix": float(last.brix) if last and last.brix is not None else None,
        "hedef_brix": float(ferm.target_brix),
        "tahmini_bitis": predicted.isoformat() if predicted else None,
        "kalan_gun": (predicted - dt.datetime.now(dt.UTC)).days if predicted else None,
        "aciklama": note,
    }
    summary = (
        f"{ferm.code} için tahmini bitiş: "
        + (predicted.strftime("%d.%m.%Y %H:%M") if predicted else "hesaplanamadı")
        + f". {note or ''}"
    )
    insight = InsightOut(
        kind="fermantasyon_tahmin",
        title=f"Fermantasyon bitiş tahmini — {ferm.code}",
        summary=summary.strip(),
        severity="uyari" if predicted is None else "bilgi",
        confidence=0.75 if predicted else 0.2,
        numeric=numeric,
        generated_at=dt.datetime.now(dt.UTC),
        disclaimer=DISCLAIMER,
    )
    if use_llm:
        payload = (
            f"Parti: {lot.code if lot else '—'}\n"
            f"Fermantasyon: {ferm.code}, tür {ferm.ferm_type}\n"
            f"Başlangıç Brix: {ferm.initial_brix}, hedef: {ferm.target_brix}\n"
            f"Sıcaklık aralığı: {ferm.temp_min_c}-{ferm.temp_max_c} °C\n"
            f"Sayısal tahmin: {numeric}\n"
            "Son ölçümler:\n"
            + "\n".join(
                f"- {r.measured_at:%d.%m %H:%M}: Brix {r.brix}, {r.temperature_c} °C"
                for r in readings[-10:]
            )
        )
        insight = await _add_llm_commentary(
            session, insight, kind="fermantasyon_tahmin", payload=payload,
            provider_key=provider_key, user_id=user_id,
            confirm_external_share=confirm_external_share,
        )
    return insight


# -------------------------------------------------------------- anomaliler
async def fermentation_anomalies(
    session: AsyncSession,
    ferm_id: int,
    *,
    use_llm: bool = False,
    provider_key: str | None = None,
    user_id: int | None = None,
    confirm_external_share: bool = False,
) -> InsightOut:
    ferm = await session.get(Fermentation, ferm_id)
    if ferm is None:
        raise ValueError(f"Fermantasyon bulunamadı: {ferm_id}")

    readings = list(
        (
            await session.execute(
                select(FermentationReading)
                .where(FermentationReading.fermentation_id == ferm_id)
                .order_by(FermentationReading.measured_at)
            )
        )
        .scalars()
        .all()
    )
    found: list[dict[str, Any]] = []
    for index, reading in enumerate(readings):
        is_anom, reason = detect_reading_anomaly(ferm, readings[:index], reading)
        if is_anom:
            found.append(
                {
                    "tarih": reading.measured_at.isoformat(),
                    "brix": float(reading.brix) if reading.brix is not None else None,
                    "sicaklik": float(reading.temperature_c)
                    if reading.temperature_c is not None
                    else None,
                    "gerekce": reason,
                }
            )

    severity = "kritik" if len(found) >= 3 else "uyari" if found else "bilgi"
    insight = InsightOut(
        kind="anomali",
        title=f"Anomali taraması — {ferm.code}",
        summary=(
            f"{len(readings)} ölçümde {len(found)} anomali tespit edildi."
            if found
            else f"{len(readings)} ölçümde anomali tespit edilmedi."
        ),
        severity=severity,
        confidence=0.8,
        numeric={"olcum_sayisi": len(readings), "anomali_sayisi": len(found), "anomaliler": found},
        generated_at=dt.datetime.now(dt.UTC),
        disclaimer=DISCLAIMER,
    )
    if use_llm and found:
        payload = f"Fermantasyon {ferm.code}. Tespit edilen anomaliler:\n" + "\n".join(
            f"- {a['tarih']}: {a['gerekce']}" for a in found
        )
        insight = await _add_llm_commentary(
            session, insight, kind="anomali", payload=payload,
            provider_key=provider_key, user_id=user_id,
            confirm_external_share=confirm_external_share,
        )
    return insight


# ------------------------------------------------------- laboratuvar yorumu
async def explain_lab_result(
    session: AsyncSession,
    result_id: int,
    *,
    use_llm: bool = True,
    provider_key: str | None = None,
    user_id: int | None = None,
    confirm_external_share: bool = False,
) -> InsightOut:
    result = await session.get(LabResult, result_id)
    if result is None:
        raise ValueError(f"Analiz sonucu bulunamadı: {result_id}")
    lot = await session.get(Lot, result.lot_id) if result.lot_id else None

    score = estimate_quality_score(
        ph=float(result.ph) if result.ph is not None else None,
        total_acidity=float(result.total_acidity) if result.total_acidity is not None else None,
        volatile_acidity=float(result.volatile_acidity)
        if result.volatile_acidity is not None
        else None,
        free_so2=float(result.free_so2) if result.free_so2 is not None else None,
        alcohol=float(result.alcohol) if result.alcohol is not None else None,
        wine_type=lot.wine_type if lot else "kirmizi",
    )

    insight = InsightOut(
        kind="lab_yorum",
        title=f"Laboratuvar yorumu — {result.code}",
        summary=(
            f"Kalite puanı {score.score}/100 (sınıf {score.grade}). "
            + (result.out_of_spec_details or "Tüm parametreler spesifikasyon içinde.")
        ),
        severity="uyari" if result.out_of_spec else "bilgi",
        confidence=score.confidence,
        numeric={
            "kalite_puani": score.score,
            "sinif": score.grade,
            "faktorler": score.factors,
            "spek_disi": result.out_of_spec,
        },
        generated_at=dt.datetime.now(dt.UTC),
        disclaimer=DISCLAIMER,
    )
    if use_llm:
        payload = (
            f"Parti: {lot.code if lot else '—'} ({lot.wine_type if lot else '—'})\n"
            f"pH: {result.ph}, TA: {result.total_acidity} g/L, "
            f"UA: {result.volatile_acidity} g/L\n"
            f"Serbest SO₂: {result.free_so2} mg/L, Toplam SO₂: {result.total_so2} mg/L\n"
            f"Alkol: {result.alcohol} %vol, Kalıntı şeker: {result.residual_sugar} g/L\n"
            f"Malik asit: {result.malic_acid}, Laktik asit: {result.lactic_acid}\n"
            f"Spesifikasyon dışı: {result.out_of_spec_details or 'yok'}\n"
            f"Sayısal kalite puanı: {score.score}/100 ({score.grade})"
        )
        insight = await _add_llm_commentary(
            session, insight, kind="lab_yorum", payload=payload,
            provider_key=provider_key, user_id=user_id,
            confirm_external_share=confirm_external_share,
        )
    return insight


# ------------------------------------------------------------ riskli parti
async def lot_risk(
    session: AsyncSession,
    lot_id: int,
    *,
    use_llm: bool = False,
    provider_key: str | None = None,
    user_id: int | None = None,
    confirm_external_share: bool = False,
) -> InsightOut:
    lot = await session.get(Lot, lot_id)
    if lot is None:
        raise ValueError(f"Parti bulunamadı: {lot_id}")

    last_lab = (
        await session.execute(
            select(LabResult.analyzed_at)
            .where(LabResult.lot_id == lot_id)
            .order_by(LabResult.analyzed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    days_since = None
    if last_lab is not None:
        ref = last_lab if last_lab.tzinfo else last_lab.replace(tzinfo=dt.UTC)
        days_since = (dt.datetime.now(dt.UTC) - ref).days

    anomalies = (
        await session.execute(
            select(func.count())
            .select_from(FermentationReading)
            .join(Fermentation, Fermentation.id == FermentationReading.fermentation_id)
            .where(Fermentation.lot_id == lot_id, FermentationReading.is_anomaly.is_(True))
        )
    ).scalar_one()

    level, reasons = assess_lot_risk(
        volatile_acidity=float(lot.current_va) if lot.current_va is not None else None,
        free_so2=float(lot.current_free_so2) if lot.current_free_so2 is not None else None,
        ph=float(lot.current_ph) if lot.current_ph is not None else None,
        days_since_last_lab=days_since,
        stage=lot.stage,
        anomaly_count=anomalies,
    )

    insight = InsightOut(
        kind="riskli_parti",
        title=f"Risk değerlendirmesi — {lot.code}",
        summary=f"Risk seviyesi: {level}. " + " ".join(reasons),
        severity="kritik" if level == "yuksek" else "uyari" if level == "orta" else "bilgi",
        confidence=0.7,
        numeric={
            "risk": level,
            "gerekceler": reasons,
            "son_lab_gun": days_since,
            "anomali_sayisi": anomalies,
        },
        generated_at=dt.datetime.now(dt.UTC),
        disclaimer=DISCLAIMER,
    )
    if use_llm:
        payload = (
            f"Parti {lot.code} ({lot.name}), aşama {lot.stage}\n"
            f"Risk: {level}\nGerekçeler: {'; '.join(reasons)}"
        )
        insight = await _add_llm_commentary(
            session, insight, kind="riskli_parti", payload=payload,
            provider_key=provider_key, user_id=user_id,
            confirm_external_share=confirm_external_share,
        )
    return insight


# ----------------------------------------------------------- kalite puani
async def quality_score(session: AsyncSession, lot_id: int) -> InsightOut:
    lot = await session.get(Lot, lot_id)
    if lot is None:
        raise ValueError(f"Parti bulunamadı: {lot_id}")
    score = estimate_quality_score(
        brix=float(lot.current_brix) if lot.current_brix is not None else None,
        ph=float(lot.current_ph) if lot.current_ph is not None else None,
        total_acidity=float(lot.current_ta) if lot.current_ta is not None else None,
        volatile_acidity=float(lot.current_va) if lot.current_va is not None else None,
        free_so2=float(lot.current_free_so2) if lot.current_free_so2 is not None else None,
        alcohol=float(lot.current_alcohol) if lot.current_alcohol is not None else None,
        wine_type=lot.wine_type,
    )
    return InsightOut(
        kind="kalite_puani",
        title=f"Kalite puanı tahmini — {lot.code}",
        summary=f"{score.score}/100 (sınıf {score.grade}), güven {score.confidence:.0%}",
        severity="uyari" if score.score < 60 else "bilgi",
        confidence=score.confidence,
        numeric={"puan": score.score, "sinif": score.grade, "faktorler": score.factors},
        generated_at=dt.datetime.now(dt.UTC),
        disclaimer=DISCLAIMER,
    )


# ------------------------------------------------------ kupaj karsilastirma
async def compare_blends(
    session: AsyncSession,
    blend_ids: list[int],
    *,
    use_llm: bool = False,
    provider_key: str | None = None,
    user_id: int | None = None,
    confirm_external_share: bool = False,
) -> InsightOut:
    scenarios: list[dict[str, Any]] = []
    for blend_id in blend_ids:
        blend = await session.get(BlendOperation, blend_id)
        if blend is None:
            continue
        comps = (
            (
                await session.execute(
                    select(BlendComponent).where(BlendComponent.blend_id == blend.id)
                )
            )
            .scalars()
            .all()
        )
        payload = []
        parts = []
        for c in comps:
            lot = await session.get(Lot, c.source_lot_id)
            payload.append(
                {
                    "volume_l": float(c.volume_l),
                    "alcohol": float(lot.current_alcohol)
                    if lot and lot.current_alcohol is not None
                    else None,
                    "ph": float(lot.current_ph) if lot and lot.current_ph is not None else None,
                    "ta": float(lot.current_ta) if lot and lot.current_ta is not None else None,
                    "cost_l": float(c.unit_cost_l or 0),
                }
            )
            parts.append(f"{lot.code if lot else c.source_lot_id}: {float(c.volume_l):.0f} L")
        pred = blend_prediction(payload)
        scenarios.append(
            {
                "kod": blend.code,
                "ad": blend.name,
                "bilesenler": parts,
                "toplam_hacim_l": pred["volume_l"],
                "tahmini_alkol": pred["alcohol"],
                "tahmini_ph": pred["ph"],
                "tahmini_ta": pred["ta"],
                "tahmini_maliyet": pred["cost"],
            }
        )

    if not scenarios:
        raise ValueError("Karşılaştırılacak kupaj senaryosu bulunamadı.")

    insight = InsightOut(
        kind="kupaj_karsilastirma",
        title=f"{len(scenarios)} kupaj senaryosu karşılaştırması",
        summary="; ".join(
            f"{s['kod']}: {s['toplam_hacim_l']:.0f} L, alkol {s['tahmini_alkol']}, "
            f"pH {s['tahmini_ph']}"
            for s in scenarios
        ),
        confidence=0.8,
        numeric={"senaryolar": scenarios},
        generated_at=dt.datetime.now(dt.UTC),
        disclaimer=DISCLAIMER,
    )
    if use_llm:
        payload_text = "\n\n".join(
            f"Senaryo {s['kod']} — {s['ad']}\n"
            f"Bileşenler: {', '.join(s['bilesenler'])}\n"
            f"Hacim {s['toplam_hacim_l']} L, alkol {s['tahmini_alkol']} %vol, "
            f"pH {s['tahmini_ph']}, TA {s['tahmini_ta']} g/L, "
            f"maliyet {s['tahmini_maliyet']} TRY"
            for s in scenarios
        )
        insight = await _add_llm_commentary(
            session, insight, kind="kupaj_karsilastirma", payload=payload_text,
            provider_key=provider_key, user_id=user_id,
            confirm_external_share=confirm_external_share,
        )
    return insight


# ------------------------------------------------------------ stok tahmini
async def stock_forecast(session: AsyncSession, *, days: int = 90) -> InsightOut:
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    items = (
        (
            await session.execute(
                select(InventoryItem).where(InventoryItem.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    from app.services.inventory import on_hand

    rows: list[dict[str, Any]] = []
    for item in items:
        moves = (
            (
                await session.execute(
                    select(StockMovement).where(
                        StockMovement.item_id == item.id,
                        StockMovement.occurred_at >= since,
                        StockMovement.movement_type.in_(
                            [MovementType.CIKIS, MovementType.URETIM_TUKETIM]
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not moves:
            continue
        daily: dict[dt.date, float] = {}
        for m in moves:
            day = m.occurred_at.date()
            daily[day] = daily.get(day, 0) + abs(float(m.quantity))
        qty = await on_hand(session, item.id)
        forecast = forecast_depletion(qty, list(daily.values()), min_stock=float(item.min_stock or 0))
        if forecast["days_left"] is not None and forecast["days_left"] < 120:
            rows.append(
                {
                    "kod": item.code,
                    "ad": item.name,
                    "mevcut": round(qty, 3),
                    "birim": item.unit,
                    "gunluk_ortalama": forecast["avg_daily"],
                    "kalan_gun": forecast["days_left"],
                    "min_stoga_gun": forecast["days_to_min"],
                }
            )
    rows.sort(key=lambda r: r["kalan_gun"] or 999)

    critical = [r for r in rows if (r["kalan_gun"] or 999) < 30]
    return InsightOut(
        kind="stok_tahmin",
        title="Stok tükenme tahmini",
        summary=(
            f"{len(rows)} kalem için tahmin üretildi; {len(critical)} kalem 30 günden "
            "kısa sürede tükenecek."
            if rows
            else "Tahmin için yeterli tüketim geçmişi bulunamadı."
        ),
        severity="uyari" if critical else "bilgi",
        confidence=0.6,
        numeric={"kalemler": rows[:40], "kritik_sayisi": len(critical)},
        generated_at=dt.datetime.now(dt.UTC),
        disclaimer=DISCLAIMER,
    )


# ------------------------------------------------------------ bakim tahmini
async def maintenance_forecast(session: AsyncSession) -> InsightOut:
    rows = (
        (
            await session.execute(
                select(Equipment).where(Equipment.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    items: list[dict[str, Any]] = []
    for e in rows:
        predicted = next_maintenance_date(e.last_maintenance_at, e.maintenance_interval_days)
        if predicted is None:
            continue
        left = (predicted - dt.date.today()).days
        items.append(
            {
                "kod": e.code,
                "ad": e.name,
                "tur": e.equipment_type,
                "son_bakim": e.last_maintenance_at.isoformat() if e.last_maintenance_at else None,
                "tahmini_bakim": predicted.isoformat(),
                "kalan_gun": left,
                "gecikmis": left < 0,
            }
        )
    items.sort(key=lambda x: x["kalan_gun"])
    overdue = [i for i in items if i["gecikmis"]]
    return InsightOut(
        kind="bakim_tahmin",
        title="Bakım zamanı tahmini",
        summary=(
            f"{len(items)} ekipman için plan üretildi; {len(overdue)} tanesi gecikmiş."
            if items
            else "Bakım aralığı tanımlı ekipman bulunamadı."
        ),
        severity="uyari" if overdue else "bilgi",
        confidence=0.65,
        numeric={"ekipmanlar": items[:40], "gecikmis_sayisi": len(overdue)},
        generated_at=dt.datetime.now(dt.UTC),
        disclaimer=DISCLAIMER,
    )


# ---------------------------------------------------------- dogal dil rapor
async def natural_language_report(
    session: AsyncSession,
    *,
    lot_id: int | None = None,
    provider_key: str | None = None,
    user_id: int | None = None,
    confirm_external_share: bool = False,
) -> InsightOut:
    from app.services.ai.context import build_context
    from app.services.costing import compute_lot_cost

    ctx = await build_context(
        session,
        lot_ids=[lot_id] if lot_id else None,
        include_dashboard=lot_id is None,
    )
    cost_text = ""
    if lot_id:
        cb = await compute_lot_cost(session, lot_id)
        cost_text = (
            f"\n\nMaliyet: toplam {cb.total_cost} TRY, litre başı {cb.cost_per_liter} TRY"
            + (f", şişe başı {cb.cost_per_bottle} TRY" if cb.cost_per_bottle else "")
            + f", fire %{cb.loss_percent}"
        )
        bottles = (
            await session.execute(
                select(func.coalesce(func.sum(BottlingOrder.produced_bottles), 0)).where(
                    BottlingOrder.lot_id == lot_id
                )
            )
        ).scalar_one()
        cost_text += f", üretilen şişe: {int(bottles or 0)}"

    insight = InsightOut(
        kind="rapor",
        title="Doğal dil raporu",
        summary="Rapor dil modeli tarafından oluşturuluyor…",
        confidence=None,
        numeric={"veri_kapsami": ctx.items},
        generated_at=dt.datetime.now(dt.UTC),
        disclaimer=DISCLAIMER,
    )
    insight = await _add_llm_commentary(
        session,
        insight,
        kind="rapor",
        payload=ctx.text + cost_text,
        provider_key=provider_key,
        user_id=user_id,
        confirm_external_share=confirm_external_share,
    )
    insight.summary = (insight.llm_commentary or "")[:400] or "Rapor üretilemedi."
    return insight
