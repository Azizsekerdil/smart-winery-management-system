import { useQuery } from '@tanstack/react-query'
import { Download, FileSpreadsheet, FileText, Table2 } from 'lucide-react'
import { useState } from 'react'
import { Grafik } from '@/components/Grafik'
import { Bos, HataKutusu, Kart, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { api, dosyaIndir, hataMesaji } from '@/lib/api'
import { para, sayi, yuzde } from '@/lib/bicim'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

/** `ad` ve `aciklama` alanları çeviri anahtarı tutar; metne render sırasında çevrilir. */
const RAPORLAR = [
  { kod: 'uretim', ad: 'raporlar.rapor.uretim.ad', aciklama: 'raporlar.rapor.uretim.aciklama' },
  { kod: 'maliyet', ad: 'raporlar.rapor.maliyet.ad', aciklama: 'raporlar.rapor.maliyet.aciklama' },
  { kod: 'stok', ad: 'raporlar.rapor.stok.ad', aciklama: 'raporlar.rapor.stok.aciklama' },
  { kod: 'laboratuvar', ad: 'raporlar.rapor.laboratuvar.ad', aciklama: 'raporlar.rapor.laboratuvar.aciklama' },
  { kod: 'fermantasyon', ad: 'raporlar.rapor.fermantasyon.ad', aciklama: 'raporlar.rapor.fermantasyon.aciklama' },
]

export default function Raporlar() {
  const t = useCeviri()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const [hata, setHata] = useState('')
  const [indiriliyor, setIndiriliyor] = useState('')

  const uretim = useQuery({
    queryKey: ['/reports/production'],
    queryFn: async () => (await api.get('/reports/production')).data,
  })

  const maliyet = useQuery({
    queryKey: ['/reports/cost/summary'],
    queryFn: async () => (await api.get('/reports/cost/summary', { params: { limit: 40 } })).data as Record<string, unknown>[],
    enabled: yetkiVar('cost:read'),
    retry: false,
  })

  async function indir(rapor: string, fmt: string) {
    setHata('')
    setIndiriliyor(`${rapor}-${fmt}`)
    try {
      await dosyaIndir('/reports/export', { report: rapor, fmt })
    } catch (err) {
      setHata(hataMesaji(err))
    } finally {
      setIndiriliyor('')
    }
  }

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('raporlar.baslik')}
        aciklama={t('raporlar.aciklama')}
      />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

      {/* ------------------------------------------------------ üretim özeti */}
      {uretim.isLoading ? (
        <Yukleniyor />
      ) : uretim.data ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {[
              [t('raporlar.ozet.uzumkabulu'), `${sayi(uretim.data.intake_kg, 0)} kg`],
              [t('raporlar.ozet.kabulsayisi'), sayi(uretim.data.intake_count, 0)],
              [t('raporlar.ozet.siselenen'), `${sayi(uretim.data.bottles_produced, 0)} ${t('raporlar.birim.sise')}`],
              [t('raporlar.ozet.aktifparti'), sayi(uretim.data.active_lots, 0)],
              [
                t('raporlar.ozet.verim'),
                uretim.data.yield_l_per_kg ? `${sayi(uretim.data.yield_l_per_kg, 3)} L/kg` : '—',
              ],
            ].map(([ad, deger]) => (
              <div key={ad} className="kart p-4">
                <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
                  {ad}
                </p>
                <p className="mt-1 text-xl font-semibold">{deger}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Kart baslik={t('raporlar.grafik.cesit')}>
              <Grafik
                veriVar={uretim.data.by_variety.length > 0}
                secenek={{
                  tooltip: { trigger: 'item', valueFormatter: (v) => `${sayi(v, 0)} kg` },
                  legend: { orient: 'vertical', right: 0, top: 'center', type: 'scroll' },
                  series: [
                    {
                      type: 'pie',
                      radius: ['45%', '72%'],
                      center: ['36%', '52%'],
                      label: { show: false },
                      itemStyle: { borderRadius: 6, borderWidth: 2 },
                      data: uretim.data.by_variety.map((v: { label: string; value: number }) => ({
                        name: v.label,
                        value: v.value,
                      })),
                    },
                  ],
                }}
              />
            </Kart>

            <Kart baslik={t('raporlar.grafik.aylik')}>
              <Grafik
                veriVar={uretim.data.by_month.length > 0}
                secenek={{
                  tooltip: { trigger: 'axis', valueFormatter: (v) => `${sayi(v, 0)} kg` },
                  xAxis: {
                    type: 'category',
                    data: uretim.data.by_month.map((m: { label: string }) => m.label),
                  },
                  yAxis: { type: 'value' },
                  series: [
                    {
                      type: 'bar',
                      data: uretim.data.by_month.map((m: { value: number }) => m.value),
                      itemStyle: { borderRadius: [4, 4, 0, 0] },
                    },
                  ],
                }}
              />
            </Kart>
          </div>
        </>
      ) : null}

      {/* ---------------------------------------------------- maliyet tablosu */}
      {yetkiVar('cost:read') && (
        <Kart baslik={t('raporlar.maliyet.baslik')} govdeSinif="p-0">
          {maliyet.isLoading ? (
            <Yukleniyor />
          ) : (maliyet.data?.length ?? 0) === 0 ? (
            <Bos metin={t('raporlar.maliyet.bos')} />
          ) : (
            <div className="overflow-x-auto">
              <table className="tablo">
                <thead>
                  <tr>
                    <th>{t('raporlar.maliyet.parti')}</th>
                    <th>{t('raporlar.maliyet.ad')}</th>
                    <th className="text-right">{t('raporlar.maliyet.rekolte')}</th>
                    <th className="text-right">{t('raporlar.maliyet.hacim')}</th>
                    <th className="text-right">{t('raporlar.maliyet.toplammaliyet')}</th>
                    <th className="text-right">{t('raporlar.maliyet.tryl')}</th>
                    <th className="text-right">{t('raporlar.maliyet.trysise')}</th>
                    <th className="text-right">{t('raporlar.maliyet.sise')}</th>
                    <th className="text-right">{t('raporlar.maliyet.fire')}</th>
                  </tr>
                </thead>
                <tbody>
                  {maliyet.data?.map((m) => (
                    <tr key={String(m.lot_id)}>
                      <td className="font-mono text-xs">{String(m.lot_code)}</td>
                      <td>{String(m.lot_name)}</td>
                      <td className="text-right">{String(m.vintage_year)}</td>
                      <td className="text-right tabular-nums">{sayi(m.volume_l as number, 0)}</td>
                      <td className="text-right tabular-nums font-medium">{para(m.total_cost as number)}</td>
                      <td className="text-right tabular-nums">{para(m.cost_per_liter as number)}</td>
                      <td className="text-right tabular-nums">
                        {m.cost_per_bottle ? para(m.cost_per_bottle as number) : '—'}
                      </td>
                      <td className="text-right tabular-nums">{sayi(m.bottles_produced as number, 0)}</td>
                      <td className="text-right tabular-nums">{yuzde(m.loss_percent as number)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Kart>
      )}

      {/* ------------------------------------------------------- dışa aktarma */}
      <Kart
        baslik={t('raporlar.disaaktar.baslik')}
        aciklama={t('raporlar.disaaktar.aciklama')}
      >
        {!yetkiVar('report:export') ? (
          <Bos metin={t('raporlar.disaaktar.yetkiyok')} />
        ) : (
          <div className="space-y-2">
            {RAPORLAR.map((r) => (
              <div
                key={r.kod}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3"
                style={{ borderColor: 'var(--kenar)' }}
              >
                <div>
                  <p className="text-sm font-medium">{t(r.ad)}</p>
                  <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
                    {t(r.aciklama)}
                  </p>
                </div>
                <div className="flex gap-2">
                  {(
                    [
                      ['xlsx', 'Excel', <FileSpreadsheet key="x" className="h-3.5 w-3.5" />],
                      ['csv', 'CSV', <Table2 key="c" className="h-3.5 w-3.5" />],
                      ['pdf', 'PDF', <FileText key="p" className="h-3.5 w-3.5" />],
                    ] as const
                  ).map(([fmt, ad, simge]) => (
                    <button
                      key={fmt}
                      type="button"
                      className="dugme dugme-ikincil text-xs"
                      onClick={() => indir(r.kod, fmt)}
                      disabled={indiriliyor === `${r.kod}-${fmt}`}
                    >
                      {indiriliyor === `${r.kod}-${fmt}` ? (
                        <Download className="h-3.5 w-3.5 animate-bounce" />
                      ) : (
                        simge
                      )}
                      {ad}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Kart>
    </div>
  )
}
