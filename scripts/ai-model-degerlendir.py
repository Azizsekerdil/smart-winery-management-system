"""LM Studio'daki yerel modelleri şaraphane görevlerinde karşılaştırır.

Her model için ölçülenler:
  * Türkçe kalitesi (dil bütünlüğü, terim doğruluğu)
  * JSON üretimi (geçerli JSON verebiliyor mu)
  * Sayısal/mantıksal doğruluk
  * Gecikme (ilk yanıt süresi)
  * Hata oranı

Sonuç `docs/AI_MODEL_EVALUATION.md` dosyasına yazılır.

Kullanım:
    .venv\\Scripts\\python.exe scripts\\ai-model-degerlendir.py
    .venv\\Scripts\\python.exe scripts\\ai-model-degerlendir.py --model qwen/qwen3-vl-8b
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "backend"))

import httpx

TABAN = "http://localhost:1234/v1"
ZAMAN_ASIMI = 240.0

# Turkce'de yalnizca bu dilde bulunan karakterler (dil butunlugu gostergesi)
TURKCE_KARAKTERLER = set("çğıöşüÇĞİÖŞÜ")


@dataclass
class Gorev:
    ad: str
    sistem: str
    kullanici: str
    dogrula: str  # "turkce" | "json" | "sayisal"
    # Akil yurutme (reasoning) modelleri butcenin buyuk kismini dusunmeye harcar;
    # bu yuzden token siniri comert tutulur. Dusuk sinir "bos yanit" uretir.
    max_token: int = 2000
    beklenen_anahtarlar: list[str] = field(default_factory=list)
    beklenen_sayi: float | None = None


GOREVLER: list[Gorev] = [
    Gorev(
        ad="Türkçe enoloji açıklaması",
        sistem=(
            "Sen bir Türk şaraphanesinde çalışan enolog danışmanısın. "
            "Yalnızca Türkçe yanıt ver."
        ),
        kullanici=(
            "Kırmızı şarap fermantasyonunda uçucu asitlik 1.10 g/L ölçüldü "
            "(üst sınır 0.90 g/L). Olası nedenleri ve alınacak önlemleri "
            "en fazla 120 kelimeyle açıkla."
        ),
        dogrula="turkce",
        max_token=2000,
    ),
    Gorev(
        ad="Yapılandırılmış JSON üretimi",
        sistem=(
            "Sen bir veri çıkarma aracısın. YALNIZCA geçerli JSON döndür. "
            "Markdown kod bloğu, açıklama veya başka metin EKLEME."
        ),
        kullanici=(
            "Şu ölçümü JSON'a çevir: 'TNK-02 tankında 12 Ağustos günü "
            "sıcaklık 28.4 derece, Brix 4.2, pH 3.52 ölçüldü.'\n"
            'Şema: {"tank": string, "sicaklik_c": number, "brix": number, "ph": number}'
        ),
        dogrula="json",
        max_token=1500,
        beklenen_anahtarlar=["tank", "sicaklik_c", "brix", "ph"],
    ),
    Gorev(
        ad="Sayısal hesap (kupaj oranı)",
        sistem="Sen bir üretim hesaplama asistanısın. Kısa ve net yanıt ver.",
        kullanici=(
            "6500 litre A partisi ile 3500 litre B partisi karıştırılıyor. "
            "A partisinin toplam karışımdaki yüzdesi kaçtır? "
            "Yalnızca sayıyı yaz, yüzde işareti koyma."
        ),
        dogrula="sayisal",
        max_token=1200,
        beklenen_sayi=65.0,
    ),
    Gorev(
        ad="Türkçe SOP adımı yazımı",
        sistem="Sen bir teknik dokümantasyon yazarısın. Türkçe yaz.",
        kullanici=(
            "Paslanmaz çelik tank için CIP (yerinde temizlik) prosedürünü "
            "5 numaralı adım hâlinde yaz. Her adım tek cümle olsun."
        ),
        dogrula="turkce",
        max_token=2000,
    ),
]


@dataclass
class Sonuc:
    model: str
    gorev: str
    basarili: bool
    gecikme_ms: int
    puan: float
    not_: str
    token: int = 0


def turkce_puani(metin: str) -> tuple[float, str]:
    """Yanıtın Türkçe bütünlüğünü kabaca ölçer."""
    if not metin.strip():
        return 0.0, "Boş yanıt"
    ozel = sum(1 for c in metin if c in TURKCE_KARAKTERLER)
    kelime = len(metin.split())
    if kelime < 15:
        return 0.3, f"Çok kısa yanıt ({kelime} kelime)"

    # İngilizceye kayma göstergesi
    ingilizce = len(
        re.findall(
            r"\b(the|and|is|are|with|from|this|that|should|would|temperature|acidity)\b",
            metin,
            re.IGNORECASE,
        )
    )
    oran = ozel / max(1, kelime)
    puan = min(1.0, oran * 6)
    if ingilizce > 3:
        puan *= 0.4
        return puan, f"İngilizce sızıntısı ({ingilizce} kelime), {kelime} kelime"
    return puan, f"{kelime} kelime, {ozel} Türkçe özel karakter"


def json_puani(metin: str, anahtarlar: list[str]) -> tuple[float, str]:
    ham = metin.strip()
    # Model kod bloğu döndürdüyse temizle
    blok = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", ham, re.DOTALL)
    if blok:
        ham = blok.group(1)
    else:
        ilk = ham.find("{")
        son = ham.rfind("}")
        if ilk != -1 and son > ilk:
            ham = ham[ilk : son + 1]
    try:
        veri = json.loads(ham)
    except json.JSONDecodeError as exc:
        return 0.0, f"Geçersiz JSON: {exc.msg}"
    if not isinstance(veri, dict):
        return 0.2, "JSON sözlük değil"
    eksik = [a for a in anahtarlar if a not in veri]
    if eksik:
        return 0.5, f"Eksik anahtar: {', '.join(eksik)}"
    temiz = metin.strip().startswith("{")
    return (1.0 if temiz else 0.85), (
        "Tam ve temiz JSON" if temiz else "Doğru JSON (fazladan metin içeriyor)"
    )


def sayisal_puan(metin: str, beklenen: float) -> tuple[float, str]:
    sayilar = re.findall(r"-?\d+[.,]?\d*", metin.replace(",", "."))
    if not sayilar:
        return 0.0, "Sayı bulunamadı"
    for s in sayilar:
        try:
            if abs(float(s) - beklenen) < 0.6:
                return 1.0, f"Doğru: {s}"
        except ValueError:
            continue
    return 0.0, f"Yanlış: {sayilar[0]} (beklenen {beklenen})"


async def modelleri_al(client: httpx.AsyncClient) -> list[str]:
    yanit = await client.get("/models")
    yanit.raise_for_status()
    return [m["id"] for m in yanit.json().get("data", []) if m.get("id")]


async def gorev_calistir(client: httpx.AsyncClient, model: str, gorev: Gorev) -> Sonuc:
    basla = time.perf_counter()
    mesajlar = [
        {"role": "system", "content": gorev.sistem},
        {"role": "user", "content": gorev.kullanici},
    ]
    katlandi = False
    try:
        yanit = await client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": mesajlar,
                "temperature": 0.2,
                "max_tokens": gorev.max_token,
            },
        )
        # Bazi yerel modellerin sohbet sablonu `system` rolunu kabul etmez
        # (orn. BioMistral: "Only user and assistant roles are supported!").
        # Uygulama katmani da ayni davranisi gosterir: sistemi katlayip yeniden dener.
        if yanit.status_code == 400 and "roles are supported" in yanit.text:
            katlandi = True
            mesajlar = [
                {"role": "user", "content": f"{gorev.sistem}\n\n---\n\n{gorev.kullanici}"}
            ]
            yanit = await client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "messages": mesajlar,
                    "temperature": 0.2,
                    "max_tokens": gorev.max_token,
                },
            )
        gecikme = int((time.perf_counter() - basla) * 1000)
        if yanit.status_code >= 400:
            return Sonuc(model, gorev.ad, False, gecikme, 0.0, f"HTTP {yanit.status_code}")
        govde = yanit.json()
        mesaj = (govde.get("choices") or [{}])[0].get("message", {})
        icerik = mesaj.get("content", "") or ""
        kullanim = govde.get("usage") or {}
        ayrinti = kullanim.get("completion_tokens_details") or {}
        dusunme = int(ayrinti.get("reasoning_tokens") or 0)
        token = int(kullanim.get("completion_tokens") or 0)
        if not icerik.strip() and dusunme > 0:
            return Sonuc(
                model, gorev.ad, True, gecikme, 0.0,
                f"Akıl yürütmede {dusunme} belirteç harcandı, yanıt üretilmedi", token,
            )
    except httpx.TimeoutException:
        return Sonuc(model, gorev.ad, False, int(ZAMAN_ASIMI * 1000), 0.0, "Zaman aşımı")
    except httpx.HTTPError as exc:
        return Sonuc(model, gorev.ad, False, 0, 0.0, f"Ağ hatası: {type(exc).__name__}")

    if gorev.dogrula == "turkce":
        puan, aciklama = turkce_puani(icerik)
    elif gorev.dogrula == "json":
        puan, aciklama = json_puani(icerik, gorev.beklenen_anahtarlar)
    else:
        puan, aciklama = sayisal_puan(icerik, gorev.beklenen_sayi or 0)

    if katlandi:
        aciklama += " · system rolü desteklenmiyor, katlandı"
    return Sonuc(model, gorev.ad, True, gecikme, puan, aciklama, token)


def rapor_yaz(sonuclar: list[Sonuc], modeller: list[str]) -> str:
    import datetime as dt

    satirlar = [
        "# Yerel Yapay Zekâ Modeli Değerlendirmesi (LM Studio)",
        "",
        f"**Oluşturma:** {dt.datetime.now():%d.%m.%Y %H:%M}  ",
        f"**Sunucu:** `{TABAN}`  ",
        "**Yöntem:** Her model, dört şaraphane görevinde küçük ve tekrarlanabilir",
        "isteklerle sınandı (temperature 0.2). Puanlama otomatiktir:",
        "Türkçe bütünlüğü karakter/kelime analiziyle, JSON geçerliliği ayrıştırmayla,",
        "sayısal doğruluk beklenen değerle karşılaştırılarak ölçülür.",
        "",
        "> Bu değerlendirme donanıma ve LM Studio ayarlarına (bağlam uzunluğu, GPU",
        "> katman sayısı, niceleme) bağlıdır. Farklı makinede sonuçlar değişebilir.",
        "",
        "## Özet tablo",
        "",
        "| Model | Ort. puan | Ort. gecikme | Türkçe | JSON | Sayısal | Hata |",
        "|---|---|---|---|---|---|---|",
    ]

    ozet: dict[str, dict] = {}
    for m in modeller:
        kendi = [s for s in sonuclar if s.model == m]
        if not kendi:
            continue
        basarili = [s for s in kendi if s.basarili]
        turkce = [s for s in kendi if "Türkçe" in s.gorev or "SOP" in s.gorev]
        js = [s for s in kendi if "JSON" in s.gorev]
        sy = [s for s in kendi if "Sayısal" in s.gorev]
        ozet[m] = {
            "puan": sum(s.puan for s in kendi) / len(kendi),
            "gecikme": (sum(s.gecikme_ms for s in basarili) / len(basarili)) if basarili else 0,
            "turkce": sum(s.puan for s in turkce) / max(1, len(turkce)),
            "json": sum(s.puan for s in js) / max(1, len(js)),
            "sayisal": sum(s.puan for s in sy) / max(1, len(sy)),
            "hata": len(kendi) - len(basarili),
        }

    for m, o in sorted(ozet.items(), key=lambda x: -x[1]["puan"]):
        satirlar.append(
            f"| `{m}` | **{o['puan']:.2f}** | {o['gecikme'] / 1000:.1f} sn | "
            f"{o['turkce']:.2f} | {o['json']:.2f} | {o['sayisal']:.2f} | {o['hata']} |"
        )

    satirlar += ["", "## Görev bazlı ayrıntı", ""]
    for m in modeller:
        kendi = [s for s in sonuclar if s.model == m]
        if not kendi:
            continue
        satirlar += [f"### `{m}`", "", "| Görev | Puan | Süre | Not |", "|---|---|---|---|"]
        for s in kendi:
            satirlar.append(
                f"| {s.gorev} | {s.puan:.2f} | {s.gecikme_ms / 1000:.1f} sn | {s.not_} |"
            )
        satirlar.append("")

    return "\n".join(satirlar)


async def main() -> int:
    ayristirici = argparse.ArgumentParser(description="LM Studio model değerlendirmesi")
    ayristirici.add_argument("--model", action="append", help="Yalnızca bu modeli test et")
    ayristirici.add_argument("--cikti", default=str(KOK / "docs" / "AI_MODEL_EVALUATION.md"))
    argumanlar = ayristirici.parse_args()

    async with httpx.AsyncClient(base_url=TABAN, timeout=ZAMAN_ASIMI) as client:
        try:
            tumu = await modelleri_al(client)
        except httpx.HTTPError as exc:
            print(f"LM Studio'ya ulaşılamadı ({TABAN}): {type(exc).__name__}")
            print("LM Studio uygulamasını açıp yerel sunucuyu başlatın.")
            return 1

        # Gömme modelleri sohbet testine girmez
        adaylar = [m for m in tumu if "embed" not in m.lower()]
        if argumanlar.model:
            adaylar = [m for m in adaylar if m in argumanlar.model]

        print(f"Bulunan model sayısı: {len(tumu)} · test edilecek: {len(adaylar)}")
        sonuclar: list[Sonuc] = []
        for model in adaylar:
            print(f"\n▶ {model}")
            for gorev in GOREVLER:
                s = await gorev_calistir(client, model, gorev)
                sonuclar.append(s)
                durum = "✓" if s.basarili else "✗"
                print(f"   {durum} {gorev.ad:34s} puan {s.puan:.2f}  {s.gecikme_ms / 1000:5.1f} sn  {s.not_}")

    rapor = rapor_yaz(sonuclar, adaylar)
    hedef = Path(argumanlar.cikti)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(rapor, encoding="utf-8", newline="\n")
    print(f"\nRapor yazıldı: {hedef}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
