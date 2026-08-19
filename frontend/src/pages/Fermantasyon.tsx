import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, LineChart, Plus, Sparkles, Thermometer } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Grafik } from '@/components/Grafik'
import {
  Alan,
  Bos,
  HataKutusu,
  Ilerleme,
  Kart,
  Kip,
  Rozet,
  SayfaBasligi,
  Yukleniyor,
} from '@/components/Ortak'
import { Tablo } from '@/components/Tablo'
import { api, hataMesaji } from '@/lib/api'
import { etiket, sayi, tarih, tarihSaat, yuzde } from '@/lib/bicim'
import { useListe, useSecenekler } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

interface Ferm {
  id: number
  code: string
  lot_code: string | null
  tank_code: string | null
  ferm_type: string
  status: string
  start_date: string
  predicted_end_date: string | null
  initial_brix: number | null
  target_brix: number
  last_brix: number | null
  last_temperature_c: number | null
  last_reading_at: string | null
  temp_min_c: number
  temp_max_c: number
  progress_percent: number
  reading_count: number
  active_alerts: number
  volume_l: number
  yeast_strain: string | null
}

export default function Fermantasyon() {
  const t = useCeviri()
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const [durum, setDurum] = useState('devam_ediyor')
  const [secili, setSecili] = useState<Ferm | null>(null)
  const [olcumAcik, setOlcumAcik] = useState(false)
  const [baslatAcik, setBaslatAcik] = useState(false)
  const [hata, setHata] = useState('')

  const liste = useListe<Ferm>('/fermentations', durum ? { status: durum } : {})
  const partiSecenek = useSecenekler('/lots', 'code')
  const tankSecenek = useSecenekler('/tanks', 'code')

  const egri = useQuery({
    queryKey: ['/fermentations', secili?.id, 'curve'],
    queryFn: async () => (await api.get(`/fermentations/${secili!.id}/curve`)).data,
    enabled: !!secili,
  })

  const [olcum, setOlcum] = useState({
    temperature_c: '',
    brix: '',
    density: '',
    ph: '',
    volatile_acidity: '',
    free_so2: '',
    cap_management: '',
    notes: '',
  })

  const [baslat, setBaslat] = useState({
    lot_id: '',
    tank_id: '',
    initial_brix: '',
    target_brix: '-1',
    temp_min_c: '24',
    temp_max_c: '29',
    yeast_strain: '',
    volume_l: '',
  })

  async function olcumKaydet(e: FormEvent) {
    e.preventDefault()
    if (!secili) return
    setHata('')
    try {
      const govde: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(olcum)) {
        if (!v) continue
        govde[k] = ['cap_management', 'notes'].includes(k) ? v : Number(v)
      }
      await api.post(`/fermentations/${secili.id}/readings`, govde)
      setOlcumAcik(false)
      setOlcum({
        temperature_c: '',
        brix: '',
        density: '',
        ph: '',
        volatile_acidity: '',
        free_so2: '',
        cap_management: '',
        notes: '',
      })
      void istemci.invalidateQueries({ queryKey: ['/fermentations'] })
      void istemci.invalidateQueries({ queryKey: ['pano'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  async function fermBaslat(e: FormEvent) {
    e.preventDefault()
    setHata('')
    try {
      await api.post('/fermentations/start', {
        lot_id: Number(baslat.lot_id),
        tank_id: baslat.tank_id ? Number(baslat.tank_id) : undefined,
        initial_brix: baslat.initial_brix ? Number(baslat.initial_brix) : undefined,
        target_brix: Number(baslat.target_brix),
        temp_min_c: Number(baslat.temp_min_c),
        temp_max_c: Number(baslat.temp_max_c),
        yeast_strain: baslat.yeast_strain || undefined,
        volume_l: baslat.volume_l ? Number(baslat.volume_l) : 0,
      })
      setBaslatAcik(false)
      void istemci.invalidateQueries({ queryKey: ['/fermentations'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  // Grafik serileri ile gösterge (legend) adları birebir eşleşmeli.
  const seriBrix = t('fermantasyon.grafik.brix')
  const seriSicaklik = t('fermantasyon.grafik.sicaklik')
  const seriPh = t('fermantasyon.grafik.ph')

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('fermantasyon.baslik')}
        aciklama={t('fermantasyon.aciklama')}
        eylemler={
          yetkiVar('fermentation:write') ? (
            <button type="button" className="dugme dugme-birincil" onClick={() => setBaslatAcik(true)}>
              <Plus className="h-4 w-4" /> {t('fermantasyon.dugme.baslat')}
            </button>
          ) : null
        }
      />

      <Tablo
        sutunlar={[
          { anahtar: 'code', baslik: t('fermantasyon.tablo.kod'), genislik: '140px' },
          { anahtar: 'lot_code', baslik: t('fermantasyon.tablo.parti'), hucre: (r) => r.lot_code ?? '—' },
          { anahtar: 'tank_code', baslik: t('fermantasyon.tablo.tank'), hucre: (r) => r.tank_code ?? '—' },
          {
            anahtar: 'ferm_type',
            baslik: t('fermantasyon.tablo.tur'),
            gizleKucuk: true,
            hucre: (r) => etiket(r.ferm_type),
          },
          {
            anahtar: 'status',
            baslik: t('fermantasyon.tablo.durum'),
            hucre: (r) => <Rozet>{etiket(r.status)}</Rozet>,
          },
          {
            anahtar: 'start_date',
            baslik: t('fermantasyon.tablo.baslangic'),
            gizleKucuk: true,
            hucre: (r) => tarih(r.start_date),
          },
          {
            anahtar: 'last_brix',
            baslik: t('fermantasyon.tablo.brix'),
            sagaYasli: true,
            hucre: (r) => (
              <span>
                {sayi(r.last_brix, 1)}
                <span className="text-xs" style={{ color: 'var(--metin-2)' }}>
                  {' '}
                  / {sayi(r.target_brix, 1)}
                </span>
              </span>
            ),
          },
          {
            anahtar: 'last_temperature_c',
            baslik: t('fermantasyon.tablo.sicaklik'),
            sagaYasli: true,
            hucre: (r) => {
              if (r.last_temperature_c === null) return '—'
              const disi = r.last_temperature_c > r.temp_max_c || r.last_temperature_c < r.temp_min_c
              return (
                <span className={disi ? 'font-semibold text-amber-600 dark:text-amber-400' : ''}>
                  {disi && <AlertTriangle className="mr-1 inline h-3 w-3" />}
                  {sayi(r.last_temperature_c, 1)} °C
                </span>
              )
            },
          },
          {
            anahtar: 'progress_percent',
            baslik: t('fermantasyon.tablo.ilerleme'),
            genislik: '150px',
            hucre: (r) => (
              <div className="flex items-center gap-2">
                <Ilerleme deger={r.progress_percent} />
                <span className="w-10 text-right text-xs tabular-nums">{yuzde(r.progress_percent, 0)}</span>
              </div>
            ),
          },
          {
            anahtar: 'active_alerts',
            baslik: t('fermantasyon.tablo.anomali'),
            sagaYasli: true,
            gizleKucuk: true,
            hucre: (r) => (r.active_alerts > 0 ? <Rozet seviye="uyari">{r.active_alerts}</Rozet> : '—'),
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
        onSatirTikla={(r) => setSecili(r)}
        bosMetin={t('fermantasyon.bos.kayit')}
        ustBar={
          <select
            className="girdi w-auto"
            value={durum}
            onChange={(e) => setDurum(e.target.value)}
            aria-label={t('fermantasyon.filtre.durum')}
          >
            <option value="">{t('fermantasyon.filtre.tumu')}</option>
            <option value="devam_ediyor">{t('fermantasyon.durum.devamediyor')}</option>
            <option value="tamamlandi">{t('fermantasyon.durum.tamamlandi')}</option>
            <option value="planlandi">{t('fermantasyon.durum.planlandi')}</option>
            <option value="durakladi">{t('fermantasyon.durum.durakladi')}</option>
          </select>
        }
      />

      {secili && (
        <Kart
          baslik={
            <span className="flex items-center gap-1.5">
              <LineChart className="h-4 w-4" /> {secili.code} — {t('fermantasyon.kart.egri')}
            </span>
          }
          aciklama={`${secili.lot_code ?? ''} · ${t('fermantasyon.kart.maya')}: ${secili.yeast_strain ?? '—'} · ${sayi(secili.volume_l, 0)} L`}
          sag={
            yetkiVar('fermentation:write') && secili.status === 'devam_ediyor' ? (
              <button type="button" className="dugme dugme-birincil" onClick={() => setOlcumAcik(true)}>
                <Thermometer className="h-4 w-4" /> {t('fermantasyon.dugme.olcumgir')}
              </button>
            ) : null
          }
        >
          {egri.isLoading ? (
            <Yukleniyor />
          ) : !egri.data || egri.data.labels.length === 0 ? (
            <Bos metin={t('fermantasyon.bos.olcum')} ipucu={t('fermantasyon.bos.olcumipucu')} />
          ) : (
            <>
              <Grafik
                yukseklik={340}
                secenek={{
                  tooltip: { trigger: 'axis' },
                  legend: { data: [seriBrix, seriSicaklik, seriPh] },
                  xAxis: {
                    type: 'category',
                    data: egri.data.labels.map((d: string) =>
                      new Date(d).toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' }),
                    ),
                  },
                  yAxis: [
                    { type: 'value', name: seriBrix, position: 'left' },
                    { type: 'value', name: '°C', position: 'right', splitLine: { show: false } },
                  ],
                  series: [
                    {
                      name: seriBrix,
                      type: 'line',
                      smooth: true,
                      data: egri.data.brix,
                      markLine: {
                        silent: true,
                        symbol: 'none',
                        label: { formatter: t('fermantasyon.grafik.hedefbrix') },
                        data: [{ yAxis: egri.data.target_brix }],
                      },
                    },
                    {
                      name: seriSicaklik,
                      type: 'line',
                      yAxisIndex: 1,
                      smooth: true,
                      data: egri.data.temperature,
                      markArea: {
                        silent: true,
                        itemStyle: { color: 'rgba(46,139,111,0.10)' },
                        data: [[{ yAxis: egri.data.temp_min_c }, { yAxis: egri.data.temp_max_c }]],
                      },
                    },
                    { name: seriPh, type: 'line', smooth: true, data: egri.data.ph, yAxisIndex: 1 },
                  ],
                }}
              />
              {egri.data.predicted_end_date ? (
                <div className="mt-3 flex items-start gap-2 rounded-lg border p-3" style={{ borderColor: 'var(--kenar)' }}>
                  <Sparkles className="mt-0.5 h-4 w-4 shrink-0" style={{ color: 'var(--vurgu)' }} />
                  <div>
                    <p className="text-sm font-medium">
                      {t('fermantasyon.tahmin.baslik')}: {tarihSaat(egri.data.predicted_end_date)}
                    </p>
                    <p className="mt-0.5 text-xs" style={{ color: 'var(--metin-2)' }}>
                      {egri.data.prediction_note} — {t('fermantasyon.tahmin.not')}
                    </p>
                  </div>
                </div>
              ) : egri.data.prediction_note ? (
                <div className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300">
                  {egri.data.prediction_note}
                </div>
              ) : null}
              {egri.data.anomalies?.length > 0 && (
                <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
                  {egri.data.anomalies.length} {t('fermantasyon.grafik.anomali')}
                </p>
              )}
            </>
          )}
        </Kart>
      )}

      {/* --------------------------------------------------------- ölçüm formu */}
      <Kip
        acik={olcumAcik}
        baslik={`${t('fermantasyon.kip.olcum')} — ${secili?.code ?? ''}`}
        onKapat={() => setOlcumAcik(false)}
      >
        <form onSubmit={olcumKaydet} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}
          <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
            {t('fermantasyon.olcum.ipucu')}{' '}
            {sayi(secili?.temp_min_c, 1)}–{sayi(secili?.temp_max_c, 1)} °C
          </p>

          <div className="grid gap-3 sm:grid-cols-3">
            <Alan etiket={t('fermantasyon.alan.sicaklik')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                value={olcum.temperature_c}
                onChange={(e) => setOlcum({ ...olcum, temperature_c: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('fermantasyon.alan.brix')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                value={olcum.brix}
                onChange={(e) => setOlcum({ ...olcum, brix: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('fermantasyon.alan.yogunluk')}>
              <input
                className="girdi"
                type="number"
                step="0.0001"
                value={olcum.density}
                onChange={(e) => setOlcum({ ...olcum, density: e.target.value })}
              />
            </Alan>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <Alan etiket={t('fermantasyon.alan.ph')}>
              <input
                className="girdi"
                type="number"
                step="0.01"
                value={olcum.ph}
                onChange={(e) => setOlcum({ ...olcum, ph: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('fermantasyon.alan.ucucuasitlik')}>
              <input
                className="girdi"
                type="number"
                step="0.01"
                value={olcum.volatile_acidity}
                onChange={(e) => setOlcum({ ...olcum, volatile_acidity: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('fermantasyon.alan.serbestso2')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                value={olcum.free_so2}
                onChange={(e) => setOlcum({ ...olcum, free_so2: e.target.value })}
              />
            </Alan>
          </div>

          <Alan etiket={t('fermantasyon.alan.sapkayonetimi')}>
            <input
              className="girdi"
              value={olcum.cap_management}
              onChange={(e) => setOlcum({ ...olcum, cap_management: e.target.value })}
              placeholder="Pigeage / Remontage / Délestage"
            />
          </Alan>

          <Alan etiket={t('fermantasyon.alan.not')}>
            <textarea
              className="girdi"
              rows={2}
              value={olcum.notes}
              onChange={(e) => setOlcum({ ...olcum, notes: e.target.value })}
            />
          </Alan>

          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setOlcumAcik(false)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('fermantasyon.dugme.olcumkaydet')}
            </button>
          </div>
        </form>
      </Kip>

      {/* ---------------------------------------------------- fermantasyon başlat */}
      <Kip acik={baslatAcik} baslik={t('fermantasyon.kip.baslat')} onKapat={() => setBaslatAcik(false)}>
        <form onSubmit={fermBaslat} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

          <Alan etiket={t('fermantasyon.alan.parti')} gerekli>
            <select
              className="girdi"
              value={baslat.lot_id}
              onChange={(e) => setBaslat({ ...baslat, lot_id: e.target.value })}
              required
            >
              <option value="">{t('fermantasyon.secim.seciniz')}</option>
              {partiSecenek.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.ad} — {String(p.ham.name)}
                </option>
              ))}
            </select>
          </Alan>

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('fermantasyon.alan.tank')}>
              <select
                className="girdi"
                value={baslat.tank_id}
                onChange={(e) => setBaslat({ ...baslat, tank_id: e.target.value })}
              >
                <option value="">—</option>
                {tankSecenek.data?.map((tk) => (
                  <option key={tk.id} value={tk.id}>
                    {tk.ad}
                  </option>
                ))}
              </select>
            </Alan>
            <Alan etiket={t('fermantasyon.alan.hacim')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                value={baslat.volume_l}
                onChange={(e) => setBaslat({ ...baslat, volume_l: e.target.value })}
              />
            </Alan>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('fermantasyon.alan.baslangicbrix')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                value={baslat.initial_brix}
                onChange={(e) => setBaslat({ ...baslat, initial_brix: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('fermantasyon.alan.hedefbrix')} ipucu={t('fermantasyon.alan.hedefbrixipucu')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                value={baslat.target_brix}
                onChange={(e) => setBaslat({ ...baslat, target_brix: e.target.value })}
              />
            </Alan>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('fermantasyon.alan.minsicaklik')}>
              <input
                className="girdi"
                type="number"
                step="0.5"
                value={baslat.temp_min_c}
                onChange={(e) => setBaslat({ ...baslat, temp_min_c: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('fermantasyon.alan.makssicaklik')}>
              <input
                className="girdi"
                type="number"
                step="0.5"
                value={baslat.temp_max_c}
                onChange={(e) => setBaslat({ ...baslat, temp_max_c: e.target.value })}
              />
            </Alan>
          </div>

          <Alan etiket={t('fermantasyon.alan.mayasusu')}>
            <input
              className="girdi"
              value={baslat.yeast_strain}
              onChange={(e) => setBaslat({ ...baslat, yeast_strain: e.target.value })}
              placeholder="Saccharomyces cerevisiae EC-1118"
            />
          </Alan>

          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setBaslatAcik(false)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('fermantasyon.dugme.basla')}
            </button>
          </div>
        </form>
      </Kip>
    </div>
  )
}
