# Yerel Yapay Zekâ Modeli Değerlendirmesi (LM Studio)

**Oluşturma:** 15.08.2026 06:50  
**Sunucu:** `http://localhost:1234/v1`  
**Yöntem:** Her model, dört şaraphane görevinde küçük ve tekrarlanabilir
isteklerle sınandı (temperature 0.2). Puanlama otomatiktir:
Türkçe bütünlüğü karakter/kelime analiziyle, JSON geçerliliği ayrıştırmayla,
sayısal doğruluk beklenen değerle karşılaştırılarak ölçülür.

> Bu değerlendirme donanıma ve LM Studio ayarlarına (bağlam uzunluğu, GPU
> katman sayısı, niceleme) bağlıdır. Farklı makinede sonuçlar değişebilir.

## Özet tablo

| Model | Ort. puan | Ort. gecikme | Türkçe | JSON | Sayısal | Hata |
|---|---|---|---|---|---|---|
| `google/gemma-4-12b-qat` | **1.00** | 32.3 sn | 1.00 | 1.00 | 1.00 | 0 |
| `qwen/qwen3-vl-8b` | **0.96** | 6.4 sn | 1.00 | 0.85 | 1.00 | 0 |
| `biomistral-7b` | **0.50** | 2.7 sn | 1.00 | 0.00 | 0.00 | 0 |
| `moondream-2b-2025-04-14` | **0.33** | 1.8 sn | 0.65 | 0.00 | 0.00 | 0 |
| `qwen2.5-math-7b-instruct` | **0.25** | 8.6 sn | 0.00 | 0.00 | 1.00 | 0 |

## Görev bazlı ayrıntı

### `biomistral-7b`

| Görev | Puan | Süre | Not |
|---|---|---|---|
| Türkçe enoloji açıklaması | 1.00 | 5.1 sn | 23 kelime, 15 Türkçe özel karakter · system rolü desteklenmiyor, katlandı |
| Yapılandırılmış JSON üretimi | 0.00 | 2.4 sn | Geçersiz JSON: Expecting value · system rolü desteklenmiyor, katlandı |
| Sayısal hesap (kupaj oranı) | 0.00 | 0.4 sn | Yanlış: 15 (beklenen 65.0) · system rolü desteklenmiyor, katlandı |
| Türkçe SOP adımı yazımı | 1.00 | 3.1 sn | 18 kelime, 9 Türkçe özel karakter · system rolü desteklenmiyor, katlandı |

### `google/gemma-4-12b-qat`

| Görev | Puan | Süre | Not |
|---|---|---|---|
| Türkçe enoloji açıklaması | 1.00 | 59.9 sn | 98 kelime, 57 Türkçe özel karakter |
| Yapılandırılmış JSON üretimi | 1.00 | 18.4 sn | Tam ve temiz JSON |
| Sayısal hesap (kupaj oranı) | 1.00 | 11.2 sn | Doğru: 65 |
| Türkçe SOP adımı yazımı | 1.00 | 39.8 sn | 74 kelime, 47 Türkçe özel karakter |

### `qwen/qwen3-vl-8b`

| Görev | Puan | Süre | Not |
|---|---|---|---|
| Türkçe enoloji açıklaması | 1.00 | 18.7 sn | 59 kelime, 44 Türkçe özel karakter |
| Yapılandırılmış JSON üretimi | 0.85 | 3.1 sn | Doğru JSON (fazladan metin içeriyor) |
| Sayısal hesap (kupaj oranı) | 1.00 | 0.4 sn | Doğru: 65 |
| Türkçe SOP adımı yazımı | 1.00 | 3.6 sn | 20 kelime, 14 Türkçe özel karakter |

### `qwen2.5-math-7b-instruct`

| Görev | Puan | Süre | Not |
|---|---|---|---|
| Türkçe enoloji açıklaması | 0.00 | 14.8 sn | İngilizce sızıntısı (56 kelime), 298 kelime |
| Yapılandırılmış JSON üretimi | 0.00 | 8.1 sn | Geçersiz JSON: Expecting property name enclosed in double quotes |
| Sayısal hesap (kupaj oranı) | 1.00 | 6.2 sn | Doğru: 65 |
| Türkçe SOP adımı yazımı | 0.00 | 5.4 sn | İngilizce sızıntısı (41 kelime), 180 kelime |

### `moondream-2b-2025-04-14`

| Görev | Puan | Süre | Not |
|---|---|---|---|
| Türkçe enoloji açıklaması | 1.00 | 5.6 sn | 19 kelime, 11 Türkçe özel karakter |
| Yapılandırılmış JSON üretimi | 0.00 | 1.0 sn | Geçersiz JSON: Expecting value |
| Sayısal hesap (kupaj oranı) | 0.00 | 0.3 sn | Sayı bulunamadı |
| Türkçe SOP adımı yazımı | 0.30 | 0.1 sn | Çok kısa yanıt (1 kelime) |

---

## Bulgular ve ürüne yansıyan düzeltmeler

Bu değerlendirme yalnızca bir karşılaştırma tablosu üretmedi; iki gerçek uyumluluk
sorununu ortaya çıkardı ve **ikisi de ürün koduna düzeltme olarak yansıtıldı**.

### 1. Akıl yürütme (reasoning) modelleri düşük token bütçesinde boş yanıt veriyor

`google/gemma-4-12b-qat` ilk turda **dört görevin dördünde de boş yanıt** döndürdü.
Ham yanıt incelendiğinde neden görüldü: model, üretimi önce `reasoning_content`
alanına yazıyor ve `max_tokens=300` bütçesinin tamamını (297 belirteç) düşünme
aşamasında harcayıp görünür yanıta hiç sıra gelmeden kesiliyordu
(`finish_reason: length`).

**Düzeltme** — `backend/app/services/ai/openai_compat.py`:

- Yanıt `usage.completion_tokens_details.reasoning_tokens` alanı okunur.
- `content` boş **ve** düşünme belirteci harcanmışsa sessizce boş yanıt dönmek
  yerine anlaşılır bir Türkçe hata verilir: *"… bir akıl yürütme modelidir ve token
  bütçesinin tamamını düşünme aşamasında harcadı. Yanıt uzunluğu sınırını artırın
  (önerilen: en az 1500)."*

Bütçe 1500'e çıkarıldığında aynı model **dört görevde de tam puan** aldı.

### 2. Bazı yerel modeller `system` rolünü kabul etmiyor

`biomistral-7b`, sistem yönergesi içeren her isteği **HTTP 400** ile reddetti:
`"Only user and assistant roles are supported!"` — modelin Jinja sohbet şablonu
`system` rolünü tanımıyor.

**Düzeltme** — aynı dosya: bu hata yakalandığında sistem yönergesi ilk kullanıcı
mesajının başına katlanarak istek **bir kez** yeniden gönderilir. Böylece sınırlı
sohbet şablonuna sahip yerel modeller de sorunsuz çalışır. Düzeltmeden sonra
BioMistral 4/4 isteği başarıyla yanıtladı.

---

## Görev bazlı model yönlendirme önerisi

Ölçüm sonuçlarına dayanarak (bu makine ve LM Studio ayarları için):

| Görev | Önerilen model | Gerekçe |
|---|---|---|
| **Genel Türkçe analiz, danışmanlık** | `qwen/qwen3-vl-8b` | Türkçe 1.00, ortalama 6.4 sn — kalite/hız dengesi en iyi |
| **Kritik rapor, uzun Türkçe metin** | `google/gemma-4-12b-qat` | Tüm görevlerde 1.00; ancak Türkçe üretimde ~60 sn |
| **Yapılandırılmış JSON / araç çağırma** | `google/gemma-4-12b-qat` | Tek "tam ve temiz JSON" üreten model (1.00) |
| **Matematik / hesap açıklaması** | `qwen2.5-math-7b-instruct` | Sayısal 1.00; **ancak Türkçe'de ağır İngilizce sızıntısı var**, yanıtı kullanıcıya doğrudan göstermeyin |
| **Görsel / etiket analizi** | `moondream-2b` veya `qwen/qwen3-vl-8b` | İkisi de görsel-dil modeli; moondream çok hızlı (1.8 sn) ama metin üretimi zayıf |
| **Gömme (RAG)** | `text-embedding-nomic-embed-text-v1.5` | Tek gömme modeli; sohbet testine dahil edilmedi |

**`biomistral-7b` varsayılan yapılmamıştır.** Tıbbi alan modelidir; şaraphane
terminolojisinde yüzeysel kalıyor, JSON ve hesap görevlerinde başarısız. Yalnızca
kullanıcı açıkça seçerse kullanılabilir.

### Uygulamada nasıl ayarlanır

**Ayarlar → LM Studio → Model listesini yenile** ile modeller çekilir, ardından
varsayılan model seçilir. Görev bazlı yönlendirme için sağlayıcının
`task_model_map` alanı kullanılır:

```json
{
  "saraphane_danismani": "qwen/qwen3-vl-8b",
  "veri_analisti": "qwen/qwen3-vl-8b",
  "rapor_yazari": "google/gemma-4-12b-qat",
  "kod_gelistirici": "google/gemma-4-12b-qat"
}
```

### Değerlendirmeyi kendi makinenizde tekrarlama

```powershell
.venv\Scripts\python.exe scripts\ai-model-degerlendir.py
.venv\Scripts\python.exe scripts\ai-model-degerlendir.py --model qwen/qwen3-vl-8b
```

Betik LM Studio'daki tüm sohbet modellerini bulur, dört görevde sınar ve bu dosyayı
yeniden üretir. Gömme modelleri otomatik olarak dışlanır.

## Yöntemin sınırları

- Puanlama **otomatiktir**: Türkçe kalitesi karakter/kelime oranıyla ölçülür, bu bir
  dil bilgisi denetimi değildir. Kısa ama doğru yanıtlar "çok kısa" diye cezalanabilir.
- Her görev **bir kez** çalıştırılır; örneklem küçüktür. Kesin karar için görev başına
  birden çok tekrar ve insan değerlendirmesi önerilir.
- Gecikmeler bu makinenin donanımına (RTX 4060 Laptop, 8 GB VRAM) ve LM Studio'nun
  GPU katman/bağlam ayarlarına bağlıdır.
- Şaraphane alan bilgisinin **doğruluğu** ölçülmemiştir; yalnızca dil, biçim ve
  sayısal doğruluk ölçülmüştür. Üretim kararları için uzman onayı zorunludur.
