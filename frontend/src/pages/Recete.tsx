import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Plus, Play } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Alan, Bos, HataKutusu, Kart, Kip, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { api, hataMesaji } from '@/lib/api'
import { etiket, para, sayi, tarihSaat } from '@/lib/bicim'
import { useSecenekler } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

interface Kupaj {
  id: number
  code: string
  name: string
  status: string
  planned_volume_l: number
  predicted_alcohol: number | null
  predicted_ph: number | null
  predicted_ta: number | null
  estimated_cost: number | null
  executed_at: string | null
  result_lot_id: number | null
  components: {
    id: number
    source_lot_id: number
    source_lot_code: string | null
    source_lot_name: string | null
    volume_l: number
    percentage: number | null
  }[]
}

export default function Recete() {
  const t = useCeviri()
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const [sekme, setSekme] = useState<'kupaj' | 'recete'>('kupaj')
  const [kipAcik, setKipAcik] = useState(false)
  const [uygulaId, setUygulaId] = useState<number | null>(null)
  const [hata, setHata] = useState('')

  const partiSecenek = useSecenekler('/lots', 'code')
  const tankSecenek = useSecenekler('/tanks', 'code')

  const kupajlar = useQuery({
    queryKey: ['/blends'],
    queryFn: async () => (await api.get<Kupaj[]>('/blends')).data,
    enabled: sekme === 'kupaj',
  })

  const receteler = useQuery({
    queryKey: ['/recipes'],
    queryFn: async () => (await api.get<Record<string, unknown>[]>('/recipes')).data,
    enabled: sekme === 'recete',
  })

  const [form, setForm] = useState({ name: '', target_tank_id: '' })
  const [bilesenler, setBilesenler] = useState([
    { source_lot_id: '', volume_l: '' },
    { source_lot_id: '', volume_l: '' },
  ])
  const [uygula, setUygula] = useState({ result_lot_name: '', target_tank_id: '' })

  async function kupajOlustur(e: FormEvent) {
    e.preventDefault()
    setHata('')
    try {
      const gecerli = bilesenler.filter((b) => b.source_lot_id && b.volume_l)
      if (gecerli.length < 2) {
        setHata(t('recete.hata.enazikibilesen'))
        return
      }
      await api.post('/blends', {
        name: form.name,
        target_tank_id: form.target_tank_id ? Number(form.target_tank_id) : undefined,
        components: gecerli.map((b) => ({
          source_lot_id: Number(b.source_lot_id),
          volume_l: Number(b.volume_l),
        })),
      })
      setKipAcik(false)
      setBilesenler([
        { source_lot_id: '', volume_l: '' },
        { source_lot_id: '', volume_l: '' },
      ])
      void istemci.invalidateQueries({ queryKey: ['/blends'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  async function kupajOnayla(id: number, kabul: boolean) {
    try {
      await api.post(`/blends/${id}/approval`, { approve: kabul })
      void istemci.invalidateQueries({ queryKey: ['/blends'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  async function kupajUygula(e: FormEvent) {
    e.preventDefault()
    if (!uygulaId) return
    setHata('')
    try {
      await api.post(`/blends/${uygulaId}/execute`, {
        result_lot_name: uygula.result_lot_name,
        target_tank_id: uygula.target_tank_id ? Number(uygula.target_tank_id) : undefined,
      })
      setUygulaId(null)
      void istemci.invalidateQueries({ queryKey: ['/blends'] })
      void istemci.invalidateQueries({ queryKey: ['/lots'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('recete.baslik')}
        aciklama={t('recete.aciklama')}
        eylemler={
          sekme === 'kupaj' && yetkiVar('recipe:write') ? (
            <button type="button" className="dugme dugme-birincil" onClick={() => setKipAcik(true)}>
              <Plus className="h-4 w-4" /> {t('recete.dugme.senaryo')}
            </button>
          ) : null
        }
      />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

      <div className="flex gap-1 border-b" style={{ borderColor: 'var(--kenar)' }}>
        {(
          [
            ['kupaj', t('recete.sekme.kupaj')],
            ['recete', t('recete.sekme.recete')],
          ] as const
        ).map(([k, ad]) => (
          <button
            key={k}
            type="button"
            onClick={() => setSekme(k)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              sekme === k ? 'border-[var(--vurgu)] font-medium text-[var(--vurgu)]' : 'border-transparent'
            }`}
          >
            {ad}
          </button>
        ))}
      </div>

      {sekme === 'kupaj' &&
        (kupajlar.isLoading ? (
          <Yukleniyor />
        ) : (kupajlar.data?.length ?? 0) === 0 ? (
          <Kart>
            <Bos metin={t('recete.bos.kupaj')} ipucu={t('recete.bos.kupajipucu')} />
          </Kart>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {kupajlar.data?.map((k) => (
              <Kart
                key={k.id}
                baslik={`${k.code} — ${k.name}`}
                aciklama={`${sayi(k.planned_volume_l, 0)} L · ${k.components.length} ${t('recete.kart.bilesen')}`}
                sag={
                  <Rozet
                    seviye={
                      k.status === 'uygulandi' ? 'dusuk' : k.status === 'onaylandi' ? 'orta' : undefined
                    }
                  >
                    {etiket(k.status)}
                  </Rozet>
                }
              >
                <table className="tablo mb-3">
                  <thead>
                    <tr>
                      <th>{t('recete.tablo.kaynakparti')}</th>
                      <th className="text-right">{t('recete.tablo.hacim')}</th>
                      <th className="text-right">{t('recete.tablo.oran')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {k.components.map((b) => (
                      <tr key={b.id}>
                        <td>
                          <span className="font-medium">{b.source_lot_code}</span>
                          <span className="ml-1 text-xs" style={{ color: 'var(--metin-2)' }}>
                            {b.source_lot_name}
                          </span>
                        </td>
                        <td className="text-right tabular-nums">{sayi(b.volume_l, 0)}</td>
                        <td className="text-right tabular-nums">
                          {b.percentage !== null ? `%${b.percentage.toFixed(1)}` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="grid grid-cols-4 gap-2 text-center">
                  {[
                    [t('recete.olcut.alkol'), k.predicted_alcohol ? `${sayi(k.predicted_alcohol, 2)} %` : '—'],
                    [t('recete.olcut.ph'), sayi(k.predicted_ph, 2)],
                    [t('recete.olcut.ta'), k.predicted_ta ? `${sayi(k.predicted_ta, 2)} g/L` : '—'],
                    [t('recete.olcut.maliyet'), k.estimated_cost ? para(k.estimated_cost) : '—'],
                  ].map(([ad, deger]) => (
                    <div key={ad} className="rounded-lg p-2" style={{ background: 'var(--yuzey-3)' }}>
                      <p className="text-[10px]" style={{ color: 'var(--metin-2)' }}>
                        {ad}
                      </p>
                      <p className="text-sm font-semibold">{deger}</p>
                    </div>
                  ))}
                </div>

                <p className="mt-2 text-[11px]" style={{ color: 'var(--metin-2)' }}>
                  {t('recete.not.tahmin')}
                </p>

                {(k.status === 'senaryo' || k.status === 'onay_bekliyor') && yetkiVar('recipe:approve') && (
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      className="dugme dugme-birincil"
                      onClick={() => kupajOnayla(k.id, true)}
                    >
                      <Check className="h-4 w-4" /> {t('genel.onayla')}
                    </button>
                    <button
                      type="button"
                      className="dugme dugme-ikincil"
                      onClick={() => kupajOnayla(k.id, false)}
                    >
                      {t('genel.reddet')}
                    </button>
                  </div>
                )}

                {k.status === 'onaylandi' && yetkiVar('recipe:write') && (
                  <button
                    type="button"
                    className="dugme dugme-birincil mt-3"
                    onClick={() => {
                      setUygulaId(k.id)
                      setUygula({
                        result_lot_name: `${k.name} (${t('recete.varsayilan.kupajeki')})`,
                        target_tank_id: '',
                      })
                    }}
                  >
                    <Play className="h-4 w-4" /> {t('recete.dugme.uygula')}
                  </button>
                )}

                {k.executed_at && (
                  <p className="mt-3 text-xs" style={{ color: 'var(--metin-2)' }}>
                    {t('recete.kart.uygulandi')}: {tarihSaat(k.executed_at)}
                  </p>
                )}
              </Kart>
            ))}
          </div>
        ))}

      {sekme === 'recete' &&
        (receteler.isLoading ? (
          <Yukleniyor />
        ) : (receteler.data?.length ?? 0) === 0 ? (
          <Kart>
            <Bos metin={t('recete.bos.recete')} />
          </Kart>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {receteler.data?.map((r) => (
              <Kart
                key={String(r.id)}
                baslik={`${String(r.code)} — ${String(r.name)} (v${String(r.version)})`}
                aciklama={`${etiket(String(r.wine_type))} · ${t('recete.kart.hedef')} ${sayi(r.target_volume_l as number, 0)} L`}
                sag={<Rozet seviye={r.status === 'onaylandi' ? 'dusuk' : undefined}>{etiket(String(r.status))}</Rozet>}
              >
                <table className="tablo">
                  <thead>
                    <tr>
                      <th>{t('recete.recetetablo.bilesen')}</th>
                      <th>{t('recete.recetetablo.tur')}</th>
                      <th className="text-right">{t('recete.recetetablo.oranmiktar')}</th>
                      <th className="text-right">{t('recete.recetetablo.maliyet')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(r.items as Record<string, unknown>[]).map((i, idx) => (
                      <tr key={idx}>
                        <td>{String(i.name)}</td>
                        <td>{etiket(String(i.item_kind))}</td>
                        <td className="text-right tabular-nums">
                          {i.percentage ? `%${sayi(i.percentage as number, 1)}` : `${sayi(i.amount as number)} ${String(i.unit)}`}
                        </td>
                        <td className="text-right tabular-nums">{para(i.line_cost as number)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {Array.isArray(r.process_steps) && r.process_steps.length > 0 && (
                  <ol className="mt-3 space-y-1 text-xs" style={{ color: 'var(--metin-2)' }}>
                    {(r.process_steps as Record<string, unknown>[]).map((a, i) => (
                      <li key={i}>
                        {String(a.no)}. {String(a.islem)} — {String(a.sure_gun)} {t('recete.birim.gun')}
                      </li>
                    ))}
                  </ol>
                )}
              </Kart>
            ))}
          </div>
        ))}

      {/* ------------------------------------------------------ kupaj oluştur */}
      <Kip acik={kipAcik} baslik={t('recete.kip.olustur')} onKapat={() => setKipAcik(false)} genis>
        <form onSubmit={kupajOlustur} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}
          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('recete.alan.senaryoadi')} gerekli>
              <input
                className="girdi"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                minLength={2}
              />
            </Alan>
            <Alan etiket={t('recete.alan.hedeftank')}>
              <select
                className="girdi"
                value={form.target_tank_id}
                onChange={(e) => setForm({ ...form, target_tank_id: e.target.value })}
              >
                <option value="">—</option>
                {tankSecenek.data?.map((tk) => (
                  <option key={tk.id} value={tk.id}>
                    {tk.ad} ({sayi(Number(tk.ham.free_capacity_l), 0)} L {t('recete.secim.bos')})
                  </option>
                ))}
              </select>
            </Alan>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium">{t('recete.bilesen.baslik')}</p>
            {bilesenler.map((b, i) => (
              <div key={i} className="mb-2 grid gap-2 sm:grid-cols-[2fr_1fr_auto]">
                <select
                  className="girdi"
                  value={b.source_lot_id}
                  onChange={(e) => {
                    const y = [...bilesenler]
                    y[i] = { ...y[i], source_lot_id: e.target.value }
                    setBilesenler(y)
                  }}
                >
                  <option value="">{t('recete.secim.partiseciniz')}</option>
                  {partiSecenek.data?.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.ad} — {String(p.ham.name)} ({sayi(Number(p.ham.volume_l), 0)} L)
                    </option>
                  ))}
                </select>
                <input
                  className="girdi"
                  type="number"
                  step="0.1"
                  placeholder={t('recete.alan.hacim')}
                  value={b.volume_l}
                  onChange={(e) => {
                    const y = [...bilesenler]
                    y[i] = { ...y[i], volume_l: e.target.value }
                    setBilesenler(y)
                  }}
                />
                <button
                  type="button"
                  className="dugme dugme-ikincil"
                  onClick={() => setBilesenler(bilesenler.filter((_, j) => j !== i))}
                  disabled={bilesenler.length <= 2}
                >
                  −
                </button>
              </div>
            ))}
            <button
              type="button"
              className="dugme dugme-ikincil"
              onClick={() => setBilesenler([...bilesenler, { source_lot_id: '', volume_l: '' }])}
            >
              <Plus className="h-3.5 w-3.5" /> {t('recete.dugme.bilesenekle')}
            </button>
          </div>

          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setKipAcik(false)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('recete.dugme.senaryoolustur')}
            </button>
          </div>
        </form>
      </Kip>

      {/* -------------------------------------------------------- kupaj uygula */}
      <Kip acik={uygulaId !== null} baslik={t('recete.kip.uygula')} onKapat={() => setUygulaId(null)}>
        <form onSubmit={kupajUygula} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}
          <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
            {t('recete.uygula.not')}
          </p>
          <Alan etiket={t('recete.alan.sonucparti')} gerekli>
            <input
              className="girdi"
              value={uygula.result_lot_name}
              onChange={(e) => setUygula({ ...uygula, result_lot_name: e.target.value })}
              required
              minLength={2}
            />
          </Alan>
          <Alan etiket={t('recete.alan.hedeftank')}>
            <select
              className="girdi"
              value={uygula.target_tank_id}
              onChange={(e) => setUygula({ ...uygula, target_tank_id: e.target.value })}
            >
              <option value="">—</option>
              {tankSecenek.data?.map((tk) => (
                <option key={tk.id} value={tk.id}>
                  {tk.ad} ({sayi(Number(tk.ham.free_capacity_l), 0)} L {t('recete.secim.bos')})
                </option>
              ))}
            </select>
          </Alan>
          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setUygulaId(null)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('recete.dugme.uygulaonay')}
            </button>
          </div>
        </form>
      </Kip>
    </div>
  )
}
