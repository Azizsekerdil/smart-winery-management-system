import { useQueryClient } from '@tanstack/react-query'
import { Plus, QrCode } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Alan, HataKutusu, Kip, Rozet, SayfaBasligi } from '@/components/Ortak'
import { Tablo } from '@/components/Tablo'
import { api, hataMesaji } from '@/lib/api'
import { etiket, para, sayi, tarih } from '@/lib/bicim'
import { useListe, useSecenekler } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

type Sekme = 'kabul' | 'bag' | 'parsel' | 'cesit'

interface Kabul {
  id: number
  code: string
  harvest_date: string
  variety_name: string | null
  vineyard_name: string | null
  net_weight_kg: number
  brix: number | null
  ph: number | null
  quality_grade: string
  total_cost: number
  vintage_year: number
}

export default function Bag() {
  const t = useCeviri()
  const [sekme, setSekme] = useState<Sekme>('kabul')
  const [kipAcik, setKipAcik] = useState(false)
  const [hata, setHata] = useState('')
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)

  const kabuller = useListe<Kabul>('/harvest-intakes')
  const baglar = useListe<Record<string, unknown>>('/vineyards', {}, { etkin: sekme === 'bag' })
  const parseller = useListe<Record<string, unknown>>('/parcels', {}, { etkin: sekme === 'parsel' })
  const cesitler = useListe<Record<string, unknown>>('/varieties', {}, { etkin: sekme === 'cesit' })

  const cesitSecenek = useSecenekler('/varieties')
  const bagSecenek = useSecenekler('/vineyards')
  const parselSecenek = useSecenekler('/parcels')

  const [form, setForm] = useState({
    variety_id: '',
    vineyard_id: '',
    parcel_id: '',
    harvest_date: new Date().toISOString().slice(0, 10),
    net_weight_kg: '',
    brix: '',
    ph: '',
    total_acidity: '',
    temperature_c: '',
    quality_grade: 'A',
    unit_price: '',
    vehicle_plate: '',
    notes: '',
  })

  async function kabulKaydet(e: FormEvent) {
    e.preventDefault()
    setHata('')
    try {
      const govde: Record<string, unknown> = {
        variety_id: Number(form.variety_id),
        harvest_date: form.harvest_date,
        net_weight_kg: Number(form.net_weight_kg),
        quality_grade: form.quality_grade,
      }
      if (form.vineyard_id) govde.vineyard_id = Number(form.vineyard_id)
      if (form.parcel_id) govde.parcel_id = Number(form.parcel_id)
      for (const alan of ['brix', 'ph', 'total_acidity', 'temperature_c', 'unit_price'] as const) {
        if (form[alan]) govde[alan] = Number(form[alan])
      }
      if (form.vehicle_plate) govde.vehicle_plate = form.vehicle_plate
      if (form.notes) govde.notes = form.notes

      await api.post('/harvest-intakes', govde)
      setKipAcik(false)
      void istemci.invalidateQueries({ queryKey: ['/harvest-intakes'] })
      void istemci.invalidateQueries({ queryKey: ['pano'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  const sekmeler: { anahtar: Sekme; ad: string }[] = [
    { anahtar: 'kabul', ad: t('bag.sekme.kabul') },
    { anahtar: 'bag', ad: t('bag.sekme.bag') },
    { anahtar: 'parsel', ad: t('bag.sekme.parsel') },
    { anahtar: 'cesit', ad: t('bag.sekme.cesit') },
  ]

  return (
    <div>
      <SayfaBasligi
        baslik={t('bag.baslik')}
        aciklama={t('bag.aciklama')}
        eylemler={
          sekme === 'kabul' && yetkiVar('harvest:write') ? (
            <button type="button" className="dugme dugme-birincil" onClick={() => setKipAcik(true)}>
              <Plus className="h-4 w-4" /> {t('bag.dugme.kabul')}
            </button>
          ) : null
        }
      />

      <div className="mb-4 flex flex-wrap gap-1 border-b" style={{ borderColor: 'var(--kenar)' }}>
        {sekmeler.map((s) => (
          <button
            key={s.anahtar}
            type="button"
            onClick={() => setSekme(s.anahtar)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm transition-colors ${
              sekme === s.anahtar
                ? 'border-[var(--vurgu)] font-medium text-[var(--vurgu)]'
                : 'border-transparent hover:text-[var(--vurgu)]'
            }`}
          >
            {s.ad}
          </button>
        ))}
      </div>

      {sekme === 'kabul' && (
        <Tablo
          sutunlar={[
            { anahtar: 'code', baslik: t('bag.tablo.kod'), genislik: '140px' },
            { anahtar: 'harvest_date', baslik: t('bag.tablo.hasat'), hucre: (r) => tarih(r.harvest_date) },
            { anahtar: 'variety_name', baslik: t('bag.tablo.cesit'), hucre: (r) => r.variety_name ?? '—' },
            { anahtar: 'vineyard_name', baslik: t('bag.tablo.bag'), gizleKucuk: true, hucre: (r) => r.vineyard_name ?? '—' },
            { anahtar: 'net_weight_kg', baslik: t('bag.tablo.netkg'), sagaYasli: true, hucre: (r) => sayi(r.net_weight_kg, 0) },
            { anahtar: 'brix', baslik: t('bag.tablo.brix'), sagaYasli: true, hucre: (r) => sayi(r.brix, 1) },
            { anahtar: 'ph', baslik: t('bag.tablo.ph'), sagaYasli: true, hucre: (r) => sayi(r.ph, 2) },
            {
              anahtar: 'quality_grade',
              baslik: t('bag.tablo.kalite'),
              hucre: (r) => (
                <Rozet seviye={r.quality_grade === 'A' ? 'dusuk' : r.quality_grade === 'red' ? 'kritik' : 'orta'}>
                  {r.quality_grade === 'red' ? t('bag.kalite.red') : r.quality_grade}
                </Rozet>
              ),
            },
            { anahtar: 'total_cost', baslik: t('bag.tablo.tutar'), sagaYasli: true, gizleKucuk: true, hucre: (r) => para(r.total_cost) },
            {
              anahtar: 'qr',
              baslik: t('bag.tablo.qr'),
              genislik: '60px',
              hucre: (r) => (
                <a
                  href={`/api/v1/harvest-intakes/${r.id}/qr.png`}
                  target="_blank"
                  rel="noreferrer"
                  title={t('bag.tablo.qrac')}
                  onClick={(e) => e.stopPropagation()}
                >
                  <QrCode className="h-4 w-4 opacity-70 hover:opacity-100" />
                </a>
              ),
            },
          ]}
          satirlar={kabuller.satirlar}
          yukleniyor={kabuller.isLoading}
          toplam={kabuller.toplam}
          sayfa={kabuller.sayfa}
          sayfaBoyu={kabuller.sayfaBoyu}
          onSayfa={kabuller.setSayfa}
          arama={kabuller.arama}
          onArama={kabuller.setArama}
          aramaIpucu={t('bag.arama.kabul')}
          bosMetin={t('bag.bos.kabul')}
          bosIpucu={t('bag.bos.kabulipucu')}
        />
      )}

      {sekme === 'bag' && (
        <Tablo
          sutunlar={[
            { anahtar: 'code', baslik: t('bag.tablo.kod'), genislik: '110px' },
            { anahtar: 'name', baslik: t('bag.tablo.bagadi') },
            { anahtar: 'region', baslik: t('bag.tablo.bolge') },
            { anahtar: 'village', baslik: t('bag.tablo.koy'), gizleKucuk: true },
            { anahtar: 'altitude_m', baslik: t('bag.tablo.rakim'), sagaYasli: true, hucre: (r) => sayi(r.altitude_m as number, 0) },
            { anahtar: 'total_area_da', baslik: t('bag.tablo.alan'), sagaYasli: true, hucre: (r) => sayi(r.total_area_da as number) },
            { anahtar: 'parcel_count', baslik: t('bag.tablo.parsel'), sagaYasli: true },
            { anahtar: 'soil_type', baslik: t('bag.tablo.toprak'), gizleKucuk: true },
          ]}
          satirlar={baglar.satirlar}
          yukleniyor={baglar.isLoading}
          toplam={baglar.toplam}
          sayfa={baglar.sayfa}
          sayfaBoyu={baglar.sayfaBoyu}
          onSayfa={baglar.setSayfa}
          arama={baglar.arama}
          onArama={baglar.setArama}
          bosMetin={t('bag.bos.bag')}
        />
      )}

      {sekme === 'parsel' && (
        <Tablo
          sutunlar={[
            { anahtar: 'code', baslik: t('bag.tablo.kod'), genislik: '110px' },
            { anahtar: 'name', baslik: t('bag.tablo.parselad') },
            { anahtar: 'vineyard_name', baslik: t('bag.tablo.bag') },
            { anahtar: 'variety_name', baslik: t('bag.tablo.cesit') },
            { anahtar: 'area_da', baslik: t('bag.tablo.alan'), sagaYasli: true, hucre: (r) => sayi(r.area_da as number) },
            { anahtar: 'planting_year', baslik: t('bag.tablo.dikim'), sagaYasli: true, gizleKucuk: true },
            { anahtar: 'vine_count', baslik: t('bag.tablo.omca'), sagaYasli: true, gizleKucuk: true, hucre: (r) => sayi(r.vine_count as number, 0) },
          ]}
          satirlar={parseller.satirlar}
          yukleniyor={parseller.isLoading}
          toplam={parseller.toplam}
          sayfa={parseller.sayfa}
          sayfaBoyu={parseller.sayfaBoyu}
          onSayfa={parseller.setSayfa}
          arama={parseller.arama}
          onArama={parseller.setArama}
          bosMetin={t('bag.bos.parsel')}
        />
      )}

      {sekme === 'cesit' && (
        <Tablo
          sutunlar={[
            { anahtar: 'code', baslik: t('bag.tablo.kod'), genislik: '110px' },
            { anahtar: 'name', baslik: t('bag.tablo.cesit') },
            { anahtar: 'color', baslik: t('bag.tablo.renk'), hucre: (r) => etiket(r.color as string) },
            { anahtar: 'origin', baslik: t('bag.tablo.mense') },
            {
              anahtar: 'brix',
              baslik: t('bag.tablo.hedefbrix'),
              hucre: (r) =>
                r.target_brix_min ? `${sayi(r.target_brix_min as number, 1)}–${sayi(r.target_brix_max as number, 1)}` : '—',
            },
            {
              anahtar: 'ph',
              baslik: t('bag.tablo.hedefph'),
              gizleKucuk: true,
              hucre: (r) =>
                r.target_ph_min ? `${sayi(r.target_ph_min as number, 2)}–${sayi(r.target_ph_max as number, 2)}` : '—',
            },
          ]}
          satirlar={cesitler.satirlar}
          yukleniyor={cesitler.isLoading}
          toplam={cesitler.toplam}
          sayfa={cesitler.sayfa}
          sayfaBoyu={cesitler.sayfaBoyu}
          onSayfa={cesitler.setSayfa}
          arama={cesitler.arama}
          onArama={cesitler.setArama}
          bosMetin={t('bag.bos.cesit')}
        />
      )}

      {/* ------------------------------------------------------- kabul formu */}
      <Kip acik={kipAcik} baslik={t('bag.kip.baslik')} onKapat={() => setKipAcik(false)} genis>
        <form onSubmit={kabulKaydet} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

          <div className="grid gap-3 sm:grid-cols-3">
            <Alan etiket={t('bag.form.cesit')} gerekli>
              <select
                className="girdi"
                value={form.variety_id}
                onChange={(e) => setForm({ ...form, variety_id: e.target.value })}
                required
              >
                <option value="">{t('bag.form.seciniz')}</option>
                {cesitSecenek.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.ad}
                  </option>
                ))}
              </select>
            </Alan>
            <Alan etiket={t('bag.form.bag')}>
              <select
                className="girdi"
                value={form.vineyard_id}
                onChange={(e) => setForm({ ...form, vineyard_id: e.target.value })}
              >
                <option value="">—</option>
                {bagSecenek.data?.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.ad}
                  </option>
                ))}
              </select>
            </Alan>
            <Alan etiket={t('bag.form.parsel')}>
              <select
                className="girdi"
                value={form.parcel_id}
                onChange={(e) => setForm({ ...form, parcel_id: e.target.value })}
              >
                <option value="">—</option>
                {parselSecenek.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.ad}
                  </option>
                ))}
              </select>
            </Alan>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <Alan etiket={t('bag.form.hasattarihi')} gerekli>
              <input
                className="girdi"
                type="date"
                value={form.harvest_date}
                onChange={(e) => setForm({ ...form, harvest_date: e.target.value })}
                required
              />
            </Alan>
            <Alan etiket={t('bag.form.netagirlik')} gerekli>
              <input
                className="girdi"
                type="number"
                step="0.01"
                min="0.01"
                value={form.net_weight_kg}
                onChange={(e) => setForm({ ...form, net_weight_kg: e.target.value })}
                required
              />
            </Alan>
            <Alan etiket={t('bag.form.plaka')}>
              <input
                className="girdi"
                value={form.vehicle_plate}
                onChange={(e) => setForm({ ...form, vehicle_plate: e.target.value })}
                placeholder={t('bag.form.plakaornek')}
              />
            </Alan>
          </div>

          <div className="grid gap-3 sm:grid-cols-4">
            <Alan etiket={t('bag.form.brix')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                value={form.brix}
                onChange={(e) => setForm({ ...form, brix: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('bag.form.ph')}>
              <input
                className="girdi"
                type="number"
                step="0.01"
                value={form.ph}
                onChange={(e) => setForm({ ...form, ph: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('bag.form.asitlik')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                value={form.total_acidity}
                onChange={(e) => setForm({ ...form, total_acidity: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('bag.form.sicaklik')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                value={form.temperature_c}
                onChange={(e) => setForm({ ...form, temperature_c: e.target.value })}
              />
            </Alan>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('bag.form.kalite')}>
              <select
                className="girdi"
                value={form.quality_grade}
                onChange={(e) => setForm({ ...form, quality_grade: e.target.value })}
              >
                <option value="A">{t('bag.kalite.a')}</option>
                <option value="B">{t('bag.kalite.b')}</option>
                <option value="C">{t('bag.kalite.c')}</option>
                <option value="red">{t('bag.kalite.red')}</option>
              </select>
            </Alan>
            <Alan etiket={t('bag.form.birimfiyat')}>
              <input
                className="girdi"
                type="number"
                step="0.01"
                min="0"
                value={form.unit_price}
                onChange={(e) => setForm({ ...form, unit_price: e.target.value })}
              />
            </Alan>
          </div>

          <Alan etiket={t('bag.form.notlar')}>
            <textarea
              className="girdi"
              rows={2}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </Alan>

          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setKipAcik(false)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('genel.kaydet')}
            </button>
          </div>
        </form>
      </Kip>
    </div>
  )
}
