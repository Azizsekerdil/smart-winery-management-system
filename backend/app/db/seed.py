"""Gerçekçi fakat TAMAMEN KURGUSAL Türkçe demo verisi.

UYARI: Buradaki kullanıcı adları, parolalar, bağ/tedarikçi/müşteri isimleri ve
tüm ölçümler yalnızca gösterim amaçlıdır. Üretim ortamında bu betik
ÇALIŞTIRILMAMALI, demo parolalar kesinlikle bırakılmamalıdır
(bkz. SECURITY.md → "Üretime geçiş kontrol listesi").
"""

from __future__ import annotations

import datetime as dt
import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.models.cellar import (
    Barrel,
    BarrelMovement,
    BarrelMovementType,
    BarrelStatus,
    BottlingOrder,
    BottlingStatus,
    OakType,
    TastingNote,
    ToastLevel,
)
from app.models.inventory import (
    Customer,
    InventoryItem,
    ItemCategory,
    MovementType,
    StockBatch,
    StockMovement,
    ValuationMethod,
    Warehouse,
)
from app.models.ops import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Equipment,
    EquipmentType,
    MaintenanceKind,
    MaintenanceLog,
)
from app.models.production import (
    CleaningStatus,
    Fermentation,
    FermentationAdditive,
    FermentationReading,
    FermentationStatus,
    FermentationType,
    Lot,
    LotEvent,
    LotSource,
    LotStage,
    LotStatus,
    Tank,
    TankStatus,
    TankTransfer,
    TankType,
    TransferType,
    WineType,
)
from app.models.quality import (
    ApprovalStatus,
    LabResult,
    LabSample,
    LabSpec,
    Recipe,
    RecipeItem,
    RecipeStatus,
    SampleStatus,
)
from app.models.user import User
from app.models.vineyard import (
    GrapeColor,
    GrapeVariety,
    HarvestIntake,
    Parcel,
    Supplier,
    Vineyard,
)
from app.services.codes import qr_payload

# Tekrarlanabilir demo verisi
RNG = random.Random(20260815)

# Hasat, demo HER ZAMAN "canlı" görünsün diye bugüne göre konumlandırılır:
# ~5 hafta önce başlamış bir bağbozumu sezonu. Böylece kontrol panelindeki
# "son 30 gün" grafikleri ve devam eden fermantasyonlar anlamlı veri gösterir.
HARVEST_START = dt.date.today() - dt.timedelta(days=32)
VINTAGE = HARVEST_START.year
ONCEKI_VINTAGE = VINTAGE - 1

# --------------------------------------------------------------- KULLANICILAR
# Parolalar YALNIZCA demo içindir; ilk girişte değiştirilmesi zorunlu tutulur.
DEMO_USERS: list[tuple[str, str, str, list[Role], str]] = [
    ("admin", "Sistem Yöneticisi", "admin@saraphane.example.com", [Role.SISTEM_YONETICISI], "Bilgi İşlem"),
    ("mudur", "Ayşe Yıldırım", "mudur@saraphane.example.com", [Role.ISLETME_YONETICISI], "Yönetim"),
    ("enolog", "Dr. Mehmet Aksoy", "enolog@saraphane.example.com", [Role.ENOLOG], "Üretim"),
    ("bagci", "Hasan Demirtaş", "bagci@saraphane.example.com", [Role.BAGCILIK_UZMANI], "Bağcılık"),
    ("lab", "Elif Korkmaz", "lab@saraphane.example.com", [Role.LABORATUVAR_TEKNISYENI], "Laboratuvar"),
    ("mahzen", "Osman Çelik", "mahzen@saraphane.example.com", [Role.MAHZEN_SORUMLUSU], "Mahzen"),
    ("operator", "Serkan Aydın", "operator@saraphane.example.com", [Role.URETIM_OPERATORU], "Üretim"),
    ("siseleme", "Zeynep Kaya", "siseleme@saraphane.example.com", [Role.SISELEME_PERSONELI], "Şişeleme"),
    ("depo", "Murat Şahin", "depo@saraphane.example.com", [Role.DEPO_SEVKIYAT], "Depo"),
    ("satis", "Deniz Arslan", "satis@saraphane.example.com", [Role.SATIS_PERSONELI], "Satış"),
    ("muhasebe", "Fatma Öztürk", "muhasebe@saraphane.example.com", [Role.MUHASEBE], "Muhasebe"),
    ("denetci", "Bağımsız Denetçi", "denetci@saraphane.example.com", [Role.DENETCI], "Denetim"),
]
DEMO_PASSWORD = "Saraphane2026!"  # noqa: S105 - yalnızca demo


async def is_seeded(session: AsyncSession) -> bool:
    count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    return count > 0


async def seed_all(session: AsyncSession, *, force: bool = False) -> dict[str, int]:
    """Tüm demo verisini yükler. Zaten yüklüyse (force=False) hiçbir şey yapmaz."""
    if await is_seeded(session) and not force:
        return {"atlandi": 1}

    stats: dict[str, int] = {}

    # ---------------------------------------------------------- kullanıcılar
    users: dict[str, User] = {}
    for username, full_name, email, roles, dept in DEMO_USERS:
        existing = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if existing is not None:
            users[username] = existing
            continue
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hash_password(DEMO_PASSWORD),
            roles=[str(r) for r in roles],
            department=dept,
            must_change_password=True,
            theme="dark",
        )
        session.add(user)
        users[username] = user
    await session.flush()
    stats["kullanici"] = len(users)

    admin = users["admin"]
    enolog = users["enolog"]
    lab_user = users["lab"]

    # ------------------------------------------------------------- çeşitler
    variety_specs = [
        ("CST-001", "Öküzgözü", GrapeColor.KIRMIZI, "Elazığ", 22, 25, 3.4, 3.7),
        ("CST-002", "Boğazkere", GrapeColor.KIRMIZI, "Diyarbakır", 23, 26, 3.3, 3.6),
        ("CST-003", "Kalecik Karası", GrapeColor.KIRMIZI, "Ankara", 21, 24, 3.4, 3.7),
        ("CST-004", "Narince", GrapeColor.BEYAZ, "Tokat", 20, 23, 3.1, 3.4),
        ("CST-005", "Emir", GrapeColor.BEYAZ, "Nevşehir", 19, 22, 3.0, 3.3),
        ("CST-006", "Sultaniye", GrapeColor.BEYAZ, "Manisa", 18, 21, 3.0, 3.3),
    ]
    varieties: dict[str, GrapeVariety] = {}
    for code, name, color, origin, bmin, bmax, pmin, pmax in variety_specs:
        v = GrapeVariety(
            code=code, name=name, color=color, origin=origin,
            target_brix_min=bmin, target_brix_max=bmax,
            target_ph_min=pmin, target_ph_max=pmax,
            description=f"{origin} yöresine özgü yerli üzüm çeşidi.",
        )
        session.add(v)
        varieties[name] = v
    await session.flush()
    stats["cesit"] = len(varieties)

    # ----------------------------------------------------------------- bağlar
    vineyard_specs = [
        ("BAG-001", "Güneşli Tepe Bağı", "Ege", "Şirince", 480, "Killi-kireçli", 145.0, 38.3921, 27.3475),
        ("BAG-002", "Kayalık Bağ", "İç Anadolu", "Ürgüp", 1180, "Volkanik tüf", 92.5, 38.6312, 34.9105),
        ("BAG-003", "Fırat Kenarı Bağı", "Doğu Anadolu", "Baskil", 950, "Kumlu-tınlı", 210.0, 38.5688, 38.8172),
        ("BAG-004", "Karaburun Sahil Bağı", "Ege", "Karaburun", 120, "Kumlu-kireçli", 64.0, 38.6389, 26.5142),
    ]
    vineyards: dict[str, Vineyard] = {}
    for code, name, region, village, alt, soil, area, lat, lon in vineyard_specs:
        vy = Vineyard(
            code=code, name=name, region=region, village=village, altitude_m=alt,
            soil_type=soil, total_area_da=area, latitude=lat, longitude=lon,
            is_owned=code != "BAG-004", created_by_id=admin.id,
            notes="Demo veri — gerçek bir işletmeye ait değildir.",
        )
        session.add(vy)
        vineyards[code] = vy
    await session.flush()
    stats["bag"] = len(vineyards)

    # --------------------------------------------------------------- parseller
    parcel_specs = [
        ("PRS-001", "Tepe Üstü A", "BAG-001", "Öküzgözü", 32.0, 2009, 9600),
        ("PRS-002", "Tepe Üstü B", "BAG-001", "Narince", 28.5, 2012, 8400),
        ("PRS-003", "Doğu Yamacı", "BAG-001", "Kalecik Karası", 41.0, 2007, 12300),
        ("PRS-004", "Peribacası Altı", "BAG-002", "Emir", 46.0, 2014, 13800),
        ("PRS-005", "Kuzey Teras", "BAG-002", "Kalecik Karası", 30.5, 2016, 9100),
        ("PRS-006", "Nehir Kenarı", "BAG-003", "Boğazkere", 88.0, 2005, 26000),
        ("PRS-007", "Yüksek Teras", "BAG-003", "Öküzgözü", 74.0, 2010, 22000),
        ("PRS-008", "Sahil Parseli", "BAG-004", "Sultaniye", 64.0, 2018, 19000),
    ]
    parcels: dict[str, Parcel] = {}
    for code, name, vcode, variety_name, area, year, vines in parcel_specs:
        p = Parcel(
            code=code, name=name, vineyard_id=vineyards[vcode].id,
            variety_id=varieties[variety_name].id, area_da=area, planting_year=year,
            vine_count=vines, rootstock="110R", training_system="Çift kollu Guyot",
            created_by_id=admin.id,
        )
        session.add(p)
        parcels[code] = p
    await session.flush()
    stats["parsel"] = len(parcels)

    # ------------------------------------------------------------ tedarikçiler
    supplier_specs = [
        ("TED-001", "Anadolu Bağcılık Kooperatifi", "uzum", "Ahmet Yılmaz"),
        ("TED-002", "Ege Cam Ambalaj A.Ş.", "ambalaj", "Selin Uçar"),
        ("TED-003", "Portekiz Mantar İthalat Ltd.", "ambalaj", "João Silva"),
        ("TED-004", "BiyoEnzim Katkı San.", "katki", "Dr. Canan Er"),
        ("TED-005", "Trakya Meşe Fıçı", "ekipman", "Kemal Bulut"),
    ]
    suppliers: dict[str, Supplier] = {}
    for code, name, stype, contact in supplier_specs:
        s = Supplier(
            code=code, name=name, supplier_type=stype, contact_person=contact,
            phone=f"+90 2{RNG.randint(10, 99)} {RNG.randint(200, 999)} {RNG.randint(1000, 9999)}",
            email=f"info@{code.lower()}.saraphane.example.com", rating=RNG.randint(3, 5),
            address="Demo adres — gerçek bir işletmeye ait değildir.",
            created_by_id=admin.id,
        )
        session.add(s)
        suppliers[code] = s
    await session.flush()
    stats["tedarikci"] = len(suppliers)

    # ------------------------------------------------------------ üzüm kabulü
    intake_specs = [
        ("PRS-001", "Öküzgözü", 14200, 23.8, 3.55, 5.9, 19.5, "A", 18.50),
        ("PRS-001", "Öküzgözü", 11800, 24.3, 3.58, 5.7, 21.0, "A", 18.50),
        ("PRS-003", "Kalecik Karası", 16500, 22.6, 3.52, 6.1, 18.0, "A", 17.25),
        ("PRS-002", "Narince", 9800, 21.4, 3.25, 6.8, 17.5, "A", 16.00),
        ("PRS-004", "Emir", 13400, 20.1, 3.12, 7.2, 16.5, "B", 14.75),
        ("PRS-005", "Kalecik Karası", 8900, 23.1, 3.49, 6.0, 20.0, "A", 17.25),
        ("PRS-006", "Boğazkere", 21000, 25.2, 3.42, 6.4, 22.5, "A", 19.80),
        ("PRS-007", "Öküzgözü", 17600, 24.0, 3.56, 5.8, 21.5, "B", 18.00),
        ("PRS-008", "Sultaniye", 12200, 19.3, 3.05, 7.5, 24.0, "B", 12.50),
        ("PRS-006", "Boğazkere", 15300, 25.8, 3.45, 6.2, 23.0, "A", 19.80),
        ("PRS-002", "Narince", 7400, 22.0, 3.28, 6.6, 18.5, "A", 16.00),
        ("PRS-003", "Kalecik Karası", 10100, 23.4, 3.51, 5.95, 19.0, "A", 17.25),
    ]
    intakes: list[HarvestIntake] = []
    for idx, (pcode, variety_name, kg, brix, ph, ta, temp, grade, price) in enumerate(intake_specs):
        parcel = parcels[pcode]
        harvest_date = HARVEST_START + dt.timedelta(days=idx * 2 + RNG.randint(0, 1))
        received = dt.datetime.combine(
            harvest_date, dt.time(RNG.randint(7, 11), RNG.choice([0, 15, 30, 45])), dt.UTC
        )
        tare = RNG.randint(3000, 4500)
        intake = HarvestIntake(
            code=f"UZK-{VINTAGE}-{idx + 1:04d}",
            vineyard_id=parcel.vineyard_id,
            parcel_id=parcel.id,
            variety_id=varieties[variety_name].id,
            supplier_id=suppliers["TED-001"].id if pcode == "PRS-008" else None,
            harvest_date=harvest_date,
            received_at=received,
            vintage_year=VINTAGE,
            gross_weight_kg=kg + tare,
            tare_weight_kg=tare,
            net_weight_kg=kg,
            vehicle_plate=f"35 {RNG.choice('ABCDEFG')}{RNG.choice('KLMNP')} {RNG.randint(100, 999)}",
            weighbridge_ticket=f"KNT-{VINTAGE}-{idx + 1:05d}",
            brix=brix, ph=ph, total_acidity=ta, temperature_c=temp,
            rot_percent=round(RNG.uniform(0.2, 2.4), 1),
            quality_grade=grade, unit_price=price, currency="TRY",
            created_by_id=users["bagci"].id,
            notes="Sabah hasadı, soğuk zincir korundu." if temp < 20 else None,
        )
        intake.qr_payload = qr_payload("uzum-kabul", intake.code)
        session.add(intake)
        intakes.append(intake)
    await session.flush()
    stats["uzum_kabul"] = len(intakes)

    # ------------------------------------------------------------------ tanklar
    tank_specs = [
        ("TNK-01", TankType.PASLANMAZ, 15000, "Fermantasyon Salonu", "A Bölgesi", 1, 1, True, True),
        ("TNK-02", TankType.PASLANMAZ, 15000, "Fermantasyon Salonu", "A Bölgesi", 2, 1, True, True),
        ("TNK-03", TankType.PASLANMAZ, 10000, "Fermantasyon Salonu", "A Bölgesi", 3, 1, True, True),
        ("TNK-04", TankType.PASLANMAZ, 10000, "Fermantasyon Salonu", "A Bölgesi", 4, 1, True, False),
        ("TNK-05", TankType.PASLANMAZ, 8000, "Fermantasyon Salonu", "B Bölgesi", 1, 2, True, True),
        ("TNK-06", TankType.BETON, 12000, "Eski Mahzen", "B Bölgesi", 2, 2, False, False),
        ("TNK-07", TankType.PASLANMAZ, 5000, "Dinlendirme Salonu", "C Bölgesi", 1, 3, True, False),
        ("TNK-08", TankType.PASLANMAZ, 5000, "Dinlendirme Salonu", "C Bölgesi", 2, 3, True, False),
        ("TNK-09", TankType.AMFORA, 2000, "Deneysel Alan", "C Bölgesi", 3, 3, False, False),
        ("TNK-10", TankType.PASLANMAZ, 20000, "Şişeleme Öncesi", "D Bölgesi", 1, 4, True, True),
    ]
    tanks: dict[str, Tank] = {}
    for code, ttype, cap, location, zone, x, y, cooling, sensor in tank_specs:
        t = Tank(
            code=code, name=f"{code} · {cap / 1000:g} ton", tank_type=ttype, capacity_l=cap,
            location=location, zone=zone, position_x=x, position_y=y,
            has_cooling=cooling, has_sensor=sensor,
            status=TankStatus.BOS, cleaning_status=CleaningStatus.TEMIZ,
            last_cleaned_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=RNG.randint(3, 30)),
            commissioned_year=RNG.choice([2015, 2018, 2020, 2022]),
            created_by_id=admin.id,
        )
        session.add(t)
        tanks[code] = t
    await session.flush()
    stats["tank"] = len(tanks)

    # ------------------------------------------------------------------ partiler
    now = dt.datetime.now(dt.UTC)
    # NOT: Hacimler ilgili tankın kapasitesini AŞMAZ (bkz. tank_specs). Gerçek
    # sistemde transfer uç noktası bunu zaten reddeder; demo verisi de aynı
    # kurala uymalıdır ki kontrol panelindeki doluluk oranları tutarlı olsun.
    ONCEKI_KOD = f"PRT-{ONCEKI_VINTAGE}-0012"
    FICI_KOD = f"PRT-{VINTAGE}-0007"
    lot_plan = [
        # (kod, ad, çeşit, tank, kaynak indeksleri, aşama, hacim, ferm durumu, gün)
        (f"PRT-{VINTAGE}-0001", f"Öküzgözü Rezerv {VINTAGE}", "Öküzgözü", "TNK-01", [0, 1], LotStage.FERMANTASYON, 14200, FermentationStatus.DEVAM_EDIYOR, 9),
        (f"PRT-{VINTAGE}-0002", f"Boğazkere Klasik {VINTAGE}", "Boğazkere", "TNK-02", [6, 9], LotStage.FERMANTASYON, 14600, FermentationStatus.DEVAM_EDIYOR, 6),
        (f"PRT-{VINTAGE}-0003", f"Kalecik Karası {VINTAGE}", "Kalecik Karası", "TNK-03", [2, 11], LotStage.FERMANTASYON, 9400, FermentationStatus.DEVAM_EDIYOR, 3),
        (f"PRT-{VINTAGE}-0004", f"Narince Beyaz {VINTAGE}", "Narince", "TNK-05", [3, 10], LotStage.DINLENDIRME, 7600, FermentationStatus.TAMAMLANDI, 24),
        (f"PRT-{VINTAGE}-0005", f"Emir Taze {VINTAGE}", "Emir", "TNK-07", [4], LotStage.DINLENDIRME, 4700, FermentationStatus.TAMAMLANDI, 21),
        (f"PRT-{VINTAGE}-0006", f"Sultaniye Sofralık {VINTAGE}", "Sultaniye", "TNK-08", [8], LotStage.STABILIZASYON, 4600, FermentationStatus.TAMAMLANDI, 26),
        (FICI_KOD, f"Öküzgözü Fıçı {VINTAGE}", "Öküzgözü", None, [7], LotStage.OLGUNLASTIRMA, 1760, FermentationStatus.TAMAMLANDI, 30),
        (ONCEKI_KOD, f"Kalecik Karası Rezerv {ONCEKI_VINTAGE}", "Kalecik Karası", "TNK-10", [5], LotStage.SISELEME, 6400, FermentationStatus.TAMAMLANDI, 300),
    ]

    lots: dict[str, Lot] = {}
    fermentations: list[Fermentation] = []
    readings_count = 0

    for code, name, variety_name, tank_code, source_idx, stage, volume, ferm_status, day_count in lot_plan:
        vintage = ONCEKI_VINTAGE if code == ONCEKI_KOD else VINTAGE
        wine_type = (
            WineType.BEYAZ
            if varieties[variety_name].color == GrapeColor.BEYAZ
            else WineType.KIRMIZI
        )
        lot = Lot(
            code=code, name=name, vintage_year=vintage, wine_type=wine_type,
            variety_id=varieties[variety_name].id, stage=stage,
            status=LotStatus.AKTIF, volume_l=volume, initial_volume_l=volume,
            current_tank_id=tanks[tank_code].id if tank_code else None,
            opened_at=HARVEST_START, created_by_id=enolog.id,
        )
        lot.qr_payload = qr_payload("parti", code)
        session.add(lot)
        await session.flush()
        lots[code] = lot

        for i in source_idx:
            intake = intakes[i]
            session.add(
                LotSource(
                    lot_id=lot.id, intake_id=intake.id,
                    weight_kg=intake.net_weight_kg,
                    juice_yield_l=round(float(intake.net_weight_kg) * 0.70, 1),
                )
            )

        start = now - dt.timedelta(days=day_count)
        session.add(
            LotEvent(
                lot_id=lot.id, occurred_at=start, event_type="olusturma",
                title=f"Parti oluşturuldu ({len(source_idx)} üzüm kabulü)",
                description=", ".join(intakes[i].code for i in source_idx),
                created_by_id=enolog.id,
            )
        )

        if tank_code:
            tank = tanks[tank_code]
            transfer = TankTransfer(
                code=f"TRF-{vintage}-{len(lots):04d}",
                transfer_type=TransferType.DOLUM, lot_id=lot.id, to_tank_id=tank.id,
                volume_l=volume, loss_l=round(volume * 0.004, 1),
                occurred_at=start, performed_by_id=users["operator"].id,
                created_by_id=users["operator"].id,
            )
            session.add(transfer)
            tank.current_volume_l = float(tank.current_volume_l) + volume
            tank.status = (
                TankStatus.DOLU
                if tank.current_volume_l >= float(tank.capacity_l) * 0.98
                else TankStatus.KISMEN_DOLU
            )
            tank.cleaning_status = CleaningStatus.KIRLI

        # --------------------------------------------------------- fermantasyon
        initial_brix = float(intakes[source_idx[0]].brix or 22)
        target_brix = -1.0 if wine_type == WineType.KIRMIZI else 0.0
        temp_min, temp_max = (24.0, 29.0) if wine_type == WineType.KIRMIZI else (14.0, 18.0)

        ferm = Fermentation(
            code=f"FRM-{vintage}-{len(lots):04d}",
            lot_id=lot.id,
            tank_id=tanks[tank_code].id if tank_code else None,
            ferm_type=FermentationType.ALKOL,
            status=ferm_status,
            start_date=start,
            target_end_date=start + dt.timedelta(days=12),
            yeast_strain=RNG.choice(
                ["Saccharomyces cerevisiae EC-1118", "Lalvin BM4x4", "Zymaflore F15", "Uvaferm 43"]
            ),
            yeast_dose_g_hl=round(RNG.uniform(18, 26), 1),
            initial_brix=initial_brix,
            target_brix=target_brix,
            initial_ph=float(intakes[source_idx[0]].ph or 3.4),
            temp_min_c=temp_min, temp_max_c=temp_max,
            volume_l=volume,
            created_by_id=enolog.id,
        )
        if ferm_status == FermentationStatus.TAMAMLANDI:
            ferm.actual_end_date = start + dt.timedelta(days=min(day_count, 11))
        session.add(ferm)
        await session.flush()
        fermentations.append(ferm)

        session.add(
            FermentationAdditive(
                fermentation_id=ferm.id,
                additive_name="Potasyum metabisülfit (PMS)",
                additive_type="koruyucu",
                amount=round(volume * 0.05, 1), unit="g",
                added_at=start + dt.timedelta(hours=2),
                created_by_id=enolog.id,
            )
        )
        session.add(
            FermentationAdditive(
                fermentation_id=ferm.id,
                additive_name="Fermaid O (maya besini)",
                additive_type="besin",
                amount=round(volume * 0.25, 1), unit="g",
                added_at=start + dt.timedelta(days=2),
                created_by_id=enolog.id,
            )
        )

        # ölçüm eğrisi: Brix üstel düşüş + sıcaklık dalgalanması
        measure_days = min(day_count, 12)
        brix = initial_brix
        for d in range(measure_days + 1):
            measured = start + dt.timedelta(days=d, hours=8)
            if measured > now:
                break
            progress = d / max(1, measure_days)
            brix = initial_brix - (initial_brix - target_brix) * (1 - pow(2.718, -3.0 * progress))
            temperature = (
                (temp_min + temp_max) / 2
                + (2.6 if 1 <= d <= 5 else 0.4) * RNG.uniform(-1, 1.35)
            )
            density = 1 + brix * 0.004
            reading = FermentationReading(
                fermentation_id=ferm.id,
                measured_at=measured,
                source="sensor" if tank_code and tanks[tank_code].has_sensor else "manuel",
                temperature_c=round(temperature, 1),
                brix=round(brix, 1),
                density=round(density, 4),
                ph=round(float(ferm.initial_ph or 3.4) + d * 0.008, 2),
                cap_management="Pigeage" if wine_type == WineType.KIRMIZI else None,
                created_by_id=users["operator"].id,
            )
            if d == 4 and code == f"PRT-{VINTAGE}-0002":
                reading.temperature_c = round(temp_max + 3.4, 1)
                reading.is_anomaly = True
                reading.anomaly_reason = (
                    f"Sıcaklık üst sınırın üzerinde: {reading.temperature_c} °C > {temp_max} °C"
                )
            session.add(reading)
            readings_count += 1

            # Parti özet değerleri HER ölçümde güncellenir; son yazılan kayıt
            # geçerli olur. (Yalnızca son güne yazmak, ölçüm döngüsü "bugün"den
            # sonrasına taştığında partiyi değersiz bırakıyordu.)
            lot.current_brix = reading.brix
            lot.current_ph = reading.ph

    await session.flush()
    stats["parti"] = len(lots)
    stats["fermantasyon"] = len(fermentations)
    stats["olcum"] = readings_count

    # ------------------------------------------------- laboratuvar spesifikasyonları
    spec_rows = [
        ("volatile_acidity", None, 0.0, 0.9, "g/L", "kritik", "Uçucu asitlik"),
        ("free_so2", None, 20.0, 45.0, "mg/L", "uyari", "Serbest SO₂"),
        ("total_so2", None, 0.0, 150.0, "mg/L", "kritik", "Toplam SO₂"),
        ("ph", "kirmizi", 3.3, 3.85, "", "uyari", "pH (kırmızı)"),
        ("ph", "beyaz", 2.95, 3.5, "", "uyari", "pH (beyaz)"),
        ("total_acidity", None, 4.5, 8.5, "g/L", "uyari", "Toplam asitlik"),
        ("alcohol", None, 8.5, 16.0, "%vol", "uyari", "Alkol"),
        ("turbidity_ntu", None, 0.0, 2.0, "NTU", "uyari", "Bulanıklık"),
    ]
    for parameter, wine_type_, vmin, vmax, unit, severity, label in spec_rows:
        session.add(
            LabSpec(
                parameter=parameter, wine_type=wine_type_, min_value=vmin, max_value=vmax,
                unit=unit, severity=severity, label_tr=label, created_by_id=admin.id,
            )
        )
    stats["lab_spek"] = len(spec_rows)

    # ------------------------------------------------------- laboratuvar sonuçları
    lab_count = 0
    for idx, (code, lot) in enumerate(lots.items()):
        for n in range(2):
            sampled = now - dt.timedelta(days=14 - n * 7, hours=RNG.randint(1, 8))
            sample = LabSample(
                code=f"NMN-{VINTAGE}-{idx * 2 + n + 1:04d}",
                lot_id=lot.id, tank_id=lot.current_tank_id,
                sampled_at=sampled, sampled_by_id=lab_user.id,
                sample_type="rutin" if n == 0 else "kontrol",
                status=SampleStatus.TAMAMLANDI, created_by_id=lab_user.id,
            )
            session.add(sample)
            await session.flush()

            high_va = code == f"PRT-{VINTAGE}-0002" and n == 1
            result = LabResult(
                code=f"LAB-{VINTAGE}-{idx * 2 + n + 1:04d}",
                sample_id=sample.id, lot_id=lot.id,
                analyzed_at=sampled + dt.timedelta(hours=3),
                analyzed_by_id=lab_user.id,
                ph=round(RNG.uniform(3.25, 3.72), 2),
                total_acidity=round(RNG.uniform(5.1, 6.9), 2),
                volatile_acidity=round(RNG.uniform(0.95, 1.15), 3) if high_va else round(RNG.uniform(0.22, 0.55), 3),
                free_so2=round(RNG.uniform(24, 42), 1),
                total_so2=round(RNG.uniform(78, 128), 1),
                alcohol=round(RNG.uniform(12.4, 14.3), 2),
                residual_sugar=round(RNG.uniform(1.2, 3.8), 2),
                density=round(RNG.uniform(0.991, 0.996), 4),
                malic_acid=round(RNG.uniform(0.8, 2.4), 2),
                lactic_acid=round(RNG.uniform(0.1, 1.6), 2),
                turbidity_ntu=round(RNG.uniform(0.4, 1.8), 2),
                micro_brettanomyces=False,
                approval_status=ApprovalStatus.ONAYLANDI if n == 0 else ApprovalStatus.BEKLIYOR,
                approved_by_id=enolog.id if n == 0 else None,
                approved_at=sampled + dt.timedelta(hours=6) if n == 0 else None,
                out_of_spec=high_va,
                out_of_spec_details=(
                    "Uçucu asitlik: 1.05 g/L > üst sınır 0.90" if high_va else None
                ),
                created_by_id=lab_user.id,
            )
            session.add(result)
            lab_count += 1
            if n == 1:
                lot.current_va = result.volatile_acidity
                lot.current_free_so2 = result.free_so2
                lot.current_alcohol = result.alcohol
                lot.current_ta = result.total_acidity
    stats["lab_sonuc"] = lab_count

    # ------------------------------------------------------------------ fıçılar
    barrels: list[Barrel] = []
    aging_lot = lots[FICI_KOD]
    for i in range(14):
        oak = RNG.choice(list(OakType))
        barrel = Barrel(
            code=f"FIC-{i + 1:03d}",
            oak_type=oak,
            cooper=RNG.choice(["Seguin Moreau", "Taransaud", "Kadar Hungary", "Trakya Meşe"]),
            toast_level=RNG.choice(list(ToastLevel)),
            capacity_l=225,
            production_year=RNG.choice([2019, 2021, 2022, 2023]),
            cellar_zone=f"Mahzen {'A' if i < 7 else 'B'}",
            rack_code=f"R{i // 4 + 1}",
            row_no=i % 4 + 1,
            level_no=i // 7 + 1,
            created_by_id=users["mahzen"].id,
        )
        barrel.qr_payload = qr_payload("fici", barrel.code)
        if i < 8:
            filled = now - dt.timedelta(days=RNG.randint(20, 40))
            barrel.status = BarrelStatus.DOLU
            barrel.current_volume_l = 220
            barrel.current_lot_id = aging_lot.id
            barrel.filled_at = filled
            barrel.fill_count = RNG.randint(1, 4)
            barrel.planned_empty_at = (filled + dt.timedelta(days=270)).date()
            barrel.total_loss_l = round(RNG.uniform(1.5, 6.0), 1)
            barrel.last_topped_at = now - dt.timedelta(days=RNG.randint(3, 15))
        else:
            barrel.status = BarrelStatus.BOS
            barrel.last_cleaned_at = now - dt.timedelta(days=RNG.randint(5, 45))
        session.add(barrel)
        barrels.append(barrel)
    await session.flush()

    for barrel in barrels[:8]:
        session.add(
            BarrelMovement(
                barrel_id=barrel.id, lot_id=aging_lot.id,
                movement_type=BarrelMovementType.DOLUM, volume_l=220, loss_l=0,
                occurred_at=barrel.filled_at, performed_by_id=users["mahzen"].id,
                created_by_id=users["mahzen"].id,
            )
        )
        session.add(
            BarrelMovement(
                barrel_id=barrel.id, lot_id=aging_lot.id,
                movement_type=BarrelMovementType.TOPPING, volume_l=2.5,
                loss_l=round(RNG.uniform(0.3, 1.2), 1),
                occurred_at=barrel.last_topped_at, performed_by_id=users["mahzen"].id,
                created_by_id=users["mahzen"].id,
            )
        )
    stats["fici"] = len(barrels)

    session.add(
        TastingNote(
            barrel_id=barrels[0].id, lot_id=aging_lot.id,
            tasted_at=now - dt.timedelta(days=5), taster_id=enolog.id,
            appearance="Yoğun mor-kırmızı, iyi berraklık.",
            aroma="Olgun vişne, kuru erik, hafif vanilya ve tarçın.",
            palate="Orta-dolgun gövde, yuvarlak tanenler, dengeli asidite.",
            finish="Uzun, hafif kavrulmuş meşe notaları.",
            score=88.5,
            conclusion="Fıçıda 4 ay daha olgunlaşabilir. Topping sıklığı korunmalı.",
            created_by_id=enolog.id,
        )
    )
    stats["tadim"] = 1

    # ------------------------------------------------------------------- depolar
    warehouses: dict[str, Warehouse] = {}
    for code, name, location, cold in [
        ("DPO-001", "Ana Hammadde Deposu", "Üretim Binası Zemin Kat", False),
        ("DPO-002", "Ambalaj Deposu", "Şişeleme Binası", False),
        ("DPO-003", "Bitmiş Ürün Deposu", "Sevkiyat Binası", True),
    ]:
        w = Warehouse(
            code=code, name=name, location=location, is_cold_storage=cold,
            temperature_c=14.0 if cold else None, created_by_id=admin.id,
        )
        session.add(w)
        warehouses[code] = w
    await session.flush()
    stats["depo"] = len(warehouses)

    # ------------------------------------------------------------ stok kartları
    item_specs = [
        ("STK-001", "Bordo şişe 750 ml", ItemCategory.AMBALAJ, "adet", 12000, 20000, 9.85, "DPO-002", 18500),
        ("STK-002", "Doğal mantar 44x24", ItemCategory.AMBALAJ, "adet", 10000, 20000, 4.20, "DPO-002", 8200),
        ("STK-003", "Kalay kapsül bordo", ItemCategory.AMBALAJ, "adet", 8000, 15000, 1.75, "DPO-002", 14300),
        ("STK-004", "Ön etiket (Rezerv serisi)", ItemCategory.AMBALAJ, "adet", 6000, 12000, 2.40, "DPO-002", 5100),
        ("STK-005", "Koli 6'lı", ItemCategory.AMBALAJ, "adet", 1200, 2500, 12.50, "DPO-002", 2600),
        ("STK-006", "Potasyum metabisülfit", ItemCategory.KATKI, "kg", 25, 50, 285.00, "DPO-001", 62),
        ("STK-007", "Maya EC-1118", ItemCategory.KATKI, "kg", 5, 15, 1450.00, "DPO-001", 11),
        ("STK-008", "Bentonit", ItemCategory.KATKI, "kg", 40, 100, 96.00, "DPO-001", 34),
        ("STK-009", "Pektolitik enzim", ItemCategory.KATKI, "kg", 3, 8, 3200.00, "DPO-001", 6.4),
        ("STK-010", "Filtre plakası 40x40", ItemCategory.SARF, "adet", 60, 120, 78.00, "DPO-001", 145),
        ("STK-011", "CIP kostik çözelti", ItemCategory.SARF, "L", 100, 250, 42.00, "DPO-001", 78),
        ("STK-012", "Meşe fıçı 225 L", ItemCategory.YEDEK_PARCA, "adet", 2, 4, 24500.00, "DPO-001", 3),
    ]
    items: dict[str, InventoryItem] = {}
    for code, name, category, unit, min_stock, reorder, cost, _wh_code, _qty in item_specs:
        item = InventoryItem(
            code=code, name=name, category=category, unit=unit,
            min_stock=min_stock, reorder_qty=reorder,
            valuation_method=ValuationMethod.FIFO if category != ItemCategory.KATKI else ValuationMethod.FEFO,
            last_unit_cost=cost, currency="TRY",
            has_expiry=category == ItemCategory.KATKI,
            shelf_life_days=730 if category == ItemCategory.KATKI else None,
            default_supplier_id=(
                suppliers["TED-002"].id if code in ("STK-001",)
                else suppliers["TED-003"].id if code == "STK-002"
                else suppliers["TED-004"].id if category == ItemCategory.KATKI
                else None
            ),
            created_by_id=users["depo"].id,
        )
        session.add(item)
        items[code] = item
    await session.flush()

    move_seq = 0
    for code, _name, _category, _unit, _min_stock, _reorder, cost, wh_code, qty in item_specs:
        item = items[code]
        received = now - dt.timedelta(days=RNG.randint(20, 90))
        batch = StockBatch(
            item_id=item.id, warehouse_id=warehouses[wh_code].id,
            batch_code=f"{code}-{received:%Y%m%d}",
            quantity=qty, unit_cost=cost, received_at=received,
            expiry_date=(received + dt.timedelta(days=730)).date() if item.has_expiry else None,
            supplier_id=item.default_supplier_id,
            created_by_id=users["depo"].id,
        )
        session.add(batch)
        await session.flush()
        move_seq += 1
        session.add(
            StockMovement(
                code=f"HRK-{VINTAGE}-{move_seq:05d}",
                item_id=item.id, batch_id=batch.id,
                warehouse_id=warehouses[wh_code].id,
                movement_type=MovementType.GIRIS, quantity=qty, unit_cost=cost,
                occurred_at=received, performed_by_id=users["depo"].id,
                notes="Demo açılış stoğu", created_by_id=users["depo"].id,
            )
        )
    stats["stok_kalemi"] = len(items)

    # ----------------------------------------------------------------- şişeleme
    bottling_lot = lots[ONCEKI_KOD]
    order = BottlingOrder(
        code=f"SSL-{VINTAGE}-0001",
        lot_id=bottling_lot.id,
        source_tank_id=tanks["TNK-10"].id,
        product_name="Kalecik Karası Rezerv",
        vintage_year=2024,
        lot_number="KKR24-0001",
        status=BottlingStatus.TAMAMLANDI,
        bottle_volume_ml=750,
        planned_bottles=8000,
        produced_bottles=7840,
        rejected_bottles=62,
        bottles_per_case=6,
        planned_volume_l=6000,
        used_volume_l=5880,
        loss_l=88.5,
        line_code="HAT-1",
        started_at=now - dt.timedelta(days=12, hours=8),
        finished_at=now - dt.timedelta(days=12),
        bottle_item_id=items["STK-001"].id,
        closure_item_id=items["STK-002"].id,
        capsule_item_id=items["STK-003"].id,
        label_item_id=items["STK-004"].id,
        case_item_id=items["STK-005"].id,
        barcode="8690000000017",
        qc_passed=True,
        qc_notes="Dolum hacmi ve kapak sıkılığı kontrol edildi; sapma yok.",
        created_by_id=users["siseleme"].id,
    )
    order.qr_payload = qr_payload("siseleme", order.code)
    session.add(order)

    planned = BottlingOrder(
        code=f"SSL-{VINTAGE}-0002",
        lot_id=lots[f"PRT-{VINTAGE}-0006"].id,
        source_tank_id=tanks["TNK-08"].id,
        product_name="Sultaniye Sofralık",
        vintage_year=VINTAGE,
        lot_number="SLT25-0002",
        status=BottlingStatus.PLANLANDI,
        bottle_volume_ml=750,
        planned_bottles=9000,
        bottles_per_case=6,
        planned_volume_l=6750,
        line_code="HAT-1",
        planned_at=now + dt.timedelta(days=6),
        bottle_item_id=items["STK-001"].id,
        closure_item_id=items["STK-002"].id,
        created_by_id=users["siseleme"].id,
    )
    planned.qr_payload = qr_payload("siseleme", planned.code)
    session.add(planned)
    await session.flush()

    finished_item = InventoryItem(
        code=f"BU-{order.code}",
        name="Kalecik Karası Rezerv 2024 (750 ml)",
        category=ItemCategory.BITMIS_URUN, unit="şişe",
        barcode=order.barcode, bottling_order_id=order.id, lot_id=bottling_lot.id,
        last_unit_cost=118.40, created_by_id=users["siseleme"].id,
    )
    session.add(finished_item)
    await session.flush()
    order.finished_item_id = finished_item.id

    fb = StockBatch(
        item_id=finished_item.id, warehouse_id=warehouses["DPO-003"].id,
        batch_code=order.lot_number, quantity=7840, unit_cost=118.40,
        received_at=order.finished_at, created_by_id=users["siseleme"].id,
    )
    session.add(fb)
    await session.flush()
    move_seq += 1
    session.add(
        StockMovement(
            code=f"HRK-{VINTAGE}-{move_seq:05d}",
            item_id=finished_item.id, batch_id=fb.id,
            warehouse_id=warehouses["DPO-003"].id,
            movement_type=MovementType.URETIM_GIRIS, quantity=7840, unit_cost=118.40,
            occurred_at=order.finished_at, lot_id=bottling_lot.id,
            ref_type="bottling_orders", ref_id=order.id,
            performed_by_id=users["siseleme"].id, created_by_id=users["siseleme"].id,
        )
    )
    stats["siseleme"] = 2

    # ----------------------------------------------------------------- müşteriler
    for code, name, ctype, city in [
        ("MST-001", "Ege Şarap Marketleri A.Ş.", "zincir", "İzmir"),
        ("MST-002", "Kapadokya Butik Otel", "otel", "Nevşehir"),
        ("MST-003", "İstanbul Gurme İthalat", "bayi", "İstanbul"),
    ]:
        session.add(
            Customer(
                code=code, name=name, customer_type=ctype, city=city,
                contact_person="Satın Alma Sorumlusu",
                email=f"siparis@{code.lower()}.saraphane.example.com",
                created_by_id=users["satis"].id,
            )
        )
    stats["musteri"] = 3

    # ------------------------------------------------------------------ ekipman
    equipment_specs = [
        ("EKP-001", "Sap Ayırıcı-Ezici", EquipmentType.DESTEMMER, "Bucher Vaslin", 180),
        ("EKP-002", "Pnömatik Pres 40 hL", EquipmentType.PRES, "Diemme", 180),
        ("EKP-003", "Şişeleme Hattı 1", EquipmentType.SISELEME_HATTI, "GAI", 90),
        ("EKP-004", "Merkezi Soğutma Ünitesi", EquipmentType.SOGUTMA, "Frigomeccanica", 120),
        ("EKP-005", "Çapraz Akış Filtre", EquipmentType.FILTRE, "Della Toffola", 120),
        ("EKP-006", "Transfer Pompası P1", EquipmentType.POMPA, "Liverani", 60),
        ("EKP-007", "Transfer Pompası P2", EquipmentType.POMPA, "Liverani", 60),
    ]
    equipment_list: list[Equipment] = []
    for code, name, etype, maker, interval in equipment_specs:
        last = dt.date.today() - dt.timedelta(days=RNG.randint(10, interval + 40))
        eq = Equipment(
            code=code, name=name, equipment_type=etype, manufacturer=maker,
            model=f"{maker[:3].upper()}-{RNG.randint(100, 999)}",
            serial_no=f"SN{RNG.randint(100000, 999999)}",
            location="Üretim Binası",
            install_date=dt.date(RNG.randint(2015, 2022), RNG.randint(1, 12), RNG.randint(1, 28)),
            maintenance_interval_days=interval,
            last_maintenance_at=last,
            next_maintenance_at=last + dt.timedelta(days=interval),
            created_by_id=admin.id,
        )
        session.add(eq)
        equipment_list.append(eq)
    await session.flush()
    stats["ekipman"] = len(equipment_list)

    for eq in equipment_list[:4]:
        son_bakim = eq.last_maintenance_at or dt.date.today()
        started = dt.datetime.combine(son_bakim, dt.time(9, 0), dt.UTC)
        session.add(
            MaintenanceLog(
                code=f"BKM-{VINTAGE}-{eq.code[-3:]}",
                equipment_id=eq.id, kind=MaintenanceKind.PERIYODIK,
                title=f"{eq.name} periyodik bakımı",
                description="Yağlama, conta kontrolü, kalibrasyon.",
                started_at=started,
                finished_at=started + dt.timedelta(hours=3),
                downtime_minutes=180, responsible_id=users["operator"].id,
                cost=RNG.choice([1200, 2400, 3800]),
                created_by_id=users["operator"].id,
            )
        )
    for tank_code in ("TNK-04", "TNK-06", "TNK-09"):
        started = now - dt.timedelta(days=RNG.randint(2, 20))
        session.add(
            MaintenanceLog(
                code=f"BKM-CIP-{tank_code[-2:]}",
                tank_id=tanks[tank_code].id, kind=MaintenanceKind.CIP,
                title=f"{tank_code} CIP temizliği",
                started_at=started, finished_at=started + dt.timedelta(hours=2),
                cip_chemical="Kostik %2 + peroksit durulama",
                cip_temperature_c=78.0, cip_duration_min=95, cip_verified=True,
                responsible_id=users["operator"].id, created_by_id=users["operator"].id,
            )
        )
    stats["bakim"] = 7

    # ------------------------------------------------------------------ uyarılar
    alert_specs = [
        (
            "fermantasyon", AlertSeverity.KRITIK,
            f"FRM-{VINTAGE}-0002: sıcaklık aralık dışı (32.4 °C)",
            "Hedef aralık 24–29 °C. Ölçülen: 32.4 °C. Soğutma devresi kontrol edilmeli.",
            "fermentations", None, f"FRM-{VINTAGE}-0002",
        ),
        (
            "lab", AlertSeverity.KRITIK,
            "Spesifikasyon dışı analiz: uçucu asitlik",
            f"PRT-{VINTAGE}-0002 partisinde uçucu asitlik 1.05 g/L (üst sınır 0.90 g/L). "
            "Mikrobiyolojik kontrol ve SO₂ ayarı önerilir.",
            "lab_results", None, None,
        ),
        (
            "stok", AlertSeverity.UYARI,
            "Minimum stok altında: Doğal mantar 44x24",
            "STK-002 — mevcut 8200 adet, minimum 10000 adet. Önerilen sipariş: 20000 adet.",
            "inventory_items", None, "STK-002",
        ),
        (
            "stok", AlertSeverity.UYARI,
            "Minimum stok altında: Ön etiket (Rezerv serisi)",
            "STK-004 — mevcut 5100 adet, minimum 6000 adet.",
            "inventory_items", None, "STK-004",
        ),
        (
            "bakim", AlertSeverity.UYARI,
            "Yaklaşan bakım: Transfer Pompası P1",
            "EKP-006 için periyodik bakım tarihi yaklaşıyor.",
            "equipment", None, "EKP-006",
        ),
        (
            "fermantasyon", AlertSeverity.BILGI,
            f"FRM-{VINTAGE}-0001 hedef Brix'e yaklaşıyor",
            "Tahmini bitiş 2 gün içinde. Aktarma planı hazırlanmalı.",
            "fermentations", None, f"FRM-{VINTAGE}-0001",
        ),
    ]
    for alert_category, severity, title, message, ref_type, ref_id, ref_code in alert_specs:
        session.add(
            Alert(
                category=alert_category, severity=severity, status=AlertStatus.ACIK,
                title=title, message=message, ref_type=ref_type, ref_id=ref_id,
                ref_code=ref_code, dedupe_key=f"demo-{title[:40]}",
            )
        )
    stats["uyari"] = len(alert_specs)

    # ------------------------------------------------------------------ reçete
    recipe = Recipe(
        code=f"RCT-{VINTAGE}-0001",
        name="Öküzgözü-Boğazkere Rezerv Kupajı",
        version=1,
        wine_type="kirmizi",
        target_volume_l=20000,
        vintage_year=VINTAGE,
        status=RecipeStatus.ONAYLANDI,
        approved_by_id=enolog.id,
        approved_at=now - dt.timedelta(days=8),
        target_alcohol=13.8,
        target_ph=3.55,
        target_ta=5.8,
        aging_months=12,
        description="Klasik Anadolu kupajı. Öküzgözü meyveliliği, Boğazkere yapısı sağlar.",
        process_steps=[
            {"no": 1, "islem": "Ayrı fermantasyon", "sure_gun": 12},
            {"no": 2, "islem": "Malolaktik fermantasyon", "sure_gun": 21},
            {"no": 3, "islem": "Kupaj", "sure_gun": 1},
            {"no": 4, "islem": "Fıçı olgunlaştırma", "sure_gun": 360},
            {"no": 5, "islem": "Soğuk stabilizasyon", "sure_gun": 14},
            {"no": 6, "islem": "Filtrasyon ve şişeleme", "sure_gun": 2},
        ],
        created_by_id=enolog.id,
    )
    session.add(recipe)
    await session.flush()
    recipe_item_specs: list[tuple[str, str | None, float | None, float | None, str, float]] = [
        ("uzum", "Öküzgözü", 65.0, None, "%", 0.0),
        ("uzum", "Boğazkere", 35.0, None, "%", 0.0),
        ("katki", None, None, 1.0, "kg", 285.0),
        ("katki", None, None, 0.4, "kg", 1450.0),
    ]
    for kind, recipe_variety, pct, amount, unit, cost in recipe_item_specs:
        session.add(
            RecipeItem(
                recipe_id=recipe.id,
                item_kind=kind,
                variety_id=varieties[recipe_variety].id if recipe_variety else None,
                name=recipe_variety
                or ("Potasyum metabisülfit" if cost == 285.0 else "Maya EC-1118"),
                percentage=pct, amount=amount, unit=unit, unit_cost=cost,
            )
        )
    stats["recete"] = 1

    await session.commit()
    return stats

