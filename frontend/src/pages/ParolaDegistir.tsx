/**
 * Zorunlu parola değiştirme ekranı.
 *
 * Sunucu, `must_change_password` işaretli bir hesabın `/auth/me`,
 * `/auth/change-password` ve `/auth/logout` dışındaki HİÇBİR uç noktasını
 * açmaz (bkz. `backend/app/core/deps.py`). Bu ekran o kuralın kullanıcı
 * tarafındaki karşılığıdır: kilidi kaldırmanın tek yolu.
 *
 * Kilit sunucuda uygulanır; bu ekran yalnızca yol gösterir. Arayüzü atlayıp
 * API'yi doğrudan çağıran bir istemci de aynı 403 yanıtını alır.
 */
import { AlertTriangle, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '@/lib/api'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

export default function ParolaDegistir() {
  const t = useCeviri()
  const { kullanici, beniYukle, cikisYap } = useOturum()
  const [eski, setEski] = useState('')
  const [yeni, setYeni] = useState('')
  const [tekrar, setTekrar] = useState('')
  const [hata, setHata] = useState<string | null>(null)
  const [gonderiliyor, setGonderiliyor] = useState(false)

  const eslesmiyor = tekrar.length > 0 && yeni !== tekrar

  async function gonder(e: React.FormEvent) {
    e.preventDefault()
    setHata(null)
    if (yeni !== tekrar) {
      setHata(t('parola.eslesmiyor'))
      return
    }
    setGonderiliyor(true)
    try {
      await api.post('/auth/change-password', { old_password: eski, new_password: yeni })
      // Sunucu diğer oturumları kapatır; kendi oturumumuzu tazeleyip devam ederiz.
      await beniYukle()
    } catch (err) {
      const yanit = (err as { response?: { data?: { detail?: unknown } } }).response
      const detay = yanit?.data?.detail
      setHata(typeof detay === 'string' ? detay : t('parola.hata'))
    } finally {
      setGonderiliyor(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center p-4">
      <div className="w-full max-w-md space-y-4">
        <div
          className="flex gap-3 rounded-lg border p-3 text-sm"
          style={{ borderColor: 'var(--uyari)', color: 'var(--metin-1)' }}
          role="alert"
        >
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" style={{ color: 'var(--uyari)' }} />
          <div>
            <p className="font-semibold">{t('parola.zorunlu.baslik')}</p>
            <p style={{ color: 'var(--metin-2)' }}>{t('parola.zorunlu.aciklama')}</p>
          </div>
        </div>

        <form onSubmit={gonder} className="kart space-y-3 p-5">
          <p className="text-sm" style={{ color: 'var(--metin-2)' }}>
            {kullanici?.username}
          </p>

          <label className="block space-y-1">
            <span className="text-sm">{t('parola.mevcut')}</span>
            <input
              className="girdi"
              type="password"
              value={eski}
              onChange={(e) => setEski(e.target.value)}
              autoComplete="current-password"
              autoFocus
              required
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm">{t('parola.yeni')}</span>
            <input
              className="girdi"
              type="password"
              value={yeni}
              onChange={(e) => setYeni(e.target.value)}
              autoComplete="new-password"
              minLength={10}
              required
            />
            <span className="text-[11px]" style={{ color: 'var(--metin-2)' }}>
              {t('parola.kural')}
            </span>
          </label>

          <label className="block space-y-1">
            <span className="text-sm">{t('parola.tekrar')}</span>
            <input
              className="girdi"
              type="password"
              value={tekrar}
              onChange={(e) => setTekrar(e.target.value)}
              autoComplete="new-password"
              required
            />
          </label>

          {(hata || eslesmiyor) && (
            <p className="text-sm" style={{ color: 'var(--hata)' }} role="alert">
              {hata ?? t('parola.eslesmiyor')}
            </p>
          )}

          <button
            type="submit"
            className="dugme dugme-birincil w-full"
            disabled={gonderiliyor || !eski || !yeni || !tekrar || eslesmiyor}
          >
            {gonderiliyor && <Loader2 className="h-4 w-4 animate-spin" />}
            {t('parola.gonder')}
          </button>

          <button type="button" className="dugme w-full" onClick={() => void cikisYap()}>
            {t('kabuk.cikis')}
          </button>
        </form>
      </div>
    </div>
  )
}
