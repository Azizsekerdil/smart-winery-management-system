/** Tema duyarlı ECharts sarmalayıcısı (Apache-2.0 lisanslı). */
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { useMemo } from 'react'
import { useAyarlar } from '@/lib/store'

export const GRAFIK_RENKLERI = [
  '#971f48', // bordo
  '#d46a28', // bakır
  '#7a56b2', // üzüm
  '#2e8b6f', // yeşil
  '#c7902a', // altın
  '#3b7ea1', // mavi
  '#b04b6a',
  '#6b8f3a',
]

export function Grafik({
  secenek,
  yukseklik = 280,
  bosMesaj = 'Görüntülenecek veri yok.',
  veriVar = true,
}: {
  secenek: EChartsOption
  yukseklik?: number
  bosMesaj?: string
  veriVar?: boolean
}) {
  const tema = useAyarlar((s) => s.tema)
  const koyu =
    tema === 'dark' ||
    (tema === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)

  const birlesik = useMemo<EChartsOption>(() => {
    const metin = koyu ? '#f3ece9' : '#2a1f24'
    const metin2 = koyu ? '#a99aa4' : '#6b5c62'
    const izgara = koyu ? '#3a2e3f' : '#e5dcce'
    return {
      color: GRAFIK_RENKLERI,
      backgroundColor: 'transparent',
      textStyle: { color: metin, fontFamily: 'Inter, Segoe UI, system-ui, sans-serif' },
      grid: { left: 48, right: 20, top: 40, bottom: 40, containLabel: true },
      tooltip: {
        backgroundColor: koyu ? '#201822' : '#ffffff',
        borderColor: izgara,
        textStyle: { color: metin, fontSize: 12 },
      },
      legend: { textStyle: { color: metin2 }, top: 4 },
      xAxis: {
        axisLine: { lineStyle: { color: izgara } },
        axisLabel: { color: metin2, fontSize: 11 },
        splitLine: { show: false },
      },
      yAxis: {
        axisLine: { show: false },
        axisLabel: { color: metin2, fontSize: 11 },
        splitLine: { lineStyle: { color: izgara, type: 'dashed' } },
      },
      ...secenek,
    } as EChartsOption
  }, [secenek, koyu])

  if (!veriVar) {
    return (
      <div
        className="flex items-center justify-center text-xs"
        style={{ height: yukseklik, color: 'var(--metin-2)' }}
      >
        {bosMesaj}
      </div>
    )
  }

  return (
    <ReactECharts
      option={birlesik}
      style={{ height: yukseklik, width: '100%' }}
      notMerge
      lazyUpdate
      opts={{ renderer: 'canvas' }}
    />
  )
}
