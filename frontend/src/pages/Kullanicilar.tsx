import { useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Plus, ShieldCheck } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Alan, BilgiKutusu, HataKutusu, Kart, Kip, Rozet, SayfaBasligi } from '@/components/Ortak'
import { Tablo } from '@/components/Tablo'
import { api, hataMesaji } from '@/lib/api'
import { tarihSaat } from '@/lib/bicim'
import { useListe } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

interface Kullanici {
  id: number
  username: string
  email: string
  full_name: string
  roles: string[]
  department: string | null
  is_active: boolean
  last_login_at: string | null
  must_change_password: boolean
}

interface Rol {
  kod: string
  ad: string
  yetkiler: string[]
}

export default function Kullanicilar() {
  const t = useCeviri()
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const [kipAcik, setKipAcik] = useState(false)
  const [parolaKip, setParolaKip] = useState<Kullanici | null>(null)
  const [rolKip, setRolKip] = useState<Rol | null>(null)
  const [hata, setHata] = useState('')

  const liste = useListe<Kullanici>('/users')

  const roller = useQuery({
    queryKey: ['/users/roles'],
    queryFn: async () => (await api.get<Rol[]>('/users/roles')).data,
  })

  const yetkiEtiketleri = useQuery({
    queryKey: ['/users/permissions'],
    queryFn: async () => (await api.get<Record<string, string>>('/users/permissions')).data,
  })

  const [form, setForm] = useState({
    username: '',
    email: '',
    full_name: '',
    department: '',
    roles: [] as string[],
    password: '',
  })
  const [yeniParola, setYeniParola] = useState('')

  async function kullaniciOlustur(e: FormEvent) {
    e.preventDefault()
    setHata('')
    try {
      await api.post('/users', {
        username: form.username.trim().toLowerCase(),
        email: form.email.trim(),
        full_name: form.full_name,
        department: form.department || undefined,
        roles: form.roles,
        password: form.password,
      })
      setKipAcik(false)
      setForm({ username: '', email: '', full_name: '', department: '', roles: [], password: '' })
      void istemci.invalidateQueries({ queryKey: ['/users'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  async function parolaSifirla(e: FormEvent) {
    e.preventDefault()
    if (!parolaKip) return
    setHata('')
    try {
      await api.post(`/users/${parolaKip.id}/reset-password`, {
        new_password: yeniParola,
        must_change: true,
      })
      setParolaKip(null)
      setYeniParola('')
      void istemci.invalidateQueries({ queryKey: ['/users'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  async function durumDegistir(k: Kullanici) {
    setHata('')
    try {
      await api.patch(`/users/${k.id}`, { is_active: !k.is_active })
      void istemci.invalidateQueries({ queryKey: ['/users'] })
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  const rolAdi = (kod: string) => roller.data?.find((r) => r.kod === kod)?.ad ?? kod

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('kullanicilar.baslik')}
        aciklama={t('kullanicilar.aciklama')}
        eylemler={
          yetkiVar('user:write') ? (
            <button type="button" className="dugme dugme-birincil" onClick={() => setKipAcik(true)}>
              <Plus className="h-4 w-4" /> {t('kullanicilar.dugme.ekle')}
            </button>
          ) : null
        }
      />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

      <Tablo
        sutunlar={[
          { anahtar: 'username', baslik: t('kullanicilar.tablo.kullaniciadi'), genislik: '140px' },
          { anahtar: 'full_name', baslik: t('kullanicilar.tablo.adsoyad') },
          { anahtar: 'email', baslik: t('kullanicilar.tablo.eposta'), gizleKucuk: true },
          {
            anahtar: 'department',
            baslik: t('kullanicilar.tablo.departman'),
            gizleKucuk: true,
            hucre: (r) => r.department ?? '—',
          },
          {
            anahtar: 'roles',
            baslik: t('kullanicilar.tablo.roller'),
            hucre: (r) => (
              <div className="flex flex-wrap gap-1">
                {r.roles.map((rol) => (
                  <Rozet key={rol}>{rolAdi(rol)}</Rozet>
                ))}
              </div>
            ),
          },
          {
            anahtar: 'is_active',
            baslik: t('kullanicilar.tablo.durum'),
            hucre: (r) => (
              <Rozet seviye={r.is_active ? 'dusuk' : 'kritik'}>
                {r.is_active ? t('kullanicilar.durum.aktif') : t('kullanicilar.durum.pasif')}
              </Rozet>
            ),
          },
          {
            anahtar: 'last_login_at',
            baslik: t('kullanicilar.tablo.songiris'),
            gizleKucuk: true,
            hucre: (r) => tarihSaat(r.last_login_at),
          },
          {
            anahtar: 'islem',
            baslik: t('kullanicilar.tablo.islem'),
            hucre: (r) =>
              yetkiVar('user:write') ? (
                <div className="flex gap-1">
                  <button
                    type="button"
                    className="dugme dugme-ikincil px-2 py-1"
                    title={t('kullanicilar.dugme.parolasifirla')}
                    onClick={(e) => {
                      e.stopPropagation()
                      setParolaKip(r)
                    }}
                  >
                    <KeyRound className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    className="dugme dugme-ikincil px-2 py-1 text-xs"
                    onClick={(e) => {
                      e.stopPropagation()
                      void durumDegistir(r)
                    }}
                  >
                    {r.is_active
                      ? t('kullanicilar.dugme.pasifeal')
                      : t('kullanicilar.dugme.aktiflestir')}
                  </button>
                </div>
              ) : null,
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
        aramaIpucu={t('genel.ara')}
        bosMetin={t('kullanicilar.bos.metin')}
      />

      <Kart
        baslik={
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="h-4 w-4" /> {t('kullanicilar.kart.rolkatalog')}
          </span>
        }
        aciklama={t('kullanicilar.kart.rolaciklama')}
      >
        <div className="flex flex-wrap gap-2">
          {roller.data?.map((r) => (
            <button
              key={r.kod}
              type="button"
              onClick={() => setRolKip(r)}
              className="rounded-lg border px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--yuzey-3)]"
              style={{ borderColor: 'var(--kenar)' }}
            >
              <p className="font-medium">{r.ad}</p>
              <p className="text-[11px]" style={{ color: 'var(--metin-2)' }}>
                {r.yetkiler.length} {t('kullanicilar.rol.yetkisayisi')}
              </p>
            </button>
          ))}
        </div>
      </Kart>

      {/* -------------------------------------------------------- yeni kullanıcı */}
      <Kip acik={kipAcik} baslik={t('kullanicilar.dugme.ekle')} onKapat={() => setKipAcik(false)}>
        <form onSubmit={kullaniciOlustur} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}
          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('kullanicilar.tablo.kullaniciadi')} gerekli>
              <input
                className="girdi"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                pattern="[a-zA-Z0-9._\-]+"
                minLength={3}
                required
              />
            </Alan>
            <Alan etiket={t('kullanicilar.tablo.eposta')} gerekli>
              <input
                className="girdi"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </Alan>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Alan etiket={t('kullanicilar.tablo.adsoyad')} gerekli>
              <input
                className="girdi"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                minLength={2}
                required
              />
            </Alan>
            <Alan etiket={t('kullanicilar.tablo.departman')}>
              <input
                className="girdi"
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
              />
            </Alan>
          </div>
          <Alan etiket={t('kullanicilar.tablo.roller')} gerekli ipucu={t('kullanicilar.form.rolipucu')}>
            <select
              className="girdi"
              multiple
              size={6}
              value={form.roles}
              onChange={(e) => setForm({ ...form, roles: [...e.target.selectedOptions].map((o) => o.value) })}
              required
            >
              {roller.data?.map((r) => (
                <option key={r.kod} value={r.kod}>
                  {r.ad}
                </option>
              ))}
            </select>
          </Alan>
          <Alan
            etiket={t('kullanicilar.form.geciciparola')}
            gerekli
            ipucu={t('kullanicilar.form.parolaipucu')}
          >
            <input
              className="girdi"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              minLength={10}
              required
            />
          </Alan>
          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setKipAcik(false)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('kullanicilar.dugme.olustur')}
            </button>
          </div>
        </form>
      </Kip>

      {/* --------------------------------------------------------- parola sıfırla */}
      <Kip
        acik={parolaKip !== null}
        baslik={`${t('kullanicilar.dugme.parolasifirla')} — ${parolaKip?.username ?? ''}`}
        onKapat={() => setParolaKip(null)}
      >
        <form onSubmit={parolaSifirla} className="space-y-4">
          {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}
          <BilgiKutusu>{t('kullanicilar.parola.bilgi')}</BilgiKutusu>
          <Alan etiket={t('kullanicilar.form.yenigeciciparola')} gerekli>
            <input
              className="girdi"
              type="password"
              value={yeniParola}
              onChange={(e) => setYeniParola(e.target.value)}
              minLength={10}
              required
            />
          </Alan>
          <div className="flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setParolaKip(null)}>
              {t('genel.iptal')}
            </button>
            <button type="submit" className="dugme dugme-birincil">
              {t('kullanicilar.dugme.sifirla')}
            </button>
          </div>
        </form>
      </Kip>

      {/* ------------------------------------------------------------ rol detayı */}
      <Kip acik={rolKip !== null} baslik={rolKip?.ad ?? ''} onKapat={() => setRolKip(null)} genis>
        {rolKip && (
          <div className="space-y-2">
            <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
              {rolKip.yetkiler.length} {t('kullanicilar.rol.yetkisayisi')}
            </p>
            <div className="grid gap-1 sm:grid-cols-2">
              {rolKip.yetkiler.map((y) => (
                <div key={y} className="rounded px-2 py-1 text-xs" style={{ background: 'var(--yuzey-3)' }}>
                  <span className="font-mono">{y}</span>
                  {yetkiEtiketleri.data?.[y] && (
                    <span className="ml-2" style={{ color: 'var(--metin-2)' }}>
                      {yetkiEtiketleri.data[y]}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </Kip>
    </div>
  )
}
