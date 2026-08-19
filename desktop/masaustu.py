"""Akilli Saraphane Yonetim Sistemi — masaustu baslatici.

Uygulamayi tarayici gerektirmeden, kendi penceresinde calistirir:

  1. Bos bir yerel port secer (sabit port cakismasi olmasin diye)
  2. Uvicorn'u arka plan is parcaciginda baslatir
  3. Saglik ucu yanit verene kadar bekler
  4. PyWebView penceresini acar

Arayuz ve API ayni kokenden sunulur (bkz. `app.main`), bu yuzden CORS ya da
ayri bir web sunucusu gerekmez.

Calistirma (gelistirme):
    python desktop\\masaustu.py

Paketleme:
    powershell -ExecutionPolicy Bypass -File scripts\\masaustu-paketle.ps1
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# Paketlenmemis calistirmada `backend` paketini gorunur kil.
_KOK = Path(__file__).resolve().parent.parent
_BACKEND = _KOK / "backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

BASLIK = "Akıllı Şaraphane Yönetim Sistemi"
BASLATMA_ZAMAN_ASIMI = 60.0


def bos_port_bul() -> int:
    """İşletim sisteminden kullanılabilir bir port ister."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# Sunucu iş parçacığında oluşan hata buraya yazılır; ana iş parçacığı bunu
# kullanıcıya gösterir. Aksi hâlde hata sessizce kaybolurdu: `console=False`
# olduğu için stderr hiçbir yere gitmez ve kullanıcı yalnızca hiç açılmayan
# bir pencere görür.
_sunucu_hatasi: list[BaseException] = []


def sunucuyu_baslat(port: int) -> threading.Thread:
    """Uvicorn'u arka planda başlatır (daemon: pencere kapanınca süreç biter)."""
    import uvicorn

    from app.main import app

    yapilandirma = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    sunucu = uvicorn.Server(yapilandirma)

    def calistir() -> None:
        try:
            sunucu.run()
        except BaseException as exc:
            _sunucu_hatasi.append(exc)

    iplik = threading.Thread(target=calistir, name="uvicorn", daemon=True)
    iplik.start()
    return iplik


def hata_goster(baslik: str, mesaj: str) -> None:
    """Kullanıcıya Türkçe bir hata kutusu gösterir.

    Pencereli uygulamada `print` hiçbir yere gitmez; kullanıcı ne olduğunu
    anlayamaz. Mesaj kutusu açılamazsa en azından stderr'e yazılır.
    """
    try:
        import ctypes

        # MB_ICONERROR (0x10) | MB_SETFOREGROUND (0x10000)
        ctypes.windll.user32.MessageBoxW(None, mesaj, baslik, 0x10 | 0x10000)
    except Exception:
        print(f"{baslik}: {mesaj}", file=sys.stderr)


def sunucuyu_bekle(port: int, zaman_asimi: float = BASLATMA_ZAMAN_ASIMI) -> bool:
    """Sağlık ucu yanıt verene kadar bekler."""
    adres = f"http://127.0.0.1:{port}/health"
    bitis = time.monotonic() + zaman_asimi
    while time.monotonic() < bitis:
        try:
            with urllib.request.urlopen(adres, timeout=2) as yanit:
                if yanit.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.3)
    return False


def main() -> int:
    try:
        import webview
    except ImportError:
        hata_goster(
            BASLIK,
            "PyWebView kurulu değil. Kurmak için:\n"
            "    .venv\\Scripts\\python.exe -m pip install pywebview",
        )
        return 1

    # Ayarların yüklenmesi veri klasörünü oluşturur; yazma izni yoksa BURADA
    # patlar. Yakalanmazsa kullanıcı ham bir traceback penceresi görür.
    try:
        from app.core.config import VERI_KOKU, settings
    except Exception as exc:
        hata_goster(
            f"{BASLIK} — başlatılamadı",
            "Uygulama ayarları yüklenemedi; büyük olasılıkla veri klasörüne "
            "yazma izni yok.\n\n"
            f"{type(exc).__name__}: {exc}\n\n"
            "Çözüm: SARAPHANE_VERI_DIZINI ortam değişkeniyle yazılabilir bir "
            "klasör gösterin.",
        )
        return 1

    if not settings.frontend_available:
        hata_goster(
            f"{BASLIK} — arayüz bulunamadı",
            "Arayüz derlenmemiş. Önce derleyin:\n\n"
            "    cd frontend; npm install; npm run build",
        )
        return 1

    port = bos_port_bul()
    print(f"{BASLIK} başlatılıyor… (yerel port {port})")
    sunucuyu_baslat(port)

    if not sunucuyu_bekle(port):
        if _sunucu_hatasi:
            ayrinti = f"{type(_sunucu_hatasi[0]).__name__}: {_sunucu_hatasi[0]}"
        else:
            ayrinti = f"Sunucu {BASLATMA_ZAMAN_ASIMI:.0f} saniye içinde yanıt vermedi."

        hata_goster(
            f"{BASLIK} — başlatılamadı",
            "Uygulama başlatılamadı.\n\n"
            f"{ayrinti}\n\n"
            f"Veri klasörü: {VERI_KOKU}\n\n"
            "Sık karşılaşılan neden: veri klasörüne yazma izni yok. "
            "SARAPHANE_VERI_DIZINI ortam değişkeniyle yazılabilir bir klasör "
            "gösterebilirsiniz.\n\n"
            "Ayrıntılı günlük: logs\\app.log",
        )
        return 1

    webview.create_window(
        BASLIK,
        f"http://127.0.0.1:{port}/",
        width=1440,
        height=900,
        min_size=(1024, 700),
        confirm_close=True,
    )
    # Uvicorn daemon iş parçacığındadır; pencere kapanınca süreçle birlikte biter.
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
