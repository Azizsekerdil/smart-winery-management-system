"""Uygulama simgesini (`saraphane.ico`) uretir.

Simge, arayuzdeki `frontend/public/uzum.svg` logosunun birebir ayni geometri ve
renkleriyle cizilir; boylece masaustu kisayolu, gorev cubugu ve MSI, web
arayuzuyle ayni kimligi tasir.

Ikili dosyayi depoya kaynagi olmadan koymamak icin simge KOD ILE uretilir:
tasarim degistiginde bu betik yeniden calistirilir.

    .venv\\Scripts\\python.exe desktop\\simge_uret.py

Cikti: desktop\\saraphane.ico  (16, 24, 32, 48, 64, 128, 256 piksel)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

CIKTI = Path(__file__).resolve().parent / "saraphane.ico"

# Windows'un kullandigi standart simge boyutlari.
BOYUTLAR = (16, 24, 32, 48, 64, 128, 256)

# Kenar yumusatma icin once buyuk cizilip kucultulur.
TUVAL = 1024
OLCEK = TUVAL / 32  # SVG viewBox 32x32

# ---------------------------------------------------------------- renkler
# uzum.svg ile ayni: bordo gradyan + asma yesili
UZUM_UST = (181, 42, 87)  # #b52a57
UZUM_ALT = (59, 10, 20)  # #3b0a14
SAP_YESIL = (107, 143, 58)  # #6b8f3a
FILIZ_YESIL = (46, 139, 111)  # #2e8b6f
ZEMIN_UST = (247, 242, 234)  # krem
ZEMIN_ALT = (232, 221, 206)

# uzum.svg'deki salkim: (cx, cy) ve yaricap 3.1
TANELER = [
    (16, 9), (12, 14), (20, 14), (16, 16),
    (9, 20), (23, 20), (16, 22), (12, 26), (20, 26),
]
TANE_YARICAP = 3.1


def _dikey_gradyan(boy: int, ust: tuple[int, int, int], alt: tuple[int, int, int]) -> Image.Image:
    """Yukaridan asagiya renk gecisi olan kare gorsel."""
    gorsel = Image.new("RGB", (1, boy))
    piksel = gorsel.load()
    if piksel is None:  # pragma: no cover - Pillow her zaman doner
        raise RuntimeError("Pillow piksel erisimi saglayamadi")
    for y in range(boy):
        oran = y / max(1, boy - 1)
        piksel[0, y] = tuple(  # type: ignore[index]
            round(ust[k] + (alt[k] - ust[k]) * oran) for k in range(3)
        )
    return gorsel.resize((boy, boy), Image.Resampling.NEAREST)


def simgeyi_ciz() -> Image.Image:
    def o(deger: float) -> float:
        """SVG birimini tuval pikseline cevirir."""
        return deger * OLCEK

    # ---------------------------------------------------------- zemin
    zemin = _dikey_gradyan(TUVAL, ZEMIN_UST, ZEMIN_ALT).convert("RGBA")
    zemin_maske = Image.new("L", (TUVAL, TUVAL), 0)
    ImageDraw.Draw(zemin_maske).rounded_rectangle(
        (0, 0, TUVAL - 1, TUVAL - 1), radius=int(TUVAL * 0.22), fill=255
    )
    tuval = Image.new("RGBA", (TUVAL, TUVAL), (0, 0, 0, 0))
    tuval.paste(zemin, (0, 0), zemin_maske)

    # ------------------------------------------------------------ sap
    # Once cizilir ki taneler sapin uzerine gelsin (SVG'deki siralama).
    sap = ImageDraw.Draw(tuval)
    kalinlik = max(1, int(o(2)))
    sap.line([(o(16), o(3)), (o(16), o(6))], fill=(*SAP_YESIL, 255), width=kalinlik)
    # Filiz: 16,3 -> 22,1.2 arasi hafif yay
    sap.arc(
        (o(15.4), o(0.2), o(22.6), o(6.0)),
        start=200, end=330,
        fill=(*FILIZ_YESIL, 255), width=kalinlik,
    )

    # ---------------------------------------------------------- taneler
    tane_maske = Image.new("L", (TUVAL, TUVAL), 0)
    maske_ciz = ImageDraw.Draw(tane_maske)
    for cx, cy in TANELER:
        maske_ciz.ellipse(
            (
                o(cx - TANE_YARICAP), o(cy - TANE_YARICAP),
                o(cx + TANE_YARICAP), o(cy + TANE_YARICAP),
            ),
            fill=255,
        )
    uzum = _dikey_gradyan(TUVAL, UZUM_UST, UZUM_ALT).convert("RGBA")
    tuval.paste(uzum, (0, 0), tane_maske)

    return tuval


def main() -> int:
    buyuk = simgeyi_ciz()
    kareler = [
        buyuk.resize((b, b), Image.Resampling.LANCZOS) for b in BOYUTLAR
    ]
    # Pillow, ilk gorseli temel alip `sizes` ile cok cozunurluklu ICO yazar;
    # ancak kucuk boyutlar icin ayri ayri kucultulmus kareler daha nettir.
    kareler[-1].save(CIKTI, format="ICO", sizes=[(b, b) for b in BOYUTLAR])
    print(f"Simge yazildi: {CIKTI}")
    print(f"  boyutlar: {', '.join(str(b) for b in BOYUTLAR)}")
    print(f"  dosya   : {CIKTI.stat().st_size:,} bayt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
