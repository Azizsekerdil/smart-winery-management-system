import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { CheckCircle2, KeyRound, Loader2, RefreshCw, ShieldCheck, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Alan, BilgiKutusu, HataKutusu, Kart, Kip, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { api, hataMesaji } from '@/lib/api'
import { tarihSaat } from '@/lib/bicim'
import { useCeviri } from '@/lib/i18n'
import { useAyarlar, useOturum } from '@/lib/store'

interface Saglayici {
  id: number
  provider_key: string
  display_name: string
  kind: string
  enabled: boolean
  base_url: string
  default_model: string
  timeout_seconds: number
  max_retries: number
  privacy_level: string
  input_cost_per_1k: number
  output_cost_per_1k: number
  currency: string
  task_model_map: Record<string, string>
  cached_models: { id: string; label?: string; context_length?: number | null }[]
  models_fetched_at: string | null
  last_status: string
  last_checked_at: string | null
  last_error: string | null
  last_latency_ms: number | null
  has_api_key: boolean
  api_key_masked: string
  api_key_fingerprint: string
  requires_api_key: boolean
  notes: string | null
}

export default function Ayarlar() {
  const t = useCeviri()
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const { tema, temaAyarla, dil, dilAyarla } = useAyarlar()
  const [hata, setHata] = useState('')
  const [basari, setBasari] = useState('')
  const [anahtarKip, setAnahtarKip] = useState<Saglayici | null>(null)
  const [anahtar, setAnahtar] = useState('')
  const [testEdilen, setTestEdilen] = useState('')

  const saglayicilar = useQuery({
    queryKey: ['/ai/providers'],
    queryFn: async () => (await api.get<Saglayici[]>('/ai/providers')).data,
  })

  const guncelle = useMutation({
    mutationFn: async ({ kod, govde }: { kod: string; govde: Record<string, unknown> }) =>
      (await api.patch(`/ai/providers/${kod}`, govde)).data,
    onSuccess: () => {
      setBasari(t('ayarlar.mesaj.kaydedildi'))
      void istemci.invalidateQueries({ queryKey: ['/ai/providers'] })
    },
    onError: (err) => setHata(hataMesaji(err)),
  })

  const anahtarKaydet = useMutation({
    mutationFn: async ({ kod, deger }: { kod: string; deger: string }) =>
      (await api.put(`/ai/providers/${kod}/api-key`, { api_key: deger })).data,
    onSuccess: (veri) => {
      setBasari(veri.detail)
      setAnahtarKip(null)
      setAnahtar('')
      void istemci.invalidateQueries({ queryKey: ['/ai/providers'] })
    },
    onError: (err) => setHata(hataMesaji(err)),
  })

  const anahtarSil = useMutation({
    mutationFn: async (kod: string) => (await api.delete(`/ai/providers/${kod}/api-key`)).data,
    onSuccess: () => {
      setBasari(t('ayarlar.mesaj.anahtarsilindi'))
      void istemci.invalidateQueries({ queryKey: ['/ai/providers'] })
    },
    onError: (err) => setHata(hataMesaji(err)),
  })

  const modelleriCek = useMutation({
    mutationFn: async (kod: string) =>
      (await api.get(`/ai/providers/${kod}/models`, { params: { refresh: true } })).data,
    onSuccess: (veri) => {
      setBasari(
        veri.warning
          ? `${t('ayarlar.mesaj.modelhata')}: ${veri.warning}`
          : `${veri.models.length} ${t('ayarlar.mesaj.modelbulundu')}`,
      )
      void istemci.invalidateQueries({ queryKey: ['/ai/providers'] })
    },
    onError: (err) => setHata(hataMesaji(err)),
  })

  async function baglantiTest(kod: string, sohbetli: boolean) {
    setHata('')
    setBasari('')
    setTestEdilen(kod)
    try {
      const { data } = await api.post(`/ai/providers/${kod}/test`, null, {
        params: { with_chat: sohbetli },
      })
      if (data.ok) {
        setBasari(
          `${data.message}${data.latency_ms ? ` (${data.latency_ms} ms)` : ''}${
            data.sample_response ? ` — ${t('ayarlar.mesaj.yanit')}: "${data.sample_response}"` : ''
          }`,
        )
      } else {
        setHata(data.message)
      }
      void istemci.invalidateQueries({ queryKey: ['/ai/providers'] })
    } catch (err) {
      setHata(hataMesaji(err))
    } finally {
      setTestEdilen('')
    }
  }

  return (
    <div className="space-y-5">
      <SayfaBasligi baslik={t('ayarlar.baslik')} aciklama={t('ayarlar.aciklama')} />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}
      {basari && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-300">
          {basari}
        </div>
      )}

      <Kart baslik={t('ayarlar.kart.arayuz')}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Alan etiket={t('ayarlar.alan.tema')}>
            <select className="girdi" value={tema} onChange={(e) => temaAyarla(e.target.value as 'dark' | 'light' | 'system')}>
              <option value="dark">{t('ayarlar.tema.koyu')}</option>
              <option value="light">{t('ayarlar.tema.acik')}</option>
              <option value="system">{t('ayarlar.tema.sistem')}</option>
            </select>
          </Alan>
          <Alan etiket={t('ayarlar.alan.dil')} ipucu={t('ayarlar.alan.dilipucu')}>
            <select className="girdi" value={dil} onChange={(e) => dilAyarla(e.target.value as 'tr' | 'en')}>
              <option value="tr">Türkçe</option>
              <option value="en">English</option>
            </select>
          </Alan>
        </div>
      </Kart>

      <BilgiKutusu>
        <span className="flex items-start gap-2">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
          <span>
            {t('ayarlar.bilgi.anahtaroncesi')} <strong>{t('ayarlar.bilgi.anahtarvurgu')}</strong>{' '}
            {t('ayarlar.bilgi.anahtarsonrasi')}
          </span>
        </span>
      </BilgiKutusu>

      {saglayicilar.isLoading ? (
        <Yukleniyor metin={t('genel.yukleniyor')} />
      ) : (
        <div className="space-y-4">
          {saglayicilar.data?.map((s) => (
            <Kart
              key={s.provider_key}
              baslik={
                <span className="flex items-center gap-2">
                  {s.display_name}
                  {s.privacy_level === 'yerel_only' && (
                    <Rozet seviye="dusuk">{t('ayarlar.gizlilik.yerel')}</Rozet>
                  )}
                  {s.privacy_level === 'herkese_acik' && (
                    <Rozet seviye="orta">{t('ayarlar.gizlilik.harici')}</Rozet>
                  )}
                </span>
              }
              aciklama={s.notes ?? undefined}
              sag={
                <div className="flex items-center gap-2">
                  {s.last_status === 'cevrimici' ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                  ) : s.last_status === 'bilinmiyor' ? null : (
                    <XCircle className="h-4 w-4 text-red-500" />
                  )}
                  <label className="flex items-center gap-1.5 text-xs">
                    <input
                      type="checkbox"
                      checked={s.enabled}
                      disabled={!yetkiVar('ai:configure')}
                      onChange={(e) =>
                        guncelle.mutate({ kod: s.provider_key, govde: { enabled: e.target.checked } })
                      }
                    />
                    {t('ayarlar.saglayici.etkin')}
                  </label>
                </div>
              }
            >
              <div className="grid gap-3 lg:grid-cols-2">
                <Alan etiket={t('ayarlar.alan.sunucu')}>
                  <input
                    className="girdi"
                    defaultValue={s.base_url}
                    disabled={!yetkiVar('ai:configure')}
                    onBlur={(e) =>
                      e.target.value !== s.base_url &&
                      guncelle.mutate({ kod: s.provider_key, govde: { base_url: e.target.value } })
                    }
                  />
                </Alan>

                <Alan etiket={t('ayarlar.alan.varsayilanmodel')}>
                  {s.cached_models.length > 0 ? (
                    <select
                      className="girdi"
                      value={s.default_model}
                      disabled={!yetkiVar('ai:configure')}
                      onChange={(e) =>
                        guncelle.mutate({ kod: s.provider_key, govde: { default_model: e.target.value } })
                      }
                    >
                      <option value="">{t('ayarlar.alan.seciniz')}</option>
                      {s.cached_models.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.label ?? m.id}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className="girdi"
                      defaultValue={s.default_model}
                      placeholder={t('ayarlar.alan.modelyertutucu')}
                      disabled={!yetkiVar('ai:configure')}
                      onBlur={(e) =>
                        e.target.value !== s.default_model &&
                        guncelle.mutate({ kod: s.provider_key, govde: { default_model: e.target.value } })
                      }
                    />
                  )}
                </Alan>

                <Alan etiket={t('ayarlar.alan.zamanasimi')}>
                  <input
                    className="girdi"
                    type="number"
                    min={5}
                    max={900}
                    defaultValue={s.timeout_seconds}
                    disabled={!yetkiVar('ai:configure')}
                    onBlur={(e) =>
                      Number(e.target.value) !== s.timeout_seconds &&
                      guncelle.mutate({
                        kod: s.provider_key,
                        govde: { timeout_seconds: Number(e.target.value) },
                      })
                    }
                  />
                </Alan>

                <Alan etiket={t('ayarlar.alan.yenidendeneme')}>
                  <input
                    className="girdi"
                    type="number"
                    min={0}
                    max={5}
                    defaultValue={s.max_retries}
                    disabled={!yetkiVar('ai:configure')}
                    onBlur={(e) =>
                      Number(e.target.value) !== s.max_retries &&
                      guncelle.mutate({
                        kod: s.provider_key,
                        govde: { max_retries: Number(e.target.value) },
                      })
                    }
                  />
                </Alan>

                <Alan etiket={t('ayarlar.alan.girismaliyet')}>
                  <input
                    className="girdi"
                    type="number"
                    step="0.000001"
                    defaultValue={s.input_cost_per_1k}
                    disabled={!yetkiVar('ai:configure')}
                    onBlur={(e) =>
                      guncelle.mutate({
                        kod: s.provider_key,
                        govde: { input_cost_per_1k: Number(e.target.value) },
                      })
                    }
                  />
                </Alan>

                <Alan etiket={t('ayarlar.alan.cikismaliyet')}>
                  <input
                    className="girdi"
                    type="number"
                    step="0.000001"
                    defaultValue={s.output_cost_per_1k}
                    disabled={!yetkiVar('ai:configure')}
                    onBlur={(e) =>
                      guncelle.mutate({
                        kod: s.provider_key,
                        govde: { output_cost_per_1k: Number(e.target.value) },
                      })
                    }
                  />
                </Alan>
              </div>

              {/* ---------------------------------------------------- anahtar */}
              {s.requires_api_key && (
                <div
                  className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border p-3"
                  style={{ borderColor: 'var(--kenar)' }}
                >
                  <KeyRound className="h-4 w-4 opacity-60" />
                  <div className="flex-1 text-xs">
                    {s.has_api_key ? (
                      <>
                        <span className="font-medium text-emerald-600 dark:text-emerald-400">
                          {t('ayarlar.anahtar.tanimli')}
                        </span>
                        <span className="ml-2 font-mono" style={{ color: 'var(--metin-2)' }}>
                          {s.api_key_masked} · {t('ayarlar.anahtar.parmakizi')} {s.api_key_fingerprint}
                        </span>
                      </>
                    ) : (
                      <span className="text-amber-600 dark:text-amber-400">
                        {t('ayarlar.anahtar.tanimsiz')}
                      </span>
                    )}
                  </div>
                  {yetkiVar('ai:configure') && (
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="dugme dugme-ikincil text-xs"
                        onClick={() => {
                          setAnahtarKip(s)
                          setAnahtar('')
                        }}
                      >
                        {s.has_api_key ? t('ayarlar.dugme.degistir') : t('ayarlar.dugme.ekle')}
                      </button>
                      {s.has_api_key && (
                        <button
                          type="button"
                          className="dugme dugme-ikincil text-xs"
                          onClick={() => {
                            if (window.confirm(t('ayarlar.uyari.anahtarsil'))) {
                              anahtarSil.mutate(s.provider_key)
                            }
                          }}
                        >
                          {t('genel.sil')}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* ------------------------------------------------------ eylemler */}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="dugme dugme-ikincil text-xs"
                  onClick={() => baglantiTest(s.provider_key, false)}
                  disabled={testEdilen === s.provider_key}
                >
                  {testEdilen === s.provider_key ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  )}
                  {t('ayarlar.dugme.baglantitest')}
                </button>
                <button
                  type="button"
                  className="dugme dugme-ikincil text-xs"
                  onClick={() => {
                    const uyari =
                      s.privacy_level === 'yerel_only'
                        ? t('ayarlar.uyari.yereltest')
                        : t('ayarlar.uyari.buluttest')
                    if (window.confirm(uyari)) baglantiTest(s.provider_key, true)
                  }}
                  disabled={testEdilen === s.provider_key}
                >
                  {t('ayarlar.dugme.sohbetlitest')}
                </button>
                <button
                  type="button"
                  className="dugme dugme-ikincil text-xs"
                  onClick={() => modelleriCek.mutate(s.provider_key)}
                  disabled={modelleriCek.isPending}
                >
                  <RefreshCw
                    className={clsx('h-3.5 w-3.5', modelleriCek.isPending && 'animate-spin')}
                  />
                  {t('ayarlar.dugme.modelyenile')} ({s.cached_models.length})
                </button>
              </div>

              <p className="mt-2 text-[11px]" style={{ color: 'var(--metin-2)' }}>
                {t('ayarlar.saglayici.durum')} <strong>{s.last_status}</strong>
                {s.last_checked_at && ` · ${tarihSaat(s.last_checked_at)}`}
                {s.last_latency_ms !== null && ` · ${s.last_latency_ms} ms`}
                {s.models_fetched_at &&
                  ` · ${t('ayarlar.saglayici.modellistesi')} ${tarihSaat(s.models_fetched_at)}`}
              </p>
              {s.last_error && (
                <p className="mt-1 text-[11px] text-red-600 dark:text-red-400">{s.last_error}</p>
              )}
            </Kart>
          ))}
        </div>
      )}

      <Kip
        acik={anahtarKip !== null}
        baslik={`${anahtarKip?.display_name ?? ''} ${t('ayarlar.kip.anahtar')}`}
        onKapat={() => setAnahtarKip(null)}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (anahtarKip) anahtarKaydet.mutate({ kod: anahtarKip.provider_key, deger: anahtar })
          }}
          className="space-y-4"
        >
          <BilgiKutusu>
            {t('ayarlar.kip.bilgioncesi')} <strong>{t('ayarlar.bilgi.anahtarvurgu')}</strong>{' '}
            {t('ayarlar.kip.bilgisonrasi')}
          </BilgiKutusu>
          <Alan etiket={t('ayarlar.kip.anahtar')} gerekli>
            <input
              className="girdi font-mono"
              type="password"
              value={anahtar}
              onChange={(e) => setAnahtar(e.target.value)}
              autoComplete="off"
              minLength={8}
              required
              placeholder={anahtarKip?.provider_key === 'nvidia' ? 'nvapi-…' : 'sk-ant-…'}
            />
          </Alan>
          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setAnahtarKip(null)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil" disabled={anahtarKaydet.isPending}>
              {t('ayarlar.dugme.sifrelikaydet')}
            </button>
          </div>
        </form>
      </Kip>
    </div>
  )
}
