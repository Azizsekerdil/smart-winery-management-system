/**
 * Merkezi API istemcisi.
 *
 * - Erişim belirteci bellekte + localStorage'da tutulur.
 * - 401 alındığında yenileme belirteciyle TEK seferlik yenileme denenir;
 *   eş zamanlı istekler aynı yenileme sözünü paylaşır (yenileme fırtınası olmaz).
 * - Hata mesajları backend'den geldiği gibi (Türkçe) yüzeye taşınır.
 */
import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

const ERISIM_ANAHTARI = 'saraphane.erisim'
const YENILEME_ANAHTARI = 'saraphane.yenileme'

export const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 180_000,
  headers: { 'Content-Type': 'application/json' },
})

export function erisimBelirteci(): string | null {
  return localStorage.getItem(ERISIM_ANAHTARI)
}

export function yenilemeBelirteci(): string | null {
  return localStorage.getItem(YENILEME_ANAHTARI)
}

export function belirtecleriKaydet(erisim: string, yenileme?: string) {
  localStorage.setItem(ERISIM_ANAHTARI, erisim)
  if (yenileme) localStorage.setItem(YENILEME_ANAHTARI, yenileme)
}

export function belirtecleriSil() {
  localStorage.removeItem(ERISIM_ANAHTARI)
  localStorage.removeItem(YENILEME_ANAHTARI)
}

/**
 * İstek başlığında gönderilen dil.
 *
 * Sunucudan gelen etiketler (rol adları, yetki açıklamaları) bu başlığa göre
 * seçilir; aksi hâlde İngilizce arayüzde Türkçe etiketler görünür.
 *
 * Değeri `store.ts` günceller. Buradan store'u içe aktarmak DAİRESEL bağımlılık
 * yaratırdı (store zaten bu modülü içe aktarıyor); bu yüzden akış tek yönlüdür.
 */
let aktifDil = 'tr'

export function istekDiliniAyarla(dil: string) {
  aktifDil = dil === 'en' ? 'en' : 'tr'
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = erisimBelirteci()
  if (token) config.headers.Authorization = `Bearer ${token}`
  config.headers['Accept-Language'] = aktifDil
  return config
})

let yenilemeSozu: Promise<string | null> | null = null

async function belirtecYenile(): Promise<string | null> {
  const refresh = yenilemeBelirteci()
  if (!refresh) return null
  try {
    const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: refresh })
    belirtecleriKaydet(data.access_token)
    return data.access_token as string
  } catch {
    belirtecleriSil()
    return null
  }
}

api.interceptors.response.use(
  (yanit) => yanit,
  async (hata: AxiosError) => {
    const istek = hata.config as InternalAxiosRequestConfig & { _yenilendi?: boolean }
    const durum = hata.response?.status

    if (durum === 401 && istek && !istek._yenilendi && !istek.url?.includes('/auth/')) {
      istek._yenilendi = true
      yenilemeSozu = yenilemeSozu ?? belirtecYenile()
      const yeni = await yenilemeSozu
      yenilemeSozu = null
      if (yeni) {
        istek.headers.Authorization = `Bearer ${yeni}`
        return api.request(istek)
      }
      belirtecleriSil()
      if (!location.pathname.startsWith('/giris')) {
        location.href = '/giris'
      }
    }
    return Promise.reject(hata)
  },
)

/** Backend hata gövdesinden okunabilir Türkçe mesaj çıkarır. */
export function hataMesaji(hata: unknown, varsayilan = 'Beklenmeyen bir hata oluştu.'): string {
  if (axios.isAxiosError(hata)) {
    const veri = hata.response?.data as
      | { detail?: string; hatalar?: { alan: string; hata: string }[] }
      | undefined
    if (veri?.hatalar?.length) {
      return veri.hatalar.map((h) => `${h.alan}: ${h.hata}`).join(' · ')
    }
    if (typeof veri?.detail === 'string') return veri.detail
    if (hata.code === 'ECONNABORTED') return 'İstek zaman aşımına uğradı.'
    if (!hata.response) return 'Sunucuya ulaşılamadı. Backend çalışıyor mu?'
    return `${hata.response.status} — ${hata.response.statusText}`
  }
  if (hata instanceof Error) return hata.message
  return varsayilan
}

/** Dosya indirir (rapor dışa aktarma, yedek indirme). */
export async function dosyaIndir(
  yol: string,
  parametreler: Record<string, unknown> = {},
) {
  const yanit = await api.get(yol, { params: parametreler, responseType: 'blob' })
  const disposition = String(yanit.headers['content-disposition'] ?? '')
  const eslesme = /filename="?([^"]+)"?/.exec(disposition)
  const adres = URL.createObjectURL(yanit.data as Blob)
  const bag = document.createElement('a')
  bag.href = adres
  bag.download = eslesme?.[1] ?? 'rapor'
  document.body.appendChild(bag)
  bag.click()
  bag.remove()
  URL.revokeObjectURL(adres)
}

/** Sayfalanmış liste yanıtı. */
export interface Sayfa<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
