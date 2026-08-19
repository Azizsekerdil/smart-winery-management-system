/** Oturum, tema ve dil durumunu tutan hafif küresel depo (zustand). */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  api,
  istekDiliniAyarla,
  belirtecleriKaydet,
  belirtecleriSil,
  erisimBelirteci,
  yenilemeBelirteci,
} from './api'

export interface Kullanici {
  id: number
  username: string
  email: string
  full_name: string
  roles: string[]
  role_labels?: string[]
  permissions?: string[]
  department?: string | null
  locale: string
  theme: string
  is_active: boolean
  must_change_password?: boolean
}

interface OturumDurumu {
  kullanici: Kullanici | null
  yukleniyor: boolean
  girisYap: (kullaniciAdi: string, parola: string) => Promise<void>
  cikisYap: () => Promise<void>
  beniYukle: () => Promise<void>
  yetkiVar: (yetki: string) => boolean
  herhangiYetki: (...yetkiler: string[]) => boolean
}

export const useOturum = create<OturumDurumu>((set, get) => ({
  kullanici: null,
  yukleniyor: true,

  girisYap: async (kullaniciAdi, parola) => {
    const { data } = await api.post('/auth/login', {
      username: kullaniciAdi,
      password: parola,
    })
    belirtecleriKaydet(data.access_token, data.refresh_token)
    await get().beniYukle()
  },

  cikisYap: async () => {
    const yenileme = yenilemeBelirteci()
    try {
      if (yenileme) await api.post('/auth/logout', { refresh_token: yenileme })
    } catch {
      // Sunucuya ulaşılamasa da yerel oturum kapatılır.
    }
    belirtecleriSil()
    set({ kullanici: null })
  },

  beniYukle: async () => {
    // Belirteç yoksa istek göndermenin anlamı yok: sunucu zaten 401 döner.
    // Gereksiz çağrı giriş sayfasını yavaşlatır ve konsolu hata ile kirletir.
    if (!erisimBelirteci()) {
      set({ kullanici: null, yukleniyor: false })
      return
    }
    set({ yukleniyor: true })
    try {
      const { data } = await api.get('/auth/me')
      set({ kullanici: data, yukleniyor: false })
    } catch {
      set({ kullanici: null, yukleniyor: false })
    }
  },

  yetkiVar: (yetki) => get().kullanici?.permissions?.includes(yetki) ?? false,

  herhangiYetki: (...yetkiler) => {
    const sahip = get().kullanici?.permissions ?? []
    return yetkiler.some((y) => sahip.includes(y))
  },
}))

// --------------------------------------------------------------------- tema
type Tema = 'dark' | 'light' | 'system'

interface AyarDurumu {
  tema: Tema
  dil: 'tr' | 'en'
  kenarCubuguAcik: boolean
  temaAyarla: (t: Tema) => void
  dilAyarla: (d: 'tr' | 'en') => void
  kenarCubuguDegistir: () => void
}

function temaUygula(tema: Tema) {
  const koyu =
    tema === 'dark' ||
    (tema === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', koyu)
}

export const useAyarlar = create<AyarDurumu>()(
  persist(
    (set) => ({
      tema: 'dark',
      dil: 'tr',
      kenarCubuguAcik: true,
      temaAyarla: (t) => {
        temaUygula(t)
        set({ tema: t })
      },
      dilAyarla: (d) => {
        set({ dil: d })
        istekDiliniAyarla(d)
      },
      kenarCubuguDegistir: () => set((s) => ({ kenarCubuguAcik: !s.kenarCubuguAcik })),
    }),
    {
      name: 'saraphane.ayarlar',
      onRehydrateStorage: () => (durum) => {
        temaUygula(durum?.tema ?? 'dark')
        // Kaydedilmis dil, ilk istekten ONCE uygulanmali; aksi halde sayfa
        // yenilendiginde ilk `/auth/me` yaniti yanlis dilde etiket dondurur.
        istekDiliniAyarla(durum?.dil ?? 'tr')
      },
    },
  ),
)

// İlk yüklemede tema ve dil uygula (persist geri yüklenmeden önce)
temaUygula((useAyarlar.getState().tema ?? 'dark') as Tema)
istekDiliniAyarla(useAyarlar.getState().dil ?? 'tr')

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  if (useAyarlar.getState().tema === 'system') temaUygula('system')
})
