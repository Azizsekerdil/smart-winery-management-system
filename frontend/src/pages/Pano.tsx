import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  Activity,
  AlertTriangle,
  Beaker,
  CalendarClock,
  Cylinder,
  Droplet,
  Grape,
  Sparkles,
  Truck,
  Wine,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Grafik } from '@/components/Grafik'
import { Bos, HataKutusu, Ilerleme, Kart, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { api, hataMesaji } from '@/lib/api'
import { asamaEtiketleri, goreliZaman, sayi, tarih, yuzde } from '@/lib/bicim'
import { useCeviri } from '@/lib/i18n'

interface Kpi {
  key: string
  label: string
  value: number | string
  unit: string
  severity: string
  trend_label?: string | null
  icon?: string | null
}

interface PanoVerisi {
  generated_at: string
  kpis: Kpi[]
  active_fermentations: Record<string, unknown>[]
  critical_alerts: {
    id: number
    severity: string
    title: string
    message: string
    category: string
    created_at: string
  }[]
  tank_fills: {
    id: number
    code: string
    fill_percent: number
    capacity_l: number
    current_volume_l: number
    status: string
    temperature_c: number | null
    lot_code: string | null
    zone: string | null
    temp_alert: boolean
  }[]
  upcoming_tasks: {
    kind: string
    title: string
    due_date: string | null
    days_left: number | null
    severity: string
    ref_code: string | null
  }[]
  daily_production: { label: string; value: number }[]
  stock_summary: { label: string; value: number }[]
  low_stock_items: Record<string, unknown>[]
  recent_activity: {
    at: string
    username: string | null
    action: string
    entity_type: string
    entity_code: string | null
    summary: string
  }[]
  ai_suggestions: Record<string, unknown>[]
  lot_stage_distribution: { label: string; value: number }[]
}

const SIMGELER: Record<string, ReactNode> = {
  grape: <Grape className="h-4 w-4" />,
  droplet: <Droplet className="h-4 w-4" />,
  activity: <Activity className="h-4 w-4" />,
  cylinder: <Cylinder className="h-4 w-4" />,
  truck: <Truck className="h-4 w-4" />,
  wine: <Wine className="h-4 w-4" />,
  alert: <AlertTriangle className="h-4 w-4" />,
  flask: <Beaker className="h-4 w-4" />,
}

function KpiKart({ kpi }: { kpi: Kpi }) {
  const t = useCeviri()
  // Sunucu Türkçe bir `label` da gönderir; çeviri anahtarı `key` üzerinden
  // çözülür ve karşılığı yoksa sunucunun etiketine düşülür. Böylece yeni bir
  // gösterge eklendiğinde arayüz bozulmaz, yalnızca çevirisiz görünür.
  const etiket = kpi.key ? t(`kpi.${kpi.key}`) : kpi.label
  const vurgu =
    kpi.severity === 'kritik'
      ? 'border-red-500/40'
      : kpi.severity === 'uyari'
        ? 'border-amber-500/40'
        : ''
  return (
    <div className={clsx('kart p-4', vurgu)}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
          {etiket === `kpi.${kpi.key}` ? kpi.label : etiket}
        </p>
        <span style={{ color: 'var(--vurgu)' }}>{SIMGELER[kpi.icon ?? ''] ?? null}</span>
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums">
        {typeof kpi.value === 'number' ? sayi(kpi.value, kpi.unit === '%' ? 1 : 0) : kpi.value}
        {kpi.unit && (
          <span className="ml-1 text-sm font-normal" style={{ color: 'var(--metin-2)' }}>
            {kpi.unit}
          </span>
        )}
      </p>
      {kpi.trend_label && (
        <p className="mt-1 text-[11px]" style={{ color: 'var(--metin-2)' }}>
          {kpi.trend_label}
        </p>
      )}
    </div>
  )
}

export default function Pano() {
  const t = useCeviri()
  const { data, isLoading, error } = useQuery({
    queryKey: ['pano'],
    queryFn: async () => (await api.get<PanoVerisi>('/dashboard')).data,
    refetchInterval: 60_000,
  })

  if (isLoading) return <Yukleniyor metin={t('pano.yukleniyor')} />
  if (error) return <HataKutusu mesaj={hataMesaji(error)} />
  if (!data) return null

  const uretimVar = data.daily_production.length > 0
  const stokVar = data.stock_summary.length > 0
  const asamaVar = data.lot_stage_distribution.length > 0

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('pano.baslik')}
        aciklama={`${t('pano.songuncelleme')}: ${goreliZaman(data.generated_at)}`}
      />

      {/* KPI kartları */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {data.kpis.map((k) => (
          <KpiKart key={k.key} kpi={k} />
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        {/* -------------------------------------------- devam eden fermantasyonlar */}
        <Kart
          className="xl:col-span-2"
          baslik={t('pano.fermantasyon.baslik')}
          aciklama={`${data.active_fermentations.length} ${t('pano.fermantasyon.aktif')}`}
          sag={
            <Link to="/fermantasyon" className="text-xs" style={{ color: 'var(--vurgu)' }}>
              {t('pano.tumu')} →
            </Link>
          }
          govdeSinif="p-0"
        >
          {data.active_fermentations.length === 0 ? (
            <Bos metin={t('pano.fermantasyon.bos')} />
          ) : (
            <div className="divide-y" style={{ borderColor: 'var(--kenar)' }}>
              {data.active_fermentations.map((f) => {
                const kod = String(f.code)
                const ilerleme = Number(f.progress_percent ?? 0)
                const sicaklikUyari = Boolean(f.temp_alert)
                return (
                  <div key={kod} className="p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {String(f.lot_name ?? f.lot_code ?? kod)}
                        </p>
                        <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
                          {kod} · {String(f.tank_code ?? t('pano.fermantasyon.tankyok'))} ·{' '}
                          {String(f.day_no)}. {t('pano.fermantasyon.gun')}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        {sicaklikUyari && (
                          <Rozet seviye="kritik">
                            <AlertTriangle className="h-3 w-3" />
                            {sayi(f.temperature_c as number, 1)} °C
                          </Rozet>
                        )}
                        {!sicaklikUyari && f.temperature_c !== null && (
                          <Rozet>{sayi(f.temperature_c as number, 1)} °C</Rozet>
                        )}
                        <Rozet>Brix {sayi(f.brix as number, 1)}</Rozet>
                      </div>
                    </div>
                    <div className="mt-3 flex items-center gap-3">
                      <Ilerleme deger={ilerleme} seviye={sicaklikUyari ? 'uyari' : undefined} />
                      <span className="w-12 shrink-0 text-right text-xs tabular-nums">
                        {yuzde(ilerleme, 0)}
                      </span>
                    </div>
                    {f.predicted_end_date ? (
                      <p className="mt-2 text-[11px]" style={{ color: 'var(--metin-2)' }}>
                        {t('pano.fermantasyon.tahminibitis')}: {tarih(f.predicted_end_date as string)}
                        {f.prediction_note ? ` — ${String(f.prediction_note)}` : ''}
                      </p>
                    ) : f.prediction_note ? (
                      <p className="mt-2 text-[11px] text-amber-600 dark:text-amber-400">
                        {String(f.prediction_note)}
                      </p>
                    ) : null}
                  </div>
                )
              })}
            </div>
          )}
        </Kart>

        {/* --------------------------------------------------------- uyarılar */}
        <Kart
          baslik={t('pano.uyari.baslik')}
          aciklama={`${data.critical_alerts.length} ${t('pano.uyari.acik')}`}
          govdeSinif="p-0"
        >
          {data.critical_alerts.length === 0 ? (
            <Bos metin={t('pano.uyari.bos')} ipucu={t('pano.uyari.bosipucu')} />
          ) : (
            <ul className="max-h-96 divide-y overflow-y-auto" style={{ borderColor: 'var(--kenar)' }}>
              {data.critical_alerts.map((u) => (
                <li key={u.id} className="p-3">
                  <div className="flex items-start gap-2">
                    <Rozet seviye={u.severity}>{u.severity}</Rozet>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium leading-snug">{u.title}</p>
                      <p className="mt-1 text-xs" style={{ color: 'var(--metin-2)' }}>
                        {u.message}
                      </p>
                      <p className="mt-1 text-[10px]" style={{ color: 'var(--metin-2)' }}>
                        {goreliZaman(u.created_at)}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Kart>
      </div>

      {/* ------------------------------------------------------------- tanklar */}
      <Kart
        baslik={t('pano.tank.baslik')}
        aciklama={`${data.tank_fills.length} ${t('pano.tank.aktif')}`}
        sag={
          <Link to="/tanklar" className="text-xs" style={{ color: 'var(--vurgu)' }}>
            {t('pano.tank.yerlesim')} →
          </Link>
        }
      >
        {data.tank_fills.length === 0 ? (
          <Bos metin={t('pano.tank.bos')} />
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {data.tank_fills.map((tf) => (
              <div key={tf.id} className="rounded-lg border p-3" style={{ borderColor: 'var(--kenar)' }}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{tf.code}</span>
                  {tf.temp_alert && <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />}
                </div>
                <p className="mb-2 truncate text-[11px]" style={{ color: 'var(--metin-2)' }}>
                  {tf.lot_code ?? t('pano.tank.bosdurum')}
                </p>
                <Ilerleme
                  deger={tf.fill_percent}
                  seviye={tf.fill_percent > 95 ? 'uyari' : undefined}
                />
                <p className="mt-1.5 text-[11px] tabular-nums" style={{ color: 'var(--metin-2)' }}>
                  {sayi(tf.current_volume_l, 0)} / {sayi(tf.capacity_l, 0)} L
                  {tf.temperature_c !== null && ` · ${sayi(tf.temperature_c, 1)} °C`}
                </p>
              </div>
            ))}
          </div>
        )}
      </Kart>

      {/* ------------------------------------------------------------ grafikler */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Kart baslik={t('pano.uretim.baslik')} aciklama={t('pano.uretim.aciklama')}>
          <Grafik
            veriVar={uretimVar}
            secenek={{
              tooltip: { trigger: 'axis' },
              xAxis: { type: 'category', data: data.daily_production.map((p) => p.label) },
              yAxis: { type: 'value' },
              series: [
                {
                  type: 'bar',
                  name: t('pano.uretim.seri'),
                  data: data.daily_production.map((p) => p.value),
                  itemStyle: { borderRadius: [4, 4, 0, 0] },
                },
              ],
            }}
          />
        </Kart>

        <Kart baslik={t('pano.asama.baslik')} aciklama={t('pano.asama.aciklama')}>
          <Grafik
            veriVar={asamaVar}
            secenek={{
              tooltip: { trigger: 'item' },
              legend: { orient: 'vertical', right: 0, top: 'center', type: 'scroll' },
              series: [
                {
                  type: 'pie',
                  radius: ['45%', '72%'],
                  center: ['38%', '52%'],
                  itemStyle: { borderRadius: 6, borderWidth: 2 },
                  label: { show: false },
                  data: data.lot_stage_distribution.map((p) => ({
                    // Sunucu ham aşama kodu gönderir; çeviri burada yapılır.
                    name: asamaEtiketleri()[p.label] ?? p.label,
                    value: p.value,
                  })),
                },
              ],
            }}
          />
        </Kart>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        {/* ------------------------------------------------------ yaklaşan işler */}
        <Kart baslik={t('pano.gorev.baslik')} govdeSinif="p-0">
          {data.upcoming_tasks.length === 0 ? (
            <Bos metin={t('pano.gorev.bos')} />
          ) : (
            <ul className="max-h-80 divide-y overflow-y-auto" style={{ borderColor: 'var(--kenar)' }}>
              {data.upcoming_tasks.map((g, i) => (
                <li key={`${g.kind}-${g.ref_code}-${i}`} className="flex items-start gap-2 p-3">
                  <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 opacity-60" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm leading-snug">{g.title}</p>
                    <p className="text-[11px]" style={{ color: 'var(--metin-2)' }}>
                      {tarih(g.due_date)}
                      {g.days_left !== null &&
                        ` · ${
                          g.days_left < 0
                            ? `${Math.abs(g.days_left)} ${t('pano.gorev.gungecikti')}`
                            : `${g.days_left} ${t('pano.gorev.gunkaldi')}`
                        }`}
                    </p>
                  </div>
                  {g.days_left !== null && g.days_left < 0 && (
                    <Rozet seviye="uyari">{t('pano.gorev.gecikti')}</Rozet>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Kart>

        {/* ---------------------------------------------------- yapay zekâ önerileri */}
        <Kart
          baslik={
            <span className="flex items-center gap-1.5">
              <Sparkles className="h-4 w-4" style={{ color: 'var(--vurgu)' }} />
              {t('pano.ai.baslik')}
            </span>
          }
          aciklama={t('pano.ai.aciklama')}
          govdeSinif="p-0"
        >
          {data.ai_suggestions.length === 0 ? (
            <Bos metin={t('pano.ai.bos')} ipucu={t('pano.ai.bosipucu')} />
          ) : (
            <ul className="max-h-80 divide-y overflow-y-auto" style={{ borderColor: 'var(--kenar)' }}>
              {data.ai_suggestions.map((o, i) => (
                <li key={i} className="p-3">
                  <div className="flex items-start gap-2">
                    <Rozet seviye={String(o.risk)}>{String(o.risk)}</Rozet>
                    <div className="min-w-0 flex-1">
                      <Link
                        to={`/partiler/${o.lot_id}`}
                        className="text-sm font-medium hover:underline"
                      >
                        {String(o.baslik)}
                      </Link>
                      <p className="mt-1 text-xs" style={{ color: 'var(--metin-2)' }}>
                        {String(o.aciklama)}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Kart>

        {/* ------------------------------------------------------- son faaliyetler */}
        <Kart baslik={t('pano.faaliyet.baslik')} govdeSinif="p-0">
          {data.recent_activity.length === 0 ? (
            <Bos metin={t('pano.faaliyet.bos')} />
          ) : (
            <ul className="max-h-80 divide-y overflow-y-auto" style={{ borderColor: 'var(--kenar)' }}>
              {data.recent_activity.map((a, i) => (
                <li key={i} className="p-3">
                  <p className="text-sm leading-snug">{a.summary}</p>
                  <p className="mt-1 text-[11px]" style={{ color: 'var(--metin-2)' }}>
                    {a.username ?? t('pano.faaliyet.sistem')} · {goreliZaman(a.at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Kart>
      </div>

      {/* --------------------------------------------------------------- stok */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Kart baslik={t('pano.stok.baslik')}>
          <Grafik
            veriVar={stokVar}
            yukseklik={240}
            secenek={{
              tooltip: { trigger: 'axis' },
              xAxis: { type: 'value' },
              yAxis: {
                type: 'category',
                data: data.stock_summary.map((s) => s.label),
              },
              series: [
                {
                  type: 'bar',
                  name: t('pano.stok.seri'),
                  data: data.stock_summary.map((s) => s.value),
                  itemStyle: { borderRadius: [0, 4, 4, 0] },
                },
              ],
            }}
          />
        </Kart>

        <Kart
          baslik={t('pano.dusukstok.baslik')}
          aciklama={`${data.low_stock_items.length} ${t('pano.dusukstok.kalem')}`}
          sag={
            <Link to="/stok" className="text-xs" style={{ color: 'var(--vurgu)' }}>
              {t('pano.dusukstok.link')} →
            </Link>
          }
          govdeSinif="p-0"
        >
          {data.low_stock_items.length === 0 ? (
            <Bos metin={t('pano.dusukstok.bos')} />
          ) : (
            <table className="tablo">
              <thead>
                <tr>
                  <th>{t('pano.dusukstok.tablo.kalem')}</th>
                  <th className="text-right">{t('pano.dusukstok.tablo.mevcut')}</th>
                  <th className="text-right">{t('pano.dusukstok.tablo.minimum')}</th>
                  <th className="text-right">{t('pano.dusukstok.tablo.eksik')}</th>
                </tr>
              </thead>
              <tbody>
                {data.low_stock_items.map((k, i) => (
                  <tr key={i}>
                    <td>
                      <span className="font-medium">{String(k.name)}</span>
                      <span className="ml-1 text-xs" style={{ color: 'var(--metin-2)' }}>
                        {String(k.code)}
                      </span>
                    </td>
                    <td className="text-right tabular-nums">
                      {sayi(k.on_hand as number)} {String(k.unit)}
                    </td>
                    <td className="text-right tabular-nums">{sayi(k.min_stock as number)}</td>
                    <td className="text-right font-medium tabular-nums text-amber-600 dark:text-amber-400">
                      {sayi(k.eksik as number)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Kart>
      </div>
    </div>
  )
}
