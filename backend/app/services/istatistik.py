"""Saraphane istatistikleri.

Mevcut `/dashboard` ANLIK durum gosterir, `/reports/production` ise toplam kg
ve aylik dagilim verir. Burasi farkli bir soruyu cevaplar: **isletme nasil
gidiyor?** — verimlilik, kayip, kalite tutarliligi ve donem karsilastirmasi.

Tasarim kararlari:

* **Konu bazli uclar, tek bir `/statistics` degil.** Yetki matrisi buna izin
  vermez: `satis_personeli` `report:read` tasir ama `cost:read` ve `lab:read`
  TASIMAZ. Tek uc, maliyet ve laboratuvar verisini bu role sizdirirdi.
* **Tarih yerine rekolte yili.** Hasat ile siseleme arasinda 1-3 yil vardir;
  kayip zincirini takvim tarihiyle dilimlemek anlamsiz sonuc uretir.
* **Toplamalar SQL'de.** `bottling_orders.yield_percent` gibi Python
  ozellikleri GROUP BY'da kullanilamaz; satir bazinda kullanilirsa tum tablo
  bellege cekilir. Oranlar `SUM(...)/SUM(...)` olarak yeniden yazilmistir.
* **`compute_lot_cost` kullanilmaz.** Parti basina ~6 sorgu + ozyineleme
  yapar; istatistikte 300 parti icin cagrilmasi pratik degildir.

SQLite tuzaklari: `Numeric` toplamlari `Decimal` doner (float'a cevrilir),
`DATE_TRUNC` yoktur (`strftime('%Y-%m')`), saat dilimi saklanmaz.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cellar import Barrel, BarrelMovement, BottlingOrder, BottlingStatus
from app.models.inventory import InventoryItem, StockMovement
from app.models.ops import Equipment, MaintenanceLog
from app.models.production import Fermentation, Lot, LotSource, TankTransfer
from app.models.quality import LabResult, LabSample
from app.models.vineyard import GrapeVariety, HarvestIntake, Parcel, Vineyard


def _f(deger: Any) -> float:
    """Decimal/None guvenli float donusumu."""
    return float(deger or 0)


def _oran(bolen: float, bolunen: float) -> float | None:
    """Sifira bolmeyi None'a cevirir; arayuz '—' gosterir."""
    return round(bolen / bolunen, 4) if bolunen else None


# ============================================================ HASAT / BAG
async def hasat(session: AsyncSession, *, yil: int | None = None) -> dict:
    """Parsel ve cesit bazinda verim, kalite dagilimi, yil karsilastirmasi.

    Ham kilogram yaniltir: 40 dekarlik parselin 20 dekarliktan cok uretmesi
    basari degildir. Bu yuzden dekar basi verim de hesaplanir.
    """
    kosul = [HarvestIntake.vintage_year == yil] if yil else []

    # --- parsel bazinda verim
    parsel_sorgu = (
        select(
            Parcel.code,
            Parcel.name,
            Vineyard.name.label("bag"),
            Parcel.area_da,
            Parcel.vine_count,
            func.sum(HarvestIntake.net_weight_kg).label("kg"),
            func.avg(HarvestIntake.brix).label("brix"),
            func.avg(HarvestIntake.rot_percent).label("curuk"),
        )
        .join(HarvestIntake, HarvestIntake.parcel_id == Parcel.id)
        .join(Vineyard, Parcel.vineyard_id == Vineyard.id, isouter=True)
        .where(*kosul)
        .group_by(Parcel.id, Parcel.code, Parcel.name, Vineyard.name,
                  Parcel.area_da, Parcel.vine_count)
        .order_by(func.sum(HarvestIntake.net_weight_kg).desc())
    )
    parseller = []
    for r in (await session.execute(parsel_sorgu)).all():
        kg = _f(r.kg)
        alan = _f(r.area_da)
        parseller.append(
            {
                "kod": r.code,
                "ad": r.name,
                "bag": r.bag,
                "alan_da": alan or None,
                "kg": round(kg, 1),
                "kg_dekar": _oran(kg, alan) if alan else None,
                "kg_asma": _oran(kg, _f(r.vine_count)) if r.vine_count else None,
                "ort_brix": round(_f(r.brix), 2) if r.brix is not None else None,
                "ort_curuk_yuzde": round(_f(r.curuk), 2) if r.curuk is not None else None,
            }
        )

    # --- cesit bazinda
    cesit_sorgu = (
        select(
            GrapeVariety.name,
            func.sum(HarvestIntake.net_weight_kg).label("kg"),
            func.avg(HarvestIntake.brix).label("brix"),
            GrapeVariety.target_brix_min,
            GrapeVariety.target_brix_max,
        )
        .join(HarvestIntake, HarvestIntake.variety_id == GrapeVariety.id)
        .where(*kosul)
        .group_by(GrapeVariety.id, GrapeVariety.name,
                  GrapeVariety.target_brix_min, GrapeVariety.target_brix_max)
        .order_by(func.sum(HarvestIntake.net_weight_kg).desc())
    )
    cesitler = []
    for r in (await session.execute(cesit_sorgu)).all():
        brix = _f(r.brix) if r.brix is not None else None
        hedefte = None
        if brix is not None and r.target_brix_min is not None and r.target_brix_max is not None:
            hedefte = _f(r.target_brix_min) <= brix <= _f(r.target_brix_max)
        cesitler.append(
            {
                "ad": r.name,
                "kg": round(_f(r.kg), 1),
                "ort_brix": round(brix, 2) if brix is not None else None,
                "hedef_brix": (
                    f"{_f(r.target_brix_min):.0f}–{_f(r.target_brix_max):.0f}"
                    if r.target_brix_min is not None and r.target_brix_max is not None
                    else None
                ),
                "hedefte_mi": hedefte,
            }
        )

    # --- kalite sinifi dagilimi
    kalite = [
        {"sinif": r.quality_grade or "belirsiz", "kg": round(_f(r.kg), 1)}
        for r in (
            await session.execute(
                select(
                    HarvestIntake.quality_grade,
                    func.sum(HarvestIntake.net_weight_kg).label("kg"),
                )
                .where(*kosul)
                .group_by(HarvestIntake.quality_grade)
            )
        ).all()
    ]

    # --- yil karsilastirmasi (filtreden bagimsiz)
    yillar = [
        {
            "yil": r.vintage_year,
            "kg": round(_f(r.kg), 1),
            "ort_brix": round(_f(r.brix), 2) if r.brix is not None else None,
            "kabul_sayisi": r.adet,
        }
        for r in (
            await session.execute(
                select(
                    HarvestIntake.vintage_year,
                    func.sum(HarvestIntake.net_weight_kg).label("kg"),
                    func.avg(HarvestIntake.brix).label("brix"),
                    func.count().label("adet"),
                )
                .group_by(HarvestIntake.vintage_year)
                .order_by(HarvestIntake.vintage_year)
            )
        ).all()
    ]

    return {
        "yil": yil,
        "parseller": parseller,
        "cesitler": cesitler,
        "kalite_dagilimi": kalite,
        "yillar": yillar,
    }


# ============================================================ KAYIP ZINCIRI
async def fire(session: AsyncSession, *, yil: int | None = None) -> dict:
    """Üzümden şişeye hacim kaybı hunisi.

    İşletmecinin en çok para kaybettiği aşamayı gösterir. Takvim tarihiyle
    değil rekolte yılıyla dilimlenir.
    """
    lot_kosul = [Lot.vintage_year == yil] if yil else []

    uzum_kg = _f(
        (
            await session.execute(
                select(func.sum(LotSource.weight_kg))
                .join(Lot, LotSource.lot_id == Lot.id)
                .where(*lot_kosul)
            )
        ).scalar()
    )
    sira_l = _f(
        (
            await session.execute(
                select(func.sum(LotSource.juice_yield_l))
                .join(Lot, LotSource.lot_id == Lot.id)
                .where(*lot_kosul)
            )
        ).scalar()
    )
    transfer_kayip = _f(
        (
            await session.execute(
                select(func.sum(TankTransfer.loss_l))
                .join(Lot, TankTransfer.lot_id == Lot.id)
                .where(*lot_kosul)
            )
        ).scalar()
    )
    fici_kayip = _f(
        (
            await session.execute(
                select(func.sum(BarrelMovement.loss_l))
                .join(Lot, BarrelMovement.lot_id == Lot.id)
                .where(*lot_kosul)
            )
        ).scalar()
    )

    sise_satiri = (
        await session.execute(
            select(
                func.sum(BottlingOrder.produced_bottles).label("sise"),
                func.sum(BottlingOrder.used_volume_l).label("hacim"),
                func.sum(BottlingOrder.loss_l).label("kayip"),
                func.sum(BottlingOrder.rejected_bottles).label("fire_sise"),
            )
            .join(Lot, BottlingOrder.lot_id == Lot.id)
            .where(*lot_kosul)
        )
    ).one()

    sise = int(sise_satiri.sise or 0)
    siseleme_hacim = _f(sise_satiri.hacim)
    siseleme_kayip = _f(sise_satiri.kayip)

    return {
        "yil": yil,
        "huni": [
            {"asama": "Üzüm (kg)", "deger": round(uzum_kg, 1), "birim": "kg"},
            {"asama": "Şıra (L)", "deger": round(sira_l, 1), "birim": "L"},
            {
                "asama": "Şişelenen (L)",
                "deger": round(siseleme_hacim, 1),
                "birim": "L",
            },
        ],
        "kayiplar": [
            {"asama": "Tank transferi", "litre": round(transfer_kayip, 1)},
            {"asama": "Fıçı (buharlaşma)", "litre": round(fici_kayip, 1)},
            {"asama": "Şişeleme", "litre": round(siseleme_kayip, 1)},
        ],
        "ozet": {
            "uzum_kg": round(uzum_kg, 1),
            "sira_l": round(sira_l, 1),
            "sise_adet": sise,
            "fire_sise": int(sise_satiri.fire_sise or 0),
            # Sektor referansi: 1 kg uzumden ~0,65-0,75 L sira
            "sira_verimi_l_kg": _oran(sira_l, uzum_kg),
            "kg_sise_basina": _oran(uzum_kg, sise) if sise else None,
            "toplam_kayip_l": round(transfer_kayip + fici_kayip + siseleme_kayip, 1),
        },
    }


# ============================================================ LABORATUVAR
async def laboratuvar(
    session: AsyncSession, *, baslangic: dt.date | None = None, bitis: dt.date | None = None
) -> dict:
    """Spesifikasyon dışı oranı, parametre trendleri, onay döngü süresi."""
    bitis = bitis or dt.date.today()
    baslangic = baslangic or (bitis - dt.timedelta(days=365))
    kosul = [
        LabResult.analyzed_at >= dt.datetime.combine(baslangic, dt.time.min),
        LabResult.analyzed_at <= dt.datetime.combine(bitis, dt.time.max),
    ]

    toplam_satir = (
        await session.execute(
            select(
                func.count().label("adet"),
                func.sum(case((LabResult.out_of_spec.is_(True), 1), else_=0)).label("disi"),
            ).where(*kosul)
        )
    ).one()
    toplam = int(toplam_satir.adet or 0)
    spec_disi = int(toplam_satir.disi or 0)

    # --- aylik spesifikasyon disi orani
    ay = func.strftime("%Y-%m", LabResult.analyzed_at)
    aylik = [
        {
            "ay": r.ay,
            "analiz": int(r.adet),
            "spec_disi": int(r.disi or 0),
            "oran": _oran(int(r.disi or 0), int(r.adet)),
        }
        for r in (
            await session.execute(
                select(
                    ay.label("ay"),
                    func.count().label("adet"),
                    func.sum(case((LabResult.out_of_spec.is_(True), 1), else_=0)).label("disi"),
                )
                .where(*kosul)
                .group_by(ay)
                .order_by(ay)
            )
        ).all()
    ]

    # --- parametre ortalamalari
    parametreler = []
    for alan, etiket, birim in (
        (LabResult.ph, "pH", ""),
        (LabResult.total_acidity, "Toplam asitlik", "g/L"),
        (LabResult.volatile_acidity, "Uçucu asitlik", "g/L"),
        (LabResult.free_so2, "Serbest SO₂", "mg/L"),
        (LabResult.alcohol, "Alkol", "%vol"),
        (LabResult.residual_sugar, "Kalıntı şeker", "g/L"),
    ):
        r = (
            await session.execute(
                select(
                    func.avg(alan).label("ort"),
                    func.min(alan).label("enaz"),
                    func.max(alan).label("encok"),
                    func.count(alan).label("adet"),
                ).where(*kosul, alan.is_not(None))
            )
        ).one()
        if r.adet:
            parametreler.append(
                {
                    "ad": etiket,
                    "birim": birim,
                    "ortalama": round(_f(r.ort), 3),
                    "en_az": round(_f(r.enaz), 3),
                    "en_cok": round(_f(r.encok), 3),
                    "olcum": int(r.adet),
                }
            )

    # --- onay dongu suresi (numune alimindan onaya)
    dongu = (
        await session.execute(
            select(
                func.avg(
                    cast(func.julianday(LabResult.approved_at), Float)
                    - cast(func.julianday(LabSample.sampled_at), Float)
                ).label("gun")
            )
            .join(LabSample, LabResult.sample_id == LabSample.id)
            .where(*kosul, LabResult.approved_at.is_not(None))
        )
    ).scalar()

    return {
        "baslangic": baslangic.isoformat(),
        "bitis": bitis.isoformat(),
        "ozet": {
            "analiz_sayisi": toplam,
            "spec_disi": spec_disi,
            "spec_disi_orani": _oran(spec_disi, toplam),
            "ort_onay_suresi_gun": round(_f(dongu), 2) if dongu is not None else None,
        },
        "aylik": aylik,
        "parametreler": parametreler,
    }


# ============================================================ FERMANTASYON
async def fermantasyon(session: AsyncSession, *, yil: int | None = None) -> dict:
    """Süre, Brix düşüş hızı ve durum dağılımı."""
    kosul = [Lot.vintage_year == yil] if yil else []

    durumlar = [
        {"durum": r.status, "adet": int(r.adet)}
        for r in (
            await session.execute(
                select(Fermentation.status, func.count().label("adet"))
                .join(Lot, Fermentation.lot_id == Lot.id)
                .where(*kosul)
                .group_by(Fermentation.status)
            )
        ).all()
    ]

    sure_satiri = (
        await session.execute(
            select(
                func.avg(
                    cast(func.julianday(Fermentation.actual_end_date), Float)
                    - cast(func.julianday(Fermentation.start_date), Float)
                ).label("ort"),
                func.min(
                    cast(func.julianday(Fermentation.actual_end_date), Float)
                    - cast(func.julianday(Fermentation.start_date), Float)
                ).label("enaz"),
                func.max(
                    cast(func.julianday(Fermentation.actual_end_date), Float)
                    - cast(func.julianday(Fermentation.start_date), Float)
                ).label("encok"),
                func.count().label("adet"),
            )
            .join(Lot, Fermentation.lot_id == Lot.id)
            .where(*kosul, Fermentation.actual_end_date.is_not(None))
        )
    ).one()

    # Tamamlanan fermantasyonlarda Brix dususu
    brix = (
        await session.execute(
            select(
                func.avg(Fermentation.initial_brix).label("bas"),
                func.avg(Fermentation.target_brix).label("hedef"),
            )
            .join(Lot, Fermentation.lot_id == Lot.id)
            .where(*kosul, Fermentation.initial_brix.is_not(None))
        )
    ).one()

    ort_gun = _f(sure_satiri.ort) if sure_satiri.ort is not None else None
    dusus = _f(brix.bas) - _f(brix.hedef) if brix.bas is not None else None

    return {
        "yil": yil,
        "durumlar": durumlar,
        "sure": {
            "tamamlanan": int(sure_satiri.adet or 0),
            "ortalama_gun": round(ort_gun, 1) if ort_gun is not None else None,
            "en_kisa_gun": round(_f(sure_satiri.enaz), 1) if sure_satiri.enaz is not None else None,
            "en_uzun_gun": round(_f(sure_satiri.encok), 1) if sure_satiri.encok is not None else None,
        },
        "brix": {
            "ortalama_baslangic": round(_f(brix.bas), 2) if brix.bas is not None else None,
            "ortalama_hedef": round(_f(brix.hedef), 2) if brix.hedef is not None else None,
            "gunluk_dusus": round(dusus / ort_gun, 3) if dusus and ort_gun else None,
        },
    }


# ============================================================ SISELEME
async def siseleme(session: AsyncSession, *, yil: int | None = None) -> dict:
    """Aylık üretim, verim/fire oranı, ambalaj ve hat kırılımı.

    Oranlar SQL'de `SUM/SUM` olarak hesaplanır: model üzerindeki
    `yield_percent` bir Python özelliğidir ve GROUP BY'da kullanılamaz.
    """
    kosul = [BottlingOrder.status == BottlingStatus.TAMAMLANDI]
    if yil:
        kosul.append(BottlingOrder.vintage_year == yil)

    ay = func.strftime("%Y-%m", BottlingOrder.finished_at)
    aylik = [
        {"ay": r.ay, "sise": int(r.sise or 0), "emir": int(r.adet)}
        for r in (
            await session.execute(
                select(
                    ay.label("ay"),
                    func.sum(BottlingOrder.produced_bottles).label("sise"),
                    func.count().label("adet"),
                )
                .where(*kosul, BottlingOrder.finished_at.is_not(None))
                .group_by(ay)
                .order_by(ay)
            )
        ).all()
    ]

    ambalaj = [
        {
            "hacim_ml": int(r.bottle_volume_ml or 0),
            "sise": int(r.sise or 0),
            "emir": int(r.adet),
        }
        for r in (
            await session.execute(
                select(
                    BottlingOrder.bottle_volume_ml,
                    func.sum(BottlingOrder.produced_bottles).label("sise"),
                    func.count().label("adet"),
                )
                .where(*kosul)
                .group_by(BottlingOrder.bottle_volume_ml)
                .order_by(BottlingOrder.bottle_volume_ml)
            )
        ).all()
    ]

    hatlar = [
        {
            "hat": r.line_code or "belirsiz",
            "sise": int(r.uretilen or 0),
            "fire": int(r.fire or 0),
            "fire_orani": _oran(int(r.fire or 0), int(r.uretilen or 0) + int(r.fire or 0)),
        }
        for r in (
            await session.execute(
                select(
                    BottlingOrder.line_code,
                    func.sum(BottlingOrder.produced_bottles).label("uretilen"),
                    func.sum(BottlingOrder.rejected_bottles).label("fire"),
                )
                .where(*kosul)
                .group_by(BottlingOrder.line_code)
            )
        ).all()
    ]

    toplam = (
        await session.execute(
            select(
                func.sum(BottlingOrder.planned_bottles).label("planlanan"),
                func.sum(BottlingOrder.produced_bottles).label("uretilen"),
                func.sum(BottlingOrder.rejected_bottles).label("fire"),
                func.sum(BottlingOrder.used_volume_l).label("hacim"),
            ).where(*kosul)
        )
    ).one()

    uretilen = int(toplam.uretilen or 0)
    fire_adet = int(toplam.fire or 0)
    planlanan = int(toplam.planlanan or 0)

    return {
        "yil": yil,
        "ozet": {
            "planlanan_sise": planlanan,
            "uretilen_sise": uretilen,
            "fire_sise": fire_adet,
            "verim_orani": _oran(uretilen, planlanan),
            "fire_orani": _oran(fire_adet, uretilen + fire_adet),
            "kullanilan_hacim_l": round(_f(toplam.hacim), 1),
        },
        "aylik": aylik,
        "ambalaj": ambalaj,
        "hatlar": hatlar,
    }


# ============================================================ STOK
async def stok(session: AsyncSession, *, gun: int = 90) -> dict:
    """Devir hızı ve hareketsiz (ölü) stok.

    Tek `GROUP BY` ile hesaplanır; kalem başına sorgu atan `inv.on_hand()`
    döngüsü istatistikte kullanılmaz (500 kalemde 500+ sorgu demektir).
    """
    sinir = dt.datetime.now() - dt.timedelta(days=gun)

    hareket = (
        select(
            StockMovement.item_id,
            func.sum(
                case((StockMovement.quantity < 0, -StockMovement.quantity), else_=0)
            ).label("cikis"),
            func.max(StockMovement.occurred_at).label("son"),
        )
        .where(StockMovement.occurred_at >= sinir)
        .group_by(StockMovement.item_id)
        .subquery()
    )

    satirlar = (
        await session.execute(
            select(
                InventoryItem.code,
                InventoryItem.name,
                InventoryItem.category,
                InventoryItem.unit,
                InventoryItem.min_stock,
                hareket.c.cikis,
                hareket.c.son,
            )
            .join(hareket, hareket.c.item_id == InventoryItem.id, isouter=True)
            .where(InventoryItem.is_active.is_(True))
        )
    ).all()

    kalemler = []
    olu = []
    for r in satirlar:
        cikis = _f(r.cikis)
        kayit = {
            "kod": r.code,
            "ad": r.name,
            "kategori": r.category,
            "birim": r.unit,
            "donem_cikis": round(cikis, 2),
            "gunluk_ortalama": round(cikis / gun, 3) if gun else None,
            "son_hareket": r.son.isoformat() if r.son else None,
        }
        kalemler.append(kayit)
        if cikis == 0:
            olu.append(kayit)

    kalemler.sort(key=lambda k: k["donem_cikis"], reverse=True)

    return {
        "gun": gun,
        "kalem_sayisi": len(kalemler),
        "hareketsiz_sayisi": len(olu),
        "en_cok_tuketilen": kalemler[:15],
        "hareketsiz": olu[:25],
    }


# ============================================================ BAKIM
async def bakim(session: AsyncSession, *, gun: int = 365) -> dict:
    """Duruş Pareto'su, ekipman arıza sıklığı, CIP doğrulama oranı."""
    sinir = dt.datetime.now() - dt.timedelta(days=gun)
    kosul = [MaintenanceLog.started_at >= sinir]

    turler = [
        {
            "tur": r.kind,
            "adet": int(r.adet),
            "durus_dakika": int(r.durus or 0),
            "maliyet": round(_f(r.maliyet), 2),
        }
        for r in (
            await session.execute(
                select(
                    MaintenanceLog.kind,
                    func.count().label("adet"),
                    func.sum(MaintenanceLog.downtime_minutes).label("durus"),
                    func.sum(MaintenanceLog.cost).label("maliyet"),
                )
                .where(*kosul)
                .group_by(MaintenanceLog.kind)
                .order_by(func.sum(MaintenanceLog.downtime_minutes).desc().nulls_last())
            )
        ).all()
    ]

    ekipmanlar = [
        {
            "kod": r.code,
            "ad": r.name,
            "kayit": int(r.adet),
            "durus_dakika": int(r.durus or 0),
        }
        for r in (
            await session.execute(
                select(
                    Equipment.code,
                    Equipment.name,
                    func.count(MaintenanceLog.id).label("adet"),
                    func.sum(MaintenanceLog.downtime_minutes).label("durus"),
                )
                .join(MaintenanceLog, MaintenanceLog.equipment_id == Equipment.id)
                .where(*kosul)
                .group_by(Equipment.id, Equipment.code, Equipment.name)
                .order_by(func.sum(MaintenanceLog.downtime_minutes).desc().nulls_last())
                .limit(15)
            )
        ).all()
    ]

    cip = (
        await session.execute(
            select(
                func.count().label("adet"),
                func.sum(case((MaintenanceLog.cip_verified.is_(True), 1), else_=0)).label(
                    "dogrulanan"
                ),
            ).where(*kosul, MaintenanceLog.kind == "cip")
        )
    ).one()

    geciken = (
        await session.execute(
            select(func.count()).where(
                Equipment.is_active.is_(True),
                Equipment.next_maintenance_at.is_not(None),
                Equipment.next_maintenance_at < dt.datetime.now(),
            )
        )
    ).scalar()

    return {
        "gun": gun,
        "turler": turler,
        "ekipmanlar": ekipmanlar,
        "cip": {
            "kayit": int(cip.adet or 0),
            "dogrulanan": int(cip.dogrulanan or 0),
            "dogrulama_orani": _oran(int(cip.dogrulanan or 0), int(cip.adet or 0)),
        },
        "geciken_bakim": int(geciken or 0),
    }


# ============================================================ FICI
async def fici(session: AsyncSession) -> dict:
    """Yaş dağılımı, kullanım sayısı ve buharlaşma kaybı."""
    bu_yil = dt.date.today().year

    yas = [
        {
            "yas": bu_yil - int(r.production_year) if r.production_year else None,
            "adet": int(r.adet),
            "kayip_l": round(_f(r.kayip), 1),
        }
        for r in (
            await session.execute(
                select(
                    Barrel.production_year,
                    func.count().label("adet"),
                    func.sum(Barrel.total_loss_l).label("kayip"),
                )
                .group_by(Barrel.production_year)
                .order_by(Barrel.production_year)
            )
        ).all()
    ]

    kullanim = [
        {"dolum_sayisi": int(r.fill_count or 0), "adet": int(r.adet)}
        for r in (
            await session.execute(
                select(Barrel.fill_count, func.count().label("adet"))
                .group_by(Barrel.fill_count)
                .order_by(Barrel.fill_count)
            )
        ).all()
    ]

    toplam = (
        await session.execute(
            select(
                func.count().label("adet"),
                func.sum(Barrel.capacity_l).label("kapasite"),
                func.sum(Barrel.current_volume_l).label("dolu"),
                func.sum(Barrel.total_loss_l).label("kayip"),
            )
        )
    ).one()

    kapasite = _f(toplam.kapasite)
    return {
        "ozet": {
            "fici_sayisi": int(toplam.adet or 0),
            "toplam_kapasite_l": round(kapasite, 1),
            "dolu_hacim_l": round(_f(toplam.dolu), 1),
            "doluluk_orani": _oran(_f(toplam.dolu), kapasite),
            "toplam_kayip_l": round(_f(toplam.kayip), 1),
        },
        "yas_dagilimi": yas,
        "kullanim_dagilimi": kullanim,
    }
