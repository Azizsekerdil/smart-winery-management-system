# Gizlilik — Privacy

Bu belge, yazılımın **hangi veriyi nerede tuttuğunu** ve **hangi koşullarda
makineden çıkardığını** anlatır. Bir hizmet gizlilik politikası değildir: bu
yazılım kendi kendine barındırılır (self-hosted), veriyi proje sahibine
göndermez ve herhangi bir merkezî sunucuya bağlanmaz.

## 1. Veriyi kim tutar

**Siz.** Yazılım sizin bilgisayarınızda veya sunucunuzda çalışır. Geliştiriciye,
proje sahibine veya herhangi bir üçüncü tarafa **otomatik olarak hiçbir veri
gönderilmez**. Telemetri, kullanım istatistiği, çökme raporlama veya "eve arama"
(phone-home) davranışı **yoktur**.

## 2. Nerede saklanır

| Veri | Konum | Not |
|---|---|---|
| Veritabanı | `data/winery.db` (SQLite) veya yapılandırdığınız PostgreSQL | Git'e girmez |
| Yüklenen belge ve fotoğraflar | `data/uploads/` | Git'e girmez |
| Yedekler | `data/backups/` | Git'e girmez |
| Uygulama günlükleri | `logs/` | Git'e girmez |
| Üretilen gizli anahtarlar | `data/gizli-anahtarlar.json` | `0600` izniyle yazılır, Git'e girmez |
| İlk kurulum parolası | `data/ILK-GIRIS.txt` | Bir kez yazılır, **parola değiştirilince silinir** |

Kurulu (MSI) sürümde veri kökü `%LOCALAPPDATA%\Saraphane` altındadır; kaynak
dosyalardan ayrı tutulur.

## 3. Kişisel veri

Sistem, çalışması gereği bazı kişisel verileri işler:

- **Personel:** kullanıcı adı, ad-soyad, e-posta, telefon, departman, roller.
- **Tedarikçi / müşteri:** firma adı, iletişim bilgileri, adres.
- **Denetim günlüğü:** kim, ne zaman, hangi IP'den, hangi kaydı değiştirdi.

Denetim günlüğü **bilinçli olarak değiştirilemez ve silinemez** — izlenebilirlik
gereksinimidir. Silme hakkı (KVKK md. 7 / GDPR md. 17) taleplerini
karşılarken bu tasarım kısıtını dikkate alın: kaydın kendisi kalır, ancak
kişiyle bağını kesmek için kullanıcı kaydını pasifleştirebilir veya
anonimleştirebilirsiniz.

**Parolalar** hiçbir zaman düz metin tutulmaz: Argon2id ile karmalanır.
Parolalar, API anahtarları ve belirteçler **günlüklere yazılmadan önce otomatik
maskelenir** (`backend/app/core/logging.py`).

## 4. Veri ne zaman makineden çıkar

**Yalnızca harici bir yapay zekâ sağlayıcısı seçtiğinizde ve siz onayladığınızda.**

Varsayılan sağlayıcı **yereldir** (LM Studio, `http://localhost:1234`). Yerel
sağlayıcı kullanılırken hiçbir şaraphane verisi ağa çıkmaz.

Harici (bulut) bir sağlayıcı seçildiğinde:

1. Kapı **her istekte ve koşulsuz** çalışır. Ekli kayıt olmasa bile devreye
   girer — yazdığınız sorunun kendisi de dışarı çıkacak bir veridir.
2. Gönderilecek her şey tek tek listelenir:
   - seçtiğiniz parti / fermantasyon kayıtları ve alanları,
   - doküman araması (RAG) ile bulunan **doküman parçaları**,
   - varsa **konuşma geçmişi**.
3. Onaylamazsanız istek **gönderilmez** (HTTP 412).
4. Yerel model çöktüğünde geri dönüş zinciri **buluta geçemez**; istek başarısız
   olur (HTTP 503).
5. Her gönderim, hangi sağlayıcıya hangi kapsamın gittiği bilgisiyle denetim
   günlüğüne yazılır.

Bunların tamamı `tests/test_harici_paylasim_onayi.py` içinde regresyon
testleriyle korunur.

### Sağlayıcının kendi politikası sizi bağlar

Veriyi bir bulut sağlayıcısına gönderdiğinizde, o verinin saklanması ve
kullanılması **o sağlayıcının** koşullarına tabidir. Bu yazılım onu kontrol
edemez. Hassas üretim verisi için yerel modeli tercih edin.

## 5. Doküman araması (RAG) hakkında dürüst ifade

- Gömme (embedding) vektörleri **yerel** modelle üretilir.
- Ancak bulunan doküman parçalarının **metni** giden isteme eklenir.
- Bu yüzden parçalar onay listesinde tek tek gösterilir ve harici sağlayıcıda
  onaysız gönderilmez.
- **Yerel modelle çalışırken hiçbir doküman içeriği makineden çıkmaz.**

## 6. Demo verisi

Depodaki demo verisi **tamamen kurgusaldır**. Gerçek kişi, işletme, adres veya
telefon numarası içermez. Üretimde `SEED_DEMO_DATA=false` yapın ve demo
hesaplarını silin.

## 7. Yedekler

Yedek dosyaları veritabanının tamamını içerir — yani tüm kişisel veriyi. Yedekleri
şifreli bir konumda saklayın ve erişimi `backup:manage` yetkisiyle sınırlayın.
Yedek indirme işlemi denetim günlüğüne yazılır.

## 8. Sorumluluk

Bu yazılımı kurup çalıştıran taraf, işlediği kişisel veri bakımından **veri
sorumlusudur**. KVKK / GDPR yükümlülükleri (aydınlatma metni, saklama süreleri,
veri sahibi talepleri, ihlal bildirimi) size aittir. Bu yazılım bu yükümlülükleri
karşılamaz ve karşıladığını iddia etmez; yalnızca teknik olarak destekleyecek
araçları (denetim günlüğü, rol tabanlı erişim, maskeleme) sağlar.
