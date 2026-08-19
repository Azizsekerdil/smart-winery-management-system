import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Play, Plus, QrCode, Tag } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Alan, HataKutusu, Kip, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { Tablo } from '@/components/Tablo'
import { api, hataMesaji } from '@/lib/api'
import { etiket, sayi, yuzde } from '@/lib/bicim'
import { useListe, useSecenekler } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

interface Emir {
  id: number
  code: string
  lot_code: string | null
  product_name: string
  vintage_year: number
  lot_number: string
  status: string
  bottle_volume_ml: number
  planned_bottles: number
  produced_bottles: number
  rejected_bottles: number
  used_volume_l: number
  loss_l: number
  yield_percent: number
  scrap_percent: number
  line_code: string | null
  started_at: string | null
  finished_at: string | null
  qc_passed: boolean | null
}

export default function Siseleme() {
  const t = useCeviri()
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const [emirAcik, setEmirAcik] = useState(false)
  const [bitirId, setBitirId] = useState<number | null>(null)
  const [etiketId, setEtiketId] = useState<number | null>(null)
  const [hata, setHata] = useState('')

  const liste = useListe<Emir>('/bottling')
  const partiSecenek = useSecenekler('/lots', 'code')
  const kalemSecenek = useSecenekler('/items', 'name')
  const depoSecenek = useSecenekler('/warehouses', 'name')

  const onizleme = useQuery({
    queryKey: ['etiket', etiketId],
    queryFn: async () => (await api.get(`/bottling/${etiketId}/label-preview`)).data,
    enabled: !!etiketId,
  })

  const [emir, setEmir] = useState({
    lot_id: '',
    product_name: '',
    planned_bottles: '',
    bottle_volume_ml: '750',
    bottles_per_case: '6',
    line_code: 'HAT-1',
    bottle_item_id: '',
    closure_item_id: '',
    capsule_item_id: '',
    label_item_id: '',
    case_item_id: '',
    barcode: '',
  })

  const [bitir, setBitir] = useState({
    produced_bottles: '',
    rejected_bottles: '0',
    loss_l: '0',
    qc_passed: true,
    qc_notes: '',
    target_warehouse_id: '',
  })

  async function emirOlustur(e: FormEvent) {
    e.preventDefault()
    setHata('')
    try {
      const govde: Record<string, unknown> = {
        lot_id: Number(emir.lot_id),
        product_name: emir.product_name,
        planned_bottles: Number(emir.planned_bottles),
        bottle_volume_ml: Number(emir.bottle_volume_ml),
        bottles_per_case: Number(emir.bottles_per_case),
        line_code: emir.line_code || undefined,
        barcode: emir.barcode || undefined,
      }
      for (const alan of ['bottle_item_id', 'closure_item_id', 'capsule_item_id', 'label_item_id', 'case_item_id'] as const) {
        if (emir[alan]) govde[alan] = Number(emir[alan])
      }
      await api.post('/bottling/orders', govde)
      setEmirAcik(false)
      void istemci.invalidateQueries({ queryKey: ['/bottling'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  async function hatBaslat(id: number) {
    try {
      await api.post(`/bottling/${id}/start`, {})
      void istemci.invalidateQueries({ queryKey: ['/bottling'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  async function hatBitir(e: FormEvent) {
    e.preventDefault()
    if (!bitirId) return
    setHata('')
    try {
      await api.post(`/bottling/${bitirId}/finish`, {
        produced_bottles: Number(bitir.produced_bottles),
        rejected_bottles: Number(bitir.rejected_bottles || 0),
        loss_l: Number(bitir.loss_l || 0),
        qc_passed: bitir.qc_passed,
        qc_notes: bitir.qc_notes || undefined,
        target_warehouse_id: bitir.target_warehouse_id ? Number(bitir.target_warehouse_id) : undefined,
      })
      setBitirId(null)
      void istemci.invalidateQueries({ queryKey: ['/bottling'] })
      void istemci.invalidateQueries({ queryKey: ['pano'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('siseleme.baslik')}
        aciklama={t('siseleme.aciklama')}
        eylemler={
          yetkiVar('bottling:write') ? (
            <button type="button" className="dugme dugme-birincil" onClick={() => setEmirAcik(true)}>
              <Plus className="h-4 w-4" /> {t('siseleme.dugme.emir')}
            </button>
          ) : null
        }
      />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

      <Tablo
        sutunlar={[
          { anahtar: 'code', baslik: t('siseleme.tablo.emir'), genislik: '130px' },
          { anahtar: 'product_name', baslik: t('siseleme.tablo.urun') },
          {
            anahtar: 'lot_number',
            baslik: t('siseleme.tablo.lotno'),
            hucre: (r) => <span className="font-mono text-xs">{r.lot_number}</span>,
          },
          { anahtar: 'lot_code', baslik: t('siseleme.tablo.parti'), hucre: (r) => r.lot_code ?? '—' },
          {
            anahtar: 'status',
            baslik: t('siseleme.tablo.durum'),
            hucre: (r) => (
              <Rozet
                seviye={
                  r.status === 'tamamlandi' ? 'dusuk' : r.status === 'devam_ediyor' ? 'orta' : undefined
                }
              >
                {etiket(r.status)}
              </Rozet>
            ),
          },
          {
            anahtar: 'planned_bottles',
            baslik: t('siseleme.tablo.planlanan'),
            sagaYasli: true,
            hucre: (r) => sayi(r.planned_bottles, 0),
          },
          {
            anahtar: 'produced_bottles',
            baslik: t('siseleme.tablo.uretilen'),
            sagaYasli: true,
            hucre: (r) => sayi(r.produced_bottles, 0),
          },
          {
            anahtar: 'yield_percent',
            baslik: t('siseleme.tablo.verim'),
            sagaYasli: true,
            hucre: (r) => (r.produced_bottles ? yuzde(r.yield_percent, 0) : '—'),
          },
          {
            anahtar: 'scrap_percent',
            baslik: t('siseleme.tablo.fire'),
            sagaYasli: true,
            gizleKucuk: true,
            hucre: (r) => (r.produced_bottles ? yuzde(r.scrap_percent, 2) : '—'),
          },
          {
            anahtar: 'line_code',
            baslik: t('siseleme.tablo.hat'),
            gizleKucuk: true,
            hucre: (r) => r.line_code ?? '—',
          },
          {
            anahtar: 'islem',
            baslik: t('siseleme.tablo.islem'),
            hucre: (r) => (
              <div className="flex gap-1">
                {yetkiVar('bottling:write') && r.status === 'planlandi' && (
                  <button
                    type="button"
                    className="dugme dugme-ikincil px-2 py-1"
                    onClick={(e) => {
                      e.stopPropagation()
                      void hatBaslat(r.id)
                    }}
                    title={t('siseleme.dugme.hatbaslat')}
                  >
                    <Play className="h-3.5 w-3.5" />
                  </button>
                )}
                {yetkiVar('bottling:write') && r.status === 'devam_ediyor' && (
                  <button
                    type="button"
                    className="dugme dugme-birincil px-2 py-1"
                    onClick={(e) => {
                      e.stopPropagation()
                      setBitirId(r.id)
                      setBitir({ ...bitir, produced_bottles: String(r.planned_bottles) })
                    }}
                    title={t('siseleme.dugme.bitir')}
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  </button>
                )}
                <button
                  type="button"
                  className="dugme dugme-ikincil px-2 py-1"
                  onClick={(e) => {
                    e.stopPropagation()
                    setEtiketId(r.id)
                  }}
                  title={t('siseleme.dugme.etiket')}
                >
                  <Tag className="h-3.5 w-3.5" />
                </button>
                <a
                  href={`/api/v1/bottling/${r.id}/qr.png`}
                  target="_blank"
                  rel="noreferrer"
                  className="dugme dugme-ikincil px-2 py-1"
                  onClick={(e) => e.stopPropagation()}
                  title={t('siseleme.dugme.qr')}
                >
                  <QrCode className="h-3.5 w-3.5" />
                </a>
              </div>
            ),
          },
        ]}
        satirlar={liste.satirlar}
        yukleniyor={liste.isLoading}
        toplam={liste.toplam}
        sayfa={liste.sayfa}
        sayfaBoyu={liste.sayfaBoyu}
        onSayfa={liste.setSayfa}
        arama={liste.arama}
        onArama={liste.setArama}
        bosMetin={t('siseleme.bos.kayit')}
        bosIpucu={t('siseleme.bos.ipucu')}
      />

      {/* ---------------------------------------------------------- emir formu */}
      <Kip acik={emirAcik} baslik={t('siseleme.kip.emir')} onKapat={() => setEmirAcik(false)} genis>
        <form onSubmit={emirOlustur} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('siseleme.alan.parti')} gerekli>
              <select
                className="girdi"
                value={emir.lot_id}
                onChange={(e) => setEmir({ ...emir, lot_id: e.target.value })}
                required
              >
                <option value="">{t('siseleme.secim.seciniz')}</option>
                {partiSecenek.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.ad} — {String(p.ham.name)} ({sayi(Number(p.ham.volume_l), 0)} L)
                  </option>
                ))}
              </select>
            </Alan>
            <Alan etiket={t('siseleme.alan.urunadi')} gerekli>
              <input
                className="girdi"
                value={emir.product_name}
                onChange={(e) => setEmir({ ...emir, product_name: e.target.value })}
                required
                minLength={2}
              />
            </Alan>
          </div>

          <div className="grid gap-3 sm:grid-cols-4">
            <Alan etiket={t('siseleme.alan.planlanansise')} gerekli>
              <input
                className="girdi"
                type="number"
                min="1"
                value={emir.planned_bottles}
                onChange={(e) => setEmir({ ...emir, planned_bottles: e.target.value })}
                required
              />
            </Alan>
            <Alan etiket={t('siseleme.alan.sisehacmi')}>
              <input
                className="girdi"
                type="number"
                value={emir.bottle_volume_ml}
                onChange={(e) => setEmir({ ...emir, bottle_volume_ml: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('siseleme.alan.koliadedi')}>
              <input
                className="girdi"
                type="number"
                value={emir.bottles_per_case}
                onChange={(e) => setEmir({ ...emir, bottles_per_case: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('siseleme.alan.hatkodu')}>
              <input
                className="girdi"
                value={emir.line_code}
                onChange={(e) => setEmir({ ...emir, line_code: e.target.value })}
              />
            </Alan>
          </div>

          <p className="text-xs font-medium">{t('siseleme.ambalaj.baslik')}</p>
          <div className="grid gap-3 sm:grid-cols-3">
            {(
              [
                ['bottle_item_id', t('siseleme.ambalaj.sise')],
                ['closure_item_id', t('siseleme.ambalaj.mantar')],
                ['capsule_item_id', t('siseleme.ambalaj.kapsul')],
                ['label_item_id', t('siseleme.ambalaj.etiket')],
                ['case_item_id', t('siseleme.ambalaj.koli')],
              ] as const
            ).map(([alan, ad]) => (
              <Alan key={alan} etiket={ad}>
                <select
                  className="girdi"
                  value={emir[alan]}
                  onChange={(e) => setEmir({ ...emir, [alan]: e.target.value })}
                >
                  <option value="">—</option>
                  {kalemSecenek.data
                    ?.filter((k) => String(k.ham.category) === 'ambalaj')
                    .map((k) => (
                      <option key={k.id} value={k.id}>
                        {k.ad}
                      </option>
                    ))}
                </select>
              </Alan>
            ))}
            <Alan etiket={t('siseleme.alan.barkod')}>
              <input
                className="girdi"
                value={emir.barcode}
                onChange={(e) => setEmir({ ...emir, barcode: e.target.value })}
                placeholder="8690000000000"
              />
            </Alan>
          </div>

          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setEmirAcik(false)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('siseleme.dugme.emirolustur')}
            </button>
          </div>
        </form>
      </Kip>

      {/* --------------------------------------------------------- hat bitirme */}
      <Kip acik={bitirId !== null} baslik={t('siseleme.kip.bitir')} onKapat={() => setBitirId(null)}>
        <form onSubmit={hatBitir} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}
          <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
            {t('siseleme.bitir.not')}
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            <Alan etiket={t('siseleme.alan.uretilensise')} gerekli>
              <input
                className="girdi"
                type="number"
                min="0"
                value={bitir.produced_bottles}
                onChange={(e) => setBitir({ ...bitir, produced_bottles: e.target.value })}
                required
              />
            </Alan>
            <Alan etiket={t('siseleme.alan.rededilen')}>
              <input
                className="girdi"
                type="number"
                min="0"
                value={bitir.rejected_bottles}
                onChange={(e) => setBitir({ ...bitir, rejected_bottles: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('siseleme.alan.fire')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                min="0"
                value={bitir.loss_l}
                onChange={(e) => setBitir({ ...bitir, loss_l: e.target.value })}
              />
            </Alan>
          </div>
          <Alan etiket={t('siseleme.alan.hedefdepo')}>
            <select
              className="girdi"
              value={bitir.target_warehouse_id}
              onChange={(e) => setBitir({ ...bitir, target_warehouse_id: e.target.value })}
            >
              <option value="">{t('siseleme.secim.varsayilandepo')}</option>
              {depoSecenek.data?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.ad}
                </option>
              ))}
            </select>
          </Alan>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={bitir.qc_passed}
              onChange={(e) => setBitir({ ...bitir, qc_passed: e.target.checked })}
            />
            {t('siseleme.onay.kalitekontrol')}
          </label>
          <Alan etiket={t('siseleme.alan.kalitenotu')}>
            <textarea
              className="girdi"
              rows={2}
              value={bitir.qc_notes}
              onChange={(e) => setBitir({ ...bitir, qc_notes: e.target.value })}
            />
          </Alan>
          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setBitirId(null)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('siseleme.dugme.tamamla')}
            </button>
          </div>
        </form>
      </Kip>

      {/* ------------------------------------------------------ etiket önizleme */}
      <Kip acik={etiketId !== null} baslik={t('siseleme.kip.etiket')} onKapat={() => setEtiketId(null)}>
        {onizleme.isLoading ? (
          <Yukleniyor />
        ) : onizleme.data ? (
          <div className="space-y-3">
            <div
              className="mx-auto w-72 rounded-lg p-5 text-center shadow-lg"
              style={{
                background: 'linear-gradient(160deg,#fdfbf7,#f0e6d4)',
                color: '#3b0a14',
                border: '1px solid #d0b98f',
              }}
            >
              <p className="text-[10px] uppercase tracking-[0.3em]">{onizleme.data.producer}</p>
              <div className="my-3 h-px" style={{ background: '#971f48' }} />
              <p className="text-lg font-semibold leading-tight">{onizleme.data.product_name}</p>
              <p className="mt-1 text-2xl font-light">{onizleme.data.vintage_year}</p>
              {onizleme.data.variety && (
                <p className="mt-1 text-xs italic">{onizleme.data.variety}</p>
              )}
              <div className="my-3 h-px" style={{ background: '#971f48' }} />
              <p className="text-xs">
                {onizleme.data.bottle_volume_ml} ml
                {onizleme.data.alcohol ? ` · ${sayi(onizleme.data.alcohol, 1)} % vol` : ''}
              </p>
              <p className="mt-1 text-[10px]">{onizleme.data.ingredients_tr}</p>
              <p className="mt-2 text-[9px] font-medium">{onizleme.data.warning_tr}</p>
              <p className="mt-2 font-mono text-[10px]">LOT: {onizleme.data.lot_number}</p>
              {onizleme.data.barcode && (
                <p className="font-mono text-[10px]">{onizleme.data.barcode}</p>
              )}
            </div>
            <p className="text-center text-[11px]" style={{ color: 'var(--metin-2)' }}>
              {t('siseleme.etiket.uyari')}
            </p>
          </div>
        ) : null}
      </Kip>
    </div>
  )
}
