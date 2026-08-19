/**
 * Eğitim modülü içerik tipleri.
 *
 * İçerik uygulamayla birlikte gelir (`egitim-icerik.ts`): iki dilli, sürüm
 * kontrollü ve çevrimdışı çalışır. Sunucuda yalnızca **kimin neyi
 * tamamladığı** saklanır — içerik için ağ isteği yapılmaz.
 */

/** Dile göre alan seçimi: `metin(adim, 'baslik', dil)`. */
export type CiftDil = { tr: string; en: string }

export interface EgitimAdimi {
  baslik: CiftDil
  metin: CiftDil
  /** İlgili uygulama yolu — kullanıcı doğrudan ekrana gidebilir. */
  ekran?: string
  ipucu?: CiftDil
}

export interface EgitimSorusu {
  soru: CiftDil
  secenekler: { tr: string[]; en: string[] }
  /** 0 tabanlı doğru seçenek indeksi. */
  dogru: number
  aciklama?: CiftDil
}

export interface EgitimModulu {
  kod: string
  baslik: CiftDil
  ozet: CiftDil
  /** İlgili roller; boşsa herkese hitap eder. */
  roller: string[]
  sureDk: number
  adimlar: EgitimAdimi[]
  sorular: EgitimSorusu[]
}

/** Aktif dile göre metin seçer; İngilizce boşsa Türkçeye düşer. */
export function ikiDil(alan: CiftDil | undefined, dil: string): string {
  if (!alan) return ''
  return dil === 'en' ? alan.en || alan.tr : alan.tr
}

export function ikiDilListe(
  alan: { tr: string[]; en: string[] } | undefined,
  dil: string,
): string[] {
  if (!alan) return []
  return dil === 'en' && alan.en.length ? alan.en : alan.tr
}

/** Geçme eşiği — backend ile aynı olmalıdır (`models/egitim.py`). */
export const GECME_ESIGI = 70
