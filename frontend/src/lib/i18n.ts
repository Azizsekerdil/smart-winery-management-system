/**
 * Hafif çeviri katmanı.
 *
 * Varsayılan dil Türkçe'dir. Sözlükler `ceviriler/tr.ts` ve `ceviriler/en.ts`
 * içinde ayrı tutulur; yeni bir dil eklemek için üçüncü bir sözlük dosyası
 * yazıp `SOZLUKLER` haritasına eklemek yeterlidir.
 *
 * Harici i18n kütüphanesi bilinçli olarak eklenmedi: bir bağımlılık daha az,
 * lisans yüzeyi daha küçük ve ihtiyaç bu ölçekte fazlasıyla karşılanıyor.
 *
 * Eksik anahtar davranışı: aktif dilde yoksa Türkçe karşılığı, o da yoksa
 * anahtarın kendisi döner. Böylece eksik çeviri ekranı boşaltmaz, gözle
 * fark edilir hale gelir.
 */
import { EN } from './ceviriler/en'
import { TR } from './ceviriler/tr'
import { useAyarlar } from './store'

type Sozluk = Record<string, string>

const SOZLUKLER: Record<string, Sozluk> = { tr: TR, en: EN }

/** Desteklenen diller — dil seçici bu listeden üretilir. */
export const DILLER = [
  { kod: 'tr', ad: 'Türkçe' },
  { kod: 'en', ad: 'English' },
] as const

export type DilKodu = (typeof DILLER)[number]['kod']

/**
 * Aktif dilin `Intl` yereli. Tarih ve sayı biçimlendirmesi buna göre yapılır;
 * para birimi TRY olarak kalır (işletmenin muhasebe birimi dilden bağımsızdır).
 */
export function yerel(dil?: string): string {
  return (dil ?? useAyarlar.getState().dil) === 'en' ? 'en-US' : 'tr-TR'
}

export function ceviri(anahtar: string, dil?: string): string {
  const aktif = dil ?? useAyarlar.getState().dil
  return SOZLUKLER[aktif]?.[anahtar] ?? TR[anahtar] ?? anahtar
}

/** Bileşenlerde kullanım: `const t = useCeviri()` */
export function useCeviri() {
  const dil = useAyarlar((s) => s.dil)
  return (anahtar: string) => ceviri(anahtar, dil)
}

/** Sözlükleri doğrulama/test amacıyla dışa açar. */
export const SOZLUK_KAYNAKLARI = SOZLUKLER
