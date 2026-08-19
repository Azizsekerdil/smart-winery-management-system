# Güvenlik

Bu belge sistemin güvenlik tasarımını, uygulanan kontrolleri ve üretime geçiş
kontrol listesini açıklar.

---

## 1. Kimlik doğrulama

| Kontrol | Uygulama |
|---|---|
| Parola karması | **Argon2id** — `time_cost=3`, `memory_cost=64 MiB`, `parallelism=4`, 32 baytlık özet, 16 baytlık tuz (OWASP Password Storage Cheat Sheet) |
| Parola politikası | En az 10 karakter, en az bir büyük harf, bir küçük harf ve bir rakam (Türkçe karakterler dahil) |
| Otomatik yeniden karma | Argon2 parametreleri güçlendirildiğinde başarılı girişte parola şeffafça yeniden karmalanır |
| Oturum | Kısa ömürlü **JWT erişim belirteci** (8 saat) + veritabanında tutulan, **iptal edilebilir yenileme belirteci** (14 gün) |
| Belirteç saklama | Yenileme belirtecinin kendisi değil, yalnızca `jti` kimliği saklanır |
| Kaba kuvvet koruması | 5 hatalı denemeden sonra hesap 15 dakika kilitlenir |
| Kullanıcı numaralandırma | Var olmayan kullanıcı ve hatalı parola **aynı** yanıtı döndürür; sahte doğrulama ile zamanlama farkı azaltılır |
| Parola değişimi | Diğer tüm oturumlar iptal edilir |
| Yönetici sıfırlaması | Tüm oturumlar iptal edilir, kullanıcı ilk girişte parola değiştirmeye zorlanır |

## 2. Yetkilendirme (RBAC)

- **12 rol**, **40+ ayrık yetki** (`kaynak:eylem` biçiminde)
- Tek kaynak-ı hakikat: `backend/app/core/permissions.py`
- Her uç nokta gerekli yetkiyi bildirimsel olarak şart koşar
- **Yetkisiz erişim denemeleri denetim günlüğüne yazılır** (`izinsiz_erisim`)
- Görevler ayrılığı: analizi yapan kişi kendi laboratuvar sonucunu onaylayamaz
- Salt okunur **denetçi** rolünde hiçbir yazma yetkisi yoktur (testle doğrulanır)
- Sistemde **en az bir aktif sistem yöneticisi** kalması zorlanır

## 3. Gizli bilgi yönetimi

| Katman | Kontrol |
|---|---|
| Depolama | API anahtarları **Fernet** (AES-128-CBC + HMAC-SHA256) ile şifrelenir; anahtar `SECRETS_ENCRYPTION_KEY`'den **HKDF-SHA256** ile türetilir |
| Okuma | Anahtarlar **hiçbir uç noktadan okunamaz**. Yalnızca "var/yok", maskeli gösterim ve geri döndürülemez 12 haneli parmak izi sunulur |
| Günlükler | `app/core/logging.py` içindeki `scrub()` her kaydı temizler: Anthropic (`sk-ant-`), NVIDIA (`nvapi-`), OpenAI (`sk-`), GitHub (`gh*_`), JWT, AWS anahtarları ve `api_key=`/`password=` kalıpları |
| Denetim günlüğü | Hassas alan adları (`password`, `api_key`, `token`, …) kaydedilmeden önce maskelenir |
| Alt süreçler | AI terminali komutlarına `ANTHROPIC_*`, `NVIDIA_*`, `OPENAI_*`, `SECRET*`, `GITHUB_*`, `DATABASE_URL` ortam değişkenleri **aktarılmaz** |
| Sürüm kontrolü | `.env`, veritabanı, günlükler, yüklemeler, model dosyaları `.gitignore` ile dışlanır |

Anahtar rotasyonu:

```powershell
# 1. Yeni anahtar üret (ekrana yazdırmadan .env'e yazın)
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
# 2. SECRETS_ENCRYPTION_KEY değiştirilirse kayıtlı API anahtarları ÇÖZÜLEMEZ;
#    Ayarlar ekranından yeniden girilmelidir.
# 3. SECRET_KEY değiştirilirse tüm oturumlar düşer (beklenen davranış).
```

## 4. Girdi doğrulama ve enjeksiyon

- Tüm istek gövdeleri **Pydantic v2** ile doğrulanır (tip, aralık, uzunluk, iş kuralı)
- Veritabanı erişimi **yalnızca SQLAlchemy ORM / parametreli sorgu** iledir; dize
  birleştirmeyle SQL kurulmaz
- Alan bazlı doğrulayıcılar iş kurallarını da denetler (brüt−dara=net, serbest SO₂ ≤
  toplam SO₂, sıcaklık min ≤ maks, kupaj oranı toplamı %100 …)
- Yanıtlar Pydantic şemalarıyla süzülür; model alanları istemeden sızmaz

## 5. Dosya yükleme

- **Uzantı beyaz listesi** (`.pdf .png .jpg .jpeg .webp .csv .xlsx .txt`)
- Boyut sınırı akış sırasında denetlenir (varsayılan 15 MB) — bellek tüketimi sınırlı
- Dosya adı `Path(...).name` ile sadeleştirilir (dizin geçişi engellenir)
- Diskte **rastgele UUID** adıyla saklanır; kullanıcı adı yalnızca meta veride tutulur
- İçerik **SHA-256** özeti hesaplanır (bütünlük ve yineleme tespiti)

## 6. Ağ ve taşıma

| Kontrol | Uygulama |
|---|---|
| CORS | Yalnızca yapılandırılmış kökenlere izin verilir; üretimde `*` kullanılmamalıdır (açılışta uyarı verilir) |
| Hız sınırlama | Kayan pencere: genel 300/dk, kimlik doğrulama **10/dk**, AI uç noktaları 30/dk |
| Hız sınırı kapsamı | Katı 10/dk sınırı **yalnızca** kimlik bilgisi doğrulayan uçlara uygulanır: `/auth/login`, `/auth/refresh`, `/auth/change-password`. `/auth/me` gibi her sayfa yüklemesinde çağrılan okuma uçları genel sınırı kullanır — aksi hâlde sayfayı birkaç kez yenileyen normal kullanıcı kaba kuvvet korumasına takılırdı. Sayaç anahtarı `IP + modül` olduğu için bir modülün yoğun kullanımı diğerini engellemez |
| Güvenlik başlıkları | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, üretimde `Strict-Transport-Security` |
| Hata yanıtları | Yığın izi ve iç ayrıntı üretimde **gösterilmez**; günlüğe maskelenmiş olarak yazılır |

## 7. AI terminali güvenlik modeli

### Önce sınırı net söyleyelim: bu bir **incelenen-diff kapısıdır**, kapsama değildir

Bu bölümdeki denetimler gerçektir ve kod düzeyinde uygulanır, ancak **işletim sistemi
düzeyinde bir hapis (containment/sandbox) DEĞİLDİR.** Aradaki fark önemlidir:

- Ajanın çalışma alanı **içinde** yazdığı bir betik, çalıştırıldığında **sıradan bir
  kullanıcı süreci** olur: ağ erişimi vardır, proje dışındaki dosyaları okuyabilir ve
  veri dışarı sızdırabilir. Yol hapsi **komuttaki yolları** denetler, sürecin sistem
  çağrılarını değil.
- Bu yüzden satır içi kod (`python -c`) yasaktır: amaç, kodun **bir dosyaya inmesini**
  ve böylece diff ekranında görünür olmasını zorlamaktır.
- **Kalan varsayım:** güvenlik, değişikliği **bir insanın incelemesine** dayanır.
  Onay adımını gözü kapalı geçerseniz bu model sizi korumaz.

Gerçek bir izolasyon gerekiyorsa ajanı ayrı bir kullanıcı hesabı, kapsayıcı (container)
veya sanal makine içinde çalıştırın. Paketlenmiş (MSI/masaüstü) sürümde ajan
**varsayılan olarak kapalıdır** ve kapsayıcıda devre dışı bırakılır.

### Bu sınır içinde iki bağımsız savunma katmanı vardır

İkisi de kod düzeyindedir — yapay zekâ tarafından değiştirilemez.

### Katman 1 — Yol hapsi (path jail)

- Her yol `AGENT_WORKSPACE` (varsayılan: proje kök dizini) altına göre **çözümlendikten sonra**
  denetlenir; `..`, sembolik bağ, sürücü değişimi ve UNC yolları normalize edilir
- Ortam değişkeni genişlemesi içeren yollar (`%USERPROFILE%`, `$HOME`, `~`) reddedilir
- Çalışma dizini de aynı denetimden geçer

### Katman 2 — Komut politikası

- **İzin listesi**: yalnızca `python, pip, pytest, ruff, mypy, alembic, uvicorn, npm, npx, node, git, echo, dir, ls, where` çalıştırılabilir
- **Kabuk zincirleme yasak**: `&&`, `||`, `;`, `|`, `>`, `<`, `` ` ``, `$(`, `&` içeren komut reddedilir — aksi hâlde izin listesi atlatılabilirdi
- **Kabuk kullanılmaz**: `shell=False` ile doğrudan süreç başlatılır; kabuk enjeksiyonu yüzeyi yoktur
- **Kara liste** (20+ kalıp): özyinelemeli silme, disk biçimlendirme, kayıt defteri, güvenlik yazılımı, servis/süreç sonlandırma, kullanıcı-yetki değişikliği, dosya izni, ağdan indirme, dinamik komut çalıştırma, `git push`, paket yayınlama, `alembic downgrade`, `.env` ve kimlik dosyası erişimi
- `git` ve `pip`/`npm` için **alt komut** düzeyinde denetim
- **Satır içi kod yasak**: `python -c`, `py -c`, `node -e`, `node -p`, `node --eval`,
  `node --print` ve bitişik yazımları (`-cimport os`) reddedilir. Gerekçe: yorumlayıcıya
  metin olarak verilen kod bir "yol" gibi görünmediği için yol hapsinden geçer, ama
  çalıştığında istediği dosyayı açabilir — yani tek başına tüm modeli geçersiz kılar.
  Kod, çalışma alanı içinde bir dosyaya yazılıp çalıştırılmalıdır; böylece değişiklik
  diff ekranında incelenebilir.
- **Yol ayracı duyarsızlığı**: Windows hem `\` hem `/` kabul ettiği için sistem dizini
  kalıpları her iki yazımı da kapsar (`C:\Windows` ve `C:/Windows`)
- **Paket kurulumu varsayılan olarak ENGELLİDİR** (`pip install`, `npm install`,
  `npm ci`, `npx`). Gerekçe: bir paketin kurulum betikleri, izin listesinin de yol
  hapsinin de **tamamen dışında** rastgele kod çalıştırır; yani izin listesini teknik
  olarak geçersiz kılar. Onay bayrağı bunu engellemez çünkü onay bir **politika**
  kontrolüdür, teknik sınır değildir. Gerçekten gerekiyorsa
  `AGENT_ALLOW_PACKAGE_INSTALL=true` ile bilinçli olarak açılır; açıldığında bu
  komutlar **her zaman yüksek risk** işaretlenir ve ek onay ister.

> Son üç madde, uçtan uca testler sırasında bulunan **gerçek atlatma yollarıdır**.
> Hepsi `tests/test_sandbox_kacis.py` ile kalıcı olarak korunmaktadır.

### İş akışı zorlaması

```
Plan → Risk değerlendirmesi → KULLANICI ONAYI → Git kontrol noktası + geçici dal
     → Komutları çalıştır → Lint + test → Diff → Birleştir VEYA geri al
```

- Onaysız çalıştırma **409** ile reddedilir (`AGENT_REQUIRE_APPROVAL=true`)
- "Engellendi" risk seviyesindeki plan **onaylanamaz**
- Testler başarısızsa birleştirme reddedilir
- Her adım (engellenen komut denemeleri dahil) denetim günlüğüne yazılır
- Zaman aşımı (180 sn) ve çıktı boyutu sınırı (256 KB) uygulanır; çıktı maskelenir

### Ayrı yetki

`ai:terminal` (plan hazırlama) ve `ai:terminal:approve` (onay + çalıştırma) ayrı
yetkilerdir ve **yalnızca sistem yöneticisi** rolünde bulunur.

## 8. Yapay zekâ ve veri gizliliği

- Harici sağlayıcıya veri gönderilmeden önce **hangi kayıtların gideceği** kullanıcıya
  gösterilir ve açık onay istenir (`confirm_external_share`); onaysız istek **412** döner
- Hassas görevler öntanımlı olarak **yerel modele** (LM Studio) yönlendirilir
- Gönderilen veri kapsamı denetim günlüğüne kaydedilir
- Yapay zekâ **hiçbir üretim değerini kendiliğinden değiştiremez**; yalnızca öneri üretir
- Sağlayıcı hata mesajları maskelenerek saklanır
- RAG gömme vektörleri yerel modelle üretilir; doküman içeriği makineden çıkmaz

## 9. Denetim günlüğü

- Kim, ne, ne zaman + **önce/sonra** değerleri, değişen alan listesi
- IP adresi, kullanıcı aracısı, istek yolu ve yöntemi
- AI sağlayıcı/model bilgisi ve terminal görev bağlantısı
- **Değiştirilemez**: güncelleme uç noktası yoktur, silme `405 Method Not Allowed` döner

## 10. Bağımlılık güvenliği

```powershell
.venv\Scripts\python.exe -m ruff check backend tests    # bandit (S) kuralları dahil
.venv\Scripts\python.exe -m pip install pip-audit
.venv\Scripts\python.exe -m pip_audit                    # bilinen CVE taraması
cd frontend; npm audit
```

`ruff` yapılandırmasında **bandit (S)** kural ailesi etkindir; `S603` (alt süreç) ve
`S105` (sabit parola) istisnaları yalnızca gerekçeli olarak ve dosya bazında verilmiştir.

## 11. Kod imzalama ve dağıtım

### Neden gerekli

İmzasız bir kurulum paketi indirildiğinde Windows SmartScreen "Bilinmeyen yayıncı"
uyarısı gösterir ve kullanıcıyı fazladan bir onay adımına zorlar. İmza ayrıca
paketin **üretimden sonra değiştirilmediğini** kanıtlar.

### Sertifika nasıl edinilir

Herkese açık olarak güvenilen bir kod imzalama sertifikası bir sertifika
otoritesinden **satın alınır** (DigiCert, Sectigo, GlobalSign vb.). İki tür vardır:

| Tür | SmartScreen davranışı | Anahtar saklama |
|---|---|---|
| **OV** (Organization Validation) | İtibar birikene kadar uyarı sürebilir | Yazılım veya donanım |
| **EV** (Extended Validation) | İlk günden itibaren itibar sağlar | **Donanım token zorunlu** |

Kendinden imzalı (self-signed) sertifika **dağıtım için kullanılamaz**: zinciri
hiçbir müşteri makinesinde güvenilir değildir. Yalnızca hattı sınamak için
uygundur.

### Sertifika nasıl tanımlanır

Sertifika ve parola **asla depoda tutulmaz**. İki yöntemden biri:

```powershell
# 1) Windows sertifika deposu — ÖNERİLEN, hiçbir yerde parola yoktur
$env:SARAPHANE_IMZA_PARMAK_IZI = "<sertifika parmak izi>"

# 2) PFX dosyası — parola yalnızca ortam değişkeninde
$env:SARAPHANE_IMZA_PFX    = "D:\gizli\saraphane.pfx"
$env:SARAPHANE_IMZA_PAROLA = "<parola>"
```

Sertifika tanımlı değilse paket **imzasız** üretilir ve betik açık uyarı verir;
derleme başarısız olmaz. Yayın derlemesinde `-ImzaZorunlu` ile bu davranış
hataya çevrilir.

### Uygulanan ilkeler

| İlke | Uygulama | Gerekçe |
|---|---|---|
| SHA-256 özet | `/fd sha256` | `signtool` 4.00'de zorunlu; SHA-1 artık kabul edilmez |
| RFC 3161 zaman damgası | `/tr <sunucu> /td sha256` | **Damgasız imza, sertifika süresi dolduğunda sahadaki tüm kurulumlarda aynı anda bozulur.** Damgalı imza, sertifika süresi dolsa bile geçerli kalır |
| Yedekli zaman damgası sunucusu | 4 sunucu sırayla denenir | Tek sunucuya bağımlılık derlemeyi kırılgan yapar |
| Üretici imzasına dokunulmaz | Zaten imzalı dosyalar atlanır | Paketteki 203 ikiliden 169'u Microsoft veya Python Software Foundation imzalıdır; yeniden imzalamak bu imzaları **siler** |
| İçerik önce, MSI sonra | `msi-paketle.ps1` sırası sabittir | MSI önce imzalanırsa içerik değişikliği imzayı geçersiz kılar |
| Parola sızdırılmaz | Hata metninde maskelenir | Komut satırı ve hata çıktısı günlüğe düşebilir |

Doğrulama: `signtool verify /pa /v <dosya>` — `/pa` olmadan Windows sürücü
ilkesi uygulanır ve normal kod imzalama sertifikaları başarısız görünür.

### Kurulum paketi ve kullanıcı verisi

MSI `C:\Program Files\Saraphane` altına kurar (perMachine, yönetici gerektirir).
Kullanıcı verisi **pakete dahil değildir** ve kurulum dizinine yazılmaz:
`%LOCALAPPDATA%\Saraphane` altında tutulur. Bunun iki güvenlik sonucu vardır:

- **Onarım/kaldırma kullanıcı verisini silemez** — veri MSI bileşeni değildir.
  Veritabanı bir MSI bileşeni olsaydı, Denetim Masası'ndaki "Onar" işlemi
  müşterinin canlı veritabanını paketteki boş kopyayla ezerdi.
- **Geliştirici veritabanı müşteriye gitmez** — paketleme betiği `data\` ve
  `logs\` artıklarını MSI'a girmeden önce temizler. `tests/test_msi_paketi.py`
  bu kuralı kalıcı olarak korur.

Paketlenmiş sürümde **AI Terminali varsayılan olarak kapalıdır**
(`AGENT_ENABLED = not DONMUS`): bir geliştirici aracıdır, son kullanıcı
kurulumunda kaynak kod ve Git deposu bulunmadığı için hiçbir fayda sağlamadan
komut çalıştırma yüzeyi eklerdi.

## 12. Test edilen güvenlik davranışları

`tests/` altında **doğrulanan** kontroller:

| Test dosyası | Kapsam |
|---|---|
| `test_auth.py` | Hesap kilitleme, kullanıcı numaralandırma, belirteç iptali, zayıf parola reddi |
| `test_permissions.py` | Rol matrisi, denetçinin yazma yetkisizliği, son yöneticinin korunması, yetkisiz erişimin denetlenmesi |
| `test_sandbox.py` | 66 test — yol hapsi, kabuk zincirleme, kara liste, izin listesi, onay zorlaması, çalışma alanı dışına yazmanın **fiilen** engellendiği |
| `test_security_masking.py` | Anahtar maskeleme, şifreleme gidiş-dönüş, anahtarın hiçbir uçtan okunamaması, denetimde maskeleme, güvenlik başlıkları |
| `test_ai_providers.py` | Hata mesajlarında anahtar sızmaması, sağlayıcı kapalıyken güvenli davranış |

---

## Üretime geçiş kontrol listesi

- [ ] `APP_ENV=production`, `DEBUG=false`
- [ ] `SECRET_KEY` ve `SECRETS_ENCRYPTION_KEY` **güçlü ve benzersiz** değerlerle dolduruldu
- [ ] **Demo kullanıcılar silindi** veya parolaları değiştirildi (`Saraphane2026!` kesinlikle kalmamalı)
- [ ] `SEED_DEMO_DATA=false`
- [ ] `DATABASE_URL` PostgreSQL'e ayarlandı; veritabanı kullanıcısı **en az yetkiyle** çalışıyor
- [ ] `CORS_ORIGINS` yalnızca gerçek arayüz adreslerini içeriyor
- [ ] Uygulama **HTTPS** arkasında (ters vekil); HSTS etkin
- [ ] `AGENT_REQUIRE_APPROVAL=true`; AI terminali gerekmiyorsa `AGENT_ENABLED=false`
- [ ] Hız sınırlama etkin; birden çok işçi (worker) kullanılıyorsa Redis tabanlı sayaca geçildi
- [ ] Günlük dosyaları döndürülüyor ve erişimi kısıtlı
- [ ] Otomatik yedekleme kurulu, yedekler **farklı fiziksel ortama** kopyalanıyor
- [ ] Yedekten geri dönüş **denenmiş** ve çalıştığı doğrulanmış
- [ ] `pip-audit` ve `npm audit` temiz
- [ ] Git geçmişinde gizli bilgi taraması yapıldı
- [ ] `.env` sunucuda yalnızca uygulama kullanıcısı tarafından okunabilir

---

## Güvenlik açığı bildirimi

Bir güvenlik açığı bulduğunuzu düşünüyorsanız **genel bir issue açmayın**. Proje
sahibiyle doğrudan iletişime geçin ve düzeltme yayımlanana kadar ayrıntıyı paylaşmayın.
