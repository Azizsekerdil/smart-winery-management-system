import { Loader2, Wine } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alan, HataKutusu } from '@/components/Ortak'
import { hataMesaji } from '@/lib/api'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

export default function Giris() {
  const t = useCeviri()
  const [kullaniciAdi, setKullaniciAdi] = useState('')
  const [parola, setParola] = useState('')
  const [hata, setHata] = useState('')
  const [gonderiliyor, setGonderiliyor] = useState(false)
  const girisYap = useOturum((s) => s.girisYap)
  const navigate = useNavigate()

  async function gonder(e: FormEvent) {
    e.preventDefault()
    setHata('')
    setGonderiliyor(true)
    try {
      await girisYap(kullaniciAdi.trim(), parola)
      navigate('/', { replace: true })
    } catch (err) {
      setHata(hataMesaji(err, t('giris.hata')))
    } finally {
      setGonderiliyor(false)
    }
  }

  return (
    <div
      className="grid min-h-screen place-items-center p-4"
      style={{
        background:
          'radial-gradient(1200px 600px at 20% -10%, rgba(151,31,72,0.22), transparent), var(--yuzey)',
      }}
    >
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <div
            className="grid h-14 w-14 place-items-center rounded-2xl text-white shadow-lg"
            style={{ background: 'linear-gradient(135deg,#971f48,#5c1a2b)' }}
            aria-hidden
          >
            <Wine className="h-7 w-7" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">{t('app.ad')}</h1>
            <p className="mt-1 text-xs" style={{ color: 'var(--metin-2)' }}>
              {t('giris.slogan')}
            </p>
          </div>
        </div>

        <form onSubmit={gonder} className="kart space-y-4 p-5">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

          <Alan etiket={t('giris.kullanici')} gerekli>
            <input
              className="girdi"
              value={kullaniciAdi}
              onChange={(e) => setKullaniciAdi(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </Alan>

          <Alan etiket={t('giris.parola')} gerekli>
            <input
              className="girdi"
              type="password"
              value={parola}
              onChange={(e) => setParola(e.target.value)}
              autoComplete="current-password"
              required
            />
          </Alan>

          <button
            type="submit"
            className="dugme dugme-birincil w-full"
            disabled={gonderiliyor || !kullaniciAdi || !parola}
          >
            {gonderiliyor && <Loader2 className="h-4 w-4 animate-spin" />}
            {t('giris.gonder')}
          </button>

          <p className="text-center text-[11px]" style={{ color: 'var(--metin-2)' }}>
            {t('giris.yardim')}
          </p>

          {/* Ilk kurulum uyarisi: gecici parolanin nereden alinacagi, degistirme
              zorunlulugu ve yalnizca-yerel kisiti burada acikca yazilir. */}
          <p className="text-center text-[11px]" style={{ color: 'var(--metin-2)' }}>
            {t('giris.ilkkurulum')}
          </p>
        </form>
      </div>
    </div>
  )
}
