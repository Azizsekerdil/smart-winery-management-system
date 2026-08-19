/** Liste/kayıt işlemleri için ortak React Query kancaları. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { type Sayfa, api } from './api'

/** Sayfalanmış liste + arama durumu. */
export function useListe<T>(
  yol: string,
  ekParametreler: Record<string, unknown> = {},
  secenekler: { sayfaBoyu?: number; etkin?: boolean } = {},
) {
  const { sayfaBoyu = 50, etkin = true } = secenekler
  const [sayfa, setSayfa] = useState(1)
  const [arama, setArama] = useState('')

  const sorgu = useQuery({
    queryKey: [yol, sayfa, arama, ekParametreler],
    queryFn: async () => {
      const { data } = await api.get<Sayfa<T>>(yol, {
        params: { page: sayfa, page_size: sayfaBoyu, q: arama || undefined, ...ekParametreler },
      })
      return data
    },
    enabled: etkin,
    placeholderData: (onceki) => onceki,
  })

  return {
    ...sorgu,
    satirlar: sorgu.data?.items ?? [],
    toplam: sorgu.data?.total ?? 0,
    sayfa,
    setSayfa,
    sayfaBoyu,
    arama,
    setArama: (q: string) => {
      setArama(q)
      setSayfa(1)
    },
  }
}

/** Sayfalanmamış basit liste. */
export function useBasitListe<T>(
  yol: string,
  parametreler: Record<string, unknown> = {},
  etkin = true,
) {
  return useQuery({
    queryKey: [yol, parametreler],
    queryFn: async () => (await api.get<T[]>(yol, { params: parametreler })).data,
    enabled: etkin,
  })
}

/** Seçim kutuları için `{id, ad}` listesi. */
export function useSecenekler(yol: string, etiketAlani = 'name', etkin = true) {
  return useQuery({
    queryKey: ['secenek', yol],
    queryFn: async () => {
      const { data } = await api.get<Sayfa<Record<string, unknown>>>(yol, {
        params: { page_size: 500 },
      })
      return data.items.map((x) => ({
        id: Number(x.id),
        ad: String(x[etiketAlani] ?? x.code ?? x.id),
        kod: String(x.code ?? ''),
        ham: x,
      }))
    },
    enabled: etkin,
    staleTime: 120_000,
  })
}

/** POST/PATCH sonrası ilgili sorguları tazeleyen mutasyon. */
export function useKaydet<TGirdi, TCikti = unknown>(
  yol: string,
  yontem: 'post' | 'patch' | 'put' = 'post',
  gecersizKil: string[] = [],
) {
  const istemci = useQueryClient()
  return useMutation<TCikti, unknown, TGirdi>({
    mutationFn: async (govde) => (await api[yontem]<TCikti>(yol, govde)).data,
    onSuccess: () => {
      for (const anahtar of [yol, ...gecersizKil]) {
        void istemci.invalidateQueries({ queryKey: [anahtar] })
      }
      void istemci.invalidateQueries({ queryKey: ['pano'] })
    },
  })
}
