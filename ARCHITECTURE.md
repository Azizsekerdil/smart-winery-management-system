# Mimari

Bu belge sistemin yapısını, önemli tasarım kararlarını ve **neden öyle yapıldığını**
açıklar.

---

## 1. Genel görünüm

```
┌──────────────────────────────────────────────────────────────────────┐
│  Tarayıcı — React 19 + TypeScript + Vite + Tailwind v4 + ECharts     │
│  Rol tabanlı menü · koyu/açık tema · Türkçe (İngilizce altyapısı hazır)│
└───────────────────────────────┬──────────────────────────────────────┘
                                │ /api/v1  (Vite proxy → aynı köken)
┌───────────────────────────────▼──────────────────────────────────────┐
│  FastAPI                                                             │
│  ┌────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────┐ │
│  │ Hız sınırı │→│ Kimlik (JWT) │→│ Yetki (RBAC) │→│ Uç nokta      │ │
│  └────────────┘ └──────────────┘ └──────────────┘ └───────┬───────┘ │
│                                                            │         │
│  ┌─────────────────────────────────────────────────────────▼───────┐ │
│  │  Servis katmanı                                                 │ │
│  │  izlenebilirlik · stok (FIFO/FEFO) · maliyet · uyarı · dışa akt.│ │
│  │  ai_features (SAYISAL, LLM'siz)                                 │ │
│  └───────────────┬─────────────────────────────┬───────────────────┘ │
│                  │                             │                     │
│  ┌───────────────▼──────────┐   ┌──────────────▼──────────────────┐  │
│  │ SQLAlchemy 2 (async)     │   │ AIProvider soyutlaması          │  │
│  │ 49 tablo · Alembic       │   │ LM Studio · Claude · NVIDIA · … │  │
│  └───────────────┬──────────┘   └──────────────┬──────────────────┘  │
│                  │                             │                     │
│  ┌───────────────▼──────────┐   ┌──────────────▼──────────────────┐  │
│  │ SQLite (gel.) / PostgreSQL│  │ AI Terminali (sandbox + git)    │  │
│  └──────────────────────────┘   └─────────────────────────────────┘  │
│                                                                      │
│  Denetim günlüğü — tüm katmanları keser, değiştirilemez              │
└──────────────────────────────────────────────────────────────────────┘
```

**Ölçek:** 49 tablo · 165 uç nokta yolu / 240 işlem · 536 pytest testi · 50 Playwright testi.

> Bu sayılar kaynak ağacından **ölçülerek** yazılmıştır, elle bakılmıyor. Doğrulamak için: tablo sayısı `len(app.models.Base.metadata.tables)`, uç nokta sayısı `/openapi.json`, test sayısı `pytest --collect-only -q`.

---

## 2. Katmanlar

| Katman | Dizin | Sorumluluk |
|---|---|---|
| **Çekirdek** | `app/core/` | Yapılandırma, güvenlik (Argon2/JWT), şifreleme, yetkilendirme, günlükleme+maskeleme, hız sınırı, denetim, bağımlılıklar |
| **Veri** | `app/models/`, `app/db/` | SQLAlchemy 2 deklaratif modeller, oturum yönetimi, demo verisi |
| **Şema** | `app/schemas/` | Pydantic v2 giriş/çıkış sözleşmeleri, iş kuralı doğrulaması |
| **API** | `app/api/` | HTTP uç noktaları, genel CRUD fabrikası |
| **Servis** | `app/services/` | Alan mantığı — HTTP'den bağımsız, doğrudan test edilebilir |
| **Yapay zekâ** | `app/services/ai/` | Sağlayıcı soyutlaması, yönlendirme, bağlam, RAG, öngörüler |
| **Ajan** | `app/agent/` | Terminal güvenlik çekirdeği: sandbox, çalıştırıcı, git işlemleri |

Bağımlılık yönü tek yönlüdür: **API → Servis → Veri**. Servisler HTTP bilmez; bu sayede
iş mantığı doğrudan birim testiyle sınanabilir.

---

## 3. Önemli tasarım kararları

### 3.1 Genel CRUD fabrikası

12 modülde tekrarlanan liste/getir/oluştur/güncelle/sil uç noktaları
`app/api/crud.py:build_crud_router()` tarafından üretilir. Fabrika arama, sayfalama,
dinamik filtre, kod üretimi, **denetim günlüğü** ve yetki kontrolünü tek yerde çözer.
Modüle özgü iş mantığı (transfer, onay, izlenebilirlik) kendi yönlendiricisinde kalır.

> **Not:** Bu modülde bilinçli olarak `from __future__ import annotations`
> **kullanılmaz**. Fabrika, iç içe tanımlanan uç noktalarda yerel değişkenleri
> (`create_schema`, `ReadDep` …) tip açıklaması olarak kullanır; ertelenmiş (string)
> açıklamalar bu yerel adları çözemez ve FastAPI şema üretimi başarısız olur.

### 3.2 İzlenebilirlik yönlü çizge olarak

İki tablo izlenebilirliğin tamamını taşır:

- `lot_sources` — üzüm kabulü → parti
- `lot_links` — parti → parti (kupaj, bölme, şişeleme)

`services/traceability.py` bu çizgede genişlik öncelikli arama yapar; döngülere karşı
ziyaret kümesi tutar, derinliği 12 ile sınırlar ve sınıra ulaşıldığında kullanıcıya
uyarı döndürür (sessizce kesmez). Tank ve fıçı düğümleri transfer/hareket
kayıtlarından türetilir.

Bu yapı sayesinde **her partiden geriye tüm üzüm kaynaklarına, ileriye tüm şişeleme
emirlerine** ulaşılabilir — kupaj ve bölme zincirleri dahil.

### 3.3 Yapay zekânın sayısal çekirdeği dil modelinden ayrıdır

`services/ai_features.py` hiçbir dil modeli kullanmaz. Fermantasyon bitiş tahmini
(en küçük kareler regresyonu), anomali tespiti (6 kural), kalite puanı (ağırlıklı
ideal aralık), risk değerlendirmesi, kupaj öngörüsü (pH için H⁺ derişimi üzerinden),
stok tükenme ve bakım tahmini burada **deterministik** olarak hesaplanır.

Gerekçe:

1. Sağlayıcı kapalıyken de özellikler **çalışır**
2. Sonuçlar **tekrarlanabilir** ve birim testiyle sınanabilir
3. Hassas veri zorunlu olmadıkça **dışarı çıkmaz**
4. Kullanıcı "neden bu sonuç" sorusuna sayısal gerekçe görür

Dil modeli yorumu `services/ai/insights.py` katmanında **isteğe bağlı** olarak
eklenir; alınamazsa sayısal sonuç yine döner.

### 3.4 AIProvider soyutlaması

```
AIProvider (soyut)
├── OpenAICompatProvider      # OpenAI uyumlu HTTP
│   ├── LMStudioProvider      # anahtar yok, is_external=False
│   └── NvidiaProvider        # nvapi- anahtarı
└── AnthropicProvider         # Messages API (system ayrı alan)
```

Uygulama kodu **hiçbir yerde** somut sağlayıcıya bağlı değildir. `registry.py`
veritabanındaki yapılandırmadan nesneyi kurar, göreve göre yönlendirir ve bir
sağlayıcı kullanılamazsa **öncelik sırasına göre güvenli geri dönüş** yapar.

Gerçek modellerle test edilirken ortaya çıkan ve koda yansıyan iki uyumluluk kuralı:

| Sorun | Çözüm |
|---|---|
| Akıl yürütme modelleri (ör. Gemma 4) token bütçesini düşünmeye harcayıp **boş içerik** döndürüyor | `reasoning_tokens` okunur; içerik boş + bütçe bittiyse sessiz boş yanıt yerine "sınırı artırın" diyen açık hata verilir |
| Bazı yerel modellerin sohbet şablonu `system` rolünü kabul etmiyor (HTTP 400) | Sistem yönergesi ilk kullanıcı mesajına katlanarak istek **bir kez** yeniden gönderilir |
| Zaman aşımında yeniden deneme toplam bekleme süresini katlıyor | Zaman aşımında **yeniden denenmez**; yalnızca ağ/sunucu hatalarında denenir |

Ayrıntılı ölçümler: [`docs/AI_MODEL_EVALUATION.md`](docs/AI_MODEL_EVALUATION.md)

### 3.5 Denetim günlüğü asla IO tetiklemez

`Base.to_dict()` yalnızca **yüklenmiş** sütunları okur (`inspect(obj).unloaded`).

Gerekçe: `updated_at` sütunu `onupdate=func.now()` taşır ve bir UPDATE flush'ından
sonra SQLAlchemy tarafından "expired" işaretlenir. Asenkron bağlamda bu alana erişmek
senkron bir SELECT başlatır ve `MissingGreenlet` hatası verir. Denetim günlüğü iş
akışını **kesmemelidir**; bu yüzden yüklenmemiş alanlar atlanır ve
`_yuklenmemis_alanlar` anahtarıyla belirtilir.

Ayrıca `Numeric` sütunlar `Decimal` döndürdüğü için JSON'a yazılmadan önce `float`'a
çevrilir.

### 3.6 Kod üretimi ve eşzamanlılık

`services/codes.py:next_code()` insan tarafından okunabilir kodlar üretir
(`PRT-2026-0007`). Veritabanındaki kayıtların **yanı sıra oturumda bekleyen**
(henüz flush edilmemiş) nesneler de dikkate alınır.

Gerekçe: FIFO stok çıkışında tek işlemde birden fazla hareket üretilir; yalnızca
veritabanına bakan bir sayaç bunlara aynı kodu verir ve benzersizlik kısıtı ihlal
edilir. Son savunma hattı yine veritabanı kısıtıdır.

### 3.7 Stok motoru (FIFO/FEFO)

Miktarlar `stock_batches` yığınları üzerinden yönetilir. Çıkışta yığınlar kalemin
değerleme yöntemine göre sıralanır:

- **FIFO** — giriş tarihine göre
- **FEFO** — son kullanma tarihine göre (tarihsizler en sona)

Her tüketilen yığın için ayrı bir `stock_movements` kaydı üretilir; böylece maliyet
katmanı hangi partiden ne kadar çıktığını bilir.

### 3.8 Dairesel yabancı anahtar kırılımı

`inventory_items.bottling_order_id` alanında **bilinçli olarak FK yoktur**.
`bottling_orders` tablosu ambalaj kalemleri için `inventory_items`'a beş ayrı FK ile
bağlıdır; çift yönlü FK dairesel bağımlılık oluşturur ve SQLite `ALTER` ile kısıt
ekleyemediği için tablolar oluşturulamaz/silinemez hâle gelir. Bütünlük uygulama
katmanında korunur.

### 3.9 Neden `asyncpg`, `psycopg` değil

`psycopg2`/`psycopg3` **LGPL** lisanslıdır. Proje ileride kapalı kaynak ticari ürüne
dönüşebileceğinden Apache-2.0 lisanslı `asyncpg` seçildi. Bu karar
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) içinde belgelenmiştir.

---

## 4. Veri modeli (49 tablo)

| Alan | Tablolar |
|---|---|
| Kullanıcı | `users`, `user_sessions` |
| Bağ | `vineyards`, `parcels`, `grape_varieties`, `suppliers`, `harvest_intakes`, `attachments` |
| Üretim | `lots`, `lot_sources`, `lot_links`, `lot_events`, `tanks`, `tank_transfers`, `fermentations`, `fermentation_readings`, `fermentation_additives` |
| Kalite | `lab_samples`, `lab_results`, `lab_specs`, `recipes`, `recipe_items`, `blend_operations`, `blend_components` |
| Mahzen | `barrels`, `barrel_movements`, `tasting_notes`, `bottling_orders` |
| Stok | `warehouses`, `inventory_items`, `stock_batches`, `stock_movements`, `purchase_orders`, `purchase_order_lines`, `customers`, `shipments`, `shipment_lines` |
| Operasyon | `equipment`, `maintenance_logs`, `alerts`, `audit_logs` |
| Yapay zekâ | `ai_provider_configs`, `ai_conversations`, `ai_messages`, `ai_usage_logs`, `agent_tasks`, `agent_runs`, `document_chunks` |

Ortak karışımlar: `TimestampMixin` (oluşturma/güncelleme), `AuthorMixin` (oluşturan/
değiştiren kullanıcı). Kısıt adlandırması `NAMING_CONVENTION` ile standarttır — Alembik
otomatik üretimi tutarlı çalışır.

---

## 5. Frontend

- **React 19 + TypeScript (strict)** — 18 sayfa, ortak bileşen kümesi
- **TanStack Query** sunucu durumu; **zustand** oturum/tema/dil
- **Tailwind v4** CSS değişkenleriyle tema (bordo, koyu üzüm, krem, bakır)
- **ECharts** fermantasyon eğrisi, izlenebilirlik çizgesi, maliyet dağılımı
- Menü **kullanıcının yetkilerine göre** süzülür; yetkisiz rota açıklayıcı mesaj gösterir
- `lib/bicim.ts` tüm biçimlendirmeyi `unknown` kabul ederek merkezîleştirir
- Geliştirmede Vite proxy'si API'yi **aynı kökenden** sunar; CORS/çerez sorunu olmaz

---

## 6. Ölçeklenebilirlik notları

Mevcut tasarım **tek makine / tek işçi** için optimize edilmiştir. Yatay ölçeklemede:

| Bileşen | Bugün | Ölçeklerken |
|---|---|---|
| Hız sınırlama | Süreç içi kayan pencere | Redis tabanlı ortak sayaç |
| RAG vektörleri | JSON sütunu, uygulama içi kosinüs | `pgvector` + ANN indeksi |
| Oturum | Veritabanı tablosu | Değişiklik gerekmez |
| Dosya yükleme | Yerel disk | Nesne depolama (S3 uyumlu) |
| Arka plan işleri | Yok (istek içi) | Görev kuyruğu |
| Veritabanı | SQLite | PostgreSQL (`DATABASE_URL` değiştirmek yeterli) |

---

## 7. Test stratejisi

| Katman | Yaklaşım |
|---|---|
| Saf mantık | `ai_features`, `sandbox`, `codes`, `exports` doğrudan birim testi |
| API | Gerçek uygulama + gerçek veritabanı (test başına temiz şema), `httpx.ASGITransport` |
| Yapay zekâ | Bulut sağlayıcılar **sahte HTTP taşıyıcısı** ile (ücret doğmaz); LM Studio testi `canli_ai` işaretli ve sunucu kapalıysa atlanır |
| Güvenlik | Sandbox sınırları, maskeleme, yetki matrisi ayrı dosyalarda |

Test veritabanı şeması **her testte** sıfırlanır; testler birbirinden bağımsızdır.
