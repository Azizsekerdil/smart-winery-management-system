# Bilinen sınırlar ve yol haritası

Bu belge, bu sürümde **bilerek eksik bırakılan** ve **henüz çözülmemiş** noktaları
listeler. Amacı, kodu değerlendiren birinin sürprizle karşılaşmamasıdır.

## 1. Doğrulanmış eksikler

### mypy 5 hata veriyor

`backend/app/api/crud.py` içinde 5 tip hatası vardır ve **bilerek** bırakılmıştır:

```
crud.py:72  Argument "tags" to "APIRouter" has incompatible type "list[str]"
crud.py:82  Variable "out_schema" is not valid as a type
crud.py:125 Variable "out_schema" is not valid as a type
crud.py:154 create_schema? has no attribute "model_dump"
crud.py:213 update_schema? has no attribute "model_dump"
```

Sebep: `build_crud_router()` çalışma zamanında Pydantic şemalarını **parametre
olarak** alıp dinamik bir router üretir. mypy'nin statik modeli bunu ifade
edemez. Çalışma zamanı davranışı doğrudur ve testlerle kapsanır. Düzeltmek için
jenerik (`Generic[TOut]`) bir yeniden yazım gerekir; kapsam dışı bırakılmıştır.

`ruff` (bandit güvenlik kuralları dâhil) **temiz geçer**.

### Uçtan uca (E2E) testler bu depoda çalıştırılmadı

50 Playwright testi mevcuttur, ancak canlı bir backend + frontend gerektirir.
Bu depo hazırlanırken çalıştırılmamıştır; **"geçiyor" iddiası yoktur**.
Çalıştırmak için `scripts\baslat.ps1` ile iki servisi başlatıp
`cd frontend && npm run e2e` komutunu verin.

### Tanıtım sunumu bu depoda yoktur

Sunum üretim betiği ve çıktı dosyaları bu dalın kapsamında değildir. Depoda
**hiçbir sunum PDF'i yayımlanmamıştır**; ekran görüntüleri `docs/screenshots/`
altındadır.

## 2. Mimari sınırlar

| Sınır | Ayrıntı |
|---|---|
| **Hız sınırlayıcı süreç içidir** | `SlidingWindowLimiter` bellekte sayaç tutar. Tek süreç / tek makine için doğrudur. Çoklu uvicorn işçisi veya yatay ölçeklemede sayaçlar paylaşılmaz; Redis tabanlı bir sayaca geçilmelidir. |
| **AI terminali kapsama değildir** | İncelenen-diff kapısıdır. Çalışma alanı içinde yazılıp çalıştırılan bir betik, sıradan bir kullanıcı süreci olarak çalışır: ağ erişimi ve proje dışı okuma yetkisi vardır. Bkz. [SECURITY.md](../SECURITY.md) §7. |
| **Tek kiracı** | Çok kiracılı (multi-tenant) SaaS değildir. Tek işletme, tek kurulum. |
| **Sensör/SCADA entegrasyonu yok** | Fermantasyon ölçümleri elle veya API ile girilir; hazır donanım sürücüsü yoktur. |
| **Denetim günlüğü silinemez** | İzlenebilirlik için bilinçli. Kişisel veri silme talepleri bu kısıtla birlikte değerlendirilmelidir; bkz. [PRIVACY.md](../PRIVACY.md) §3. |
| **SQLite varsayılan** | Geliştirme ve tek kullanıcılı kurulum için yeterlidir. Eşzamanlı yazma yükü altında PostgreSQL'e geçin (`DATABASE_URL`). |
| **Yedekler şifrelenmez** | Yedek dosyası veritabanının tamamını içerir. Şifreleme ve saklama sizin sorumluluğunuzdadır. |

### Kapsayici (Docker) notlari

Bu depo hazirlanirken **Docker mevcut degildi**; bu yuzden asagidakiler
*derlenerek dogrulanmamistir*:

- `frontend/nginx.conf` ve yeni `frontend/nginx-snippets/` parcaciginin nginx
  soz dizimi **calistirilarak sinanmadi**. Degisiklik, guvenlik basliklarinin
  `/assets/` konumunda dusmesini gideren standart bir `include` duzenidir.
- `frontend/Dockerfile` ve `backend/Dockerfile` **derlenmedi**.

Ayrica bilinen ve **kabul edilmis** bir tarama bulgusu vardir:

| Bulgu | Durum |
|---|---|
| Trivy `DS-0002` (HIGH) — `frontend/Dockerfile` icin `USER` yonergesi yok | **Kabul edildi.** Resmi `nginx` imajinda ana surec root olarak baslar, isci surecler `nginx` kullanicisina duser; bu, yaygin ve desteklenen yapilandirmadir. Tam olarak gidermek icin `nginxinc/nginx-unprivileged` imajina gecmek ve portu 8080'e almak gerekir. Docker ile dogrulanamayacagi icin bu surumde **yapilmamistir**. |
| Trivy `DS-0026` (LOW) — backend `HEALTHCHECK` yok | **Giderildi.** |

`backend/Dockerfile` zaten kok olmayan (`USER saraphane`) kullaniciyla calisir.

## 3. Olgunluk

**Çalışan, test edilmiş, üretimde denenmemiş.** 536 otomatik test geçer ve tam
bir kurulum zinciri vardır; ancak yazılım gerçek bir şaraphanede canlı kullanıma
alınmamıştır. Ölçek, eşzamanlılık ve uzun süreli veri büyümesi davranışı saha
verisiyle doğrulanmamıştır.

## 4. Yol haritası (taahhüt değil)

Aşağıdakiler bilinen boşluklardır. Hiçbiri için tarih taahhüdü yoktur.

1. `crud.py` için jenerik yeniden yazım; mypy'yi sıfır hataya indirmek.
2. Redis tabanlı hız sınırlayıcı (çoklu işçi desteği).
3. AI terminali için gerçek işletim sistemi düzeyinde izolasyon (ayrı kullanıcı
   veya kapsayıcı).
4. Yedeklerin şifrelenmesi ve saklama süresi politikası.
5. E2E paketinin CI'da düzenli çalıştırılması.
6. Sensör/veri toplama entegrasyonu için giriş API'si.
