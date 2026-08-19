# Üçüncü Taraf Bağımlılıklar ve Lisansları

Bu proje ileride **ticari ve kapalı kaynak** bir ürüne dönüştürülebilir. Bu nedenle
tüm bağımlılıklar bilinçli olarak **izin verici (permissive)** lisanslardan seçilmiştir.

## Lisans politikası

| Durum | Lisanslar | Karar |
|---|---|---|
| ✅ Kabul | MIT, BSD-2/3-Clause, Apache-2.0, ISC, Unlicense, PSF, MIT-CMU | Kullanılabilir |
| ⚠️ Kaçınıldı | LGPL-2.1/3.0 | Dinamik bağlamada teknik olarak mümkün olsa da hukuki yük getirir; kullanılmadı |
| ❌ Yasak | GPL-2.0/3.0, AGPL-3.0, SSPL, BUSL | Kaynak açma yükümlülüğü doğurabilir; **hiçbiri kullanılmadı** |

### Bilinçli olarak reddedilen paketler

| Paket | Lisans | Yerine kullanılan | Gerekçe |
|---|---|---|---|
| `psycopg2` / `psycopg` | LGPL-3.0 (istisnalı) | **`asyncpg`** (Apache-2.0) | PostgreSQL sürücüsü LGPL'dir; ticari kapalı kaynak dağıtımda hukuki inceleme gerektirir |
| Wine Cellar ve benzeri şaraphane projeleri | AGPL-3.0 | — | **Hiçbir kaynak kodu kopyalanmadı veya türev temel alınmadı.** Yalnızca sektörün genel iş akışları (üzüm kabulü → fermantasyon → şişeleme) referans alındı; bunlar korunabilir ifade değil, alan bilgisidir |
| `slowapi` / `limits` | MIT | Kendi `SlidingWindowLimiter` sınıfımız | Bağımlılık ve lisans yüzeyini küçültmek; ihtiyaç bu ölçekte 60 satırla karşılanıyor |
| `i18next` / `react-i18next` | MIT | Kendi `lib/i18n.ts` katmanımız | Aynı gerekçe: iki dil için harici kütüphane gereksiz |
| **WiX Toolset v6+** | MS-RL + **OSMF EULA** | **WiX v5.0.2** (MS-RL) | v6 ve sonrası, yıllık brüt geliri 10.000 USD üzerindeki ticari kullanıcılara **aylık ücret yükümlülüğü** getiren bir sözleşmenin kabulünü zorunlu tutar; kabul edilmeden hiçbir komut çalışmaz. v5 aynı işi ücretsiz görür |

---

## Backend (Python)

Doğrulanan ortam: **Python 3.14.0 / Windows 11 x64**

### Çalışma zamanı bağımlılıkları

| Paket | Sürüm | Lisans | Kullanım amacı |
|---|---|---|---|
| `fastapi` | 0.141.1 | MIT | Web çatısı, OpenAPI üretimi |
| `starlette` | 1.6.0 | BSD-3-Clause | FastAPI'nin ASGI çekirdeği |
| `uvicorn[standard]` | 0.52.3 | BSD-3-Clause | ASGI sunucusu |
| `python-multipart` | 0.0.32 | Apache-2.0 | Dosya yükleme (multipart form) |
| `SQLAlchemy` | 2.0.52 | MIT | ORM ve sorgu katmanı |
| `alembic` | 1.19.1 | MIT | Veritabanı göçleri |
| `aiosqlite` | 0.22.1 | MIT | Geliştirme veritabanı sürücüsü |
| `asyncpg` | 0.31.0 | Apache-2.0 | Üretim PostgreSQL sürücüsü |
| `greenlet` | 3.5.5 | MIT | SQLAlchemy async köprüsü |
| `pydantic` | 2.13.4 | MIT | Veri doğrulama ve serileştirme |
| `pydantic-settings` | 2.15.0 | MIT | Ortam değişkeni yapılandırması |
| `pydantic-core` | 2.46.4 | MIT | Pydantic çekirdeği (Rust) |
| `email-validator` | 2.3.0 | Unlicense | E-posta biçim doğrulaması |
| `argon2-cffi` | 25.1.0 | MIT | Argon2id parola karması |
| `argon2-cffi-bindings` | 25.1.0 | MIT | Argon2 C bağlamaları |
| `PyJWT` | 2.13.0 | MIT | JWT üretimi/doğrulaması |
| `cryptography` | 50.0.0 | Apache-2.0 **veya** BSD-3-Clause | API anahtarlarının şifrelenmesi (Fernet, HKDF) |
| `cffi` | 2.1.1 | MIT | C eklenti köprüsü |
| `httpx` | 0.28.1 | BSD-3-Clause | Yapay zekâ sağlayıcılarına HTTP istemcisi |
| `httpcore` | 1.0.9 | BSD-3-Clause | httpx taşıma katmanı |
| `h11` | 0.16.0 | MIT | HTTP/1.1 protokol uygulaması |
| `anyio` | 4.14.2 | MIT | Asenkron uyumluluk katmanı |
| `openpyxl` | 3.1.5 | MIT | Excel (.xlsx) dışa aktarma |
| `et-xmlfile` | 2.0.0 | MIT | openpyxl XML yardımcısı |
| `reportlab` | 5.0.0 | BSD-3-Clause | PDF rapor üretimi |
| `qrcode` | 8.2 | BSD-3-Clause | Parti/fıçı/şişeleme QR kodları |
| `pillow` | 12.3.0 | MIT-CMU | QR görüntü üretimi |
| `structlog` | 26.1.0 | MIT **veya** Apache-2.0 | Yapılandırılmış günlükleme |
| `python-dotenv` | 1.2.2 | BSD-3-Clause | `.env` okuma |
| `certifi` | 2026.7.22 | MPL-2.0 * | TLS kök sertifikaları |
| `idna` | 3.18 | BSD-3-Clause | Alan adı kodlaması |
| `click` | 8.4.2 | BSD-3-Clause | Komut satırı (uvicorn/alembic) |
| `Mako` | 1.4.1 | MIT | Alembic şablonları |
| `MarkupSafe` | 3.0.3 | BSD-3-Clause | Mako yardımcısı |
| `PyYAML` | 6.0.3 | MIT | uvicorn yapılandırma desteği |
| `websockets` | 17.0.1 | BSD-3-Clause | uvicorn WebSocket desteği |
| `httptools` | 0.8.0 | MIT | uvicorn HTTP ayrıştırıcı |
| `watchfiles` | 1.2.0 | MIT | Geliştirmede otomatik yeniden yükleme |
| `colorama` | 0.4.6 | BSD-3-Clause | Windows konsol renkleri |
| `dnspython` | 2.8.0 | ISC | email-validator bağımlılığı |
| `typing-extensions` | 4.16.0 | PSF-2.0 | Tip desteği |
| `annotated-types` | 0.8.0 | MIT | Pydantic kısıt tipleri |

\* **certifi (MPL-2.0):** Mozilla Public License 2.0 **dosya bazlı** copyleft'tir.
Yalnızca certifi'nin *kendi dosyalarında* yapılan değişiklikler paylaşılmalıdır; bu
paket değiştirilmeden kullanıldığı için projenin kapalı kaynak kalmasına engel
değildir. (certifi doğrudan bağımlılık değildir; `httpx` üzerinden gelir.)

### Geliştirme bağımlılıkları (ürüne dahil edilmez)

| Paket | Sürüm | Lisans | Amaç |
|---|---|---|---|
| `pytest` | 9.1.1 | MIT | Test çatısı |
| `pytest-asyncio` | 1.4.0 | Apache-2.0 | Asenkron test desteği |
| `pytest-cov` | 7.1.0 | MIT | Kapsam raporu |
| `coverage` | 7.15.4 | Apache-2.0 | Kapsam ölçümü |
| `ruff` | 0.16.3 | MIT | Kod kalitesi + güvenlik taraması |
| `mypy` | 2.3.0 | MIT | Statik tip denetimi |
| `pyinstaller` | 6.x | GPL-2.0 **çalışma zamanı istisnalı** | Masaüstü paketleme |
| `pywebview` | 6.2.1 | BSD-3-Clause | Masaüstü penceresi |
| `pillow` | 12.3.0 | MIT-CMU | Uygulama simgesinin üretimi |
| `@playwright/test` | 1.x | Apache-2.0 | Uçtan uca testler |

> **PyInstaller notu:** PyInstaller GPL-2.0 lisanslıdır **ancak** özel bir
> çalışma zamanı istisnası içerir: üretilen paketler (bootloader dahil) için
> GPL yükümlülüğü doğmaz. Kapalı kaynak ticari dağıtım açıkça serbesttir.
> Bu istisna PyInstaller'ın `COPYING.txt` dosyasında yer alır.

### Paketleme araçları (yalnızca derleme zamanı)

| Araç | Sürüm | Lisans | Ücret | Amaç |
|---|---|---|---|---|
| **WiX Toolset** | **5.0.2** | **MS-RL** | **Yok** | MSI kurulum paketi |
| Windows SDK `signtool` | 10.0.26100 | Microsoft SDK şartları | Yok | Kod imzalama |

> **WiX sürüm seçimi bilinçlidir — v6 ve üzeri kullanılmamalıdır.**
>
> WiX Toolset **v6 ve sonrası**, "Open Source Maintenance Fee" (OSMF) EULA'sının
> kabulünü zorunlu tutar. Bu sözleşme, yazılımı gelir getirici faaliyette
> kullanan ve **yıllık brüt geliri 10.000 USD ve üzerinde** olan kullanıcılara
> **aylık ücret yükümlülüğü** getirir. Kabul edilmeden `wix` komutlarının hiçbiri
> çalışmaz (`error WIX7015`).
>
> **v5.0.2** ise MS-RL (Microsoft Reciprocal License) altındadır, OSMF kapısı
> yoktur ve ticari kullanım için ücretsizdir. MS-RL'in karşılıklılık şartı
> yalnızca **WiX'in kendi kaynak kodunda yapılan değişiklikler** için geçerlidir;
> WiX ile üretilen MSI dosyasına veya paketlenen uygulamaya hiçbir lisans
> yükümlülüğü bindirmez.
>
> Bu nedenle `scripts\msi-paketle.ps1` sürümü açıkça `5.0.2` olarak belgeler ve
> WiX bulunamadığında kurulum komutunu bu sürümle önerir. Sürüm yükseltilecekse
> önce OSMF yükümlülüğü değerlendirilmelidir.

---

## Frontend (Node / npm)

### Çalışma zamanı bağımlılıkları

| Paket | Sürüm | Lisans | Kullanım amacı |
|---|---|---|---|
| `react` | 19.2.8 | MIT | Arayüz kütüphanesi |
| `react-dom` | 19.2.8 | MIT | DOM oluşturucu |
| `react-router-dom` | 7.18.2 | MIT | Sayfa yönlendirme |
| `@tanstack/react-query` | 5.101.4 | MIT | Sunucu durumu yönetimi, önbellek |
| `axios` | 1.19.0 | MIT | HTTP istemcisi |
| `echarts` | 6.1.0 | **Apache-2.0** | Grafikler (fermantasyon eğrisi, izlenebilirlik çizgesi) |
| `echarts-for-react` | 3.0.6 | MIT | ECharts React sarmalayıcısı |
| `lucide-react` | 1.31.0 | ISC | Simge seti |
| `clsx` | 2.1.1 | MIT | Koşullu CSS sınıfı birleştirme |
| `date-fns` | 4.4.0 | MIT | Tarih yardımcıları |
| `zustand` | 5.0.15 | MIT | Hafif küresel durum (oturum, tema) |

### Geliştirme bağımlılıkları

| Paket | Sürüm | Lisans | Amaç |
|---|---|---|---|
| `vite` | 8.2.0 | MIT | Geliştirme sunucusu ve paketleyici |
| `@vitejs/plugin-react` | 6.0.4 | MIT | React desteği |
| `typescript` | 6.0.2 | Apache-2.0 | Tip sistemi |
| `tailwindcss` | 4.3.3 | MIT | Stil çatısı |
| `@tailwindcss/vite` | 4.3.3 | MIT | Tailwind Vite eklentisi |
| `oxlint` | 1.75.0 | MIT | Hızlı JS/TS linter |
| `eslint-plugin-react-hooks` | 7.1.1 | MIT | React hook kuralları |
| `@types/*` | — | MIT | DefinitelyTyped tip tanımları |

---

## Yapay zekâ sağlayıcıları

Sağlayıcılara **resmî SDK ile değil**, doğrudan HTTP (httpx) ile bağlanılır. Bu bilinçli
bir karardır: bağımlılık ve lisans yüzeyi küçülür, sürüm kırılmaları azalır ve
`AIProvider` soyutlaması sağlayıcıdan bağımsız kalır.

| Servis | Erişim | Not |
|---|---|---|
| **LM Studio** | OpenAI uyumlu yerel HTTP API | Yazılımın kendisi ayrı lisanslıdır; proje yalnızca HTTP arayüzünü kullanır. Model ağırlıklarının lisansı **kullanıcının sorumluluğundadır** |
| **Anthropic Claude** | Messages API (HTTP) | Kullanım Anthropic hizmet şartlarına tabidir |
| **NVIDIA Build** | OpenAI uyumlu HTTP API | Kullanım NVIDIA şartlarına ve model kartı lisanslarına tabidir |

> **Model ağırlıkları:** Yerel modellerin (Gemma, Qwen, Mistral, Moondream vb.)
> lisansları birbirinden farklıdır ve bazıları ticari kullanımı kısıtlayabilir.
> Bu proje model ağırlığı **dağıtmaz**; kullanıcının LM Studio üzerinden indirdiği
> modellerin lisans uygunluğu kullanıcıya aittir.

---

## Yazı tipleri ve görseller

- Arayüz sistem yazı tiplerini kullanır (Inter → Segoe UI → system-ui zinciri);
  **hiçbir yazı tipi dosyası dağıtılmaz**.
- Simgeler `lucide-react` (ISC) paketinden gelir.
- `frontend/public/uzum.svg` bu proje için özgün olarak çizilmiştir.

---

## Özgünlük beyanı

- Şaraphane yönetim çekirdeği (veri modeli, izlenebilirlik çizgesi, maliyet hesabı,
  fermantasyon tahmini, kupaj öngörüsü, stok motoru, güvenlik katmanı, AI soyutlaması
  ve terminal güvenlik çekirdeği) **bu proje için özgün olarak yazılmıştır**.
- Hiçbir GPL/AGPL/LGPL projeden kod kopyalanmamış, türev alınmamıştır.
- Lisansı belirtilmemiş kaynaklardan kod alınmamıştır.

## Doğrulama

Kurulu paketlerin güncel lisanslarını denetlemek için:

```powershell
.venv\Scripts\python.exe -m pip install pip-licenses
.venv\Scripts\python.exe -m piplicenses --format=markdown --with-urls
cd frontend; npx license-checker --summary
```

> Bağımlılık eklerken lisansı **eklemeden önce** doğrulayın ve bu dosyayı güncelleyin.
