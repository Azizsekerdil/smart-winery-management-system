import { useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowRightLeft, Sparkles } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Alan, HataKutusu, Ilerleme, Kart, Kip, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { Tablo } from '@/components/Tablo'
import { api, hataMesaji } from '@/lib/api'
import { etiket, sayi, tarihSaat } from '@/lib/bicim'
import { useListe, useSecenekler } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

interface Tank {
  id: number
  code: string
  tank_type: string
  capacity_l: number
  current_volume_l: number
  fill_percent: number
  free_capacity_l: number
  status: string
  cleaning_status: string
  temperature_c: number | null
  target_temperature_c: number | null
  zone: string | null
  location: string | null
  current_lot_code: string | null
  last_cleaned_at: string | null
}

export default function Tanklar() {
  const t = useCeviri()
  const [gorunum, setGorunum] = useState<'yerlesim' | 'liste'>('yerlesim')
  const [transferAcik, setTransferAcik] = useState(false)
  const [hata, setHata] = useState('')
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)

  const yerlesim = useQuery({
    queryKey: ['/tanks/layout/map'],
    queryFn: async () =>
      (await api.get('/tanks/layout/map')).data as {
        zones: { name: string; tanks: Tank[] }[]
        total_capacity_l: number
        total_volume_l: number
      },
  })

  const liste = useListe<Tank>('/tanks', {}, { etkin: gorunum === 'liste' })
  const tankSecenek = useSecenekler('/tanks', 'code')
  const partiSecenek = useSecenekler('/lots', 'code')

  const [form, setForm] = useState({
    lot_id: '',
    from_tank_id: '',
    to_tank_id: '',
    volume_l: '',
    loss_l: '0',
    transfer_type: 'tank_arasi',
    notes: '',
  })

  async function transferYap(e: FormEvent) {
    e.preventDefault()
    setHata('')
    try {
      await api.post('/transfers', {
        lot_id: Number(form.lot_id),
        from_tank_id: form.from_tank_id ? Number(form.from_tank_id) : undefined,
        to_tank_id: form.to_tank_id ? Number(form.to_tank_id) : undefined,
        volume_l: Number(form.volume_l),
        loss_l: Number(form.loss_l || 0),
        transfer_type: form.transfer_type,
        notes: form.notes || undefined,
      })
      setTransferAcik(false)
      void istemci.invalidateQueries({ queryKey: ['/tanks/layout/map'] })
      void istemci.invalidateQueries({ queryKey: ['/tanks'] })
      void istemci.invalidateQueries({ queryKey: ['/lots'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  const dolulukOrani = yerlesim.data
    ? (yerlesim.data.total_volume_l / Math.max(1, yerlesim.data.total_capacity_l)) * 100
    : 0

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('tanklar.baslik')}
        aciklama={
          yerlesim.data
            ? `${t('tanklar.ozet.toplam')} ${sayi(yerlesim.data.total_volume_l, 0)} / ${sayi(yerlesim.data.total_capacity_l, 0)} L · ${t('tanklar.ozet.doluluk')} %${dolulukOrani.toFixed(1)}`
            : undefined
        }
        eylemler={
          <>
            <div className="flex rounded-lg border" style={{ borderColor: 'var(--kenar)' }}>
              {(['yerlesim', 'liste'] as const).map((g) => (
                <button
                  key={g}
                  type="button"
                  onClick={() => setGorunum(g)}
                  className={clsx(
                    'px-3 py-1.5 text-xs first:rounded-l-lg last:rounded-r-lg',
                    gorunum === g ? 'bg-[var(--vurgu)] text-[var(--vurgu-yazi)]' : '',
                  )}
                >
                  {g === 'yerlesim' ? t('tanklar.gorunum.yerlesim') : t('tanklar.gorunum.liste')}
                </button>
              ))}
            </div>
            {yetkiVar('tank:transfer') && (
              <button type="button" className="dugme dugme-birincil" onClick={() => setTransferAcik(true)}>
                <ArrowRightLeft className="h-4 w-4" /> {t('tanklar.dugme.transfer')}
              </button>
            )}
          </>
        }
      />

      {gorunum === 'yerlesim' ? (
        yerlesim.isLoading ? (
          <Yukleniyor />
        ) : (
          <div className="space-y-5">
            {yerlesim.data?.zones.map((bolge) => (
              <Kart
                key={bolge.name}
                baslik={bolge.name}
                aciklama={`${bolge.tanks.length} ${t('tanklar.bolge.tank')}`}
              >
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6">
                  {bolge.tanks.map((tank) => {
                    const sicaklikSapma =
                      tank.temperature_c !== null &&
                      tank.target_temperature_c !== null &&
                      Math.abs(tank.temperature_c - tank.target_temperature_c) > 3
                    return (
                      <div
                        key={tank.id}
                        className={clsx(
                          'rounded-lg border p-3 transition-shadow hover:shadow-md',
                          sicaklikSapma && 'border-amber-500/50',
                        )}
                        style={{ borderColor: sicaklikSapma ? undefined : 'var(--kenar)' }}
                      >
                        <div className="mb-1 flex items-center justify-between">
                          <span className="font-medium">{tank.code}</span>
                          <Rozet
                            seviye={
                              tank.status === 'bos' ? 'dusuk' : tank.status === 'dolu' ? 'orta' : undefined
                            }
                          >
                            {etiket(tank.status)}
                          </Rozet>
                        </div>
                        <p className="mb-2 truncate text-[11px]" style={{ color: 'var(--metin-2)' }}>
                          {tank.current_lot_code ?? etiket(tank.tank_type)}
                        </p>
                        {/* Görsel tank: dikey doluluk */}
                        <div
                          className="relative mx-auto mb-2 h-20 w-12 overflow-hidden rounded-b-lg rounded-t border-2"
                          style={{ borderColor: 'var(--kenar)' }}
                          title={`${tank.fill_percent}% ${t('tanklar.tank.dolu')}`}
                        >
                          <div
                            className="absolute bottom-0 w-full transition-all"
                            style={{
                              height: `${Math.min(100, tank.fill_percent)}%`,
                              background:
                                'linear-gradient(180deg, rgba(151,31,72,0.85), rgba(92,26,43,0.95))',
                            }}
                          />
                          <span className="absolute inset-0 grid place-items-center text-[10px] font-semibold text-white mix-blend-difference">
                            %{tank.fill_percent.toFixed(0)}
                          </span>
                        </div>
                        <p className="text-center text-[11px] tabular-nums" style={{ color: 'var(--metin-2)' }}>
                          {sayi(tank.current_volume_l, 0)}/{sayi(tank.capacity_l, 0)} L
                        </p>
                        {tank.temperature_c !== null && (
                          <p
                            className={clsx(
                              'mt-0.5 text-center text-[11px] tabular-nums',
                              sicaklikSapma && 'font-semibold text-amber-600 dark:text-amber-400',
                            )}
                          >
                            {sayi(tank.temperature_c, 1)} °C
                            {tank.target_temperature_c !== null &&
                              ` / ${sayi(tank.target_temperature_c, 1)}`}
                          </p>
                        )}
                      </div>
                    )
                  })}
                </div>
              </Kart>
            ))}
          </div>
        )
      ) : (
        <Tablo
          sutunlar={[
            { anahtar: 'code', baslik: t('tanklar.tablo.kod'), genislik: '110px' },
            { anahtar: 'tank_type', baslik: t('tanklar.tablo.tip'), hucre: (r) => etiket(r.tank_type) },
            { anahtar: 'capacity_l', baslik: t('tanklar.tablo.kapasite'), sagaYasli: true, hucre: (r) => sayi(r.capacity_l, 0) },
            { anahtar: 'current_volume_l', baslik: t('tanklar.tablo.dolu'), sagaYasli: true, hucre: (r) => sayi(r.current_volume_l, 0) },
            {
              anahtar: 'fill_percent',
              baslik: t('tanklar.tablo.doluluk'),
              genislik: '140px',
              hucre: (r) => (
                <div className="flex items-center gap-2">
                  <Ilerleme deger={r.fill_percent} />
                  <span className="w-10 text-right text-xs tabular-nums">%{r.fill_percent.toFixed(0)}</span>
                </div>
              ),
            },
            { anahtar: 'status', baslik: t('tanklar.tablo.durum'), hucre: (r) => <Rozet>{etiket(r.status)}</Rozet> },
            { anahtar: 'cleaning_status', baslik: t('tanklar.tablo.temizlik'), gizleKucuk: true, hucre: (r) => etiket(r.cleaning_status) },
            { anahtar: 'current_lot_code', baslik: t('tanklar.tablo.parti'), hucre: (r) => r.current_lot_code ?? '—' },
            { anahtar: 'zone', baslik: t('tanklar.tablo.bolge'), gizleKucuk: true, hucre: (r) => r.zone ?? r.location ?? '—' },
            {
              anahtar: 'last_cleaned_at',
              baslik: t('tanklar.tablo.sontemizlik'),
              gizleKucuk: true,
              hucre: (r) => tarihSaat(r.last_cleaned_at),
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
          bosMetin={t('tanklar.bos')}
        />
      )}

      <Kart
        baslik={
          <span className="flex items-center gap-1.5">
            <Sparkles className="h-4 w-4" style={{ color: 'var(--vurgu)' }} /> {t('tanklar.ipucu.baslik')}
          </span>
        }
      >
        <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
          {t('tanklar.ipucu.metin')}
        </p>
      </Kart>

      <Kip acik={transferAcik} baslik={t('tanklar.kip.baslik')} onKapat={() => setTransferAcik(false)}>
        <form onSubmit={transferYap} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

          <Alan etiket={t('tanklar.form.parti')} gerekli>
            <select
              className="girdi"
              value={form.lot_id}
              onChange={(e) => setForm({ ...form, lot_id: e.target.value })}
              required
            >
              <option value="">{t('tanklar.form.seciniz')}</option>
              {partiSecenek.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.ad} — {String(p.ham.name)} ({sayi(Number(p.ham.volume_l), 0)} L)
                </option>
              ))}
            </select>
          </Alan>

          <Alan etiket={t('tanklar.form.islemturu')}>
            <select
              className="girdi"
              value={form.transfer_type}
              onChange={(e) => setForm({ ...form, transfer_type: e.target.value })}
            >
              <option value="dolum">{t('tanklar.islem.dolum')}</option>
              <option value="tank_arasi">{t('tanklar.islem.tankarasi')}</option>
              <option value="aktarma">{t('tanklar.islem.aktarma')}</option>
              <option value="bosaltim">{t('tanklar.islem.bosaltim')}</option>
            </select>
          </Alan>

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('tanklar.form.kaynaktank')} ipucu={t('tanklar.form.kaynakipucu')}>
              <select
                className="girdi"
                value={form.from_tank_id}
                onChange={(e) => setForm({ ...form, from_tank_id: e.target.value })}
              >
                <option value="">—</option>
                {tankSecenek.data?.map((tk) => (
                  <option key={tk.id} value={tk.id}>
                    {tk.ad} ({sayi(Number(tk.ham.current_volume_l), 0)} {t('tanklar.form.ldolu')})
                  </option>
                ))}
              </select>
            </Alan>
            <Alan etiket={t('tanklar.form.hedeftank')} ipucu={t('tanklar.form.hedefipucu')}>
              <select
                className="girdi"
                value={form.to_tank_id}
                onChange={(e) => setForm({ ...form, to_tank_id: e.target.value })}
              >
                <option value="">—</option>
                {tankSecenek.data?.map((tk) => (
                  <option key={tk.id} value={tk.id}>
                    {tk.ad} ({sayi(Number(tk.ham.free_capacity_l), 0)} {t('tanklar.form.lbos')})
                  </option>
                ))}
              </select>
            </Alan>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('tanklar.form.hacim')} gerekli>
              <input
                className="girdi"
                type="number"
                step="0.1"
                min="0.1"
                value={form.volume_l}
                onChange={(e) => setForm({ ...form, volume_l: e.target.value })}
                required
              />
            </Alan>
            <Alan etiket={t('tanklar.form.fire')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                min="0"
                value={form.loss_l}
                onChange={(e) => setForm({ ...form, loss_l: e.target.value })}
              />
            </Alan>
          </div>

          <Alan etiket={t('tanklar.form.not')}>
            <input
              className="girdi"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </Alan>

          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setTransferAcik(false)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('tanklar.dugme.kaydet')}
            </button>
          </div>
        </form>
      </Kip>
    </div>
  )
}
