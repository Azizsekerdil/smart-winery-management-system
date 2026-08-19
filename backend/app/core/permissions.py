"""Rol tabanli yetkilendirme (RBAC) tanimlari.

Yetkiler `kaynak:eylem` bicimindedir. Roller yetki kumelerine eslenir.
Tek kaynak-i hakikat burasidir; API katmani yalnizca bu tabloyu sorgular.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Sistemdeki roller (madde 5)."""

    SISTEM_YONETICISI = "sistem_yoneticisi"
    ISLETME_YONETICISI = "isletme_yoneticisi"
    ENOLOG = "enolog"
    BAGCILIK_UZMANI = "bagcilik_uzmani"
    LABORATUVAR_TEKNISYENI = "laboratuvar_teknisyeni"
    MAHZEN_SORUMLUSU = "mahzen_sorumlusu"
    URETIM_OPERATORU = "uretim_operatoru"
    SISELEME_PERSONELI = "siseleme_personeli"
    DEPO_SEVKIYAT = "depo_sevkiyat"
    SATIS_PERSONELI = "satis_personeli"
    MUHASEBE = "muhasebe"
    DENETCI = "denetci"


ROLE_LABELS_TR: dict[str, str] = {
    Role.SISTEM_YONETICISI: "Sistem Yöneticisi",
    Role.ISLETME_YONETICISI: "İşletme Yöneticisi",
    Role.ENOLOG: "Enolog / Şarap Üretim Uzmanı",
    Role.BAGCILIK_UZMANI: "Bağcılık Uzmanı",
    Role.LABORATUVAR_TEKNISYENI: "Laboratuvar Teknisyeni",
    Role.MAHZEN_SORUMLUSU: "Mahzen / Fıçı Sorumlusu",
    Role.URETIM_OPERATORU: "Üretim Operatörü",
    Role.SISELEME_PERSONELI: "Şişeleme ve Paketleme Personeli",
    Role.DEPO_SEVKIYAT: "Depo ve Sevkiyat Personeli",
    Role.SATIS_PERSONELI: "Satış Personeli",
    Role.MUHASEBE: "Muhasebe Personeli",
    Role.DENETCI: "Salt Okunur Denetçi",
}

ROLE_LABELS_EN: dict[str, str] = {
    Role.SISTEM_YONETICISI: "System Administrator",
    Role.ISLETME_YONETICISI: "Operations Manager",
    Role.ENOLOG: "Winemaker / Oenologist",
    Role.BAGCILIK_UZMANI: "Viticulturist",
    Role.LABORATUVAR_TEKNISYENI: "Laboratory Technician",
    Role.MAHZEN_SORUMLUSU: "Cellar / Barrel Supervisor",
    Role.URETIM_OPERATORU: "Production Operator",
    Role.SISELEME_PERSONELI: "Bottling & Packaging Operator",
    Role.DEPO_SEVKIYAT: "Warehouse & Shipping Clerk",
    Role.SATIS_PERSONELI: "Sales Representative",
    Role.MUHASEBE: "Accountant",
    Role.DENETCI: "Read-only Auditor",
}


class Perm(StrEnum):
    """Ayrik yetkiler."""

    # Kullanici / sistem
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"
    AUDIT_READ = "audit:read"

    # Yedekleme. DIKKAT: bu yetkiler bilerek ":read" ile BITMIYOR.
    # `_ALL_READ` her ":read" yetkisini toplayip salt-okunur denetci rolune
    # verir; "backup:read" adi kullanilsaydi denetci butun veritabanini
    # (parola ozetleri, sifreli API anahtarlari, denetim gunlugu dahil)
    # indirebilirdi.
    BACKUP_MANAGE = "backup:manage"  # yedek al / listele / sil
    BACKUP_DOWNLOAD = "backup:download"  # yedek dosyasini makine disina cikar

    # Bag / uzum kabul
    VINEYARD_READ = "vineyard:read"
    VINEYARD_WRITE = "vineyard:write"
    HARVEST_READ = "harvest:read"
    HARVEST_WRITE = "harvest:write"

    # Parti / izlenebilirlik
    LOT_READ = "lot:read"
    LOT_WRITE = "lot:write"

    # Tank
    TANK_READ = "tank:read"
    TANK_WRITE = "tank:write"
    TANK_TRANSFER = "tank:transfer"

    # Fermantasyon
    FERMENTATION_READ = "fermentation:read"
    FERMENTATION_WRITE = "fermentation:write"

    # Laboratuvar
    LAB_READ = "lab:read"
    LAB_WRITE = "lab:write"
    LAB_APPROVE = "lab:approve"

    # Recete / kupaj
    RECIPE_READ = "recipe:read"
    RECIPE_WRITE = "recipe:write"
    RECIPE_APPROVE = "recipe:approve"

    # Fici / mahzen
    BARREL_READ = "barrel:read"
    BARREL_WRITE = "barrel:write"

    # Siseleme
    BOTTLING_READ = "bottling:read"
    BOTTLING_WRITE = "bottling:write"

    # Stok / satinalma / sevkiyat
    INVENTORY_READ = "inventory:read"
    INVENTORY_WRITE = "inventory:write"
    PURCHASE_READ = "purchase:read"
    PURCHASE_WRITE = "purchase:write"
    SHIPMENT_READ = "shipment:read"
    SHIPMENT_WRITE = "shipment:write"

    # Bakim / temizlik
    MAINTENANCE_READ = "maintenance:read"
    MAINTENANCE_WRITE = "maintenance:write"

    # Maliyet / rapor
    COST_READ = "cost:read"
    REPORT_READ = "report:read"
    REPORT_EXPORT = "report:export"

    # Yapay zeka
    AI_USE = "ai:use"
    AI_CONFIGURE = "ai:configure"
    AI_TERMINAL = "ai:terminal"
    AI_TERMINAL_APPROVE = "ai:terminal:approve"


PERM_LABELS_TR: dict[str, str] = {
    Perm.USER_READ: "Kullanıcıları görüntüle",
    Perm.USER_WRITE: "Kullanıcı yönet",
    Perm.SETTINGS_READ: "Ayarları görüntüle",
    Perm.SETTINGS_WRITE: "Ayarları değiştir",
    Perm.AUDIT_READ: "Denetim günlüğünü görüntüle",
    Perm.BACKUP_MANAGE: "Yedek al ve yönet",
    Perm.BACKUP_DOWNLOAD: "Yedek dosyasını indir",
    Perm.VINEYARD_READ: "Bağ/parsel görüntüle",
    Perm.VINEYARD_WRITE: "Bağ/parsel yönet",
    Perm.HARVEST_READ: "Üzüm kabul görüntüle",
    Perm.HARVEST_WRITE: "Üzüm kabul kaydı gir",
    Perm.LOT_READ: "Parti görüntüle",
    Perm.LOT_WRITE: "Parti yönet",
    Perm.TANK_READ: "Tank görüntüle",
    Perm.TANK_WRITE: "Tank yönet",
    Perm.TANK_TRANSFER: "Tank transferi yap",
    Perm.FERMENTATION_READ: "Fermantasyon görüntüle",
    Perm.FERMENTATION_WRITE: "Fermantasyon ölçümü gir",
    Perm.LAB_READ: "Laboratuvar sonuçlarını görüntüle",
    Perm.LAB_WRITE: "Laboratuvar analizi gir",
    Perm.LAB_APPROVE: "Laboratuvar sonucu onayla/reddet",
    Perm.RECIPE_READ: "Reçete/kupaj görüntüle",
    Perm.RECIPE_WRITE: "Reçete/kupaj düzenle",
    Perm.RECIPE_APPROVE: "Reçete/kupaj onayla",
    Perm.BARREL_READ: "Fıçı görüntüle",
    Perm.BARREL_WRITE: "Fıçı yönet",
    Perm.BOTTLING_READ: "Şişeleme görüntüle",
    Perm.BOTTLING_WRITE: "Şişeleme emri yönet",
    Perm.INVENTORY_READ: "Stok görüntüle",
    Perm.INVENTORY_WRITE: "Stok hareketi gir",
    Perm.PURCHASE_READ: "Satın alma görüntüle",
    Perm.PURCHASE_WRITE: "Satın alma yönet",
    Perm.SHIPMENT_READ: "Sevkiyat görüntüle",
    Perm.SHIPMENT_WRITE: "Sevkiyat yönet",
    Perm.MAINTENANCE_READ: "Bakım kayıtlarını görüntüle",
    Perm.MAINTENANCE_WRITE: "Bakım/temizlik kaydı gir",
    Perm.COST_READ: "Maliyet görüntüle",
    Perm.REPORT_READ: "Rapor görüntüle",
    Perm.REPORT_EXPORT: "Rapor dışa aktar",
    Perm.AI_USE: "Yapay zekâ kullan",
    Perm.AI_CONFIGURE: "Yapay zekâ sağlayıcı ayarla",
    Perm.AI_TERMINAL: "AI terminal görevini hazırla",
    Perm.AI_TERMINAL_APPROVE: "AI terminal görevini onayla/çalıştır",
}

PERM_LABELS_EN: dict[str, str] = {
    Perm.USER_READ: "View users",
    Perm.USER_WRITE: "Manage users",
    Perm.SETTINGS_READ: "View settings",
    Perm.SETTINGS_WRITE: "Change settings",
    Perm.AUDIT_READ: "View audit log",
    Perm.BACKUP_MANAGE: "Create and manage backups",
    Perm.BACKUP_DOWNLOAD: "Download backup file",
    Perm.VINEYARD_READ: "View vineyards/parcels",
    Perm.VINEYARD_WRITE: "Manage vineyards/parcels",
    Perm.HARVEST_READ: "View grape intake",
    Perm.HARVEST_WRITE: "Record grape intake",
    Perm.LOT_READ: "View lots",
    Perm.LOT_WRITE: "Manage lots",
    Perm.TANK_READ: "View tanks",
    Perm.TANK_WRITE: "Manage tanks",
    Perm.TANK_TRANSFER: "Perform tank transfers",
    Perm.FERMENTATION_READ: "View fermentations",
    Perm.FERMENTATION_WRITE: "Record fermentation readings",
    Perm.LAB_READ: "View lab results",
    Perm.LAB_WRITE: "Record lab analyses",
    Perm.LAB_APPROVE: "Approve/reject lab results",
    Perm.RECIPE_READ: "View recipes/blends",
    Perm.RECIPE_WRITE: "Edit recipes/blends",
    Perm.RECIPE_APPROVE: "Approve recipes/blends",
    Perm.BARREL_READ: "View barrels",
    Perm.BARREL_WRITE: "Manage barrels",
    Perm.BOTTLING_READ: "View bottling",
    Perm.BOTTLING_WRITE: "Manage bottling orders",
    Perm.INVENTORY_READ: "View inventory",
    Perm.INVENTORY_WRITE: "Record stock movements",
    Perm.PURCHASE_READ: "View purchasing",
    Perm.PURCHASE_WRITE: "Manage purchasing",
    Perm.SHIPMENT_READ: "View shipments",
    Perm.SHIPMENT_WRITE: "Manage shipments",
    Perm.MAINTENANCE_READ: "View maintenance records",
    Perm.MAINTENANCE_WRITE: "Record maintenance/cleaning",
    Perm.COST_READ: "View costs",
    Perm.REPORT_READ: "View reports",
    Perm.REPORT_EXPORT: "Export reports",
    Perm.AI_USE: "Use AI features",
    Perm.AI_CONFIGURE: "Configure AI providers",
    Perm.AI_TERMINAL: "Prepare AI terminal tasks",
    Perm.AI_TERMINAL_APPROVE: "Approve/run AI terminal tasks",
}


def rol_etiketleri(dil: str = "tr") -> dict[str, str]:
    """Dile gore rol etiketleri; eksik ceviri Turkceye duser."""
    if dil != "en":
        return dict(ROLE_LABELS_TR)
    return {k: ROLE_LABELS_EN.get(k, v) for k, v in ROLE_LABELS_TR.items()}


def yetki_etiketleri(dil: str = "tr") -> dict[str, str]:
    """Dile gore yetki etiketleri; eksik ceviri Turkceye duser."""
    if dil != "en":
        return {str(k): v for k, v in PERM_LABELS_TR.items()}
    return {str(k): PERM_LABELS_EN.get(k, v) for k, v in PERM_LABELS_TR.items()}

# Salt-okunur yetkilerin tamami (denetci rolu icin)
_ALL_READ: frozenset[Perm] = frozenset(p for p in Perm if p.value.endswith(":read"))

_ALL: frozenset[Perm] = frozenset(Perm)


ROLE_PERMISSIONS: dict[Role, frozenset[Perm]] = {
    # Her seye erisir
    Role.SISTEM_YONETICISI: _ALL,
    # Uretim disi sistem ayarlari haric her sey + onaylar.
    # BACKUP_DOWNLOAD haric tutulur: yedek dosyasi tum veritabaninin kopyasidir
    # (parola ozetleri, sifreli API anahtarlari, denetim gunlugu). Yedek ALMAK
    # isletme sorumlulugudur, yedegi makine disina CIKARMAK sistem yoneticisinin.
    Role.ISLETME_YONETICISI: _ALL
    - {
        Perm.USER_WRITE,
        Perm.AI_TERMINAL,
        Perm.AI_TERMINAL_APPROVE,
        Perm.BACKUP_DOWNLOAD,
    },
    # Sarap uretiminin teknik sahibi
    Role.ENOLOG: frozenset(
        _ALL_READ
        | {
            Perm.HARVEST_WRITE,
            Perm.LOT_WRITE,
            Perm.TANK_WRITE,
            Perm.TANK_TRANSFER,
            Perm.FERMENTATION_WRITE,
            Perm.LAB_WRITE,
            Perm.LAB_APPROVE,
            Perm.RECIPE_WRITE,
            Perm.RECIPE_APPROVE,
            Perm.BARREL_WRITE,
            Perm.BOTTLING_WRITE,
            Perm.REPORT_EXPORT,
            Perm.AI_USE,
        }
    ),
    Role.BAGCILIK_UZMANI: frozenset(
        {
            Perm.VINEYARD_READ,
            Perm.VINEYARD_WRITE,
            Perm.HARVEST_READ,
            Perm.HARVEST_WRITE,
            Perm.LOT_READ,
            Perm.LAB_READ,
            Perm.REPORT_READ,
            Perm.REPORT_EXPORT,
            Perm.AI_USE,
        }
    ),
    Role.LABORATUVAR_TEKNISYENI: frozenset(
        {
            Perm.LAB_READ,
            Perm.LAB_WRITE,
            Perm.LOT_READ,
            Perm.TANK_READ,
            Perm.FERMENTATION_READ,
            Perm.FERMENTATION_WRITE,
            Perm.BARREL_READ,
            Perm.REPORT_READ,
            Perm.REPORT_EXPORT,
            Perm.AI_USE,
        }
    ),
    Role.MAHZEN_SORUMLUSU: frozenset(
        {
            Perm.BARREL_READ,
            Perm.BARREL_WRITE,
            Perm.TANK_READ,
            Perm.TANK_TRANSFER,
            Perm.LOT_READ,
            Perm.LAB_READ,
            Perm.MAINTENANCE_READ,
            Perm.MAINTENANCE_WRITE,
            Perm.REPORT_READ,
            Perm.AI_USE,
        }
    ),
    Role.URETIM_OPERATORU: frozenset(
        {
            Perm.TANK_READ,
            Perm.TANK_TRANSFER,
            Perm.FERMENTATION_READ,
            Perm.FERMENTATION_WRITE,
            Perm.LOT_READ,
            Perm.HARVEST_READ,
            Perm.MAINTENANCE_READ,
            Perm.MAINTENANCE_WRITE,
            Perm.AI_USE,
        }
    ),
    Role.SISELEME_PERSONELI: frozenset(
        {
            Perm.BOTTLING_READ,
            Perm.BOTTLING_WRITE,
            Perm.LOT_READ,
            Perm.TANK_READ,
            Perm.INVENTORY_READ,
            Perm.INVENTORY_WRITE,
            Perm.MAINTENANCE_READ,
            Perm.AI_USE,
        }
    ),
    Role.DEPO_SEVKIYAT: frozenset(
        {
            Perm.INVENTORY_READ,
            Perm.INVENTORY_WRITE,
            Perm.SHIPMENT_READ,
            Perm.SHIPMENT_WRITE,
            Perm.PURCHASE_READ,
            Perm.BOTTLING_READ,
            Perm.LOT_READ,
            Perm.REPORT_READ,
            Perm.AI_USE,
        }
    ),
    Role.SATIS_PERSONELI: frozenset(
        {
            Perm.INVENTORY_READ,
            Perm.SHIPMENT_READ,
            Perm.SHIPMENT_WRITE,
            Perm.BOTTLING_READ,
            Perm.LOT_READ,
            Perm.REPORT_READ,
            Perm.REPORT_EXPORT,
            Perm.AI_USE,
        }
    ),
    Role.MUHASEBE: frozenset(
        {
            Perm.COST_READ,
            Perm.PURCHASE_READ,
            Perm.PURCHASE_WRITE,
            Perm.INVENTORY_READ,
            Perm.SHIPMENT_READ,
            Perm.BOTTLING_READ,
            Perm.LOT_READ,
            Perm.REPORT_READ,
            Perm.REPORT_EXPORT,
            Perm.AI_USE,
        }
    ),
    # Salt okunur: hicbir yazma yetkisi yok
    Role.DENETCI: frozenset(_ALL_READ | {Perm.AUDIT_READ}),
}


def permissions_for(roles: list[str] | set[str]) -> set[str]:
    """Verilen rollerin birlesik yetki kumesini doner."""
    out: set[str] = set()
    for r in roles:
        try:
            role = Role(r)
        except ValueError:
            continue
        out |= {p.value for p in ROLE_PERMISSIONS[role]}
    return out


def has_permission(roles: list[str] | set[str], perm: Perm | str) -> bool:
    return str(perm) in permissions_for(roles)


def role_catalog() -> list[dict[str, object]]:
    """Arayuz icin rol + yetki katalogu."""
    return [
        {
            "kod": role.value,
            "ad": ROLE_LABELS_TR[role],
            "yetkiler": sorted(p.value for p in perms),
        }
        for role, perms in ROLE_PERMISSIONS.items()
    ]
