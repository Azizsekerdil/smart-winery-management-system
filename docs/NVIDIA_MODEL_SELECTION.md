# NVIDIA Build — Model Seçimi ve API Kurulumu

**İnceleme tarihi:** 15.08.2026
**Kaynak:** <https://build.nvidia.com/models> (katalogda **124 model**; 57 ücretsiz uç
nokta, 27 iş ortağı uç noktası)
**Erişim biçimi:** OpenAI uyumlu HTTP · `https://integrate.api.nvidia.com/v1`

> Bu belgedeki model kimlikleri ve uç nokta bilgisi, katalog **doğrudan incelenerek**
> doğrulanmıştır; tahmin edilmemiştir. Katalog sık güncellenir — uygulamadaki
> **Ayarlar → NVIDIA Build → Model listesini yenile** düğmesi her zaman güncel listeyi
> API'den çeker.

---

## 1. API anahtarı oluşturma (kullanıcı tarafından yapılmalıdır)

Anahtar oluşturma işlemi hesap ayarı değişikliği, kullanım koşulu onayı ve kota seçimi
içerebildiği için **sizin tarafınızdan** yapılmalıdır. Adımlar:

1. <https://build.nvidia.com> adresinde oturumunuzun açık olduğundan emin olun
2. Kullanmak istediğiniz model kartını açın
   (örn. <https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b>)
3. Sağ üstteki **`Generate API Key`** (bazı kartlarda **`Get API Key`**) düğmesine basın
4. Açılan pencerede kullanım koşullarını okuyup onaylayın
5. Üretilen anahtarı **kopyalayın** — `nvapi-` ile başlar ve **yalnızca bir kez gösterilir**

> ⚠️ Anahtarı sohbete, e-postaya, ekran görüntüsüne veya bir dosyaya yapıştırmayın.

### Anahtarı uygulamaya girme

**Ayarlar → NVIDIA Build → Ekle** → anahtarı yapıştırın → **Şifreleyerek kaydet**

Anahtar Fernet (AES-128-CBC + HMAC-SHA256) ile şifrelenerek veritabanına yazılır;
hiçbir ekranda, API yanıtında veya günlükte açık gösterilmez. Doğrulamak için
**Bağlantıyı test et** düğmesini kullanın (model listesi çeker, ücret doğurmaz).

Alternatif olarak `.env` dosyasına yazabilirsiniz:

```
NVIDIA_API_KEY=[nvapi- ile başlayan anahtarınız]
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=nvidia/nemotron-3-ultra-550b-a55b
```

> `.env` dosyası `.gitignore` içindedir ve depoya gönderilmez. Anahtarı `.env.example`
> gibi **şablon** dosyalara yazmayın.

---

## 2. Şaraphane görevleri için model önerileri

Katalogdan, uygulamanın **gerçek görev türlerine** göre seçilen adaylar:

### Genel asistan, Türkçe analiz ve uzun bağlamlı akıl yürütme

| Model | Kimlik | Neden |
|---|---|---|
| **Nemotron 3 Ultra** ⭐ | `nvidia/nemotron-3-ultra-550b-a55b` | Katalogun en çok kullanılan modeli (30 günde 52M çağrı). **1M bağlam**, 561B parametre, hibrit Mamba-Transformer MoE. Agentic akıl yürütme, planlama ve araç çağırmada güçlü. Ücretsiz uç noktası var |
| GLM-5.2 | `glm-5.2` (kart: Z.ai) | Agentic iş akışları ve uzun ufuklu akıl yürütme için amiral gemisi LLM |
| MiniMax M3 | `minimax-m3` (kart: MiniMaxAI) | Çok modlu MoE; akıl yürütme, kod ve araç çağırma. 30 günde 10M çağrı |
| Step 3.7 Flash | `step-3.7-flash` (kart: StepFun-AI) | Kurumsal/agentic görevler için seyrek MoE; hızlı |

**Seçim:** `nvidia/nemotron-3-ultra-550b-a55b` — 1M bağlam, bir partinin **tüm**
fermantasyon ölçümlerini ve laboratuvar geçmişini tek istekte değerlendirmeye yeter.

### Kod üretimi (AI Terminali "kod geliştirici" görevi)

| Model | Kimlik | Neden |
|---|---|---|
| **Poolside Laguna XS** ⭐ | `laguna-xs-2.1` (kart: Poolside) | 33B MoE, **uzun ufuklu agentic kodlama ve terminal görevleri** için özel olarak tanımlanmış — bu projedeki AI Terminali senaryosuyla birebir örtüşüyor |
| Nemotron 3 Ultra | `nvidia/nemotron-3-ultra-550b-a55b` | Kodlama ve araç çağırma yetenekleri güçlü, tek model ile idare edilmek istenirse |
| GLM-5.2 | `glm-5.2` | Kodlama odaklı amiral gemisi |

### Yapılandırılmış JSON / rapor üretimi

`nvidia/nemotron-3-ultra-550b-a55b` veya `nvidia/nemotron-3.5-lightning-30b-a3b`
(*"Fastest 30B A3B MoE model with leading domain accuracy for specialized agentic
tasks"*) — hız/maliyet dengesi için ikincisi tercih edilebilir.

### Görsel ve etiket analizi (şişe etiketi, ekipman fotoğrafı)

| Model | Kimlik | Neden |
|---|---|---|
| **Nemotron 3 Nano Omni** ⭐ | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | Görüntü, video, ses ve metni birlikte anlayan omni-modal akıl yürütme modeli; OCR yeteneği de var |
| Muse Glimmer 30B | `muse-glimmer-30b` (kart: Meta) | Çok modlu akıl yürütme, yerel araç çağırma desteği |
| Nemotron OCR v2 | `nvidia/nemotron-ocr-v2` | **Çok dilli OCR** — analiz sertifikası, irsaliye, kantar fişi taramaları için |

### Embedding / RAG (şaraphane dokümanlarında arama)

| Model | Kimlik | Neden |
|---|---|---|
| **Nemotron 3 Embed** ⭐ | `nvidia/nemotron-3-embed-1b` | 1B gömme modeli; semantik arama, getirme ve **RAG** için tasarlanmış. Ücretsiz uç noktası var |

> **Ancak öneri:** Doküman içeriği hassas olabileceğinden, projenin varsayılanı
> **yerel gömme** modelidir (`text-embedding-nomic-embed-text-v1.5`, LM Studio).
> NVIDIA gömme modeli yalnızca yerel model kullanılamadığında veya doküman hassas
> değilse tercih edilmelidir.

### Ek olarak değerlendirilebilecek modeller

| Model | Kimlik | Olası kullanım |
|---|---|---|
| Riva Translate | `nvidia/riva-translate-4b-instruct-v2` | **37 dilde çeviri** — ihracat için etiket/belge çevirisi, çok dilli arayüz içeriği |
| Nemotron Content Safety | `nvidia/nemotron-3.5-content-safety` | Çok dilli içerik güvenliği — kullanıcı üretimi metinlerin (tadım notu, şikâyet) denetimi |

---

## 3. Uygulamada görev bazlı yönlendirme

**Ayarlar → NVIDIA Build → Model listesini yenile** ile modeller çekildikten sonra
sağlayıcının `task_model_map` alanı şu şekilde ayarlanabilir:

```json
{
  "saraphane_danismani": "nvidia/nemotron-3-ultra-550b-a55b",
  "veri_analisti": "nvidia/nemotron-3-ultra-550b-a55b",
  "rapor_yazari": "nvidia/nemotron-3.5-lightning-30b-a3b",
  "kod_gelistirici": "laguna-xs-2.1",
  "hata_teshis": "nvidia/nemotron-3-ultra-550b-a55b",
  "kalite_kontrol": "nvidia/nemotron-3-ultra-550b-a55b"
}
```

> Kimlikleri **kendiniz doğrulayın**: her model kartındaki kod örneğinde
> `model="…"` satırı tam kimliği verir. Yayıncı öneki (`nvidia/`, `meta/` …) modele
> göre değişir.

---

## 4. Teknik uyumluluk notları

### 4.1 OpenAI uyumluluğu doğrulandı

Model kartındaki resmî örnek, uygulamanın `OpenAICompatProvider` sınıfıyla **birebir
uyumludur**:

```python
client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key="$NVIDIA_API_KEY")
completion = client.chat.completions.create(model="nvidia/nemotron-3-ultra-550b-a55b", ...)
```

Bu nedenle NVIDIA için ayrı bir istemci yazılmamış, `NvidiaProvider` yalnızca varsayılan
adresi ve anahtarsız durumdaki yönlendirici hata mesajını ekleyen ince bir katman
olarak tanımlanmıştır.

### 4.2 Akıl yürütme (reasoning) modelleri

Nemotron 3 Ultra'nın resmî örneği `reasoning_content` alanını ve `reasoning_budget`
parametresini kullanır:

```python
extra_body={"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}
```

Bu, yerel Gemma 4 testinde karşılaşılan durumun aynısıdır: **model bütçenin bir kısmını
düşünmeye harcar.** Uygulama bu durumu zaten ele alır — `completion_tokens_details.
reasoning_tokens` okunur ve içerik boş dönerse *"token bütçesinin tamamını düşünme
aşamasında harcadı, sınırı artırın"* şeklinde açık bir Türkçe hata verilir
(bkz. `backend/app/services/ai/openai_compat.py`).

**Pratik öneri:** NVIDIA akıl yürütme modellerinde yanıt uzunluğu sınırını **en az
4000** yapın.

### 4.3 Gizlilik

NVIDIA Build **harici bir bulut servisidir**. Uygulama, bu sağlayıcıya şaraphane
verisi gönderilmeden önce hangi kayıtların gideceğini listeler ve açık onay ister
(`confirm_external_share`). Hassas veriler için yerel LM Studio modeli önerilir.

### 4.4 Maliyet ve kota

- Katalogda **57 model ücretsiz uç nokta** sunar; ücretsiz katmanın istek/kota
  sınırları NVIDIA tarafından belirlenir ve değişebilir
- Uygulama her isteğin token sayısını ve tahmini maliyetini kaydeder
  (**Yapay Zekâ Merkezi → Kullanım**)
- Maliyet katsayıları **Ayarlar** ekranından girilir (varsayılan 0 — ücretsiz katman)
- **Ücret doğurabilecek kapsamlı testler kullanıcı onayı olmadan çalıştırılmaz;**
  "Sohbetli test" düğmesi öncesinde onay sorar

---

## 5. Bu incelemede yapılmayanlar

Güvenlik ve hesap bütünlüğü gereği aşağıdakiler **bilinçli olarak yapılmamıştır**:

- ❌ API anahtarı **oluşturulmadı** — kullanım koşulu onayı ve kota seçimi içerdiği için
  kullanıcı işlemi olarak bırakıldı
- ❌ Hesap ayarı değiştirilmedi, hiçbir forma veri girilmedi
- ❌ CAPTCHA veya çok faktörlü doğrulama aşılmaya çalışılmadı
- ❌ Ücret doğuran çıkarım isteği gönderilmedi

Yapılan: **yalnızca genel model kataloğunun ve model kartlarının okunması.**

---

## 6. Anahtar girildikten sonra doğrulama

```
Ayarlar → NVIDIA Build
  1. Ekle → anahtarı yapıştır → Şifreleyerek kaydet
  2. Model listesini yenile        (ücretsiz — yalnızca /models çağrısı)
  3. Varsayılan modeli seç
  4. Bağlantıyı test et            (ücretsiz)
  5. Sohbetli test                 (çok küçük istek — onay sorulur)
```

Test sonucunda gecikme, model adı ve örnek yanıt gösterilir; **anahtar hiçbir aşamada
görüntülenmez.** Sonuç ayrıca denetim günlüğüne (anahtar olmadan) yazılır.
