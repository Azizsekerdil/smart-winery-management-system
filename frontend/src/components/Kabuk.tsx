/** Uygulama kabuğu: yan menü (role göre filtreli) + üst çubuk. */
import clsx from 'clsx'
import {
  Activity,
  BarChart3,
  Beaker,
  Bell,
  Boxes,
  Cylinder,
  Grape,
  GraduationCap,
  HardDrive,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Moon,
  Package,
  ScrollText,
  Settings,
  Sparkles,
  Sun,
  Terminal,
  TrendingUp,
  Users,
  Wine,
  Wrench,
} from 'lucide-react'
import { type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useCeviri } from '@/lib/i18n'
import { useAyarlar, useOturum } from '@/lib/store'

interface MenuOgesi {
  yol: string
  etiketAnahtari: string
  simge: ReactNode
  yetkiler: string[]
  grup: string
}

const MENU: MenuOgesi[] = [
  { yol: '/', etiketAnahtari: 'menu.pano', simge: <LayoutDashboard className="h-4 w-4" />, yetkiler: ['lot:read'], grup: 'grup.genel' },
  { yol: '/bag', etiketAnahtari: 'menu.bag', simge: <Grape className="h-4 w-4" />, yetkiler: ['vineyard:read', 'harvest:read'], grup: 'grup.uretim' },
  { yol: '/partiler', etiketAnahtari: 'menu.parti', simge: <ListChecks className="h-4 w-4" />, yetkiler: ['lot:read'], grup: 'grup.uretim' },
  { yol: '/tanklar', etiketAnahtari: 'menu.tank', simge: <Cylinder className="h-4 w-4" />, yetkiler: ['tank:read'], grup: 'grup.uretim' },
  { yol: '/fermantasyon', etiketAnahtari: 'menu.fermantasyon', simge: <Activity className="h-4 w-4" />, yetkiler: ['fermentation:read'], grup: 'grup.uretim' },
  { yol: '/laboratuvar', etiketAnahtari: 'menu.lab', simge: <Beaker className="h-4 w-4" />, yetkiler: ['lab:read'], grup: 'grup.kalite' },
  { yol: '/recete', etiketAnahtari: 'menu.recete', simge: <Wine className="h-4 w-4" />, yetkiler: ['recipe:read'], grup: 'grup.kalite' },
  { yol: '/fici', etiketAnahtari: 'menu.fici', simge: <Package className="h-4 w-4" />, yetkiler: ['barrel:read'], grup: 'grup.uretim' },
  { yol: '/siseleme', etiketAnahtari: 'menu.siseleme', simge: <Wine className="h-4 w-4" />, yetkiler: ['bottling:read'], grup: 'grup.uretim' },
  { yol: '/stok', etiketAnahtari: 'menu.stok', simge: <Boxes className="h-4 w-4" />, yetkiler: ['inventory:read'], grup: 'grup.lojistik' },
  { yol: '/bakim', etiketAnahtari: 'menu.bakim', simge: <Wrench className="h-4 w-4" />, yetkiler: ['maintenance:read'], grup: 'grup.lojistik' },
  { yol: '/raporlar', etiketAnahtari: 'menu.rapor', simge: <BarChart3 className="h-4 w-4" />, yetkiler: ['report:read', 'cost:read'], grup: 'grup.analiz' },
  { yol: '/istatistikler', etiketAnahtari: 'menu.istatistik', simge: <TrendingUp className="h-4 w-4" />, yetkiler: ['harvest:read', 'lot:read', 'fermentation:read', 'lab:read', 'bottling:read', 'barrel:read', 'inventory:read', 'maintenance:read'], grup: 'grup.analiz' },
  { yol: '/yapay-zeka', etiketAnahtari: 'menu.ai', simge: <Sparkles className="h-4 w-4" />, yetkiler: ['ai:use'], grup: 'grup.ai' },
  { yol: '/ai-terminal', etiketAnahtari: 'menu.terminal', simge: <Terminal className="h-4 w-4" />, yetkiler: ['ai:terminal'], grup: 'grup.ai' },
  { yol: '/denetim', etiketAnahtari: 'menu.denetim', simge: <ScrollText className="h-4 w-4" />, yetkiler: ['audit:read'], grup: 'grup.sistem' },
  { yol: '/kullanicilar', etiketAnahtari: 'menu.kullanici', simge: <Users className="h-4 w-4" />, yetkiler: ['user:read'], grup: 'grup.sistem' },
  { yol: '/egitim', etiketAnahtari: 'menu.egitim', simge: <GraduationCap className="h-4 w-4" />, yetkiler: [], grup: 'grup.sistem' },
  { yol: '/yedekleme', etiketAnahtari: 'menu.yedekleme', simge: <HardDrive className="h-4 w-4" />, yetkiler: ['backup:manage'], grup: 'grup.sistem' },
  { yol: '/ayarlar', etiketAnahtari: 'menu.ayarlar', simge: <Settings className="h-4 w-4" />, yetkiler: ['settings:read', 'ai:configure'], grup: 'grup.sistem' },
]

export function Kabuk({ children, uyariSayisi }: { children: ReactNode; uyariSayisi?: number }) {
  const t = useCeviri()
  const navigate = useNavigate()
  const { kullanici, cikisYap, herhangiYetki } = useOturum()
  const { tema, temaAyarla, dil, dilAyarla, kenarCubuguAcik, kenarCubuguDegistir } = useAyarlar()

  const gorunur = MENU.filter((m) => herhangiYetki(...m.yetkiler))
  const gruplar = [...new Set(gorunur.map((m) => m.grup))]

  return (
    <div className="flex min-h-screen">
      {/* -------------------------------------------------------- yan menü */}
      <aside
        className={clsx(
          'yazdirma-gizle sticky top-0 flex h-screen shrink-0 flex-col border-r transition-all duration-200',
          kenarCubuguAcik ? 'w-60' : 'w-16',
        )}
        style={{ borderColor: 'var(--kenar)', background: 'var(--yuzey-2)' }}
      >
        <div className="flex h-14 items-center gap-2 px-3">
          <div
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-white"
            style={{ background: 'linear-gradient(135deg,#971f48,#5c1a2b)' }}
            aria-hidden
          >
            <Wine className="h-4 w-4" />
          </div>
          {kenarCubuguAcik && (
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold leading-tight">{t('app.kisa')}</p>
              <p className="truncate text-[10px]" style={{ color: 'var(--metin-2)' }}>
                {t('kabuk.altbaslik')}
              </p>
            </div>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto px-2 pb-4">
          {gruplar.map((grup) => (
            <div key={grup} className="mb-3">
              {kenarCubuguAcik && (
                <p
                  className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider"
                  style={{ color: 'var(--metin-2)' }}
                >
                  {t(grup)}
                </p>
              )}
              {gorunur
                .filter((m) => m.grup === grup)
                .map((m) => (
                  <NavLink
                    key={m.yol}
                    to={m.yol}
                    end={m.yol === '/'}
                    title={t(m.etiketAnahtari)}
                    className={({ isActive }) =>
                      clsx(
                        'mb-0.5 flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm transition-colors',
                        isActive
                          ? 'bg-[var(--vurgu)] font-medium text-[var(--vurgu-yazi)]'
                          : 'hover:bg-[var(--yuzey-3)]',
                      )
                    }
                  >
                    <span className="shrink-0">{m.simge}</span>
                    {kenarCubuguAcik && <span className="truncate">{t(m.etiketAnahtari)}</span>}
                  </NavLink>
                ))}
            </div>
          ))}
        </nav>
      </aside>

      {/* ------------------------------------------------------- ana bölge */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header
          className="yazdirma-gizle sticky top-0 z-30 flex h-14 items-center gap-2 border-b px-4 backdrop-blur"
          style={{ borderColor: 'var(--kenar)', background: 'color-mix(in oklab, var(--yuzey-2) 88%, transparent)' }}
        >
          <button
            type="button"
            onClick={kenarCubuguDegistir}
            className="rounded p-1.5 hover:bg-[var(--yuzey-3)]"
            aria-label={t('kabuk.menudaralt')}
          >
            <Menu className="h-4 w-4" />
          </button>

          <div className="flex-1" />

          {typeof uyariSayisi === 'number' && uyariSayisi > 0 && (
            <button
              type="button"
              onClick={() => navigate('/')}
              className="relative rounded p-1.5 hover:bg-[var(--yuzey-3)]"
              aria-label={`${uyariSayisi} ${t('kabuk.uyari')}`}
            >
              <Bell className="h-4 w-4" />
              <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
                {uyariSayisi > 99 ? '99+' : uyariSayisi}
              </span>
            </button>
          )}

          <select
            className="girdi w-auto py-1 text-xs"
            value={dil}
            onChange={(e) => dilAyarla(e.target.value as 'tr' | 'en')}
            aria-label={t('kabuk.dil')}
          >
            <option value="tr">Türkçe</option>
            <option value="en">English</option>
          </select>

          <button
            type="button"
            onClick={() => temaAyarla(tema === 'dark' ? 'light' : 'dark')}
            className="rounded p-1.5 hover:bg-[var(--yuzey-3)]"
            aria-label={t('kabuk.tema')}
          >
            {tema === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          <div className="ml-1 flex items-center gap-2 border-l pl-3" style={{ borderColor: 'var(--kenar)' }}>
            <div className="hidden text-right sm:block">
              <p className="text-xs font-medium leading-tight">{kullanici?.full_name}</p>
              <p className="text-[10px]" style={{ color: 'var(--metin-2)' }}>
                {kullanici?.role_labels?.[0] ?? kullanici?.username}
              </p>
            </div>
            <button
              type="button"
              onClick={async () => {
                await cikisYap()
                navigate('/giris')
              }}
              className="rounded p-1.5 hover:bg-[var(--yuzey-3)]"
              aria-label={t('kabuk.cikis')}
              title={t('kabuk.cikis')}
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </header>

        <main className="flex-1 p-4 md:p-6">{children}</main>

        <footer
          className="yazdirma-gizle border-t px-4 py-2 text-[11px]"
          style={{ borderColor: 'var(--kenar)', color: 'var(--metin-2)' }}
        >
          {t('app.ad')} · {t('kabuk.altbilgi')}
        </footer>
      </div>
    </div>
  )
}
