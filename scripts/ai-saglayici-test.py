"""Tüm yapay zekâ sağlayıcılarının bağlantısını sırayla test eder.

Her sağlayıcı için:
  * yapılandırma durumu (etkin mi, anahtar var mı, model seçili mi)
  * `/models` çağrısı (ücretsiz)
  * isteğe bağlı küçük sohbet isteği (`--sohbet` — bulutta cüzi ücret doğurabilir)

API anahtarları **hiçbir aşamada ekrana yazılmaz**; yalnızca "var/yok" ve
geri döndürülemez parmak izi gösterilir.

Kullanım:
    .venv\\Scripts\\python.exe scripts\\ai-saglayici-test.py
    .venv\\Scripts\\python.exe scripts\\ai-saglayici-test.py --sohbet
    .venv\\Scripts\\python.exe scripts\\ai-saglayici-test.py --saglayici lmstudio
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

VARSAYILAN_TABAN = os.environ.get("SARAPHANE_API", "http://127.0.0.1:8010/api/v1")

ONERI: dict[str, list[str]] = {
    "anthropic": [
        "1. https://console.anthropic.com adresinden bir API anahtarı oluşturun",
        "2. Uygulamada: Ayarlar → Claude (Anthropic) → Ekle → anahtarı yapıştırın",
        "3. 'Model listesini yenile' ile güncel modelleri çekip varsayılanı seçin",
    ],
    "nvidia": [
        "1. https://build.nvidia.com adresinde bir model kartını açın",
        "2. 'Generate API Key' düğmesiyle anahtar oluşturun (nvapi- ile başlar)",
        "3. Uygulamada: Ayarlar → NVIDIA Build → Ekle → anahtarı yapıştırın",
        "   Ayrıntılı model önerileri: docs/NVIDIA_MODEL_SELECTION.md",
    ],
    "lmstudio": [
        "1. LM Studio uygulamasını açın",
        "2. Developer (Geliştirici) sekmesinden bir model yükleyin",
        "3. 'Start Server' ile yerel sunucuyu başlatın (http://localhost:1234/v1)",
    ],
}


def yaz(metin: str = "", girinti: int = 0) -> None:
    print(" " * girinti + metin)


def main() -> int:
    ayristirici = argparse.ArgumentParser(description="AI sağlayıcı bağlantı testi")
    ayristirici.add_argument("--taban", default=VARSAYILAN_TABAN, help="API kök adresi")
    ayristirici.add_argument("--kullanici", default="admin")
    ayristirici.add_argument("--parola", default=os.environ.get("SARAPHANE_PAROLA", ""))
    ayristirici.add_argument("--saglayici", action="append", help="Yalnızca bu sağlayıcıyı test et")
    ayristirici.add_argument(
        "--sohbet",
        action="store_true",
        help="Model listesine ek olarak küçük bir sohbet isteği de gönder "
        "(bulut sağlayıcılarda cüzi ücret doğurabilir)",
    )
    argumanlar = ayristirici.parse_args()

    if not argumanlar.parola:
        yaz("Parola verilmedi.")
        yaz("Kullanım: --parola <parola>  veya  SARAPHANE_PAROLA ortam değişkeni")
        return 2

    with httpx.Client(base_url=argumanlar.taban, timeout=420) as istemci:
        try:
            giris = istemci.post(
                "/auth/login",
                json={"username": argumanlar.kullanici, "password": argumanlar.parola},
            )
        except httpx.HTTPError as exc:
            yaz(f"Backend'e ulaşılamadı ({argumanlar.taban}): {type(exc).__name__}")
            yaz("Sistemi başlatın:  .\\Baslat.bat")
            return 1

        if giris.status_code != 200:
            yaz(f"Giriş başarısız ({giris.status_code}): {giris.json().get('detail', '')}")
            return 1

        basliklar = {"Authorization": f"Bearer {giris.json()['access_token']}"}
        saglayicilar = istemci.get("/ai/providers", headers=basliklar).json()
        if argumanlar.saglayici:
            saglayicilar = [
                s for s in saglayicilar if s["provider_key"] in argumanlar.saglayici
            ]

        yaz("=" * 74)
        yaz("  YAPAY ZEKÂ SAĞLAYICI BAĞLANTI TESTİ")
        yaz("=" * 74)

        hazir: list[str] = []
        eksik: list[str] = []

        for s in saglayicilar:
            kod = s["provider_key"]
            yaz()
            yaz(f"▶ {s['display_name']}  ({kod})")
            yaz(f"gizlilik : {s['privacy_level']}", 3)
            yaz(f"etkin    : {'evet' if s['enabled'] else 'HAYIR'}", 3)

            if s["requires_api_key"]:
                if s["has_api_key"]:
                    yaz(f"anahtar  : tanımlı (parmak izi {s['api_key_fingerprint']})", 3)
                else:
                    yaz("anahtar  : TANIMSIZ", 3)
            else:
                yaz("anahtar  : gerekmiyor", 3)

            yaz(f"model    : {s['default_model'] or '(seçilmedi)'}", 3)

            if not s["enabled"]:
                yaz("→ Sağlayıcı kapalı, test edilmedi.", 3)
                eksik.append(kod)
                continue

            if s["requires_api_key"] and not s["has_api_key"]:
                yaz("→ Anahtar olmadan test edilemez.", 3)
                for adim in ONERI.get(kod, []):
                    yaz(adim, 5)
                eksik.append(kod)
                continue

            # ---------------------------------------------------- bağlantı testi
            try:
                sonuc = istemci.post(
                    f"/ai/providers/{kod}/test",
                    headers=basliklar,
                    params={"with_chat": argumanlar.sohbet},
                ).json()
            except httpx.HTTPError as exc:
                yaz(f"→ İstek başarısız: {type(exc).__name__}", 3)
                eksik.append(kod)
                continue

            if sonuc["ok"]:
                yaz(
                    f"→ BAĞLANTI TAMAM · {sonuc.get('models_found', 0)} model · "
                    f"{sonuc.get('latency_ms', 0)} ms",
                    3,
                )
                if sonuc.get("sample_response"):
                    yaz(f"örnek yanıt: {sonuc['sample_response'][:70]}", 5)
                hazir.append(kod)
            else:
                yaz(f"→ BAŞARISIZ ({sonuc['status']})", 3)
                yaz(sonuc["message"][:200], 5)
                for adim in ONERI.get(kod, []):
                    yaz(adim, 5)
                eksik.append(kod)

        yaz()
        yaz("=" * 74)
        yaz(f"  HAZIR : {', '.join(hazir) if hazir else '(yok)'}")
        yaz(f"  EKSİK : {', '.join(eksik) if eksik else '(yok)'}")
        yaz("=" * 74)
        if eksik:
            yaz()
            yaz("Not: Eksik sağlayıcılar uygulamayı ETKİLEMEZ. Sistem, kullanılabilir")
            yaz("     ilk sağlayıcıya güvenli şekilde geri döner; hiçbiri yoksa açık")
            yaz("     bir Türkçe uyarı gösterir ve diğer bölümler normal çalışır.")

    return 0 if hazir else 1


if __name__ == "__main__":
    sys.exit(main())
