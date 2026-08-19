"""Depoya gönderilecek dosyalarda gizli bilgi taraması.

Git tarafından **takip edilen** tüm dosyalar bilinen anahtar biçimlerine karşı
denetlenir. Bulunan değerler ekrana **yazılmaz**; yalnızca dosya, satır ve kalıp
adı bildirilir.

Kullanım:
    .venv\\Scripts\\python.exe scripts\\gizli-tara.py
    .venv\\Scripts\\python.exe scripts\\gizli-tara.py --gecmis   # Git geçmişini de tara

Çıkış kodu 0 = temiz, 1 = bulgu var (commit/push etmeyin).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]

KALIPLAR: list[tuple[str, re.Pattern[str]]] = [
    ("Anthropic API anahtarı", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("NVIDIA API anahtarı", re.compile(r"nvapi-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI API anahtarı", re.compile(r"\bsk-[A-Za-z0-9]{32,}")),
    ("GitHub belirteci", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("AWS erişim anahtarı", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack belirteci", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("Google API anahtarı", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Özel anahtar bloğu", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("JWT", re.compile(r"\bey[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}")),
    ("Bağlantı dizesinde parola", re.compile(r"://[^\s:/@]+:[^\s:/@]{6,}@")),
    ("Doldurulmuş SECRET_KEY", re.compile(r"(?m)^SECRET_KEY=.{16,}$")),
    ("Doldurulmuş şifreleme anahtarı", re.compile(r"(?m)^SECRETS_ENCRYPTION_KEY=.{16,}$")),
    ("Doldurulmuş ANTHROPIC anahtarı", re.compile(r"(?m)^ANTHROPIC_API_KEY=.{8,}$")),
    ("Doldurulmuş NVIDIA anahtarı", re.compile(r"(?m)^NVIDIA_API_KEY=.{8,}$")),
]

# Açıkça yer tutucu olan eşleşmeler (dokümantasyon ve şablonlar)
YER_TUTUCU = re.compile(
    r"\[|\]|<|>|\$\{|\$[A-Z_]+|xxx|XXX|\.\.\.|örnek|ornek|placeholder|PAROLA|degistirin|"
    r"YOUR_|SIZIN_|anahtariniz|anahtarınız",
    re.IGNORECASE,
)

# Bilinçli olarak sahte anahtar içeren dosyalar (maskeleme testleri)
BEKLENEN_DOSYALAR = {
    "tests/test_security_masking.py",
    "tests/test_ai_providers.py",
    "tests/conftest.py",
}

# Depoda hiç bulunmaması gereken dizinler ve uzantılar
YASAK_DIZINLER = ("data/uploads/", "data/backups/", "logs/", "models/")
YASAK_UZANTILAR = (".db", ".sqlite", ".sqlite3", ".log", ".gguf", ".safetensors", ".pem", ".key")


def yasak_dosya_mi(yol: str) -> bool:
    """`.env.example` ŞABLONDUR ve depoda bulunmalıdır; gerçek `.env` bulunmamalıdır."""
    if yol == ".env" or (yol.startswith(".env.") and yol != ".env.example"):
        return True
    return yol.startswith(YASAK_DIZINLER) or yol.endswith(YASAK_UZANTILAR)


def _git(*argumanlar: str) -> str:
    return subprocess.run(
        ["git", "-C", str(KOK), *argumanlar],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
        errors="ignore",
    ).stdout


def satir_no(metin: str, konum: int) -> int:
    return metin[:konum].count("\n") + 1


def dosyalari_tara(dosyalar: list[str]) -> tuple[list[str], list[str]]:
    """(gerçek bulgular, beklenen eşleşmeler) döner."""
    bulgular: list[str] = []
    beklenen: list[str] = []

    for rel in dosyalar:
        yol = KOK / rel
        if not yol.is_file():
            continue
        try:
            metin = yol.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for ad, kalip in KALIPLAR:
            for eslesme in kalip.finditer(metin):
                parca = eslesme.group(0)
                if rel in BEKLENEN_DOSYALAR:
                    beklenen.append(f"{rel} — {ad} (test verisi)")
                elif YER_TUTUCU.search(parca):
                    beklenen.append(f"{rel}:{satir_no(metin, eslesme.start())} — {ad} (yer tutucu)")
                else:
                    bulgular.append(f"{rel}:{satir_no(metin, eslesme.start())} — {ad}")
    return bulgular, beklenen


def gecmisi_tara() -> tuple[list[str], list[str]]:
    """Git geçmişindeki değişiklikleri **dosya bağlamıyla** tarar.

    Yama metnini olduğu gibi taramak, maskeleme testlerindeki sahte anahtarları
    da yakalayıp yanlış alarm üretir. Bu yüzden `+++ b/<yol>` başlıkları izlenir
    ve çalışma ağacıyla aynı muafiyetler uygulanır.
    """
    bulgular: list[str] = []
    beklenen: list[str] = []
    try:
        commitler = _git("rev-list", "--all").split()
    except subprocess.CalledProcessError:
        return [], []

    for commit in commitler:
        yama = _git("show", "--format=%H", "--unified=0", commit)
        aktif_dosya = "(bilinmiyor)"
        for satir in yama.splitlines():
            if satir.startswith("+++ b/"):
                aktif_dosya = satir[6:].strip()
                continue
            # Yalnızca EKLENEN satırlar denetlenir; silinenler zaten geçmişte kalır
            if not satir.startswith("+") or satir.startswith("+++"):
                continue
            for ad, kalip in KALIPLAR:
                for eslesme in kalip.finditer(satir):
                    if aktif_dosya in BEKLENEN_DOSYALAR:
                        beklenen.append(f"{aktif_dosya} — {ad} (test verisi)")
                    elif YER_TUTUCU.search(eslesme.group(0)):
                        beklenen.append(f"{aktif_dosya} — {ad} (yer tutucu)")
                    else:
                        bulgular.append(f"commit {commit[:8]} · {aktif_dosya} — {ad}")
    return sorted(set(bulgular)), sorted(set(beklenen))


def main() -> int:
    ayristirici = argparse.ArgumentParser(description="Gizli bilgi taraması")
    ayristirici.add_argument("--gecmis", action="store_true", help="Git geçmişini de tara")
    argumanlar = ayristirici.parse_args()

    try:
        dosyalar = [s for s in _git("ls-files").splitlines() if s.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("HATA: Git deposu bulunamadı veya git kurulu değil.")
        return 1

    print(f"Taranan takip edilen dosya : {len(dosyalar)}")
    print(f"Kalıp sayısı               : {len(KALIPLAR)}")
    print()

    bulgular, beklenen = dosyalari_tara(dosyalar)

    # Takip edilmemesi gereken dosyalar
    riskli = [d for d in dosyalar if yasak_dosya_mi(d)]

    if beklenen:
        print("Beklenen eşleşmeler (yer tutucu / test verisi) — sorun DEĞİL:")
        for b in sorted(set(beklenen)):
            print(f"  · {b}")
        print()

    hatali = False

    if bulgular:
        hatali = True
        print("!!! GİZLİ BİLGİ BULUNDU — COMMIT/PUSH ETMEYİN !!!")
        for b in bulgular:
            print(f"  ✗ {b}")
        print()

    if riskli:
        hatali = True
        print("!!! Depoda olmaması gereken dosyalar takip ediliyor !!!")
        for r in riskli:
            print(f"  ✗ {r}")
        print()

    if argumanlar.gecmis:
        print("Git geçmişi taranıyor…")
        gecmis_bulgulari, gecmis_beklenen = gecmisi_tara()
        if gecmis_beklenen:
            print("  Geçmişteki beklenen eşleşmeler (yer tutucu / test verisi):")
            for b in gecmis_beklenen:
                print(f"    · {b}")
        if gecmis_bulgulari:
            hatali = True
            print("!!! GİT GEÇMİŞİNDE GİZLİ BİLGİ !!!")
            for b in gecmis_bulgulari:
                print(f"  ✗ {b}")
            print("  Geçmişi temizlemeden push ETMEYİN.")
        else:
            print("  ✓ Git geçmişi temiz.")
        print()

    if hatali:
        return 1

    print("SONUÇ: Temiz.")
    print("  ✓ Takip edilen hiçbir dosyada gerçek gizli bilgi yok")
    print("  ✓ .env, veritabanı, günlükler, yüklemeler ve model dosyaları depo dışında")
    return 0


if __name__ == "__main__":
    sys.exit(main())
