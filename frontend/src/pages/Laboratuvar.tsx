import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, FlaskConical, Plus, Sparkles, X } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Alan, Bos, HataKutusu, Kart, Kip, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { Tablo } from '@/components/Tablo'
import { api, hataMesaji } from '@/lib/api'
import { etiket, sayi, tarihSaat } from '@/lib/bicim'
import { useListe, useSecenekler } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

interface Sonuc {
  id: number
  code: string
  lot_code: string | null
  sample_code: string | null
  analyzed_at: string
  ph: number | null
  total_acidity: number | null
  volatile_acidity: number | null
  free_so2: number | null
  total_so2: number | null
  alcohol: number | null
  residual_sugar: number | null
  approval_status: string
  out_of_spec: boolean
  out_of_spec_details: string | null
}

export default function Laboratuvar() {
  const t = useCeviri()
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const [sekme, setSekme] = useState<'sonuc' | 'numune' | 'spek'>('sonuc')
  const [numuneAcik, setNumuneAcik] = useState(false)
  const [sonucAcik, setSonucAcik] = useState<number | null>(null)
  const [yorumId, setYorumId] = useState<number | null>(null)
  const [hata, setHata] = useState('')
  const [onayFiltre, setOnayFiltre] = useState('')

  const partiSecenek = useSecenekler('/lots', 'code')

  const sonuclar = useQuery({
    queryKey: ['/lab/results', onayFiltre],
    queryFn: async () =>
      (await api.get<Sonuc[]>('/lab/results', {
        params: { approval_status: onayFiltre || undefined, limit: 200 },
      })).data,
    enabled: sekme === 'sonuc',
  })

  const numuneler = useListe<Record<string, unknown>>('/lab/samples', {}, { etkin: sekme === 'numune' })
  const spekler = useListe<Record<string, unknown>>('/lab/specs', {}, { etkin: sekme === 'spek' })

  const yorum = useQuery({
    queryKey: ['lab-yorum', yorumId],
    queryFn: async () =>
      (await api.post('/ai/insights', { kind: 'lab_yorum', lot_id: yorumId, use_llm: true })).data,
    enabled: !!yorumId,
    retry: false,
  })

  const [numune, setNumune] = useState({ lot_id: '', sample_type: 'rutin', notes: '' })
  const [sonuc, setSonuc] = useState({
    ph: '',
    total_acidity: '',
    volatile_acidity: '',
    free_so2: '',
    total_so2: '',
    alcohol: '',
    residual_sugar: '',
    density: '',
    malic_acid: '',
    turbidity_ntu: '',
    notes: '',
  })

  async function numuneKaydet(e: FormEvent) {
    e.preventDefault()
    setHata('')
    try {
      const { data } = await api.post('/lab/samples', {
        lot_id: Number(numune.lot_id),
        sample_type: numune.sample_type,
        notes: numune.notes || undefined,
      })
      setNumuneAcik(false)
      setSonucAcik(data.id)
      void istemci.invalidateQueries({ queryKey: ['/lab/samples'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  async function sonucKaydet(e: FormEvent) {
    e.preventDefault()
    if (!sonucAcik) return
    setHata('')
    try {
      const govde: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(sonuc)) {
        if (!v) continue
        govde[k] = k === 'notes' ? v : Number(v)
      }
      await api.post(`/lab/samples/${sonucAcik}/results`, govde)
      setSonucAcik(null)
      setSonuc({
        ph: '', total_acidity: '', volatile_acidity: '', free_so2: '', total_so2: '',
        alcohol: '', residual_sugar: '', density: '', malic_acid: '', turbidity_ntu: '', notes: '',
      })
      void istemci.invalidateQueries({ queryKey: ['/lab/results'] })
      void istemci.invalidateQueries({ queryKey: ['pano'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  async function onayla(id: number, kabul: boolean) {
    const gerekce = kabul ? undefined : window.prompt(t('laboratuvar.uyari.redgerekce'))
    if (!kabul && !gerekce) return
    try {
      await api.post(`/lab/results/${id}/approval`, { approve: kabul, reason: gerekce })
      void istemci.invalidateQueries({ queryKey: ['/lab/results'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('laboratuvar.baslik')}
        aciklama={t('laboratuvar.aciklama')}
        eylemler={
          yetkiVar('lab:write') ? (
            <button type="button" className="dugme dugme-birincil" onClick={() => setNumuneAcik(true)}>
              <Plus className="h-4 w-4" /> {t('laboratuvar.dugme.numunal')}
            </button>
          ) : null
        }
      />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

      <div className="flex flex-wrap gap-1 border-b" style={{ borderColor: 'var(--kenar)' }}>
        {(
          [
            ['sonuc', t('laboratuvar.sekme.sonuc')],
            ['numune', t('laboratuvar.sekme.numune')],
            ['spek', t('laboratuvar.sekme.spek')],
          ] as const
        ).map(([k, ad]) => (
          <button
            key={k}
            type="button"
            onClick={() => setSekme(k)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              sekme === k
                ? 'border-[var(--vurgu)] font-medium text-[var(--vurgu)]'
                : 'border-transparent'
            }`}
          >
            {ad}
          </button>
        ))}
      </div>

      {sekme === 'sonuc' && (
        <>
          <div className="flex items-center gap-2">
            <select
              className="girdi w-auto"
              value={onayFiltre}
              onChange={(e) => setOnayFiltre(e.target.value)}
              aria-label={t('laboratuvar.filtre.onay')}
            >
              <option value="">{t('laboratuvar.filtre.tumu')}</option>
              <option value="bekliyor">{t('laboratuvar.filtre.bekleyen')}</option>
              <option value="onaylandi">{t('laboratuvar.filtre.onaylanan')}</option>
              <option value="reddedildi">{t('laboratuvar.filtre.reddedilen')}</option>
            </select>
          </div>

          {sonuclar.isLoading ? (
            <Yukleniyor />
          ) : (sonuclar.data?.length ?? 0) === 0 ? (
            <Kart>
              <Bos metin={t('laboratuvar.bos.sonuc')} ipucu={t('laboratuvar.bos.sonucipucu')} />
            </Kart>
          ) : (
            <div className="kart overflow-x-auto">
              <table className="tablo">
                <thead>
                  <tr>
                    <th>{t('laboratuvar.tablo.kod')}</th>
                    <th>{t('laboratuvar.tablo.parti')}</th>
                    <th>{t('laboratuvar.tablo.tarih')}</th>
                    <th className="text-right">{t('laboratuvar.tablo.ph')}</th>
                    <th className="text-right">{t('laboratuvar.tablo.ta')}</th>
                    <th className="text-right">{t('laboratuvar.tablo.ua')}</th>
                    <th className="text-right">{t('laboratuvar.tablo.serbestso2')}</th>
                    <th className="text-right">{t('laboratuvar.tablo.toplamso2')}</th>
                    <th className="text-right">{t('laboratuvar.tablo.alkol')}</th>
                    <th className="text-right">{t('laboratuvar.tablo.seker')}</th>
                    <th>{t('laboratuvar.tablo.onay')}</th>
                    <th>{t('laboratuvar.tablo.islem')}</th>
                  </tr>
                </thead>
                <tbody>
                  {sonuclar.data?.map((s) => (
                    <tr key={s.id} className={s.out_of_spec ? 'bg-red-500/5' : undefined}>
                      <td className="font-medium">{s.code}</td>
                      <td>{s.lot_code ?? '—'}</td>
                      <td className="whitespace-nowrap text-xs">{tarihSaat(s.analyzed_at)}</td>
                      <td className="text-right tabular-nums">{sayi(s.ph, 2)}</td>
                      <td className="text-right tabular-nums">{sayi(s.total_acidity, 2)}</td>
                      <td
                        className={`text-right tabular-nums ${
                          (s.volatile_acidity ?? 0) >= 0.9 ? 'font-semibold text-red-600 dark:text-red-400' : ''
                        }`}
                      >
                        {sayi(s.volatile_acidity, 2)}
                      </td>
                      <td className="text-right tabular-nums">{sayi(s.free_so2, 0)}</td>
                      <td className="text-right tabular-nums">{sayi(s.total_so2, 0)}</td>
                      <td className="text-right tabular-nums">{sayi(s.alcohol, 1)}</td>
                      <td className="text-right tabular-nums">{sayi(s.residual_sugar, 1)}</td>
                      <td>
                        <Rozet
                          seviye={
                            s.approval_status === 'onaylandi'
                              ? 'dusuk'
                              : s.approval_status === 'reddedildi'
                                ? 'kritik'
                                : 'orta'
                          }
                        >
                          {etiket(s.approval_status)}
                        </Rozet>
                        {s.out_of_spec && (
                          <span
                            className="mt-1 block text-[10px] text-red-600 dark:text-red-400"
                            title={s.out_of_spec_details ?? ''}
                          >
                            {t('laboratuvar.rozet.spekdisi')}
                          </span>
                        )}
                      </td>
                      <td>
                        <div className="flex gap-1">
                          {yetkiVar('lab:approve') && s.approval_status === 'bekliyor' && (
                            <>
                              <button
                                type="button"
                                className="dugme dugme-ikincil px-2 py-1"
                                onClick={() => onayla(s.id, true)}
                                title={t('genel.onayla')}
                              >
                                <Check className="h-3.5 w-3.5" />
                              </button>
                              <button
                                type="button"
                                className="dugme dugme-ikincil px-2 py-1"
                                onClick={() => onayla(s.id, false)}
                                title={t('genel.reddet')}
                              >
                                <X className="h-3.5 w-3.5" />
                              </button>
                            </>
                          )}
                          {yetkiVar('ai:use') && (
                            <button
                              type="button"
                              className="dugme dugme-ikincil px-2 py-1"
                              onClick={() => setYorumId(s.id)}
                              title={t('laboratuvar.dugme.aiyorum')}
                            >
                              <Sparkles className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {sekme === 'numune' && (
        <Tablo
          sutunlar={[
            { anahtar: 'code', baslik: t('laboratuvar.numunetablo.kod') },
            {
              anahtar: 'lot_code',
              baslik: t('laboratuvar.numunetablo.parti'),
              hucre: (r) => (r.lot_code as string) ?? '—',
            },
            {
              anahtar: 'tank_code',
              baslik: t('laboratuvar.numunetablo.tank'),
              hucre: (r) => (r.tank_code as string) ?? '—',
            },
            {
              anahtar: 'sampled_at',
              baslik: t('laboratuvar.numunetablo.alinma'),
              hucre: (r) => tarihSaat(r.sampled_at as string),
            },
            {
              anahtar: 'sample_type',
              baslik: t('laboratuvar.numunetablo.tur'),
              hucre: (r) => etiket(r.sample_type as string),
            },
            {
              anahtar: 'status',
              baslik: t('laboratuvar.numunetablo.durum'),
              hucre: (r) => <Rozet>{etiket(r.status as string)}</Rozet>,
            },
            { anahtar: 'result_count', baslik: t('laboratuvar.numunetablo.sonuc'), sagaYasli: true },
            {
              anahtar: 'islem',
              baslik: '',
              hucre: (r) =>
                yetkiVar('lab:write') && Number(r.result_count) === 0 ? (
                  <button
                    type="button"
                    className="dugme dugme-ikincil px-2 py-1 text-xs"
                    onClick={(e) => {
                      e.stopPropagation()
                      setSonucAcik(Number(r.id))
                    }}
                  >
                    <FlaskConical className="h-3.5 w-3.5" /> {t('laboratuvar.dugme.sonucgir')}
                  </button>
                ) : null,
            },
          ]}
          satirlar={numuneler.satirlar}
          yukleniyor={numuneler.isLoading}
          toplam={numuneler.toplam}
          sayfa={numuneler.sayfa}
          sayfaBoyu={numuneler.sayfaBoyu}
          onSayfa={numuneler.setSayfa}
          arama={numuneler.arama}
          onArama={numuneler.setArama}
          bosMetin={t('laboratuvar.bos.numune')}
        />
      )}

      {sekme === 'spek' && (
        <Tablo
          sutunlar={[
            {
              anahtar: 'label_tr',
              baslik: t('laboratuvar.spektablo.parametre'),
              hucre: (r) => (r.label_tr as string) || (r.parameter as string),
            },
            { anahtar: 'parameter', baslik: t('laboratuvar.spektablo.alan') },
            {
              anahtar: 'wine_type',
              baslik: t('laboratuvar.spektablo.saraptipi'),
              hucre: (r) => (r.wine_type ? etiket(r.wine_type as string) : t('laboratuvar.spektablo.tumu')),
            },
            {
              anahtar: 'min_value',
              baslik: t('laboratuvar.spektablo.altsinir'),
              sagaYasli: true,
              hucre: (r) => sayi(r.min_value as number, 2),
            },
            {
              anahtar: 'max_value',
              baslik: t('laboratuvar.spektablo.ustsinir'),
              sagaYasli: true,
              hucre: (r) => sayi(r.max_value as number, 2),
            },
            { anahtar: 'unit', baslik: t('laboratuvar.spektablo.birim') },
            {
              anahtar: 'severity',
              baslik: t('laboratuvar.spektablo.seviye'),
              hucre: (r) => <Rozet seviye={r.severity as string}>{etiket(r.severity as string)}</Rozet>,
            },
          ]}
          satirlar={spekler.satirlar}
          yukleniyor={spekler.isLoading}
          toplam={spekler.toplam}
          sayfa={spekler.sayfa}
          sayfaBoyu={spekler.sayfaBoyu}
          onSayfa={spekler.setSayfa}
          arama={spekler.arama}
          onArama={spekler.setArama}
          bosMetin={t('laboratuvar.bos.spek')}
          bosIpucu={t('laboratuvar.bos.spekipucu')}
        />
      )}

      {/* ------------------------------------------------------------ numune */}
      <Kip acik={numuneAcik} baslik={t('laboratuvar.kip.numune')} onKapat={() => setNumuneAcik(false)}>
        <form onSubmit={numuneKaydet} className="space-y-4">
          <Alan etiket={t('laboratuvar.alan.parti')} gerekli>
            <select
              className="girdi"
              value={numune.lot_id}
              onChange={(e) => setNumune({ ...numune, lot_id: e.target.value })}
              required
            >
              <option value="">{t('laboratuvar.secim.seciniz')}</option>
              {partiSecenek.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.ad} — {String(p.ham.name)}
                </option>
              ))}
            </select>
          </Alan>
          <Alan etiket={t('laboratuvar.alan.numunetur')}>
            <select
              className="girdi"
              value={numune.sample_type}
              onChange={(e) => setNumune({ ...numune, sample_type: e.target.value })}
            >
              <option value="rutin">{t('laboratuvar.numunetur.rutin')}</option>
              <option value="kontrol">{t('laboratuvar.numunetur.kontrol')}</option>
              <option value="siseleme_oncesi">{t('laboratuvar.numunetur.sislemeoncesi')}</option>
              <option value="sikayet">{t('laboratuvar.numunetur.sikayet')}</option>
            </select>
          </Alan>
          <Alan etiket={t('laboratuvar.alan.not')}>
            <textarea
              className="girdi"
              rows={2}
              value={numune.notes}
              onChange={(e) => setNumune({ ...numune, notes: e.target.value })}
            />
          </Alan>
          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setNumuneAcik(false)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('laboratuvar.dugme.numunekaydet')}
            </button>
          </div>
        </form>
      </Kip>

      {/* ------------------------------------------------------- analiz sonucu */}
      <Kip acik={sonucAcik !== null} baslik={t('laboratuvar.kip.sonuc')} onKapat={() => setSonucAcik(null)} genis>
        <form onSubmit={sonucKaydet} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}
          <div className="grid gap-3 sm:grid-cols-4">
            {(
              [
                ['ph', t('laboratuvar.alan.ph'), '0.01'],
                ['total_acidity', t('laboratuvar.alan.toplamasitlik'), '0.1'],
                ['volatile_acidity', t('laboratuvar.alan.ucucuasitlik'), '0.01'],
                ['free_so2', t('laboratuvar.alan.serbestso2'), '0.1'],
                ['total_so2', t('laboratuvar.alan.toplamso2'), '0.1'],
                ['alcohol', t('laboratuvar.alan.alkol'), '0.01'],
                ['residual_sugar', t('laboratuvar.alan.kalintiseker'), '0.1'],
                ['density', t('laboratuvar.alan.yogunluk'), '0.0001'],
                ['malic_acid', t('laboratuvar.alan.malikasit'), '0.01'],
                ['turbidity_ntu', t('laboratuvar.alan.bulaniklik'), '0.1'],
              ] as const
            ).map(([alan, ad, adim]) => (
              <Alan key={alan} etiket={ad}>
                <input
                  className="girdi"
                  type="number"
                  step={adim}
                  value={sonuc[alan]}
                  onChange={(e) => setSonuc({ ...sonuc, [alan]: e.target.value })}
                />
              </Alan>
            ))}
          </div>
          <Alan etiket={t('laboratuvar.alan.not')}>
            <textarea
              className="girdi"
              rows={2}
              value={sonuc.notes}
              onChange={(e) => setSonuc({ ...sonuc, notes: e.target.value })}
            />
          </Alan>
          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setSonucAcik(null)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('laboratuvar.dugme.sonuckaydet')}
            </button>
          </div>
        </form>
      </Kip>

      {/* ------------------------------------------------------- AI yorumu */}
      <Kip
        acik={yorumId !== null}
        baslik={t('laboratuvar.kip.aiyorum')}
        onKapat={() => setYorumId(null)}
        genis
      >
        {yorum.isLoading ? (
          <Yukleniyor metin={t('laboratuvar.yukleniyor.yorum')} />
        ) : yorum.error ? (
          <HataKutusu mesaj={hataMesaji(yorum.error)} />
        ) : yorum.data ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Rozet seviye={yorum.data.severity}>{yorum.data.severity}</Rozet>
              <span className="text-sm font-medium">{yorum.data.title}</span>
            </div>
            <p className="text-sm">{yorum.data.summary}</p>
            {yorum.data.numeric?.faktorler && (
              <table className="tablo">
                <thead>
                  <tr>
                    <th>{t('laboratuvar.aitablo.parametre')}</th>
                    <th className="text-right">{t('laboratuvar.aitablo.deger')}</th>
                    <th>{t('laboratuvar.aitablo.ideal')}</th>
                    <th className="text-right">{t('laboratuvar.aitablo.puan')}</th>
                  </tr>
                </thead>
                <tbody>
                  {(yorum.data.numeric.faktorler as Record<string, unknown>[]).map((f, i) => (
                    <tr key={i}>
                      <td>{String(f.parametre)}</td>
                      <td className="text-right tabular-nums">{String(f.deger)}</td>
                      <td>{String(f.ideal)}</td>
                      <td className="text-right tabular-nums">{String(f.puan)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {yorum.data.llm_commentary && (
              <div className="rounded-lg border p-3 text-sm whitespace-pre-wrap" style={{ borderColor: 'var(--kenar)' }}>
                {yorum.data.llm_commentary}
              </div>
            )}
            <p className="text-[11px]" style={{ color: 'var(--metin-2)' }}>
              {yorum.data.disclaimer}
            </p>
          </div>
        ) : null}
      </Kip>
    </div>
  )
}
