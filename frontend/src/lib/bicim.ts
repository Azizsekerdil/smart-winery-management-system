/**
 * Biçimlendirme yardımcıları (TR/EN).
 *
 * Tüm fonksiyonlar `unknown` kabul eder: API'den gelen gevşek tipli alanları
 * (Record<string, unknown>) sayfalarda tek tek dönüştürmek yerine burada güvenli
 * biçimde ele alırız. Geçersiz/boş değerler her zaman "—" döner.
 *
 * Etiket sözlükleri ve sayı/tarih yereli aktif dile göre seçilir. Buradaki
 * fonksiyonlar React kancası DEĞİLDİR; aktif dil doğrudan store'dan okunur
 * (lib/i18n.ts içindeki `ceviri()` ile aynı kalıp). Para birimi her dilde TRY kalır.
 */
import { useAyarlar } from './store'

type Dil = 'tr' | 'en'

const YOK = '—'

function aktifDil(): Dil {
  return useAyarlar.getState().dil === 'en' ? 'en' : 'tr'
}

/** Aktif dile karşılık gelen Intl yereli. */
function yerel(): string {
  return aktifDil() === 'en' ? 'en-US' : 'tr-TR'
}

// Intl biçimlendiricileri pahalıdır; dil + seçenek bazında önbelleğe alınır.
const SAYI_ONBELLEK = new Map<string, Intl.NumberFormat>()
const TARIH_ONBELLEK = new Map<string, Intl.DateTimeFormat>()

function sayiBicimi(basamak: number): Intl.NumberFormat {
  const kod = yerel()
  const anahtar = `${kod}:${basamak}`
  let bicimci = SAYI_ONBELLEK.get(anahtar)
  if (!bicimci) {
    bicimci = new Intl.NumberFormat(kod, { maximumFractionDigits: basamak })
    SAYI_ONBELLEK.set(anahtar, bicimci)
  }
  return bicimci
}

function paraBicimi(): Intl.NumberFormat {
  const kod = yerel()
  const anahtar = `${kod}:para`
  let bicimci = SAYI_ONBELLEK.get(anahtar)
  if (!bicimci) {
    bicimci = new Intl.NumberFormat(kod, {
      style: 'currency',
      currency: 'TRY',
      maximumFractionDigits: 2,
    })
    SAYI_ONBELLEK.set(anahtar, bicimci)
  }
  return bicimci
}

function tarihBicimi(saatli: boolean): Intl.DateTimeFormat {
  const kod = yerel()
  const anahtar = `${kod}:${saatli ? 'tarihsaat' : 'tarih'}`
  let bicimci = TARIH_ONBELLEK.get(anahtar)
  if (!bicimci) {
    const secenekler: Intl.DateTimeFormatOptions = saatli
      ? { dateStyle: 'medium', timeStyle: 'short' }
      : { dateStyle: 'medium' }
    bicimci = new Intl.DateTimeFormat(kod, secenekler)
    TARIH_ONBELLEK.set(anahtar, bicimci)
  }
  return bicimci
}

function sayiyaCevir(deger: unknown): number | null {
  if (deger === null || deger === undefined || deger === '') return null
  const n = typeof deger === 'number' ? deger : Number(deger)
  return Number.isFinite(n) ? n : null
}

function tariheCevir(deger: unknown): Date | null {
  if (!deger) return null
  const d = deger instanceof Date ? deger : new Date(String(deger))
  return Number.isNaN(d.getTime()) ? null : d
}

export function sayi(deger: unknown, basamak = 2): string {
  const n = sayiyaCevir(deger)
  return n === null ? YOK : sayiBicimi(basamak).format(n)
}

export function para(deger: unknown): string {
  const n = sayiyaCevir(deger)
  return n === null ? YOK : paraBicimi().format(n)
}

export function tarih(deger: unknown): string {
  const d = tariheCevir(deger)
  return d ? tarihBicimi(false).format(d) : YOK
}

export function tarihSaat(deger: unknown): string {
  const d = tariheCevir(deger)
  return d ? tarihBicimi(true).format(d) : YOK
}

/** Göreli zaman parçaları — çeviri anahtarları: `goreli.*` */
const GORELI: Record<Dil, { simdi: string; dk: string; sa: string; gun: string }> = {
  tr: { simdi: 'az önce', dk: 'dk önce', sa: 'sa önce', gun: 'gün önce' },
  en: { simdi: 'just now', dk: 'min ago', sa: 'h ago', gun: 'd ago' },
}

export function goreliZaman(deger: unknown): string {
  const d = tariheCevir(deger)
  if (!d) return YOK
  const s = GORELI[aktifDil()]
  const fark = (Date.now() - d.getTime()) / 1000
  if (fark < 60) return s.simdi
  if (fark < 3600) return `${Math.floor(fark / 60)} ${s.dk}`
  if (fark < 86400) return `${Math.floor(fark / 3600)} ${s.sa}`
  if (fark < 2592000) return `${Math.floor(fark / 86400)} ${s.gun}`
  return tarih(d)
}

/** Türkçede yüzde işareti sayının önünde, İngilizcede arkasında yazılır. */
export function yuzde(deger: unknown, basamak = 1): string {
  const n = sayiyaCevir(deger)
  if (n === null) return YOK
  const metinDeger = n.toFixed(basamak)
  return aktifDil() === 'en' ? `${metinDeger}%` : `%${metinDeger}`
}

/** snake_case veya kebab-case kodu okunabilir başlığa çevirir. */
export function baslikYap(deger: unknown): string {
  if (!deger) return YOK
  const kod = yerel()
  return String(deger)
    .replace(/[_-]/g, ' ')
    .replace(/\b\p{L}/gu, (c) => c.toLocaleUpperCase(kod))
}

// ------------------------------------------------------------- etiket haritaları
// Her sözlüğün TR ve EN sürümü tutulur; `etiket()` aktif dile göre seçer.
// TR sürümleri geriye dönük uyumluluk için dışa aktarılmaya devam eder.

export const ASAMA_ETIKET: Record<string, string> = {
  uzum_kabul: 'Üzüm kabul',
  sira: 'Şıra',
  fermantasyon: 'Fermantasyon',
  malolaktik: 'Malolaktik',
  dinlendirme: 'Dinlendirme',
  olgunlastirma: 'Olgunlaştırma',
  kupaj: 'Kupaj',
  stabilizasyon: 'Stabilizasyon',
  siseleme: 'Şişeleme',
  tamamlandi: 'Tamamlandı',
}

export const ASAMA_ETIKET_EN: Record<string, string> = {
  uzum_kabul: 'Grape intake',
  sira: 'Must',
  fermantasyon: 'Fermentation',
  malolaktik: 'Malolactic',
  dinlendirme: 'Aging',
  olgunlastirma: 'Maturation',
  kupaj: 'Blending',
  stabilizasyon: 'Stabilization',
  siseleme: 'Bottling',
  tamamlandi: 'Completed',
}

export const DURUM_ETIKET: Record<string, string> = {
  aktif: 'Aktif',
  beklemede: 'Beklemede',
  karantina: 'Karantina',
  kapandi: 'Kapandı',
  iptal: 'İptal',
  bos: 'Boş',
  dolu: 'Dolu',
  kismen_dolu: 'Kısmen dolu',
  temizlikte: 'Temizlikte',
  bakimda: 'Bakımda',
  devre_disi: 'Devre dışı',
  planlandi: 'Planlandı',
  hazirlik: 'Hazırlık',
  devam_ediyor: 'Devam ediyor',
  durakladi: 'Duraklandı',
  bekliyor: 'Bekliyor',
  onaylandi: 'Onaylandı',
  reddedildi: 'Reddedildi',
  taslak: 'Taslak',
  senaryo: 'Senaryo',
  onay_bekliyor: 'Onay bekliyor',
  uygulandi: 'Uygulandı',
  arsiv: 'Arşiv',
  sevk_edildi: 'Sevk edildi',
  teslim_edildi: 'Teslim edildi',
  hazirlaniyor: 'Hazırlanıyor',
  teslim_alindi: 'Teslim alındı',
  kismen_teslim: 'Kısmen teslim',
  siparis_verildi: 'Sipariş verildi',
  calisiyor: 'Çalışıyor',
  arizali: 'Arızalı',
  onarimda: 'Onarımda',
  emekli: 'Emekli',
  acik: 'Açık',
  okundu: 'Okundu',
  cozuldu: 'Çözüldü',
  yoksayildi: 'Yoksayıldı',
  // AI terminal görev durumları
  plan_hazir: 'Plan hazır',
  calisiyor_gorev: 'Çalışıyor',
  test_ediliyor: 'Test ediliyor',
  basarili: 'Başarılı',
  basarisiz: 'Başarısız',
  geri_alindi: 'Geri alındı',
  // Denetim eylemleri
  olustur: 'Oluştur',
  guncelle: 'Güncelle',
  sil: 'Sil',
  giris: 'Giriş',
  cikis: 'Çıkış',
  giris_basarisiz: 'Başarısız giriş',
  onay: 'Onay',
  red: 'Red',
  disa_aktar: 'Dışa aktar',
  ai_istek: 'AI isteği',
  ai_oneri: 'AI önerisi',
  terminal_komut: 'Terminal komutu',
  terminal_onay: 'Terminal onayı',
  terminal_red: 'Terminal reddi',
  terminal_geri_al: 'Terminal geri alma',
  ayar_degisikligi: 'Ayar değişikliği',
  izinsiz_erisim: 'İzinsiz erişim',
  // Stok hareketleri
  uretim_tuketim: 'Üretim tüketimi',
  uretim_giris: 'Üretim girişi',
  transfer: 'Transfer',
  sayim: 'Sayım',
  fire: 'Fire',
  iade: 'İade',
  // Bakım
  periyodik: 'Periyodik',
  ariza: 'Arıza',
  kalibrasyon: 'Kalibrasyon',
  cip: 'CIP',
  temizlik: 'Temizlik',
  // Fıçı / meşe
  fransiz: 'Fransız',
  amerikan: 'Amerikan',
  macar: 'Macar',
  kafkas: 'Kafkas',
  slavonya: 'Slavonya',
  hafif: 'Hafif',
  orta_plus: 'Orta+',
  agir: 'Ağır',
  paslanmaz_celik: 'Paslanmaz çelik',
  beton: 'Beton',
  ahsap: 'Ahşap',
  amfora: 'Amfora',
  fiberglas: 'Fiberglas',
  // Ekipman
  pompa: 'Pompa',
  pres: 'Pres',
  siseleme_hatti: 'Şişeleme hattı',
  sogutma: 'Soğutma',
  filtre: 'Filtre',
  sap_ayirici: 'Sap ayırıcı',
  tank: 'Tank',
  diger: 'Diğer',
  // Stok kategorileri
  hammadde: 'Hammadde',
  katki: 'Katkı',
  sarf: 'Sarf malzemesi',
  ambalaj: 'Ambalaj',
  bitmis_urun: 'Bitmiş ürün',
  yedek_parca: 'Yedek parça',
  // Fermantasyon
  alkol: 'Alkol',
  ikincil: 'İkincil',
  // Numune
  rutin: 'Rutin',
  kontrol: 'Kontrol',
}

export const DURUM_ETIKET_EN: Record<string, string> = {
  aktif: 'Active',
  beklemede: 'Pending',
  karantina: 'Quarantine',
  kapandi: 'Closed',
  iptal: 'Cancelled',
  bos: 'Empty',
  dolu: 'Full',
  kismen_dolu: 'Partially full',
  temizlikte: 'In cleaning',
  bakimda: 'Under maintenance',
  devre_disi: 'Disabled',
  planlandi: 'Planned',
  hazirlik: 'Preparation',
  devam_ediyor: 'In progress',
  durakladi: 'Paused',
  bekliyor: 'Waiting',
  onaylandi: 'Approved',
  reddedildi: 'Rejected',
  taslak: 'Draft',
  senaryo: 'Scenario',
  onay_bekliyor: 'Awaiting approval',
  uygulandi: 'Applied',
  arsiv: 'Archive',
  sevk_edildi: 'Shipped',
  teslim_edildi: 'Delivered',
  hazirlaniyor: 'Preparing',
  teslim_alindi: 'Received',
  kismen_teslim: 'Partially received',
  siparis_verildi: 'Ordered',
  calisiyor: 'Running',
  arizali: 'Faulty',
  onarimda: 'Under repair',
  emekli: 'Retired',
  acik: 'Open',
  okundu: 'Read',
  cozuldu: 'Resolved',
  yoksayildi: 'Ignored',
  // AI terminal görev durumları
  plan_hazir: 'Plan ready',
  calisiyor_gorev: 'Running',
  test_ediliyor: 'Testing',
  basarili: 'Succeeded',
  basarisiz: 'Failed',
  geri_alindi: 'Rolled back',
  // Denetim eylemleri
  olustur: 'Create',
  guncelle: 'Update',
  sil: 'Delete',
  giris: 'Sign in',
  cikis: 'Sign out',
  giris_basarisiz: 'Failed sign-in',
  onay: 'Approval',
  red: 'Rejection',
  disa_aktar: 'Export',
  ai_istek: 'AI request',
  ai_oneri: 'AI suggestion',
  terminal_komut: 'Terminal command',
  terminal_onay: 'Terminal approval',
  terminal_red: 'Terminal rejection',
  terminal_geri_al: 'Terminal rollback',
  ayar_degisikligi: 'Settings change',
  izinsiz_erisim: 'Unauthorized access',
  // Stok hareketleri
  uretim_tuketim: 'Production consumption',
  uretim_giris: 'Production intake',
  transfer: 'Transfer',
  sayim: 'Stock count',
  fire: 'Loss',
  iade: 'Return',
  // Bakım
  periyodik: 'Periodic',
  ariza: 'Breakdown',
  kalibrasyon: 'Calibration',
  cip: 'CIP',
  temizlik: 'Cleaning',
  // Fıçı / meşe
  fransiz: 'French',
  amerikan: 'American',
  macar: 'Hungarian',
  kafkas: 'Caucasian',
  slavonya: 'Slavonian',
  hafif: 'Light',
  orta_plus: 'Medium+',
  agir: 'Heavy',
  paslanmaz_celik: 'Stainless steel',
  beton: 'Concrete',
  ahsap: 'Wood',
  amfora: 'Amphora',
  fiberglas: 'Fiberglass',
  // Ekipman
  pompa: 'Pump',
  pres: 'Press',
  siseleme_hatti: 'Bottling line',
  sogutma: 'Cooling',
  filtre: 'Filter',
  sap_ayirici: 'Destemmer',
  tank: 'Tank',
  diger: 'Other',
  // Stok kategorileri
  hammadde: 'Raw material',
  katki: 'Additive',
  sarf: 'Consumable',
  ambalaj: 'Packaging',
  bitmis_urun: 'Finished goods',
  yedek_parca: 'Spare part',
  // Fermantasyon
  alkol: 'Alcoholic',
  ikincil: 'Secondary',
  // Numune
  rutin: 'Routine',
  kontrol: 'Control',
}

export const SARAP_TIPI: Record<string, string> = {
  kirmizi: 'Kırmızı',
  beyaz: 'Beyaz',
  rose: 'Roze',
  kopuklu: 'Köpüklü',
  tatli: 'Tatlı',
}

export const SARAP_TIPI_EN: Record<string, string> = {
  kirmizi: 'Red',
  beyaz: 'White',
  rose: 'Rosé',
  kopuklu: 'Sparkling',
  tatli: 'Sweet',
}

/** Renk sınıfları çevrilmez (teknik sabit). */
export const SEVIYE_RENK: Record<string, string> = {
  kritik: 'bg-red-500/15 text-red-600 dark:text-red-400',
  uyari: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
  bilgi: 'bg-sky-500/15 text-sky-700 dark:text-sky-400',
  dusuk: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400',
  orta: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
  yuksek: 'bg-orange-500/15 text-orange-700 dark:text-orange-400',
  engellendi: 'bg-red-500/15 text-red-600 dark:text-red-400',
}

/** Aktif dildeki aşama sözlüğü (açılır liste vb. için). */
export function asamaEtiketleri(): Record<string, string> {
  return aktifDil() === 'en' ? ASAMA_ETIKET_EN : ASAMA_ETIKET
}

/** Aktif dildeki durum sözlüğü. */
export function durumEtiketleri(): Record<string, string> {
  return aktifDil() === 'en' ? DURUM_ETIKET_EN : DURUM_ETIKET
}

/** Aktif dildeki şarap tipi sözlüğü. */
export function sarapTipleri(): Record<string, string> {
  return aktifDil() === 'en' ? SARAP_TIPI_EN : SARAP_TIPI
}

export function etiket(deger: unknown): string {
  if (deger === null || deger === undefined || deger === '') return YOK
  const anahtar = String(deger)
  return (
    durumEtiketleri()[anahtar] ??
    asamaEtiketleri()[anahtar] ??
    sarapTipleri()[anahtar] ??
    // Aktif dilde karşılığı yoksa Türkçe sözlüklere düş, o da yoksa başlığa çevir.
    DURUM_ETIKET[anahtar] ??
    ASAMA_ETIKET[anahtar] ??
    SARAP_TIPI[anahtar] ??
    baslikYap(anahtar)
  )
}

/** Bilinmeyen bir değeri güvenli metne çevirir (React çocuğu olarak kullanılabilir). */
export function metin(deger: unknown, varsayilan = YOK): string {
  if (deger === null || deger === undefined || deger === '') return varsayilan
  return String(deger)
}
