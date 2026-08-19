import { useQuery } from '@tanstack/react-query'
import type { EChartsOption } from 'echarts'
import { ArrowLeft, GitBranch, QrCode, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Grafik } from '@/components/Grafik'
import { Bos, HataKutusu, Kart, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { api, hataMesaji } from '@/lib/api'
import { asamaEtiketleri, etiket, para, sayi, tarihSaat, yuzde } from '@/lib/bicim'
import { useCeviri } from '@/lib/i18n'

interface Dugum {
  kind: string
  id: number
  code: string
  label: string
  detail: Record<string, unknown>
}
interface Kenar {
  from_key: string
  to_key: string
  relation: string
  volume_l: number | null
  occurred_at: string | null
}

const TUR_RENK: Record<string, string> = {
  uzum_kabul: '#7a56b2',
  parti: '#971f48',
  tank: '#3b7ea1',
  fici: '#d46a28',
  siseleme: '#2e8b6f',
}

export default function PartiDetay() {
  const t = useCeviri()
  const { id } = useParams<{ id: string }>()
  const [yon, setYon] = useState<'tam' | 'geri' | 'ileri'>('tam')

  const parti = useQuery({
    queryKey: ['/lots', id],
    queryFn: async () => (await api.get(`/lots/${id}`)).data,
    enabled: !!id,
  })

  const izleme = useQuery({
    queryKey: ['/lots', id, 'trace', yon],
    queryFn: async () =>
      (await api.get<{ nodes: Dugum[]; edges: Kenar[]; warnings: string[]; root: string }>(
        `/lots/${id}/trace`,
        { params: { direction: yon } },
      )).data,
    enabled: !!id,
  })

  const zaman = useQuery({
    queryKey: ['/lots', id, 'timeline'],
    queryFn: async () => (await api.get(`/lots/${id}/timeline`)).data as Record<string, unknown>[],
    enabled: !!id,
  })

  const maliyet = useQuery({
    queryKey: ['maliyet', id],
    queryFn: async () => (await api.get(`/reports/cost/lot/${id}`)).data,
    enabled: !!id,
    retry: false,
  })

  const risk = useQuery({
    queryKey: ['risk', id],
    queryFn: async () =>
      (await api.post('/ai/insights', { kind: 'riskli_parti', lot_id: Number(id), use_llm: false }))
        .data,
    enabled: !!id,
    retry: false,
  })

  if (parti.isLoading) return <Yukleniyor />
  if (parti.error) return <HataKutusu mesaj={hataMesaji(parti.error)} />
  const p = parti.data

  // Çizge düğüm türlerinin görünen adları
  const TUR_AD: Record<string, string> = {
    uzum_kabul: t('partidetay.tur.kabul'),
    parti: t('partidetay.tur.parti'),
    tank: t('partidetay.tur.tank'),
    fici: t('partidetay.tur.fici'),
    siseleme: t('partidetay.tur.siseleme'),
  }

  // Çizge verisi -> ECharts graph
  const dugumler = izleme.data?.nodes ?? []
  const kenarlar = izleme.data?.edges ?? []
  const anahtarIndeks = new Map(dugumler.map((d) => [`${d.kind}:${d.id}`, d]))

  const grafikSecenek: EChartsOption = {
    tooltip: {
      formatter: (params: unknown) => {
        const p2 = params as {
          dataType?: string
          data?: { ad?: string; ayrinti?: string; iliski?: string }
        }
        if (p2.dataType === 'edge') return String(p2.data?.iliski ?? '')
        return `<b>${p2.data?.ad ?? ''}</b><br/>${p2.data?.ayrinti ?? ''}`
      },
    },
    legend: [
      {
        data: [...new Set(dugumler.map((d) => TUR_AD[d.kind] ?? d.kind))],
        top: 0,
      },
    ],
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        label: { show: true, position: 'bottom', fontSize: 10, formatter: '{b}' },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 8,
        force: { repulsion: 420, edgeLength: 130, gravity: 0.08 },
        categories: [...new Set(dugumler.map((d) => d.kind))].map((k) => ({
          name: TUR_AD[k] ?? k,
          itemStyle: { color: TUR_RENK[k] ?? '#888' },
        })),
        data: dugumler.map((d) => ({
          id: `${d.kind}:${d.id}`,
          name: d.code,
          ad: d.label,
          ayrinti: Object.entries(d.detail)
            .filter(([, v]) => v !== null && v !== undefined)
            .map(([k, v]) => `${k}: ${v}`)
            .join('<br/>'),
          category: [...new Set(dugumler.map((x) => x.kind))].indexOf(d.kind),
          symbolSize: d.kind === 'parti' ? 44 : 30,
          itemStyle: { color: TUR_RENK[d.kind] ?? '#888' },
        })),
        links: kenarlar
          .filter((e) => anahtarIndeks.has(e.from_key) && anahtarIndeks.has(e.to_key))
          .map((e) => ({
            source: e.from_key,
            target: e.to_key,
            iliski: `${etiket(e.relation)}${e.volume_l ? ` · ${sayi(e.volume_l, 0)} L` : ''}`,
            lineStyle: { curveness: 0.12, opacity: 0.75 },
          })),
      },
    ],
  }

  return (
    <div className="space-y-5">
      <Link to="/partiler" className="inline-flex items-center gap-1 text-sm" style={{ color: 'var(--vurgu)' }}>
        <ArrowLeft className="h-4 w-4" /> {t('partidetay.gerilink')}
      </Link>

      <SayfaBasligi
        baslik={`${p.code} — ${p.name}`}
        aciklama={`${p.vintage_year} ${t('partidetay.rekoltesi')} · ${etiket(p.wine_type)} · ${p.variety_name ?? t('partidetay.kupaj')}`}
        eylemler={
          <a
            href={`/api/v1/lots/${id}/qr.png`}
            target="_blank"
            rel="noreferrer"
            className="dugme dugme-ikincil"
          >
            <QrCode className="h-4 w-4" /> {t('partidetay.qrkodu')}
          </a>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        {[
          { ad: t('partidetay.ozet.asama'), deger: asamaEtiketleri()[p.stage] ?? p.stage },
          { ad: t('partidetay.ozet.durum'), deger: etiket(p.status) },
          { ad: t('partidetay.ozet.hacim'), deger: `${sayi(p.volume_l, 0)} L` },
          { ad: t('partidetay.ozet.tank'), deger: p.tank_code ?? '—' },
          { ad: t('partidetay.ozet.ph'), deger: sayi(p.current_ph, 2) },
          {
            ad: t('partidetay.ozet.alkol'),
            deger: p.current_alcohol ? `${sayi(p.current_alcohol, 1)} %vol` : '—',
          },
        ].map((k) => (
          <div key={k.ad} className="kart p-3">
            <p className="text-[11px]" style={{ color: 'var(--metin-2)' }}>
              {k.ad}
            </p>
            <p className="mt-1 text-sm font-semibold">{k.deger}</p>
          </div>
        ))}
      </div>

      {risk.data && risk.data.severity !== 'bilgi' && (
        <Kart
          baslik={
            <span className="flex items-center gap-1.5">
              <Sparkles className="h-4 w-4" style={{ color: 'var(--vurgu)' }} />
              {t('partidetay.risk.baslik')}
            </span>
          }
          aciklama={t('partidetay.risk.aciklama')}
        >
          <div className="flex items-start gap-2">
            <Rozet seviye={risk.data.severity}>{risk.data.numeric?.risk}</Rozet>
            <p className="text-sm">{risk.data.summary}</p>
          </div>
        </Kart>
      )}

      {/* ------------------------------------------------------ izlenebilirlik */}
      <Kart
        baslik={
          <span className="flex items-center gap-1.5">
            <GitBranch className="h-4 w-4" /> {t('partidetay.izleme.baslik')}
          </span>
        }
        aciklama={t('partidetay.izleme.aciklama')}
        sag={
          <select
            className="girdi w-auto py-1 text-xs"
            value={yon}
            onChange={(e) => setYon(e.target.value as 'tam' | 'geri' | 'ileri')}
          >
            <option value="tam">{t('partidetay.izleme.tam')}</option>
            <option value="geri">{t('partidetay.izleme.geri')}</option>
            <option value="ileri">{t('partidetay.izleme.ileri')}</option>
          </select>
        }
      >
        {izleme.isLoading ? (
          <Yukleniyor />
        ) : dugumler.length <= 1 ? (
          <Bos
            metin={t('partidetay.izleme.bos')}
            ipucu={t('partidetay.izleme.bosipucu')}
          />
        ) : (
          <>
            <Grafik secenek={grafikSecenek} yukseklik={420} />
            {izleme.data?.warnings?.length ? (
              <ul className="mt-2 space-y-1 text-xs" style={{ color: 'var(--metin-2)' }}>
                {izleme.data.warnings.map((u) => (
                  <li key={u}>• {u}</li>
                ))}
              </ul>
            ) : null}
          </>
        )}
      </Kart>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* -------------------------------------------------------- zaman çizelgesi */}
        <Kart baslik={t('partidetay.gecmis.baslik')} govdeSinif="p-0">
          {zaman.isLoading ? (
            <Yukleniyor />
          ) : (zaman.data?.length ?? 0) === 0 ? (
            <Bos metin={t('partidetay.gecmis.bos')} />
          ) : (
            <ol className="max-h-96 divide-y overflow-y-auto" style={{ borderColor: 'var(--kenar)' }}>
              {zaman.data?.map((o, i) => (
                <li key={i} className="p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium">{String(o.title)}</p>
                      {o.description ? (
                        <p className="mt-0.5 text-xs" style={{ color: 'var(--metin-2)' }}>
                          {String(o.description)}
                        </p>
                      ) : null}
                    </div>
                    <Rozet>{etiket(String(o.event_type))}</Rozet>
                  </div>
                  <p className="mt-1 text-[11px]" style={{ color: 'var(--metin-2)' }}>
                    {tarihSaat(String(o.occurred_at))}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </Kart>

        {/* --------------------------------------------------------------- maliyet */}
        <Kart baslik={t('partidetay.maliyet.baslik')} aciklama={t('partidetay.maliyet.aciklama')}>
          {maliyet.isLoading ? (
            <Yukleniyor />
          ) : maliyet.error ? (
            <Bos metin={t('partidetay.maliyet.yetkiyok')} />
          ) : maliyet.data ? (
            <>
              <div className="mb-4 grid grid-cols-3 gap-3">
                <div>
                  <p className="text-[11px]" style={{ color: 'var(--metin-2)' }}>
                    {t('partidetay.maliyet.toplam')}
                  </p>
                  <p className="text-lg font-semibold">{para(maliyet.data.total_cost)}</p>
                </div>
                <div>
                  <p className="text-[11px]" style={{ color: 'var(--metin-2)' }}>
                    {t('partidetay.maliyet.litrebasi')}
                  </p>
                  <p className="text-lg font-semibold">{para(maliyet.data.cost_per_liter)}</p>
                </div>
                <div>
                  <p className="text-[11px]" style={{ color: 'var(--metin-2)' }}>
                    {t('partidetay.maliyet.fire')}
                  </p>
                  <p className="text-lg font-semibold">{yuzde(maliyet.data.loss_percent)}</p>
                </div>
              </div>
              <Grafik
                yukseklik={220}
                veriVar={maliyet.data.total_cost > 0}
                secenek={{
                  tooltip: { trigger: 'item', valueFormatter: (v) => para(v) },
                  legend: { orient: 'vertical', right: 0, top: 'center', type: 'scroll' },
                  series: [
                    {
                      type: 'pie',
                      radius: ['42%', '70%'],
                      center: ['35%', '55%'],
                      label: { show: false },
                      itemStyle: { borderRadius: 5, borderWidth: 2 },
                      data: [
                        { name: t('partidetay.maliyet.uzum'), value: maliyet.data.grape_cost },
                        { name: t('partidetay.maliyet.katki'), value: maliyet.data.additive_cost },
                        { name: t('partidetay.maliyet.ambalaj'), value: maliyet.data.packaging_cost },
                        { name: t('partidetay.maliyet.iscilik'), value: maliyet.data.labor_cost },
                        { name: t('partidetay.maliyet.enerji'), value: maliyet.data.energy_cost },
                        { name: t('partidetay.maliyet.genelgider'), value: maliyet.data.overhead_cost },
                      ].filter((x) => x.value > 0),
                    },
                  ],
                }}
              />
            </>
          ) : null}
        </Kart>
      </div>
    </div>
  )
}
