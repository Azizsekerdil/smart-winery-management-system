"""Yapay zeka destekli saraphane ozelliklerinin SAYISAL cekirdegi.

Bu modul dil modeli KULLANMAZ; deterministik, test edilebilir istatistiksel
hesaplar yapar. Dil modeli yorumu `app.services.ai.insights` katmaninda,
bu sonuclarin uzerine eklenir. Boylece:
  * saglayici kapaliyken de ozellikler calisir,
  * sonuclar tekrarlanabilir ve testlenebilir olur,
  * hassas veri zorunlu olmadikca disari cikmaz.

Tum ciktilar KARAR DESTEK niteligindedir.
"""

from __future__ import annotations

import datetime as dt
import math
import statistics
from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------- yardimcilar
def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def _hours_between(a: dt.datetime, b: dt.datetime) -> float:
    return (_aware(b) - _aware(a)).total_seconds() / 3600.0


# ------------------------------------------------- fermantasyon bitis tahmini
def predict_fermentation_end(
    ferm: Any, readings: list[Any]
) -> tuple[dt.datetime | None, str | None]:
    """Brix dususu egiminden tahmini bitis tarihi.

    Yontem: son 5 olcumun dogrusal regresyonu (en kucuk kareler) ile Brix/saat
    hizi bulunur, hedef Brix'e kalan sure hesaplanir. Hiz cok dusukse veya
    yeterli veri yoksa None doner.
    """
    points = [
        (_aware(r.measured_at), _f(r.brix))
        for r in readings
        if _f(r.brix) is not None
    ]
    if len(points) < 3:
        return None, "Tahmin için en az 3 Brix ölçümü gerekir."

    points.sort(key=lambda p: p[0])
    window = points[-5:]
    t0 = window[0][0]
    xs = [_hours_between(t0, t) for t, _ in window]
    ys = [b for _, b in window if b is not None]
    if len(xs) != len(ys) or len(xs) < 3:
        return None, "Tahmin için yeterli veri yok."

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return None, "Ölçümler aynı zaman damgasına sahip; eğim hesaplanamıyor."

    slope = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n)) / denom  # Brix/saat

    last_time, last_brix = window[-1]
    target = _f(ferm.target_brix) or 0.0
    remaining = (last_brix or 0.0) - target

    if remaining <= 0:
        return last_time, "Hedef Brix değerine ulaşıldı."
    if slope >= -0.005:  # saatte 0.005 Brix'ten yavaş = pratikte durmuş
        return None, (
            "Brix düşüşü durmuş görünüyor (takılmış fermantasyon riski). "
            "Sıcaklık, besin ve maya canlılığı kontrol edilmeli."
        )

    hours_left = remaining / abs(slope)
    if hours_left > 24 * 60:
        return None, "Tahmini süre 60 günden uzun; eğim güvenilir değil."

    predicted = _aware(last_time) + dt.timedelta(hours=hours_left)
    note = (
        f"Son {n} ölçüme göre hız {abs(slope):.3f} Brix/saat "
        f"({abs(slope) * 24:.2f} Brix/gün). Kalan {remaining:.1f} Brix."
    )
    return predicted, note


# ------------------------------------------------------------ anomali tespiti
def detect_reading_anomaly(
    ferm: Any, previous: list[Any], new: Any
) -> tuple[bool, str | None]:
    """Yeni olcumu gecmise gore degerlendirir.

    Kontroller:
      1. Sicaklik hedef araligin disinda mi
      2. Brix yukselmis mi (fiziksel olarak beklenmez)
      3. Brix dususu durmus mu (takilmis fermantasyon)
      4. Sicaklik sicramasi (saatlik degisim asiri)
      5. Ucucu asitlik esigi (0.9 g/L uyari, kirmizi icin 1.2 kritik)
      6. pH ani sapma
    """
    reasons: list[str] = []

    temp = _f(new.temperature_c)
    tmin, tmax = _f(ferm.temp_min_c) or 0.0, _f(ferm.temp_max_c) or 40.0
    if temp is not None:
        if temp > tmax:
            reasons.append(f"Sıcaklık üst sınırın üzerinde: {temp:.1f} °C > {tmax:.1f} °C")
        elif temp < tmin:
            reasons.append(f"Sıcaklık alt sınırın altında: {temp:.1f} °C < {tmin:.1f} °C")

    prev_sorted = sorted(
        (p for p in previous if p.measured_at is not None),
        key=lambda p: _aware(p.measured_at),
    )
    last = prev_sorted[-1] if prev_sorted else None

    brix = _f(new.brix)
    if last is not None and brix is not None:
        prev_brix = _f(last.brix)
        if prev_brix is not None:
            delta = brix - prev_brix
            if delta > 0.5:
                reasons.append(
                    f"Brix beklenmedik şekilde yükseldi: {prev_brix:.1f} → {brix:.1f}. "
                    "Ölçüm hatası veya tanka ekleme olabilir."
                )
            hours = _hours_between(last.measured_at, new.measured_at)
            if hours >= 18 and abs(delta) < 0.2 and brix > (_f(ferm.target_brix) or 0) + 2:
                reasons.append(
                    f"Son {hours:.0f} saatte Brix neredeyse değişmedi "
                    f"({prev_brix:.1f} → {brix:.1f}). Takılmış fermantasyon riski."
                )

        prev_temp = _f(last.temperature_c)
        if prev_temp is not None and temp is not None:
            hours = max(1.0, _hours_between(last.measured_at, new.measured_at))
            rate = abs(temp - prev_temp) / hours
            if rate > 1.5:
                reasons.append(
                    f"Hızlı sıcaklık değişimi: saatte {rate:.1f} °C "
                    f"({prev_temp:.1f} → {temp:.1f} °C)."
                )

    va = _f(new.volatile_acidity)
    if va is not None:
        if va >= 1.2:
            reasons.append(f"Uçucu asitlik kritik seviyede: {va:.2f} g/L (≥1.20).")
        elif va >= 0.9:
            reasons.append(f"Uçucu asitlik yükseliyor: {va:.2f} g/L (≥0.90).")

    ph = _f(new.ph)
    if ph is not None:
        if ph > 4.0:
            reasons.append(f"pH çok yüksek: {ph:.2f} (mikrobiyolojik risk).")
        elif ph < 2.8:
            reasons.append(f"pH çok düşük: {ph:.2f}.")
        prev_phs = [_f(p.ph) for p in prev_sorted[-5:] if _f(p.ph) is not None]
        if len(prev_phs) >= 3:
            avg = statistics.fmean(prev_phs)  # type: ignore[arg-type]
            if abs(ph - avg) > 0.35:
                reasons.append(
                    f"pH son ölçümlerin ortalamasından ({avg:.2f}) belirgin saptı: {ph:.2f}."
                )

    return (bool(reasons), " ".join(reasons) if reasons else None)


# --------------------------------------------------------- kalite puani tahmini
@dataclass
class QualityScore:
    score: float
    grade: str
    factors: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5


def estimate_quality_score(
    *,
    brix: float | None = None,
    ph: float | None = None,
    total_acidity: float | None = None,
    volatile_acidity: float | None = None,
    free_so2: float | None = None,
    alcohol: float | None = None,
    rot_percent: float | None = None,
    wine_type: str = "kirmizi",
) -> QualityScore:
    """Basit, aciklanabilir agirlikli puanlama (0-100).

    Her parametre ideal araligina gore 0-1 arasi puanlanir; agirliklarla
    birlestirilir. Amac 'kara kutu' degil, gerekcesi gosterilebilir bir tahmin.
    """
    ideals: dict[str, tuple[float, float, float]] = {
        # parametre: (ideal_min, ideal_max, agirlik)
        "ph": (3.3, 3.7, 0.18) if wine_type == "kirmizi" else (3.0, 3.4, 0.18),
        "total_acidity": (5.0, 7.0, 0.15),
        "volatile_acidity": (0.0, 0.6, 0.22),
        "free_so2": (25.0, 45.0, 0.12),
        "alcohol": (12.0, 14.5, 0.13) if wine_type == "kirmizi" else (11.0, 13.5, 0.13),
        "brix": (21.0, 26.0, 0.12) if wine_type == "kirmizi" else (19.0, 24.0, 0.12),
        "rot_percent": (0.0, 2.0, 0.08),
    }
    values = {
        "ph": ph,
        "total_acidity": total_acidity,
        "volatile_acidity": volatile_acidity,
        "free_so2": free_so2,
        "alcohol": alcohol,
        "brix": brix,
        "rot_percent": rot_percent,
    }

    labels = {
        "ph": "pH",
        "total_acidity": "Toplam asitlik",
        "volatile_acidity": "Uçucu asitlik",
        "free_so2": "Serbest SO₂",
        "alcohol": "Alkol",
        "brix": "Brix",
        "rot_percent": "Çürük oranı",
    }

    total_weight = 0.0
    weighted = 0.0
    factors: list[dict[str, Any]] = []

    for key, (lo, hi, weight) in ideals.items():
        val = values.get(key)
        if val is None:
            continue
        span = max(hi - lo, 0.001)
        if lo <= val <= hi:
            sub = 1.0
        elif val < lo:
            sub = max(0.0, 1.0 - (lo - val) / span)
        else:
            sub = max(0.0, 1.0 - (val - hi) / span)
        weighted += sub * weight
        total_weight += weight
        factors.append(
            {
                "parametre": labels[key],
                "deger": round(val, 3),
                "ideal": f"{lo}–{hi}",
                "puan": round(sub * 100, 1),
                "agirlik": weight,
            }
        )

    if total_weight == 0:
        return QualityScore(score=0.0, grade="veri_yok", factors=[], confidence=0.0)

    score = round(weighted / total_weight * 100, 1)
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D"
    confidence = round(min(1.0, total_weight / sum(w for _, _, w in ideals.values())), 2)
    return QualityScore(score=score, grade=grade, factors=factors, confidence=confidence)


# -------------------------------------------------------------- riskli parti
def assess_lot_risk(
    *,
    volatile_acidity: float | None,
    free_so2: float | None,
    ph: float | None,
    days_since_last_lab: int | None,
    stage: str,
    anomaly_count: int = 0,
) -> tuple[str, list[str]]:
    """(risk_seviyesi, gerekceler) doner: dusuk | orta | yuksek."""
    reasons: list[str] = []
    score = 0

    if volatile_acidity is not None:
        if volatile_acidity >= 1.2:
            score += 3
            reasons.append(f"Uçucu asitlik kritik: {volatile_acidity:.2f} g/L")
        elif volatile_acidity >= 0.9:
            score += 2
            reasons.append(f"Uçucu asitlik yüksek: {volatile_acidity:.2f} g/L")

    if free_so2 is not None and stage not in ("uzum_kabul", "sira", "fermantasyon"):
        if free_so2 < 15:
            score += 2
            reasons.append(f"Serbest SO₂ düşük: {free_so2:.0f} mg/L (oksidasyon riski)")
        elif free_so2 < 25:
            score += 1
            reasons.append(f"Serbest SO₂ sınırda: {free_so2:.0f} mg/L")

    if ph is not None and ph > 3.85:
        score += 2
        reasons.append(f"pH yüksek: {ph:.2f} (mikrobiyolojik stabilite riski)")

    if days_since_last_lab is not None and days_since_last_lab > 45:
        score += 1
        reasons.append(f"{days_since_last_lab} gündür laboratuvar analizi yapılmamış")

    if anomaly_count >= 3:
        score += 2
        reasons.append(f"{anomaly_count} adet fermantasyon anomalisi kaydı var")
    elif anomaly_count > 0:
        score += 1
        reasons.append(f"{anomaly_count} adet fermantasyon anomalisi kaydı var")

    level = "yuksek" if score >= 4 else "orta" if score >= 2 else "dusuk"
    if not reasons:
        reasons.append("Bilinen risk göstergesi yok.")
    return level, reasons


# ----------------------------------------------------------- kupaj hesaplama
def blend_prediction(components: list[dict[str, Any]]) -> dict[str, float | None]:
    """Hacim agirlikli kupaj ongorusu.

    components: [{"volume_l": 100, "alcohol": 13.2, "ph": 3.5, "ta": 5.8, "cost_l": 12}]
    Not: pH logaritmik bir olcek oldugu icin dogrudan agirlikli ortalama
    yaklasiktir; H+ derisimi uzerinden hesaplanir (daha dogru).
    """
    total_v = sum(float(c.get("volume_l") or 0) for c in components)
    if total_v <= 0:
        return {"volume_l": 0.0, "alcohol": None, "ph": None, "ta": None, "cost": None}

    def wavg(key: str) -> float | None:
        pairs = [
            (float(c["volume_l"]), float(c[key]))
            for c in components
            if c.get(key) is not None and c.get("volume_l")
        ]
        if not pairs:
            return None
        v = sum(p[0] for p in pairs)
        return round(sum(p[0] * p[1] for p in pairs) / v, 3) if v else None

    # pH: H+ derisimi uzerinden
    ph_pairs = [
        (float(c["volume_l"]), float(c["ph"]))
        for c in components
        if c.get("ph") is not None and c.get("volume_l")
    ]
    ph_blend: float | None = None
    if ph_pairs:
        v = sum(p[0] for p in ph_pairs)
        h_total = sum(p[0] * (10 ** (-p[1])) for p in ph_pairs)
        ph_blend = round(-math.log10(h_total / v), 2) if v and h_total > 0 else None

    cost = sum(
        float(c["volume_l"]) * float(c.get("cost_l") or 0)
        for c in components
        if c.get("volume_l")
    )

    return {
        "volume_l": round(total_v, 2),
        "alcohol": wavg("alcohol"),
        "ph": ph_blend,
        "ta": wavg("ta"),
        "cost": round(cost, 2),
    }


# ------------------------------------------------------- stok tukenme tahmini
def forecast_depletion(
    on_hand: float, daily_usage: list[float], *, min_stock: float = 0.0
) -> dict[str, Any]:
    """Ortalama gunluk tuketimden tukenme tarihine kalan gun sayisi."""
    usable = [u for u in daily_usage if u > 0]
    if not usable or on_hand <= 0:
        return {
            "avg_daily": 0.0,
            "days_left": None,
            "days_to_min": None,
            "note": "Yeterli tüketim geçmişi yok veya stok sıfır.",
        }
    avg = statistics.fmean(usable)
    days_left = on_hand / avg if avg > 0 else None
    days_to_min = (on_hand - min_stock) / avg if avg > 0 and on_hand > min_stock else 0.0
    return {
        "avg_daily": round(avg, 3),
        "days_left": round(days_left, 1) if days_left is not None else None,
        "days_to_min": round(days_to_min, 1),
        "note": f"Son {len(usable)} günün ortalaması kullanıldı.",
    }


# ------------------------------------------------------- bakim zamani tahmini
def next_maintenance_date(
    last_at: dt.date | None, interval_days: int | None, *, usage_factor: float = 1.0
) -> dt.date | None:
    """Kullanim yogunluguna gore duzeltilmis bir sonraki bakim tarihi."""
    if last_at is None or not interval_days:
        return None
    factor = max(0.3, min(2.0, usage_factor))
    return last_at + dt.timedelta(days=int(interval_days / factor))
