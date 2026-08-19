# Değişiklik Günlüğü

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) biçimini ve
[Semantik Sürümleme](https://semver.org/lang/tr/) kurallarını izler.

## [Yayımlanmamış]

### Eklendi
- **Uçtan uca test paketi (Playwright)** — gerçek tarayıcıda 42 test: kimlik doğrulama,
  17 ekranın gezinmesi, rol tabanlı erişim, parti izlenebilirliği, yapay zekâ güvenlik
  korkulukları. Ücretli model çağrısı yapmaz.
- **Belge ekran görüntüleri** — `npm run gorseller` ile `docs/screenshots/` altına
  otomatik üretilir; README görsellerle güncellendi
- `tests/test_route_ordering.py` — 150 uç noktanın tamamını tarayıp `{param}` rotası
  tarafından gölgelenen (erişilemez) uçları bulur
- `tests/test_ratelimit.py` — hız sınırı kapsamlandırması (15 test)
- `tests/test_sandbox_kacis.py` — kapatılan sandbox kaçış yolları (23 test)

- **Tam iki dilli arayüz (Türkçe / İngilizce)** — tüm sayfalar, bileşenler,
  tablo başlıkları, boş durum metinleri, erişilebilirlik etiketleri ve
  durum/aşama sözlükleri çeviri katmanına taşındı. Tarih ve sayı biçimi aktif
  dile göre (`tr-TR` / `en-US`); para birimi TRY kalır.
  Sunucu tarafında rol adları ve yetki açıklamaları `Accept-Language` başlığına
  göre döner (`core/i18n.py`) — aksi hâlde İngilizce arayüzde bu etiketler
  Türkçe kalırdı. `tests/test_ceviri_butunlugu.py` iki sözlüğün anahtar
  kümesinin aynı kalmasını ve kodda çağrılan her anahtarın tanımlı olmasını
  zorunlu tutar; eksik çeviri sessizce ekrana düşmez.
- **Eğitim ve Kullanım Kılavuzu modülü** — rol bazlı, adım adım modüller; her
  adım gerçek ekrana bağlantı verir, sonunda çoktan seçmeli sınav vardır.
  İlerleme sunucuda saklanır (`training_progress` tablosu + Alembic göçü):
  kullanıcı yalnızca kendi kaydını görür ve yazar, yöneticiler ekip özetini
  görür — gıda güvenliği denetiminde "personel eğitildi mi" sorusunun cevabı.
  Geçme notu %70; tekrar denemek daha düşük puanla kazanılmış başarıyı silmez.
  İçerik iki dilli ve uygulamayla birlikte gelir (çevrimdışı çalışır).
- **İstatistik raporlama sistemi** — sekiz konu: bağ/hasat (parsel bazlı
  kg/dekar verimi, hedef Brix karşılaştırması), üzümden şişeye kayıp zinciri,
  fermantasyon süreleri, laboratuvar spesifikasyon dışı oranı ve onay döngüsü,
  şişeleme verim/fire oranları, fıçı yaş ve kullanım dağılımı, stok devri ve
  hareketsiz stok, bakım duruş Pareto'su ve CIP doğrulama oranı.
  **Her konu kendi yetkisiyle korunur**: tek bir uç nokta, `report:read` taşıyan
  ama `cost:read`/`lab:read` taşımayan rollere (satış, depo) maliyet ve
  laboratuvar verisi sızdırırdı.
- **Uygulama içi yedekleme** — `VACUUM INTO` ile tutarlı kopya, yedek listesi,
  disk durumu, saklama politikası ve indirme. Kurulu (MSI) sürümde PowerShell
  betiği bulunmadığı için kullanıcının **hiçbir yedek alma yolu yoktu**;
  yedeksiz bir üretim sistemi ilk disk arızasında tüm üretim geçmişini kaybeder.
  Yetki ikiye ayrıldı: `backup:manage` (al/listele/sil) ve `backup:download`
  (makine dışına çıkar — yalnızca sistem yöneticisi). Geri yükleme bilerek
  uygulanmadı: kullanıcının hazırladığı bir veritabanını yüklemek doğrudan
  ayrıcalık yükseltme yoludur; yordam README'de belgelendi.
- **MSI kurulum paketi (WiX Toolset 5.0.2)** — `scripts\msi-paketle.ps1` ile
  `dist\Saraphane-<sürüm>-x64.msi` üretilir (~37 MB). perMachine kurulum, Başlat
  menüsü ve masaüstü kısayolu, otomatik sürüm yükseltme, sessiz kurulum desteği.
  WiX v6+ ticari kullanıcılara aylık ücret yükümlülüğü getirdiği için **v5
  bilinçli olarak seçilmiştir** (bkz. `THIRD_PARTY_LICENSES.md`).
- **Kod imzalama hattı** — `scripts\imzala.ps1`: SHA-256 + RFC 3161 zaman
  damgası, dört yedekli zaman damgası sunucusu, sertifika deposu veya PFX
  desteği. Sertifika ve parola asla depoda tutulmaz. Zaten imzalı dosyalar
  atlanır: paketteki 203 ikiliden 169'u Microsoft/Python Software Foundation
  imzalıdır ve yeniden imzalamak üretici imzasını silerdi.
- **Uygulama simgesi** — `desktop\simge_uret.py` arayüzdeki üzüm salkımı
  logosundan 7 boyutlu `.ico` üretir; exe, kısayollar ve MSI'da kullanılır.
- **Sürüm kaynağı (VERSIONINFO)** — exe artık Windows dosya özelliklerinde ve
  UAC/SmartScreen kutularında ürün adı, sürüm ve yayıncı gösterir.
- **Veritabanı şeması Alembic ile yönetiliyor** — `app/db/sema.py`. Boş
  veritabanı kurulur, `create_all` ile oluşturulmuş eski veritabanı devralınır,
  mevcut kurulum yükseltilir.
- **Masaüstü uygulaması (PyWebView + PyInstaller)** — `scripts\masaustu-paketle.ps1`
  ile kurulum gerektirmeyen `dist\Saraphane\Saraphane.exe` üretilir (~75 MB).
  Boş port seçer, sunucuyu kendi içinde başlatır, kendi penceresinde açılır.
- **Derlenmiş arayüzün API ile aynı kökenden sunulması** — `frontend/dist` varsa
  FastAPI onu SPA olarak sunar (istemci rotaları `index.html`'e düşer, yol kaçışı
  engellenir). Yoksa API salt JSON olarak çalışır.

### Düzeltildi
- **Yeni kurulumda hiçbir hesap oluşmuyordu** — demo verisi yalnızca elle
  yüklendiği için kullanıcı tablosu boş kalıyor, uygulama açılıyor ama **hiçbir
  parola çalışmıyordu**. İlk açılışta rastgele parolalı yönetici hesabı oluşur;
  parola veri klasöründeki `ILK-GIRIS.txt` dosyasına bir kez yazılır ve ilk
  girişte değiştirilmesi zorunludur
- **`/reports/production` verim oranı 10 kata kadar şişiyordu** — şıra hacmi
  tarih filtresi olmadan toplanıp tarih filtreli üzüm miktarına bölünüyordu.
  Şıra artık aynı üzüm kabullerinden hesaplanır
- **Bozuk API yolları arayüz sayfası döndürüyordu** — SPA yakalayıcısı
  `/api/...` isteklerini yutup 200 HTML veriyordu; istemci hatayı başarı
  sanardı. API yolları artık her koşulda JSON 404 döner
- **`yedekle.ps1` kurulu sürümde yanlış klasöre bakıyordu** — yedek dizinini
  depo kökünden hesaplıyordu; artık veri kökünü uygulamanın kendi
  yapılandırmasından okur
- **Kurulu sürümde kaydedilen API anahtarları kalıcı olarak kayboluyordu.**
  `.env` `C:\Program Files` altında kaldığı ve yazılamadığı için
  `SECRETS_ENCRYPTION_KEY` her açılışta yeniden üretiliyordu; şifreli anahtarlar
  çözülemez hale gelip **hata mesajı bile olmadan** boş dönüyordu. Aynı sebeple
  her açılışta tüm oturumlar düşüyordu. Üretilen anahtarlar artık veri kökünde
  kalıcı olarak saklanıyor (`data\gizli-anahtarlar.json`, `.gitignore` kapsamında)
- **Program Files'a kurulan uygulama hiç açılmıyordu.** Veri kökü kaynak
  kökünden ayrıldı: kurulum dizini yazılamıyorsa `%LOCALAPPDATA%\Saraphane`
  kullanılır. Yazılabilirlik `os.access` ile değil, gerçek dosya oluşturma
  denemesiyle ölçülür (`os.access` Windows'ta ACL'leri değerlendirmez ve
  `C:\Program Files` için yanlışlıkla `True` döner)
- **Sürüm yükseltmesi uygulamayı bozuyordu.** `create_all` mevcut tabloya sütun
  eklemediği için 0.1.0 → 0.2.0 geçişinde uygulama açılıp ilk ekranda
  `no such column` veriyordu. Şema artık Alembic ile güncelleniyor
- **Açılış hataları sessizce yutuluyordu.** `console=False` olduğu için kullanıcı
  60 saniye bekleyip hiçbir şey görmüyordu; artık Türkçe hata kutusu gösterilir
- **Geliştirici veritabanı pakete sızıyordu.** `dist\Saraphane\data\winery.db`
  (+ 3,5 MB WAL) ve `logs\app.log` paketleme sonrası çalıştırmadan kalıyordu;
  MSI'a girseydi her Onarım işlemi müşterinin canlı verisini ezerdi
- **Belgeler ve `alembic.ini` pakete girmiyordu** — RAG indeksleme sessizce boş
  dönüyor, şema yükseltmesi çalıştırılamıyordu
- **PowerShell betikleri Windows'ta çalışmıyordu**: `kurulum.ps1`, `testler.ps1`,
  `yedekle.ps1` ve `masaustu-paketle.ps1` UTF-8 BOM taşımadığı için Windows
  PowerShell 5.1 bunları ANSI olarak okuyor, Türkçe karakterler bozuluyor ve
  **ayrıştırma hatası** veriyordu — yani README'de belgelenen komutlar hiç
  çalışmıyordu. Tüm betikler BOM ile kaydedildi (`tests/test_betikler.py` korur)
- **`GET /maintenance/due` 422 dönüyordu** ve "Yaklaşan bakımlar" listesi hep boş
  kalıyordu: CRUD router'ı `/{item_id}` rotasını `/due`'dan önce kaydediyordu
- **Hız sınırı normal kullanımı engelliyordu**: `/auth/me` her sayfa yüklemesinde
  çağrıldığı hâlde kaba kuvvet için ayrılmış 10/dk sınırına dahildi; sayfayı dakikada
  10 kez yenileyen kullanıcı API'den kilitleniyordu
- Giriş sayfasında belirteç yokken bile `/auth/me` isteği gönderiliyordu

### Güvenlik
- **AI terminali çalışma alanı dışına yazabiliyordu**: `python -c "open('C:/...','w')"`
  izin alıyordu. Satır içi kod çalıştırma (`python -c`, `py -c`, `node -e/-p/--eval/
  --print` ve bitişik yazımları) engellendi
- **Sistem dizini koruması atlatılabiliyordu**: kalıplar yalnızca `\` arıyordu,
  `C:/Windows/...` yazımı geçiyordu. Her iki ayraç da kapsandı
- `npx` yüksek risk sınıfına alındı (uzak paket indirip çalıştırabilir), açık onay ister
- Ayarlar ekran görüntüsünde maskeli anahtarın son karakterleri ve parmak izi de
  yer tutucuyla değiştirilir — depoya hiçbir anahtar türevi girmez

### Sonraki aşama için planlananlar
- Kod imzalama sertifikası edinimi (OV/EV) — hat hazır, sertifika bekliyor
- Taşınabilir sürümden kurulu sürüme veri taşıma sihirbazı
- E2E testlerinin Firefox/WebKit üzerinde de koşturulması
- PostgreSQL üzerinde tam test koşusu
- Sensör/IoT entegrasyonu için WebSocket akışı
- Redis tabanlı hız sınırlama (çok işçili dağıtım)
- `pgvector` ile büyük ölçekli RAG

---

## [0.1.0] — 15.08.2026

İlk sürüm. Bağdan şişeye tüm üretim zinciri, rol tabanlı yetkilendirme, üç yapay zekâ
sağlayıcısı ve güvenli AI terminali.

### Eklendi — Şaraphane çekirdeği

- **48 tablo**luk veri modeli; Alembic ile göç desteği (`0001_ilk_sema`)
- **Bağ ve üzüm kabulü**: bağ, parsel, üzüm çeşidi, tedarikçi; kantar kaydı,
  Brix/pH/asitlik/sıcaklık, kalite sınıfı, QR kodu, fotoğraf ve belge ekleri
- **Parti izlenebilirliği**: `lot_sources` + `lot_links` yönlü çizgesi üzerinde geriye
  ve ileriye izleme, döngü koruması, derinlik sınırı ve kullanıcıya uyarı
- **Tank yönetimi**: doluluk, sıcaklık, temizlik durumu, transferler (kapasite ve
  temizlik denetimli), görsel yerleşim haritası
- **Fermantasyon**: günlük/sensör ölçümleri, eğriler, maya ve katkılar, eşik alarmları,
  6 kurallı anomali tespiti, en küçük kareler ile tahmini bitiş tarihi
- **Laboratuvar**: 15+ parametre, numune yönetimi, spesifikasyon denetimi, onay/red
  iş akışı, görevler ayrılığı (analizi yapan kendi sonucunu onaylayamaz)
- **Reçete ve kupaj**: versiyonlu reçeteler, kupaj senaryoları, hacim ağırlıklı
  alkol/pH/asitlik öngörüsü (pH için H⁺ derişimi), maliyet, yetkili onayı, uygulama
- **Fıçı ve mahzen**: QR kodlu fıçılar, dolum/boşaltım/topping/temizlik geçmişi,
  mahzen haritası, fire takibi, tadım notları
- **Şişeleme**: emir, LOT numarası, hat takibi, ambalaj tüketimi ve bitmiş ürün girişi,
  fire/verim, etiket önizleme, barkod/QR
- **Stok**: FIFO/FEFO tüketim motoru, parti bazlı maliyet, minimum stok alarmı,
  depolar arası transfer, sayım, son kullanma takibi
- **Satın alma ve sevkiyat**: sipariş, mal kabul, müşteri, sevkiyat, teslim
- **Bakım ve temizlik**: ekipman envanteri, periyodik bakım, arıza, CIP doğrulama
- **Maliyet ve raporlama**: parti bazlı maliyet dökümü, kupajda maliyet taşıma,
  fire/verim, Excel/CSV/PDF dışa aktarma
- **Kontrol paneli**: 8 KPI, aktif fermantasyonlar, kritik uyarılar, tank doluluk,
  yaklaşan işlemler, üretim ve stok grafikleri, son faaliyetler, yapay zekâ önerileri

### Eklendi — Güvenlik

- Argon2id parola karması (OWASP parametreleri), parola politikası, otomatik yeniden karma
- JWT erişim + iptal edilebilir yenileme belirteci; hesap kilitleme; kullanıcı
  numaralandırma koruması
- **12 rol / 40+ yetki** ile rol tabanlı yetkilendirme; yetkisiz erişimin denetlenmesi
- API anahtarlarının Fernet ile şifreli saklanması; hiçbir uçtan okunamaması
- Günlük ve denetim kayıtlarında otomatik gizli değer maskeleme (7 anahtar biçimi)
- Hız sınırlama, güvenlik başlıkları, CORS daraltma
- Dosya yükleme doğrulaması (uzantı, boyut, SHA-256)
- **Değiştirilemez denetim günlüğü** (önce/sonra değerleri, IP, AI ve terminal bağlantısı)

### Eklendi — Yapay zekâ

- Ortak **`AIProvider`** soyutlaması; uygulama kodu sağlayıcıdan bağımsız
- **LM Studio** (yerel, anahtarsız), **Claude** (Messages API), **NVIDIA Build**,
  genişletilebilir OpenAI uyumlu sağlayıcı
- Bağlantı testi, model listesi (önbellekli), görev bazlı model yönlendirme, akış,
  yeniden deneme, **güvenli geri dönüş**, token/maliyet kaydı
- **Veri kapsamı önizlemesi**: harici sağlayıcıya veri gitmeden önce onay
- **Sayısal AI çekirdeği** (dil modelinden bağımsız): fermantasyon tahmini, anomali
  tespiti, kalite puanı, risk değerlendirmesi, kupaj öngörüsü, stok ve bakım tahmini
- **RAG**: doküman parçalama, yerel gömme, kosinüs benzerliği, anahtar kelime yedeği
- Yapay Zekâ Çalışma Merkezi: 8 görev türü, konuşma geçmişi, kullanım/maliyet paneli

### Eklendi — AI Terminali

- Plan → onay → Git kontrol noktası → çalıştır → lint+test → diff → birleştir/geri al
- **Yol hapsi**: `AGENT_WORKSPACE` dışına erişim kod düzeyinde engelli
- **Komut politikası**: izin listesi, kabuk zincirleme yasağı, 20+ yıkıcı kalıp kara listesi,
  git/pip/npm alt komut denetimi
- Zaman aşımı, çıktı sınırı, gizli değer maskeleme, alt sürece gizli ortam değişkeni
  aktarılmaması
- Ayrı yetkiler: `ai:terminal` (plan) ve `ai:terminal:approve` (onay + çalıştırma)

### Eklendi — Arayüz

- React 19 + TypeScript (strict) + Vite + Tailwind v4 + ECharts
- 18 sayfa; rol bazlı süzülen menü; koyu/açık tema; şaraphane renk kimliği
- Türkçe arayüz, İngilizce sözlük altyapısı hazır
- İzlenebilirlik çizgesi, fermantasyon eğrisi, tank/mahzen görsel yerleşimi,
  etiket önizleme, maliyet dağılımı

### Eklendi — Araçlar ve dokümantasyon

- `Baslat.bat` tek tık başlatıcı; kurulum, başlatma, test, yedekleme, demo veri betikleri
- LM Studio model değerlendirme betiği ve raporu
- README, ARCHITECTURE, SECURITY, THIRD_PARTY_LICENSES,
  AI_MODEL_EVALUATION, NVIDIA_MODEL_SELECTION
- **225 test**; Ruff + mypy + TypeScript kalite kapıları

### Düzeltildi — Geliştirme sırasında bulunan gerçek hatalar

| Sorun | Çözüm |
|---|---|
| `bottling_orders` ↔ `inventory_items` dairesel yabancı anahtarı tabloların oluşturulmasını engelliyordu | Mantıksal referansa çevrildi |
| NOT NULL sütunlara şemadan `None` gitmesi kayıt oluşturmayı bozuyordu | Şema varsayılanları + CRUD katmanında None süzme |
| `Decimal` değerler denetim günlüğünde JSON'a yazılamıyordu | `to_dict()` içinde `float` dönüşümü |
| `updated_at` alanı asenkron bağlamda `MissingGreenlet` çökmesine yol açıyordu | `to_dict()` yalnızca yüklenmiş alanları okur |
| Pydantic'in tembel ilişkileri okuması kupaj/reçete/sipariş yanıtlarını çökertiyordu | Açık sözlükten doğrulama |
| FIFO çıkışında aynı kod üretilip benzersizlik kısıtı ihlal ediliyordu | Kod üreteci bekleyen nesneleri de dikkate alır |
| CRUD fabrikasında ertelenmiş tip açıklamaları FastAPI şema üretimini bozuyordu | Modülde `from __future__ import annotations` kaldırıldı |
| Akıl yürütme modelleri (Gemma 4) boş yanıt döndürüyordu | `reasoning_tokens` okunur, açıklayıcı hata verilir |
| `system` rolünü desteklemeyen modeller HTTP 400 veriyordu | Sistem yönergesi katlanıp bir kez yeniden denenir |
| Zaman aşımında yeniden deneme bekleme süresini katlıyordu | Zaman aşımında yeniden denenmez |
| `%USERPROFILE%` gibi genişleyen yollar sandbox denetiminden kaçıyordu | Genişleyen yol kalıpları reddedilir |
| Demo verisinde tank hacimleri kapasiteyi aşıyordu | Hacimler kapasiteye uyacak şekilde düzeltildi |
| Demo hasat tarihleri geçmişte kalıp panoyu boş gösteriyordu | Hasat, çalıştırma tarihine göre konumlandırılır |

### Güvenlik notları

- Varsayılan backend portu **8010** (8000 Windows'ta sık kullanılıyor)
- Demo kullanıcılar yalnızca geliştirme içindir; üretim kontrol listesi
  [SECURITY.md](SECURITY.md) içindedir
- LGPL/GPL/AGPL lisanslı hiçbir bağımlılık kullanılmamıştır
