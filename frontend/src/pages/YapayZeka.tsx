import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, Coins, Send, ShieldCheck, Sparkles } from 'lucide-react'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { Alan, Bos, HataKutusu, Kart, Kip, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { api, hataMesaji } from '@/lib/api'
import { goreliZaman, sayi } from '@/lib/bicim'
import { useSecenekler } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'

interface Saglayici {
  provider_key: string
  display_name: string
  enabled: boolean
  default_model: string
  privacy_level: string
  last_status: string
  has_api_key: boolean
  requires_api_key: boolean
  cached_models: { id: string; label?: string }[]
}

interface Mesaj {
  id: number
  role: string
  content: string
  model: string | null
  provider_key: string | null
  input_tokens: number
  output_tokens: number
  latency_ms: number | null
  created_at: string
  error: string | null
}

// Etiketler çeviri sözlüğünden gelir: yapayzeka.gorev.<kod>
const GOREVLER = [
  'saraphane_danismani',
  'veri_analisti',
  'rapor_yazari',
  'kalite_kontrol',
  'kod_gelistirici',
  'hata_teshis',
  'dokumantasyon',
  'genel',
] as const

// Etiketler çeviri sözlüğünden gelir: yapayzeka.analiz.<kod>
const ANALIZLER = ['stok_tahmin', 'bakim_tahmin', 'rapor'] as const

export default function YapayZeka() {
  const t = useCeviri()
  const istemci = useQueryClient()
  const [gorev, setGorev] = useState<string>('saraphane_danismani')
  const [saglayiciKod, setSaglayiciKod] = useState('')
  const [model, setModel] = useState('')
  const [mesaj, setMesaj] = useState('')
  const [konusmaId, setKonusmaId] = useState<number | null>(null)
  const [partiler, setPartiler] = useState<number[]>([])
  const [panoEkle, setPanoEkle] = useState(false)
  const [ragKullan, setRagKullan] = useState(false)
  const [kapsamAcik, setKapsamAcik] = useState(false)
  const [kapsam, setKapsam] = useState<Record<string, unknown> | null>(null)
  const [hata, setHata] = useState('')
  const kaydirmaRef = useRef<HTMLDivElement>(null)

  const partiSecenek = useSecenekler('/lots', 'code')

  const saglayicilar = useQuery({
    queryKey: ['/ai/providers'],
    queryFn: async () => (await api.get<Saglayici[]>('/ai/providers')).data,
  })

  const konusmalar = useQuery({
    queryKey: ['/ai/conversations'],
    queryFn: async () => (await api.get<Record<string, unknown>[]>('/ai/conversations')).data,
  })

  const mesajlar = useQuery({
    queryKey: ['/ai/conversations', konusmaId, 'messages'],
    queryFn: async () =>
      (await api.get<Mesaj[]>(`/ai/conversations/${konusmaId}/messages`)).data,
    enabled: !!konusmaId,
  })

  const kullanim = useQuery({
    queryKey: ['/ai/usage'],
    queryFn: async () => (await api.get('/ai/usage')).data,
  })

  useEffect(() => {
    kaydirmaRef.current?.scrollTo({ top: kaydirmaRef.current.scrollHeight, behavior: 'smooth' })
  }, [mesajlar.data])

  const aktifSaglayici = saglayicilar.data?.find(
    (s) => s.provider_key === (saglayiciKod || saglayicilar.data?.[0]?.provider_key),
  )
  const harici = aktifSaglayici ? aktifSaglayici.privacy_level !== 'yerel_only' : false

  function govdeYap(onayla = false) {
    return {
      message: mesaj,
      conversation_id: konusmaId ?? undefined,
      provider_key: saglayiciKod || undefined,
      model: model || undefined,
      task_kind: gorev,
      context_lot_ids: partiler,
      include_dashboard: panoEkle,
      use_rag: ragKullan,
      confirm_external_share: onayla,
    }
  }

  const gonder = useMutation({
    mutationFn: async (onayla: boolean) => (await api.post('/ai/chat', govdeYap(onayla))).data,
    onSuccess: (veri) => {
      setKonusmaId(veri.conversation_id)
      setMesaj('')
      setKapsamAcik(false)
      void istemci.invalidateQueries({ queryKey: ['/ai/conversations'] })
      void istemci.invalidateQueries({ queryKey: ['/ai/usage'] })
    },
    onError: (err) => setHata(hataMesaji(err)),
  })

  const analiz = useMutation({
    mutationFn: async (tur: string) =>
      (await api.post('/ai/insights', { kind: tur, use_llm: tur === 'rapor', provider_key: saglayiciKod || undefined }))
        .data,
    onError: (err) => setHata(hataMesaji(err)),
  })

  async function kapsamGoster(e: FormEvent) {
    e.preventDefault()
    setHata('')
    if (!mesaj.trim()) return
    // Yerel sağlayıcıda veri makineden çıkmaz; doğrudan gönder.
    if (!harici || (partiler.length === 0 && !panoEkle)) {
      gonder.mutate(true)
      return
    }
    try {
      const { data } = await api.post('/ai/data-scope-preview', govdeYap())
      setKapsam(data)
      setKapsamAcik(true)
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  return (
    <div className="space-y-5">
      <SayfaBasligi baslik={t('yapayzeka.baslik')} aciklama={t('yapayzeka.aciklama')} />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

      <div className="grid gap-5 xl:grid-cols-[300px_1fr]">
        {/* --------------------------------------------------------- sol panel */}
        <div className="space-y-4">
          <Kart baslik={t('yapayzeka.kart.saglayici')}>
            <div className="space-y-3">
              <Alan etiket={t('yapayzeka.alan.saglayici')}>
                <select
                  className="girdi"
                  value={saglayiciKod}
                  onChange={(e) => {
                    setSaglayiciKod(e.target.value)
                    setModel('')
                  }}
                >
                  <option value="">{t('yapayzeka.saglayici.otomatik')}</option>
                  {saglayicilar.data?.map((s) => (
                    <option key={s.provider_key} value={s.provider_key} disabled={!s.enabled}>
                      {s.display_name}
                      {s.privacy_level === 'yerel_only' ? ' 🔒' : ''}
                      {!s.enabled ? ` (${t('yapayzeka.saglayici.kapali')})` : ''}
                    </option>
                  ))}
                </select>
              </Alan>

              {aktifSaglayici && (aktifSaglayici.cached_models?.length ?? 0) > 0 && (
                <Alan etiket={t('yapayzeka.alan.model')}>
                  <select className="girdi" value={model} onChange={(e) => setModel(e.target.value)}>
                    <option value="">
                      {t('yapayzeka.model.varsayilan')} ({aktifSaglayici.default_model || '—'})
                    </option>
                    {aktifSaglayici.cached_models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label ?? m.id}
                      </option>
                    ))}
                  </select>
                </Alan>
              )}

              <Alan etiket={t('yapayzeka.alan.gorev')}>
                <select className="girdi" value={gorev} onChange={(e) => setGorev(e.target.value)}>
                  {GOREVLER.map((k) => (
                    <option key={k} value={k}>
                      {t(`yapayzeka.gorev.${k}`)}
                    </option>
                  ))}
                </select>
              </Alan>

              {aktifSaglayici && (
                <div
                  className={clsx(
                    'flex items-start gap-2 rounded-lg p-2 text-xs',
                    harici ? 'bg-amber-500/10 text-amber-700 dark:text-amber-300' : 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
                  )}
                >
                  {harici ? (
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  ) : (
                    <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  )}
                  <span>
                    {harici ? t('yapayzeka.gizlilik.harici') : t('yapayzeka.gizlilik.yerel')}
                  </span>
                </div>
              )}
            </div>
          </Kart>

          <Kart baslik={t('yapayzeka.kart.baglam')} aciklama={t('yapayzeka.kart.baglamaciklama')}>
            <div className="space-y-3">
              <Alan etiket={t('yapayzeka.alan.partiler')}>
                <select
                  className="girdi"
                  multiple
                  size={5}
                  value={partiler.map(String)}
                  onChange={(e) =>
                    setPartiler([...e.target.selectedOptions].map((o) => Number(o.value)))
                  }
                >
                  {partiSecenek.data?.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.ad} — {String(p.ham.name)}
                    </option>
                  ))}
                </select>
              </Alan>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={panoEkle} onChange={(e) => setPanoEkle(e.target.checked)} />
                {t('yapayzeka.baglam.panoekle')}
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={ragKullan} onChange={(e) => setRagKullan(e.target.checked)} />
                {t('yapayzeka.baglam.rag')}
              </label>
            </div>
          </Kart>

          <Kart baslik={t('yapayzeka.kart.analiz')}>
            <div className="space-y-2">
              {ANALIZLER.map((k) => (
                <button
                  key={k}
                  type="button"
                  className="dugme dugme-ikincil w-full justify-start text-xs"
                  onClick={() => analiz.mutate(k)}
                  disabled={analiz.isPending}
                >
                  <Sparkles className="h-3.5 w-3.5" /> {t(`yapayzeka.analiz.${k}`)}
                </button>
              ))}
            </div>
            {analiz.data && (
              <div className="mt-3 rounded-lg border p-3" style={{ borderColor: 'var(--kenar)' }}>
                <div className="mb-1 flex items-center gap-2">
                  <Rozet seviye={analiz.data.severity}>{analiz.data.severity}</Rozet>
                  <span className="text-xs font-medium">{analiz.data.title}</span>
                </div>
                <p className="text-xs">{analiz.data.summary}</p>
                {analiz.data.llm_commentary && (
                  <p className="mt-2 whitespace-pre-wrap text-xs" style={{ color: 'var(--metin-2)' }}>
                    {analiz.data.llm_commentary}
                  </p>
                )}
              </div>
            )}
          </Kart>

          {kullanim.data && (
            <Kart
              baslik={
                <span className="flex items-center gap-1.5">
                  <Coins className="h-4 w-4" /> {t('yapayzeka.kart.kullanim')}
                </span>
              }
            >
              <div className="space-y-1 text-xs">
                <p>
                  {t('yapayzeka.kullanim.istek')} <strong>{kullanim.data.total_requests}</strong>
                </p>
                <p>
                  {t('yapayzeka.kullanim.token')}{' '}
                  <strong>{sayi(kullanim.data.total_input_tokens, 0)}</strong>{' '}
                  {t('yapayzeka.kullanim.giris')} /{' '}
                  <strong>{sayi(kullanim.data.total_output_tokens, 0)}</strong>{' '}
                  {t('yapayzeka.kullanim.cikis')}
                </p>
                <p>
                  {t('yapayzeka.kullanim.maliyet')}{' '}
                  <strong>${kullanim.data.total_cost_usd?.toFixed(4) ?? '0.0000'}</strong>
                </p>
                {kullanim.data.by_provider?.map((p: Record<string, unknown>) => (
                  <p key={String(p.provider_key)} style={{ color: 'var(--metin-2)' }}>
                    {String(p.display_name)}: {String(p.requests)} {t('yapayzeka.kullanim.istekadet')}
                    {Number(p.failed) > 0 && ` (${String(p.failed)} ${t('yapayzeka.kullanim.hataadet')})`}
                  </p>
                ))}
              </div>
            </Kart>
          )}
        </div>

        {/* -------------------------------------------------------- sohbet */}
        <div className="space-y-4">
          <Kart
            baslik={t('yapayzeka.kart.sohbet')}
            aciklama={
              konusmaId
                ? `${t('yapayzeka.sohbet.konusmano')} #${konusmaId}`
                : t('yapayzeka.sohbet.yenigorev')
            }
            sag={
              <select
                className="girdi w-auto py-1 text-xs"
                value={konusmaId ?? ''}
                onChange={(e) => setKonusmaId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">{t('yapayzeka.sohbet.yenikonusma')}</option>
                {konusmalar.data?.map((k) => (
                  <option key={String(k.id)} value={String(k.id)}>
                    {String(k.title).slice(0, 40)}
                  </option>
                ))}
              </select>
            }
            govdeSinif="p-0"
          >
            <div ref={kaydirmaRef} className="max-h-[52vh] min-h-64 space-y-3 overflow-y-auto p-4">
              {!konusmaId ? (
                <Bos metin={t('yapayzeka.bos.metin')} ipucu={t('yapayzeka.bos.ipucu')} />
              ) : mesajlar.isLoading ? (
                <Yukleniyor metin={t('genel.yukleniyor')} />
              ) : (
                mesajlar.data?.map((m) => (
                  <div
                    key={m.id}
                    className={clsx('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}
                  >
                    <div
                      className={clsx(
                        'max-w-[85%] rounded-xl px-3 py-2 text-sm',
                        m.role === 'user'
                          ? 'bg-[var(--vurgu)] text-[var(--vurgu-yazi)]'
                          : 'border',
                      )}
                      style={
                        m.role === 'user'
                          ? undefined
                          : { borderColor: 'var(--kenar)', background: 'var(--yuzey-3)' }
                      }
                    >
                      <p className="whitespace-pre-wrap">{m.content || m.error}</p>
                      {m.role === 'assistant' && (
                        <p className="mt-1.5 text-[10px] opacity-70">
                          {m.model} · {m.input_tokens + m.output_tokens}{' '}
                          {t('yapayzeka.sohbet.token')}
                          {m.latency_ms
                            ? ` · ${(m.latency_ms / 1000).toFixed(1)} ${t('yapayzeka.sohbet.saniye')}`
                            : ''}{' '}
                          · {goreliZaman(m.created_at)}
                        </p>
                      )}
                    </div>
                  </div>
                ))
              )}
              {gonder.isPending && <Yukleniyor metin={t('yapayzeka.sohbet.yanitliyor')} />}
            </div>

            <form
              onSubmit={kapsamGoster}
              className="flex gap-2 border-t p-3"
              style={{ borderColor: 'var(--kenar)' }}
            >
              <textarea
                className="girdi resize-none"
                rows={2}
                placeholder={t('yapayzeka.sohbet.yertutucu')}
                value={mesaj}
                onChange={(e) => setMesaj(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault()
                    void kapsamGoster(e as unknown as FormEvent)
                  }
                }}
              />
              <button
                type="submit"
                className="dugme dugme-birincil self-end"
                disabled={gonder.isPending || !mesaj.trim()}
              >
                <Send className="h-4 w-4" /> {t('yapayzeka.dugme.gonder')}
              </button>
            </form>
          </Kart>

          <p className="text-[11px]" style={{ color: 'var(--metin-2)' }}>
            {t('yapayzeka.uyari.oncesi')} <strong>{t('yapayzeka.uyari.vurgu')}</strong>{' '}
            {t('yapayzeka.uyari.sonrasi')}
          </p>
        </div>
      </div>

      {/* --------------------------------------------------- veri kapsamı onayı */}
      <Kip
        acik={kapsamAcik}
        baslik={t('yapayzeka.kapsam.baslik')}
        onKapat={() => setKapsamAcik(false)}
        genis
      >
        {kapsam && (
          <div className="space-y-4">
            <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200">
              <p className="font-medium">{kapsam.provider_name as string}</p>
              <p className="mt-1 text-xs">{kapsam.warning_tr as string}</p>
            </div>

            <table className="tablo">
              <thead>
                <tr>
                  <th>{t('yapayzeka.kapsam.tur')}</th>
                  <th>{t('yapayzeka.kapsam.kod')}</th>
                  <th>{t('yapayzeka.kapsam.ad')}</th>
                  <th>{t('yapayzeka.kapsam.alanlar')}</th>
                </tr>
              </thead>
              <tbody>
                {(kapsam.items as Record<string, string>[]).map((i, idx) => (
                  <tr key={idx}>
                    <td>{i.tur}</td>
                    <td className="font-mono text-xs">{i.kod}</td>
                    <td>{i.ad}</td>
                    <td className="text-xs">{i.alanlar}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
              {t('yapayzeka.kapsam.yaklasik')} {sayi(kapsam.approx_chars as number, 0)}{' '}
              {t('yapayzeka.kapsam.karakter')}
            </p>

            <div className="flex justify-end gap-2">
              <button type="button" className="dugme dugme-ikincil" onClick={() => setKapsamAcik(false)}>
                {t('genel.iptal')}
              </button>
              <button
                type="button"
                className="dugme dugme-birincil"
                onClick={() => gonder.mutate(true)}
                disabled={gonder.isPending}
              >
                {t('yapayzeka.kapsam.onayla')}
              </button>
            </div>
          </div>
        )}
      </Kip>
    </div>
  )
}
