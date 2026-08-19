import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowDownToLine, ArrowUpFromLine, Repeat } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Alan, Bos, HataKutusu, Kart, Kip, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { api, hataMesaji } from '@/lib/api'
import { etiket, para, sayi, tarih, tarihSaat } from '@/lib/bicim'
import { useSecenekler } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

interface Seviye {
  item_id: number
  item_code: string
  item_name: string
  category: string
  unit: string
  on_hand: number
  min_stock: number
  below_min: boolean
  stock_value: number
  warehouses: Record<string, number>
  nearest_expiry: string | null
}

type Islem = 'giris' | 'cikis' | 'transfer' | 'sayim'

export default function Stok() {
  const t = useCeviri()
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const [sekme, setSekme] = useState<'seviye' | 'hareket' | 'sevkiyat' | 'satinalma'>('seviye')
  const [kategori, setKategori] = useState('')
  const [islem, setIslem] = useState<Islem | null>(null)
  const [hata, setHata] = useState('')

  const seviyeler = useQuery({
    queryKey: ['/stock/levels', kategori],
    queryFn: async () =>
      (await api.get<Seviye[]>('/stock/levels', { params: { category: kategori || undefined } })).data,
    enabled: sekme === 'seviye',
  })

  const hareketler = useQuery({
    queryKey: ['/stock/movements'],
    queryFn: async () =>
      (await api.get<Record<string, unknown>[]>('/stock/movements', { params: { limit: 300 } })).data,
    enabled: sekme === 'hareket',
  })

  const sevkiyatlar = useQuery({
    queryKey: ['/shipments'],
    queryFn: async () => (await api.get<Record<string, unknown>[]>('/shipments')).data,
    enabled: sekme === 'sevkiyat',
  })

  const siparisler = useQuery({
    queryKey: ['/purchases'],
    queryFn: async () => (await api.get<Record<string, unknown>[]>('/purchases')).data,
    enabled: sekme === 'satinalma',
  })

  const kalemSecenek = useSecenekler('/items', 'name')
  const depoSecenek = useSecenekler('/warehouses', 'name')

  const [form, setForm] = useState({
    item_id: '',
    warehouse_id: '',
    to_warehouse_id: '',
    quantity: '',
    unit_cost: '',
    counted_quantity: '',
    batch_code: '',
    expiry_date: '',
    notes: '',
  })

  async function islemYap(e: FormEvent) {
    e.preventDefault()
    setHata('')
    try {
      if (islem === 'giris') {
        await api.post('/stock/in', {
          item_id: Number(form.item_id),
          warehouse_id: Number(form.warehouse_id),
          quantity: Number(form.quantity),
          unit_cost: Number(form.unit_cost || 0),
          batch_code: form.batch_code || undefined,
          expiry_date: form.expiry_date || undefined,
          notes: form.notes || undefined,
        })
      } else if (islem === 'cikis') {
        await api.post('/stock/out', {
          item_id: Number(form.item_id),
          warehouse_id: Number(form.warehouse_id),
          quantity: Number(form.quantity),
          notes: form.notes || undefined,
        })
      } else if (islem === 'transfer') {
        await api.post('/stock/transfer', {
          item_id: Number(form.item_id),
          from_warehouse_id: Number(form.warehouse_id),
          to_warehouse_id: Number(form.to_warehouse_id),
          quantity: Number(form.quantity),
          notes: form.notes || undefined,
        })
      } else if (islem === 'sayim') {
        await api.post('/stock/count', {
          item_id: Number(form.item_id),
          warehouse_id: Number(form.warehouse_id),
          counted_quantity: Number(form.counted_quantity),
          notes: form.notes || undefined,
        })
      }
      setIslem(null)
      setForm({ ...form, quantity: '', counted_quantity: '', batch_code: '', notes: '' })
      void istemci.invalidateQueries({ queryKey: ['/stock/levels'] })
      void istemci.invalidateQueries({ queryKey: ['/stock/movements'] })
      void istemci.invalidateQueries({ queryKey: ['pano'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  const baslik: Record<Islem, string> = {
    giris: t('stok.kip.giris'),
    cikis: t('stok.kip.cikis'),
    transfer: t('stok.kip.transfer'),
    sayim: t('stok.kip.sayim'),
  }

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('stok.baslik')}
        aciklama={t('stok.aciklama')}
        eylemler={
          yetkiVar('inventory:write') ? (
            <>
              <button type="button" className="dugme dugme-ikincil" onClick={() => setIslem('giris')}>
                <ArrowDownToLine className="h-4 w-4" /> {t('stok.dugme.giris')}
              </button>
              <button type="button" className="dugme dugme-ikincil" onClick={() => setIslem('cikis')}>
                <ArrowUpFromLine className="h-4 w-4" /> {t('stok.dugme.cikis')}
              </button>
              <button type="button" className="dugme dugme-ikincil" onClick={() => setIslem('transfer')}>
                <Repeat className="h-4 w-4" /> {t('stok.dugme.transfer')}
              </button>
              <button type="button" className="dugme dugme-birincil" onClick={() => setIslem('sayim')}>
                {t('stok.dugme.sayim')}
              </button>
            </>
          ) : null
        }
      />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

      <div className="flex flex-wrap gap-1 border-b" style={{ borderColor: 'var(--kenar)' }}>
        {(
          [
            ['seviye', t('stok.sekme.seviye')],
            ['hareket', t('stok.sekme.hareket')],
            ['satinalma', t('stok.sekme.satinalma')],
            ['sevkiyat', t('stok.sekme.sevkiyat')],
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

      {sekme === 'seviye' && (
        <>
          <select
            className="girdi w-auto"
            value={kategori}
            onChange={(e) => setKategori(e.target.value)}
            aria-label={t('stok.filtre.kategori')}
          >
            <option value="">{t('stok.kategori.tumu')}</option>
            <option value="hammadde">{t('stok.kategori.hammadde')}</option>
            <option value="katki">{t('stok.kategori.katki')}</option>
            <option value="sarf">{t('stok.kategori.sarf')}</option>
            <option value="ambalaj">{t('stok.kategori.ambalaj')}</option>
            <option value="bitmis_urun">{t('stok.kategori.bitmisurun')}</option>
            <option value="yedek_parca">{t('stok.kategori.yedekparca')}</option>
          </select>

          {seviyeler.isLoading ? (
            <Yukleniyor />
          ) : (seviyeler.data?.length ?? 0) === 0 ? (
            <Kart>
              <Bos metin={t('stok.seviye.bos')} />
            </Kart>
          ) : (
            <div className="kart overflow-x-auto">
              <table className="tablo">
                <thead>
                  <tr>
                    <th>{t('stok.tablo.kod')}</th>
                    <th>{t('stok.seviye.kalem')}</th>
                    <th>{t('stok.seviye.kategori')}</th>
                    <th className="text-right">{t('stok.seviye.mevcut')}</th>
                    <th className="text-right">{t('stok.seviye.min')}</th>
                    <th>{t('stok.seviye.depolar')}</th>
                    <th className="text-right">{t('stok.seviye.deger')}</th>
                    <th>{t('stok.seviye.skt')}</th>
                  </tr>
                </thead>
                <tbody>
                  {seviyeler.data?.map((s) => (
                    <tr key={s.item_id} className={s.below_min ? 'bg-amber-500/5' : undefined}>
                      <td className="font-mono text-xs">{s.item_code}</td>
                      <td className="font-medium">{s.item_name}</td>
                      <td>{etiket(s.category)}</td>
                      <td className="text-right tabular-nums">
                        {s.below_min && <AlertTriangle className="mr-1 inline h-3.5 w-3.5 text-amber-500" />}
                        {sayi(s.on_hand)} {s.unit}
                      </td>
                      <td className="text-right tabular-nums">{sayi(s.min_stock)}</td>
                      <td className="text-xs">
                        {Object.entries(s.warehouses)
                          .map(([d, m]) => `${d}: ${sayi(m)}`)
                          .join(' · ') || '—'}
                      </td>
                      <td className="text-right tabular-nums">{para(s.stock_value)}</td>
                      <td className="text-xs">{s.nearest_expiry ? tarih(s.nearest_expiry) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {sekme === 'hareket' &&
        (hareketler.isLoading ? (
          <Yukleniyor />
        ) : (
          <div className="kart overflow-x-auto">
            <table className="tablo">
              <thead>
                <tr>
                  <th>{t('stok.tablo.kod')}</th>
                  <th>{t('stok.hareket.tarih')}</th>
                  <th>{t('stok.hareket.kalem')}</th>
                  <th>{t('stok.hareket.tur')}</th>
                  <th className="text-right">{t('stok.hareket.miktar')}</th>
                  <th className="text-right">{t('stok.hareket.birimmaliyet')}</th>
                  <th className="text-right">{t('stok.hareket.tutar')}</th>
                  <th>{t('stok.hareket.depo')}</th>
                  <th>{t('stok.hareket.kullanici')}</th>
                </tr>
              </thead>
              <tbody>
                {hareketler.data?.map((h) => (
                  <tr key={String(h.id)}>
                    <td className="font-mono text-xs">{String(h.code)}</td>
                    <td className="whitespace-nowrap text-xs">{tarihSaat(h.occurred_at as string)}</td>
                    <td>{String(h.item_name ?? h.item_id)}</td>
                    <td>
                      <Rozet seviye={Number(h.quantity) < 0 ? 'orta' : 'dusuk'}>
                        {etiket(String(h.movement_type))}
                      </Rozet>
                    </td>
                    <td className="text-right tabular-nums">{sayi(h.quantity as number, 3)}</td>
                    <td className="text-right tabular-nums">{para(h.unit_cost as number)}</td>
                    <td className="text-right tabular-nums">{para(h.value as number)}</td>
                    <td>{String(h.warehouse_code ?? '—')}</td>
                    <td className="text-xs">{String(h.performed_by_name ?? '—')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

      {sekme === 'satinalma' &&
        (siparisler.isLoading ? (
          <Yukleniyor />
        ) : (siparisler.data?.length ?? 0) === 0 ? (
          <Kart>
            <Bos metin={t('stok.satinalma.bos')} />
          </Kart>
        ) : (
          <div className="kart overflow-x-auto">
            <table className="tablo">
              <thead>
                <tr>
                  <th>{t('stok.tablo.kod')}</th>
                  <th>{t('stok.satinalma.tedarikci')}</th>
                  <th>{t('stok.satinalma.siparistarihi')}</th>
                  <th>{t('stok.satinalma.durum')}</th>
                  <th className="text-right">{t('stok.satinalma.kalem')}</th>
                  <th className="text-right">{t('stok.satinalma.aratoplam')}</th>
                  <th className="text-right">{t('stok.satinalma.geneltoplam')}</th>
                </tr>
              </thead>
              <tbody>
                {siparisler.data?.map((s) => (
                  <tr key={String(s.id)}>
                    <td className="font-mono text-xs">{String(s.code)}</td>
                    <td>{String(s.supplier_name ?? '—')}</td>
                    <td>{tarih(s.order_date as string)}</td>
                    <td>
                      <Rozet seviye={s.status === 'teslim_alindi' ? 'dusuk' : undefined}>
                        {etiket(String(s.status))}
                      </Rozet>
                    </td>
                    <td className="text-right">{(s.lines as unknown[]).length}</td>
                    <td className="text-right tabular-nums">{para(s.subtotal as number)}</td>
                    <td className="text-right tabular-nums font-medium">{para(s.total as number)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

      {sekme === 'sevkiyat' &&
        (sevkiyatlar.isLoading ? (
          <Yukleniyor />
        ) : (sevkiyatlar.data?.length ?? 0) === 0 ? (
          <Kart>
            <Bos metin={t('stok.sevkiyat.bos')} />
          </Kart>
        ) : (
          <div className="kart overflow-x-auto">
            <table className="tablo">
              <thead>
                <tr>
                  <th>{t('stok.tablo.kod')}</th>
                  <th>{t('stok.sevkiyat.musteri')}</th>
                  <th>{t('stok.sevkiyat.siparis')}</th>
                  <th>{t('stok.sevkiyat.durum')}</th>
                  <th>{t('stok.sevkiyat.tasiyici')}</th>
                  <th className="text-right">{t('stok.sevkiyat.tutar')}</th>
                </tr>
              </thead>
              <tbody>
                {sevkiyatlar.data?.map((s) => (
                  <tr key={String(s.id)}>
                    <td className="font-mono text-xs">{String(s.code)}</td>
                    <td>{String(s.customer_name ?? '—')}</td>
                    <td>{tarih(s.order_date as string)}</td>
                    <td>
                      <Rozet seviye={s.status === 'teslim_edildi' ? 'dusuk' : undefined}>
                        {etiket(String(s.status))}
                      </Rozet>
                    </td>
                    <td>{String(s.carrier ?? '—')}</td>
                    <td className="text-right tabular-nums">{para(s.total as number)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

      {/* ------------------------------------------------------- işlem formu */}
      <Kip acik={islem !== null} baslik={islem ? baslik[islem] : ''} onKapat={() => setIslem(null)}>
        <form onSubmit={islemYap} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

          <Alan etiket={t('stok.form.kalem')} gerekli>
            <select
              className="girdi"
              value={form.item_id}
              onChange={(e) => setForm({ ...form, item_id: e.target.value })}
              required
            >
              <option value="">{t('stok.form.seciniz')}</option>
              {kalemSecenek.data?.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.ad} ({String(k.ham.unit)})
                </option>
              ))}
            </select>
          </Alan>

          <Alan etiket={islem === 'transfer' ? t('stok.form.kaynakdepo') : t('stok.form.depo')} gerekli>
            <select
              className="girdi"
              value={form.warehouse_id}
              onChange={(e) => setForm({ ...form, warehouse_id: e.target.value })}
              required
            >
              <option value="">{t('stok.form.seciniz')}</option>
              {depoSecenek.data?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.ad}
                </option>
              ))}
            </select>
          </Alan>

          {islem === 'transfer' && (
            <Alan etiket={t('stok.form.hedefdepo')} gerekli>
              <select
                className="girdi"
                value={form.to_warehouse_id}
                onChange={(e) => setForm({ ...form, to_warehouse_id: e.target.value })}
                required
              >
                <option value="">{t('stok.form.seciniz')}</option>
                {depoSecenek.data?.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.ad}
                  </option>
                ))}
              </select>
            </Alan>
          )}

          {islem === 'sayim' ? (
            <Alan etiket={t('stok.form.sayilanmiktar')} gerekli>
              <input
                className="girdi"
                type="number"
                step="0.001"
                min="0"
                value={form.counted_quantity}
                onChange={(e) => setForm({ ...form, counted_quantity: e.target.value })}
                required
              />
            </Alan>
          ) : (
            <Alan etiket={t('stok.form.miktar')} gerekli>
              <input
                className="girdi"
                type="number"
                step="0.001"
                min="0.001"
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                required
              />
            </Alan>
          )}

          {islem === 'giris' && (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <Alan etiket={t('stok.form.birimmaliyet')}>
                  <input
                    className="girdi"
                    type="number"
                    step="0.0001"
                    min="0"
                    value={form.unit_cost}
                    onChange={(e) => setForm({ ...form, unit_cost: e.target.value })}
                  />
                </Alan>
                <Alan etiket={t('stok.form.skt')}>
                  <input
                    className="girdi"
                    type="date"
                    value={form.expiry_date}
                    onChange={(e) => setForm({ ...form, expiry_date: e.target.value })}
                  />
                </Alan>
              </div>
              <Alan etiket={t('stok.form.particodu')} ipucu={t('stok.form.particoduipucu')}>
                <input
                  className="girdi"
                  value={form.batch_code}
                  onChange={(e) => setForm({ ...form, batch_code: e.target.value })}
                />
              </Alan>
            </>
          )}

          <Alan etiket={t('stok.form.not')}>
            <input
              className="girdi"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </Alan>

          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setIslem(null)}>
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
