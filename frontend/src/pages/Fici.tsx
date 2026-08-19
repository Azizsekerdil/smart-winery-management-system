import { useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Droplets, QrCode } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Alan, Bos, HataKutusu, Kart, Kip, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { Tablo } from '@/components/Tablo'
import { api, hataMesaji } from '@/lib/api'
import { etiket, sayi } from '@/lib/bicim'
import { useListe, useSecenekler } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

interface Fici {
  id: number
  code: string
  oak_type: string
  cooper: string | null
  toast_level: string
  capacity_l: number
  current_volume_l: number
  status: string
  current_lot_code: string | null
  cellar_zone: string | null
  rack_code: string | null
  age_years: number | null
  aging_days: number | null
  total_loss_l: number
  fill_count: number
}

export default function Fici() {
  const t = useCeviri()
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const [gorunum, setGorunum] = useState<'harita' | 'liste'>('harita')
  const [hareketFici, setHareketFici] = useState<Fici | null>(null)
  const [hata, setHata] = useState('')

  const harita = useQuery({
    queryKey: ['/barrels/cellar/map'],
    queryFn: async () =>
      (await api.get('/barrels/cellar/map')).data as {
        zones: { name: string; barrels: Fici[] }[]
        total_barrels: number
        filled_barrels: number
        total_volume_l: number
        total_loss_l: number
      },
  })

  const liste = useListe<Fici>('/barrels', {}, { etkin: gorunum === 'liste' })
  const partiSecenek = useSecenekler('/lots', 'code')

  const [hareket, setHareket] = useState({
    movement_type: 'dolum',
    lot_id: '',
    volume_l: '',
    loss_l: '0',
    notes: '',
  })

  async function hareketKaydet(e: FormEvent) {
    e.preventDefault()
    if (!hareketFici) return
    setHata('')
    try {
      await api.post(`/barrels/${hareketFici.id}/movements`, {
        movement_type: hareket.movement_type,
        lot_id: hareket.lot_id ? Number(hareket.lot_id) : undefined,
        volume_l: Number(hareket.volume_l || 0),
        loss_l: Number(hareket.loss_l || 0),
        notes: hareket.notes || undefined,
      })
      setHareketFici(null)
      void istemci.invalidateQueries({ queryKey: ['/barrels/cellar/map'] })
      void istemci.invalidateQueries({ queryKey: ['/barrels'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('fici.baslik')}
        aciklama={
          harita.data
            ? `${harita.data.filled_barrels}/${harita.data.total_barrels} ${t('fici.ozet.dolu')} · ${sayi(harita.data.total_volume_l, 0)} L · ${t('fici.ozet.toplamfire')} ${sayi(harita.data.total_loss_l, 1)} L`
            : undefined
        }
        eylemler={
          <div className="flex rounded-lg border" style={{ borderColor: 'var(--kenar)' }}>
            {(['harita', 'liste'] as const).map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => setGorunum(g)}
                className={clsx(
                  'px-3 py-1.5 text-xs first:rounded-l-lg last:rounded-r-lg',
                  gorunum === g ? 'bg-[var(--vurgu)] text-[var(--vurgu-yazi)]' : '',
                )}
              >
                {g === 'harita' ? t('fici.gorunum.harita') : t('fici.gorunum.liste')}
              </button>
            ))}
          </div>
        }
      />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

      {gorunum === 'harita' ? (
        harita.isLoading ? (
          <Yukleniyor />
        ) : (harita.data?.zones.length ?? 0) === 0 ? (
          <Kart>
            <Bos metin={t('fici.bos.kayit')} />
          </Kart>
        ) : (
          <div className="space-y-5">
            {harita.data?.zones.map((bolge) => (
              <Kart
                key={bolge.name}
                baslik={bolge.name}
                aciklama={`${bolge.barrels.length} ${t('fici.kart.fici')}`}
              >
                <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-7">
                  {bolge.barrels.map((f) => {
                    const doluluk = (f.current_volume_l / Math.max(1, f.capacity_l)) * 100
                    const dolu = f.status === 'dolu'
                    return (
                      <button
                        key={f.id}
                        type="button"
                        onClick={() => {
                          if (!yetkiVar('barrel:write')) return
                          setHareketFici(f)
                          setHareket({
                            movement_type: dolu ? 'topping' : 'dolum',
                            lot_id: '',
                            volume_l: dolu ? '2' : '220',
                            loss_l: '0',
                            notes: '',
                          })
                        }}
                        className="rounded-lg border p-2 text-left transition-shadow hover:shadow-md"
                        style={{ borderColor: 'var(--kenar)' }}
                        title={`${f.code} — ${etiket(f.status)}`}
                      >
                        {/* Fıçı görseli */}
                        <div
                          className="relative mx-auto mb-2 h-14 w-12 overflow-hidden rounded-full"
                          style={{
                            border: '2px solid var(--kenar)',
                            background: 'var(--yuzey-3)',
                          }}
                        >
                          <div
                            className="absolute bottom-0 w-full"
                            style={{
                              height: `${Math.min(100, doluluk)}%`,
                              background: 'linear-gradient(180deg,#d46a28,#993d1c)',
                            }}
                          />
                        </div>
                        <p className="truncate text-center text-xs font-medium">{f.code}</p>
                        <p
                          className="truncate text-center text-[10px]"
                          style={{ color: 'var(--metin-2)' }}
                        >
                          {f.current_lot_code ?? etiket(f.oak_type)}
                        </p>
                        {f.aging_days !== null && (
                          <p className="text-center text-[10px]" style={{ color: 'var(--metin-2)' }}>
                            {f.aging_days} {t('fici.birim.gun')}
                          </p>
                        )}
                      </button>
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
            { anahtar: 'code', baslik: t('fici.tablo.kod'), genislik: '100px' },
            { anahtar: 'oak_type', baslik: t('fici.tablo.mese'), hucre: (r) => etiket(r.oak_type) },
            {
              anahtar: 'cooper',
              baslik: t('fici.tablo.uretici'),
              gizleKucuk: true,
              hucre: (r) => r.cooper ?? '—',
            },
            {
              anahtar: 'toast_level',
              baslik: t('fici.tablo.kavurma'),
              gizleKucuk: true,
              hucre: (r) => etiket(r.toast_level),
            },
            {
              anahtar: 'age_years',
              baslik: t('fici.tablo.yas'),
              sagaYasli: true,
              hucre: (r) => (r.age_years !== null ? `${r.age_years} ${t('fici.birim.yil')}` : '—'),
            },
            {
              anahtar: 'capacity_l',
              baslik: t('fici.tablo.kapasite'),
              sagaYasli: true,
              hucre: (r) => `${sayi(r.capacity_l, 0)} L`,
            },
            {
              anahtar: 'current_volume_l',
              baslik: t('fici.tablo.dolu'),
              sagaYasli: true,
              hucre: (r) => `${sayi(r.current_volume_l, 0)} L`,
            },
            { anahtar: 'status', baslik: t('fici.tablo.durum'), hucre: (r) => <Rozet>{etiket(r.status)}</Rozet> },
            {
              anahtar: 'current_lot_code',
              baslik: t('fici.tablo.parti'),
              hucre: (r) => r.current_lot_code ?? '—',
            },
            {
              anahtar: 'aging_days',
              baslik: t('fici.tablo.olgunlasma'),
              sagaYasli: true,
              hucre: (r) => (r.aging_days !== null ? `${r.aging_days} ${t('fici.birim.gun')}` : '—'),
            },
            {
              anahtar: 'total_loss_l',
              baslik: t('fici.tablo.fire'),
              sagaYasli: true,
              gizleKucuk: true,
              hucre: (r) => sayi(r.total_loss_l, 1),
            },
            {
              anahtar: 'qr',
              baslik: t('fici.tablo.qr'),
              genislik: '50px',
              hucre: (r) => (
                <a
                  href={`/api/v1/barrels/${r.id}/qr.png`}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  <QrCode className="h-4 w-4 opacity-70 hover:opacity-100" />
                </a>
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
          onSatirTikla={
            yetkiVar('barrel:write')
              ? (r) => {
                  setHareketFici(r)
                  setHareket({
                    movement_type: r.status === 'dolu' ? 'topping' : 'dolum',
                    lot_id: '',
                    volume_l: r.status === 'dolu' ? '2' : String(r.capacity_l - 5),
                    loss_l: '0',
                    notes: '',
                  })
                }
              : undefined
          }
          bosMetin={t('fici.bos.kayit')}
        />
      )}

      <Kip
        acik={hareketFici !== null}
        baslik={`${t('fici.kip.hareket')} — ${hareketFici?.code ?? ''}`}
        onKapat={() => setHareketFici(null)}
      >
        <form onSubmit={hareketKaydet} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}
          <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
            {t('fici.hareket.mevcut')}: {sayi(hareketFici?.current_volume_l, 1)} /{' '}
            {sayi(hareketFici?.capacity_l, 0)} L · {t('fici.hareket.durum')}:{' '}
            {etiket(hareketFici?.status)}
          </p>

          <Alan etiket={t('fici.alan.islemturu')} gerekli>
            <select
              className="girdi"
              value={hareket.movement_type}
              onChange={(e) => setHareket({ ...hareket, movement_type: e.target.value })}
            >
              <option value="dolum">{t('fici.hareket.dolum')}</option>
              <option value="topping">{t('fici.hareket.topping')}</option>
              <option value="bosaltim">{t('fici.hareket.bosaltim')}</option>
              <option value="aktarma">{t('fici.hareket.aktarma')}</option>
              <option value="temizlik">{t('fici.hareket.temizlik')}</option>
              <option value="onarim">{t('fici.hareket.onarim')}</option>
            </select>
          </Alan>

          {(hareket.movement_type === 'dolum' || hareket.movement_type === 'topping') && (
            <Alan etiket={t('fici.alan.parti')} gerekli={hareket.movement_type === 'dolum'}>
              <select
                className="girdi"
                value={hareket.lot_id}
                onChange={(e) => setHareket({ ...hareket, lot_id: e.target.value })}
                required={hareket.movement_type === 'dolum'}
              >
                <option value="">{t('fici.secim.seciniz')}</option>
                {partiSecenek.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.ad} — {String(p.ham.name)} ({sayi(Number(p.ham.volume_l), 0)} L)
                  </option>
                ))}
              </select>
            </Alan>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('fici.alan.hacim')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                min="0"
                value={hareket.volume_l}
                onChange={(e) => setHareket({ ...hareket, volume_l: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('fici.alan.fire')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                min="0"
                value={hareket.loss_l}
                onChange={(e) => setHareket({ ...hareket, loss_l: e.target.value })}
              />
            </Alan>
          </div>

          <Alan etiket={t('fici.alan.not')}>
            <input
              className="girdi"
              value={hareket.notes}
              onChange={(e) => setHareket({ ...hareket, notes: e.target.value })}
            />
          </Alan>

          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setHareketFici(null)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              <Droplets className="h-4 w-4" /> {t('genel.kaydet')}
            </button>
          </div>
        </form>
      </Kip>
    </div>
  )
}
