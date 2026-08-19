# Yapay zekâ şeffaflığı — AI transparency

Bu belge, yazılımın yapay zekâyı **nerede**, **nasıl** ve **hangi sınırlarla**
kullandığını anlatır.

## 1. İki ayrı katman vardır

Bu ayrım ürünün temel tasarım kararıdır:

| Katman | Ne yapar | Dil modeli gerekir mi |
|---|---|---|
| **Sayısal çekirdek** (`backend/app/services/ai_features.py`) | Fermantasyon bitiş tahmini, anomali tespiti, kalite puanı, risk değerlendirmesi, kupaj öngörüsü, stok tükenme tahmini, bakım tarihi | **Hayır** |
| **Dil modeli yorumu** (`backend/app/services/ai/`) | Yukarıdaki sayısal sonucu düz Türkçe/İngilizce anlatır, serbest sohbet, doküman araması | Evet |

**Sayısal çekirdek deterministiktir**: aynı girdi her zaman aynı çıktıyı verir,
birim testleriyle doğrulanır ve hiçbir sağlayıcıya bağlı değildir. Tüm
sağlayıcılar kapalıyken bile bu özellikler **çalışmaya devam eder**. Dil modeli
kapandığında kaybettiğiniz tek şey, sonucun sözel yorumudur.

Bu, "yapay zekâ" etiketinin arkasında ne olduğu konusunda dürüst olmak içindir:
tahminler bir dil modelinin uydurması değil, ölçülebilir hesaplardır.

## 2. Hangi sağlayıcılar kullanılabilir

| Sağlayıcı | Konum | API anahtarı | Varsayılan |
|---|---|---|---|
| **LM Studio** | **Yerel** (`localhost:1234`) | Gerekmez | **Evet** |
| Anthropic Claude | Bulut | Gerekir | Hayır |
| NVIDIA Build | Bulut | Gerekir | Hayır |
| OpenAI uyumlu (genel) | Değişken | Gerekir | Hayır (kapalı) |

Uygulama kodu hiçbir sağlayıcıya doğrudan bağlı değildir; hepsi ortak bir
`AIProvider` soyutlaması üzerinden çağrılır. **Resmî SDK kullanılmaz**, düz
HTTP ile konuşulur.

**Yerel seçenek her zaman vardır.** Hiçbir bulut sağlayıcısı yapılandırmadan
sistemin tamamı çalışır.

## 3. Model kimlikleri sabit varsayılmaz

Model listesi API'den okunur, koda gömülmez. Bu bilinçlidir: model adları
sağlayıcı tarafında değişir ve sabit bir ad, sessizce başarısız olan bir
entegrasyon demektir.

## 4. Veri sınırları

Ayrıntı: [PRIVACY.md](PRIVACY.md). Özetle:

- Harici sağlayıcı seçildiğinde onay kapısı **her istekte ve koşulsuz** çalışır.
- Gönderilecek kayıtlar, doküman parçaları ve konuşma geçmişi tek tek listelenir.
- Onay yoksa istek gönderilmez.
- Yerel model çökerse istek başarısız olur; **sessizce buluta geçilmez**.

## 5. İnsan onayı — modelin yetkisi nerede biter

**Yapay zekâ hiçbir üretim değerini kendiliğinden değiştirmez.**

- Bir öneri; bir tanka, reçeteye, kupaja, stok hareketine veya laboratuvar
  kaydına **otomatik olarak uygulanmaz**.
- Her yazma işlemi, yetkisi olan bir kullanıcının açık eylemini gerektirir.
- AI terminali (geliştirici aracı) plan → **kullanıcı onayı** → çalıştır
  akışını zorunlu tutar; onaysız çalıştırma 409 ile reddedilir.
- Her AI isteği denetim günlüğüne yazılır.

## 6. Sınırlar ve bilinen zayıflıklar

- **Dil modelleri hata yapar ve uydurur.** Sistem istemi modeli verilen veriyle
  sınırlamaya çalışır, ancak bu bir garanti değildir. Yorumları doğrulayın.
- **Sayısal tahminler modeldir, kehanet değildir.** Fermantasyon bitiş tahmini
  geçmiş Brix eğrisinin doğrusal öngörüsüne dayanır; duraklamış (stuck)
  fermantasyonu önceden bilemez.
- **Anomali tespiti eşik tabanlıdır**, öğrenen bir model değildir. Yanlış
  pozitif üretebilir.
- **Kalite puanı bir sektör standardı değildir.** Bu projeye özgü, ağırlıklı bir
  göstergedir; resmî derecelendirme veya sertifikasyon yerine geçmez.
- **Kupaj öngörüsü hacim ağırlıklı doğrusal bir hesaptır**; gerçek şaraptaki
  kimyasal etkileşimleri modellemez. Laboratuvar doğrulaması yerine geçmez.
- **RAG araması** gömme yoksa anahtar kelimeye düşer; alakasız sonuç dönebilir.
- **Maliyet tahminleri yaklaşıktır** ve sağlayıcının güncel fiyatlandırmasına
  bağlıdır; fatura yerine geçmez.

## 7. Ne için kullanılmamalıdır

Bu sistemin yapay zekâ çıktıları **şunlar için kullanılamaz**:

- yasal uyum beyanı, sertifikasyon veya resmî mevzuat kararı,
- sağlık, gıda güvenliği veya alerjen beyanı,
- mali beyan, vergi veya muhasebe kaydı,
- yatırım, fiyatlama veya ticari tavsiye.

Bunların hepsi uzman insan kararıdır. Sistem **karar desteği** sağlar, karar
vermez.
