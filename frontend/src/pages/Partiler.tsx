import { useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alan, HataKutusu, Kip, Rozet, SayfaBasligi } from '@/components/Ortak'
import { Tablo } from '@/components/Tablo'
import { api, hataMesaji } from '@/lib/api'
import { asamaEtiketleri, etiket, sayi } from '@/lib/bicim'
import { useListe, useSecenekler } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

interface Parti {
  id: number
  code: string
  name: string
  vintage_year: number
  wine_type: string
  stage: string
  status: string
  volume_l: number
  variety_name: string | null
  tank_code: string | null
  is_blend: boolean
  current_ph: number | null
  current_alcohol: number | null
}

interface KaynakSatiri {
  intake_id: string
  weight_kg: string
  juice_yield_l: string
}

export default function Partiler() {
  const t = useCeviri()
  const navigate = useNavigate()
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const [asama, setAsama] = useState('')
  const [kipAcik, setKipAcik] = useState(false)
  const [hata, setHata] = useState('')

  const liste = useListe<Parti>('/lots', asama ? { stage: asama } : {})
  const tankSecenek = useSecenekler('/tanks', 'code')
  const kabulSecenek = useSecenekler('/harvest-intakes', 'code')

  const [form, setForm] = useState({ name: '', wine_type: 'kirmizi', volume_l: '', current_tank_id: '' })
  const [kaynaklar, setKaynaklar] = useState<KaynakSatiri[]>([
    { intake_id: '', weight_kg: '', juice_yield_l: '' },
  ])

  async function partiOlustur(e: FormEvent) {
    e.preventDefault()
    setHata('')
    try {
      const gecerli = kaynaklar.filter((k) => k.intake_id && k.weight_kg)
      if (gecerli.length === 0) {
        setHata(t('partiler.hata.kaynakyok'))
        return
      }
      const { data } = await api.post('/lots/with-sources', {
        name: form.name,
        wine_type: form.wine_type,
        volume_l: Number(form.volume_l || 0),
        current_tank_id: form.current_tank_id ? Number(form.current_tank_id) : undefined,
        sources: gecerli.map((k) => ({
          intake_id: Number(k.intake_id),
          weight_kg: Number(k.weight_kg),
          juice_yield_l: k.juice_yield_l ? Number(k.juice_yield_l) : undefined,
        })),
      })
      setKipAcik(false)
      setKaynaklar([{ intake_id: '', weight_kg: '', juice_yield_l: '' }])
      void istemci.invalidateQueries({ queryKey: ['/lots'] })
      navigate(`/partiler/${data.id}`)
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  return (
    <div>
      <SayfaBasligi
        baslik={t('partiler.baslik')}
        aciklama={t('partiler.aciklama')}
        eylemler={
          yetkiVar('lot:write') ? (
            <button type="button" className="dugme dugme-birincil" onClick={() => setKipAcik(true)}>
              <Plus className="h-4 w-4" /> {t('partiler.dugme.olustur')}
            </button>
          ) : null
        }
      />

      <Tablo
        sutunlar={[
          { anahtar: 'code', baslik: t('partiler.tablo.kod'), genislik: '150px' },
          {
            anahtar: 'name',
            baslik: t('partiler.tablo.ad'),
            hucre: (r) => (
              <span className="flex items-center gap-2">
                {r.name}
                {r.is_blend && <Rozet>{t('partiler.rozet.kupaj')}</Rozet>}
              </span>
            ),
          },
          { anahtar: 'vintage_year', baslik: t('partiler.tablo.rekolte'), sagaYasli: true, genislik: '80px' },
          { anahtar: 'wine_type', baslik: t('partiler.tablo.tip'), hucre: (r) => etiket(r.wine_type) },
          { anahtar: 'variety_name', baslik: t('partiler.tablo.cesit'), gizleKucuk: true, hucre: (r) => r.variety_name ?? '—' },
          { anahtar: 'stage', baslik: t('partiler.tablo.asama'), hucre: (r) => <Rozet>{asamaEtiketleri()[r.stage] ?? r.stage}</Rozet> },
          {
            anahtar: 'status',
            baslik: t('partiler.tablo.durum'),
            hucre: (r) => (
              <Rozet seviye={r.status === 'karantina' ? 'kritik' : r.status === 'aktif' ? 'dusuk' : undefined}>
                {etiket(r.status)}
              </Rozet>
            ),
          },
          { anahtar: 'volume_l', baslik: t('partiler.tablo.hacim'), sagaYasli: true, hucre: (r) => sayi(r.volume_l, 0) },
          { anahtar: 'tank_code', baslik: t('partiler.tablo.tank'), hucre: (r) => r.tank_code ?? '—' },
          {
            anahtar: 'current_alcohol',
            baslik: t('partiler.tablo.alkol'),
            sagaYasli: true,
            gizleKucuk: true,
            hucre: (r) => (r.current_alcohol ? `${sayi(r.current_alcohol, 1)} %` : '—'),
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
        aramaIpucu={t('partiler.arama')}
        onSatirTikla={(r) => navigate(`/partiler/${r.id}`)}
        bosMetin={t('partiler.bos')}
        bosIpucu={t('partiler.bosipucu')}
        ustBar={
          <select
            className="girdi w-auto"
            value={asama}
            onChange={(e) => setAsama(e.target.value)}
            aria-label={t('partiler.filtre.arialabel')}
          >
            <option value="">{t('partiler.filtre.tumasamalar')}</option>
            {Object.entries(asamaEtiketleri()).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        }
      />

      <Kip acik={kipAcik} baslik={t('partiler.kip.baslik')} onKapat={() => setKipAcik(false)} genis>
        <form onSubmit={partiOlustur} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('partiler.form.ad')} gerekli>
              <input
                className="girdi"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder={t('partiler.form.adornek')}
                minLength={2}
                required
              />
            </Alan>
            <Alan etiket={t('partiler.form.tip')}>
              <select
                className="girdi"
                value={form.wine_type}
                onChange={(e) => setForm({ ...form, wine_type: e.target.value })}
              >
                <option value="kirmizi">{t('partiler.tip.kirmizi')}</option>
                <option value="beyaz">{t('partiler.tip.beyaz')}</option>
                <option value="rose">{t('partiler.tip.rose')}</option>
                <option value="kopuklu">{t('partiler.tip.kopuklu')}</option>
                <option value="tatli">{t('partiler.tip.tatli')}</option>
              </select>
            </Alan>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('partiler.form.hacim')} ipucu={t('partiler.form.hacimipucu')}>
              <input
                className="girdi"
                type="number"
                step="0.1"
                min="0"
                value={form.volume_l}
                onChange={(e) => setForm({ ...form, volume_l: e.target.value })}
              />
            </Alan>
            <Alan etiket={t('partiler.form.tank')}>
              <select
                className="girdi"
                value={form.current_tank_id}
                onChange={(e) => setForm({ ...form, current_tank_id: e.target.value })}
              >
                <option value="">—</option>
                {tankSecenek.data?.map((tk) => (
                  <option key={tk.id} value={tk.id}>
                    {tk.ad} ({sayi(Number(tk.ham.capacity_l), 0)} L)
                  </option>
                ))}
              </select>
            </Alan>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium">{t('partiler.form.kaynakbaslik')}</p>
            <div className="space-y-2">
              {kaynaklar.map((k, i) => (
                <div key={i} className="grid gap-2 sm:grid-cols-[2fr_1fr_1fr_auto]">
                  <select
                    className="girdi"
                    value={k.intake_id}
                    onChange={(e) => {
                      const y = [...kaynaklar]
                      y[i] = { ...y[i], intake_id: e.target.value }
                      setKaynaklar(y)
                    }}
                  >
                    <option value="">{t('partiler.form.kabulsec')}</option>
                    {kabulSecenek.data?.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.ad} · {sayi(Number(c.ham.net_weight_kg), 0)} kg
                      </option>
                    ))}
                  </select>
                  <input
                    className="girdi"
                    type="number"
                    step="0.1"
                    placeholder={t('partiler.form.agirlikipucu')}
                    value={k.weight_kg}
                    onChange={(e) => {
                      const y = [...kaynaklar]
                      y[i] = { ...y[i], weight_kg: e.target.value }
                      setKaynaklar(y)
                    }}
                  />
                  <input
                    className="girdi"
                    type="number"
                    step="0.1"
                    placeholder={t('partiler.form.siraipucu')}
                    value={k.juice_yield_l}
                    onChange={(e) => {
                      const y = [...kaynaklar]
                      y[i] = { ...y[i], juice_yield_l: e.target.value }
                      setKaynaklar(y)
                    }}
                  />
                  <button
                    type="button"
                    className="dugme dugme-ikincil"
                    onClick={() => setKaynaklar(kaynaklar.filter((_, j) => j !== i))}
                    disabled={kaynaklar.length === 1}
                    aria-label={t('partiler.form.satirkaldir')}
                  >
                    −
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="dugme dugme-ikincil mt-2"
              onClick={() => setKaynaklar([...kaynaklar, { intake_id: '', weight_kg: '', juice_yield_l: '' }])}
            >
              <Plus className="h-3.5 w-3.5" /> {t('partiler.form.kaynakekle')}
            </button>
          </div>

          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setKipAcik(false)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('partiler.dugme.olustur')}
            </button>
          </div>
        </form>
      </Kip>
    </div>
  )
}
