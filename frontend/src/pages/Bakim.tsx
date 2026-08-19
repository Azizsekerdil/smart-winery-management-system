import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Plus, Wrench } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Alan, HataKutusu, Kart, Kip, Rozet, SayfaBasligi } from '@/components/Ortak'
import { Tablo } from '@/components/Tablo'
import { api, hataMesaji } from '@/lib/api'
import { etiket, para, sayi, tarih, tarihSaat } from '@/lib/bicim'
import { useListe, useSecenekler } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

export default function Bakim() {
  const t = useCeviri()
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const [sekme, setSekme] = useState<'ekipman' | 'kayit'>('ekipman')
  const [kipAcik, setKipAcik] = useState(false)
  const [hata, setHata] = useState('')

  const ekipmanlar = useListe<Record<string, unknown>>('/equipment', {}, { etkin: sekme === 'ekipman' })
  const kayitlar = useListe<Record<string, unknown>>('/maintenance', {}, { etkin: sekme === 'kayit' })

  const yaklasan = useQuery({
    queryKey: ['/maintenance/due'],
    queryFn: async () => (await api.get<Record<string, unknown>[]>('/maintenance/due')).data,
  })

  const ekipmanSecenek = useSecenekler('/equipment', 'name')
  const tankSecenek = useSecenekler('/tanks', 'code')

  const [form, setForm] = useState({
    kind: 'periyodik',
    equipment_id: '',
    tank_id: '',
    title: '',
    description: '',
    finished: true,
    downtime_minutes: '',
    cost: '',
    cip_chemical: '',
    cip_temperature_c: '',
    cip_duration_min: '',
    cip_verified: false,
  })

  async function kaydet(e: FormEvent) {
    e.preventDefault()
    setHata('')
    try {
      const simdi = new Date().toISOString()
      const govde: Record<string, unknown> = {
        kind: form.kind,
        title: form.title,
        description: form.description || undefined,
        started_at: simdi,
        cost: Number(form.cost || 0),
      }
      if (form.finished) govde.finished_at = simdi
      if (form.equipment_id) govde.equipment_id = Number(form.equipment_id)
      if (form.tank_id) govde.tank_id = Number(form.tank_id)
      if (form.downtime_minutes) govde.downtime_minutes = Number(form.downtime_minutes)
      if (form.kind === 'cip' || form.kind === 'temizlik') {
        if (form.cip_chemical) govde.cip_chemical = form.cip_chemical
        if (form.cip_temperature_c) govde.cip_temperature_c = Number(form.cip_temperature_c)
        if (form.cip_duration_min) govde.cip_duration_min = Number(form.cip_duration_min)
        govde.cip_verified = form.cip_verified
      }
      await api.post('/maintenance/log', govde)
      setKipAcik(false)
      void istemci.invalidateQueries({ queryKey: ['/maintenance'] })
      void istemci.invalidateQueries({ queryKey: ['/equipment'] })
      void istemci.invalidateQueries({ queryKey: ['/maintenance/due'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  const gecikmis = (yaklasan.data ?? []).filter((x) => x.overdue)

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('bakim.baslik')}
        aciklama={t('bakim.aciklama')}
        eylemler={
          yetkiVar('maintenance:write') ? (
            <button type="button" className="dugme dugme-birincil" onClick={() => setKipAcik(true)}>
              <Plus className="h-4 w-4" /> {t('bakim.dugme.yenikayit')}
            </button>
          ) : null
        }
      />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

      {(yaklasan.data?.length ?? 0) > 0 && (
        <Kart
          baslik={t('bakim.yaklasan.baslik')}
          aciklama={`${gecikmis.length} ${t('bakim.yaklasan.gecikmis')} · ${(yaklasan.data?.length ?? 0) - gecikmis.length} ${t('bakim.yaklasan.yaklasan')}`}
          govdeSinif="p-0"
        >
          <table className="tablo">
            <thead>
              <tr>
                <th>{t('bakim.yaklasan.ekipman')}</th>
                <th>{t('bakim.yaklasan.tur')}</th>
                <th>{t('bakim.yaklasan.planlanantarih')}</th>
                <th className="text-right">{t('bakim.yaklasan.kalangun')}</th>
                <th>{t('bakim.yaklasan.durum')}</th>
              </tr>
            </thead>
            <tbody>
              {yaklasan.data?.map((y) => (
                <tr key={String(y.equipment_id)} className={y.overdue ? 'bg-amber-500/5' : undefined}>
                  <td className="font-medium">{String(y.name)}</td>
                  <td>{etiket(String(y.equipment_type))}</td>
                  <td>{tarih(y.next_maintenance_at as string)}</td>
                  <td className="text-right tabular-nums">
                    {y.overdue ? (
                      <span className="font-semibold text-amber-600 dark:text-amber-400">
                        <AlertTriangle className="mr-1 inline h-3.5 w-3.5" />
                        {Math.abs(Number(y.days_left))} {t('bakim.yaklasan.gungecikti')}
                      </span>
                    ) : (
                      `${Number(y.days_left)} ${t('bakim.birim.gun')}`
                    )}
                  </td>
                  <td>
                    <Rozet seviye={y.status === 'arizali' ? 'kritik' : undefined}>
                      {etiket(String(y.status))}
                    </Rozet>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Kart>
      )}

      <div className="flex gap-1 border-b" style={{ borderColor: 'var(--kenar)' }}>
        {(
          [
            ['ekipman', t('bakim.sekme.ekipman')],
            ['kayit', t('bakim.sekme.kayit')],
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

      {sekme === 'ekipman' ? (
        <Tablo
          sutunlar={[
            { anahtar: 'code', baslik: t('bakim.ekipman.kod'), genislik: '100px' },
            { anahtar: 'name', baslik: t('bakim.ekipman.ad') },
            { anahtar: 'equipment_type', baslik: t('bakim.ekipman.tur'), hucre: (r) => etiket(r.equipment_type as string) },
            { anahtar: 'manufacturer', baslik: t('bakim.ekipman.uretici'), gizleKucuk: true, hucre: (r) => (r.manufacturer as string) ?? '—' },
            {
              anahtar: 'status',
              baslik: t('bakim.ekipman.durum'),
              hucre: (r) => (
                <Rozet seviye={r.status === 'arizali' ? 'kritik' : r.status === 'calisiyor' ? 'dusuk' : 'orta'}>
                  {etiket(r.status as string)}
                </Rozet>
              ),
            },
            { anahtar: 'last_maintenance_at', baslik: t('bakim.ekipman.sonbakim'), hucre: (r) => tarih(r.last_maintenance_at as string) },
            { anahtar: 'next_maintenance_at', baslik: t('bakim.ekipman.sonrakibakim'), hucre: (r) => tarih(r.next_maintenance_at as string) },
            {
              anahtar: 'maintenance_due_days',
              baslik: t('bakim.ekipman.kalan'),
              sagaYasli: true,
              hucre: (r) =>
                r.maintenance_due_days === null ? '—' : `${Number(r.maintenance_due_days)} ${t('bakim.birim.gun')}`,
            },
          ]}
          satirlar={ekipmanlar.satirlar}
          yukleniyor={ekipmanlar.isLoading}
          toplam={ekipmanlar.toplam}
          sayfa={ekipmanlar.sayfa}
          sayfaBoyu={ekipmanlar.sayfaBoyu}
          onSayfa={ekipmanlar.setSayfa}
          arama={ekipmanlar.arama}
          onArama={ekipmanlar.setArama}
          bosMetin={t('bakim.ekipman.bos')}
        />
      ) : (
        <Tablo
          sutunlar={[
            { anahtar: 'code', baslik: t('bakim.kayit.kod'), genislik: '130px' },
            { anahtar: 'kind', baslik: t('bakim.kayit.tur'), hucre: (r) => <Rozet>{etiket(r.kind as string)}</Rozet> },
            { anahtar: 'title', baslik: t('bakim.kayit.baslik') },
            { anahtar: 'equipment_name', baslik: t('bakim.kayit.ekipman'), hucre: (r) => (r.equipment_name as string) ?? (r.tank_code as string) ?? '—' },
            { anahtar: 'started_at', baslik: t('bakim.kayit.baslangic'), hucre: (r) => tarihSaat(r.started_at as string) },
            { anahtar: 'finished_at', baslik: t('bakim.kayit.bitis'), gizleKucuk: true, hucre: (r) => tarihSaat(r.finished_at as string) },
            { anahtar: 'downtime_minutes', baslik: t('bakim.kayit.durus'), sagaYasli: true, gizleKucuk: true, hucre: (r) => sayi(r.downtime_minutes as number, 0) },
            { anahtar: 'cost', baslik: t('bakim.kayit.maliyet'), sagaYasli: true, hucre: (r) => para(r.cost as number) },
            { anahtar: 'responsible_name', baslik: t('bakim.kayit.sorumlu'), gizleKucuk: true, hucre: (r) => (r.responsible_name as string) ?? '—' },
          ]}
          satirlar={kayitlar.satirlar}
          yukleniyor={kayitlar.isLoading}
          toplam={kayitlar.toplam}
          sayfa={kayitlar.sayfa}
          sayfaBoyu={kayitlar.sayfaBoyu}
          onSayfa={kayitlar.setSayfa}
          arama={kayitlar.arama}
          onArama={kayitlar.setArama}
          bosMetin={t('bakim.kayit.bos')}
        />
      )}

      <Kip acik={kipAcik} baslik={t('bakim.kip.baslik')} onKapat={() => setKipAcik(false)}>
        <form onSubmit={kaydet} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

          <Alan etiket={t('bakim.form.tur')} gerekli>
            <select
              className="girdi"
              value={form.kind}
              onChange={(e) => setForm({ ...form, kind: e.target.value })}
            >
              <option value="periyodik">{t('bakim.tur.periyodik')}</option>
              <option value="ariza">{t('bakim.tur.ariza')}</option>
              <option value="kalibrasyon">{t('bakim.tur.kalibrasyon')}</option>
              <option value="cip">{t('bakim.tur.cip')}</option>
              <option value="temizlik">{t('bakim.tur.temizlik')}</option>
            </select>
          </Alan>

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('bakim.form.ekipman')}>
              <select
                className="girdi"
                value={form.equipment_id}
                onChange={(e) => setForm({ ...form, equipment_id: e.target.value, tank_id: '' })}
              >
                <option value="">—</option>
                {ekipmanSecenek.data?.map((e2) => (
                  <option key={e2.id} value={e2.id}>
                    {e2.ad}
                  </option>
                ))}
              </select>
            </Alan>
            <Alan etiket={t('bakim.form.tank')} ipucu={t('bakim.form.tankipucu')}>
              <select
                className="girdi"
                value={form.tank_id}
                onChange={(e) => setForm({ ...form, tank_id: e.target.value, equipment_id: '' })}
              >
                <option value="">—</option>
                {tankSecenek.data?.map((t2) => (
                  <option key={t2.id} value={t2.id}>
                    {t2.ad}
                  </option>
                ))}
              </select>
            </Alan>
          </div>

          <Alan etiket={t('bakim.form.baslik')} gerekli>
            <input
              className="girdi"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              required
              minLength={2}
            />
          </Alan>

          <Alan etiket={t('bakim.form.aciklama')}>
            <textarea
              className="girdi"
              rows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Alan>

          {(form.kind === 'cip' || form.kind === 'temizlik') && (
            <div className="space-y-3 rounded-lg border p-3" style={{ borderColor: 'var(--kenar)' }}>
              <p className="text-xs font-medium">{t('bakim.form.cipbaslik')}</p>
              <div className="grid gap-3 sm:grid-cols-3">
                <Alan etiket={t('bakim.form.kimyasal')}>
                  <input
                    className="girdi"
                    value={form.cip_chemical}
                    onChange={(e) => setForm({ ...form, cip_chemical: e.target.value })}
                    placeholder={t('bakim.form.kimyasalornek')}
                  />
                </Alan>
                <Alan etiket={t('bakim.form.sicaklik')}>
                  <input
                    className="girdi"
                    type="number"
                    step="0.5"
                    value={form.cip_temperature_c}
                    onChange={(e) => setForm({ ...form, cip_temperature_c: e.target.value })}
                  />
                </Alan>
                <Alan etiket={t('bakim.form.sure')}>
                  <input
                    className="girdi"
                    type="number"
                    value={form.cip_duration_min}
                    onChange={(e) => setForm({ ...form, cip_duration_min: e.target.value })}
                  />
                </Alan>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.cip_verified}
                  onChange={(e) => setForm({ ...form, cip_verified: e.target.checked })}
                />
                {t('bakim.form.dogrulandi')}
              </label>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('bakim.form.durus')}>
              <input
                className="girdi"
                type="number"
                min="0"
                value={form.downtime_minutes}
                onChange={(e) => setForm({ ...form, downtime_minutes: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('bakim.form.maliyet')}>
              <input
                className="girdi"
                type="number"
                step="0.01"
                min="0"
                value={form.cost}
                onChange={(e) => setForm({ ...form, cost: e.target.value })}
              />
            </Alan>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.finished}
              onChange={(e) => setForm({ ...form, finished: e.target.checked })}
            />
            {t('bakim.form.tamamlandi')}
          </label>

          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setKipAcik(false)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              <Wrench className="h-4 w-4" /> {t('genel.kaydet')}
            </button>
          </div>
        </form>
      </Kip>
    </div>
  )
}
