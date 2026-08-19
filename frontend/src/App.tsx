import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Kabuk } from '@/components/Kabuk'
import { Bos, Yukleniyor } from '@/components/Ortak'
import { api } from '@/lib/api'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'
import AiTerminal from '@/pages/AiTerminal'
import Ayarlar from '@/pages/Ayarlar'
import Bag from '@/pages/Bag'
import Bakim from '@/pages/Bakim'
import Denetim from '@/pages/Denetim'
import Egitim from '@/pages/Egitim'
import Fermantasyon from '@/pages/Fermantasyon'
import Fici from '@/pages/Fici'
import Giris from '@/pages/Giris'
import Istatistikler from '@/pages/Istatistikler'
import Kullanicilar from '@/pages/Kullanicilar'
import Laboratuvar from '@/pages/Laboratuvar'
import Pano from '@/pages/Pano'
import ParolaDegistir from '@/pages/ParolaDegistir'
import PartiDetay from '@/pages/PartiDetay'
import Partiler from '@/pages/Partiler'
import Raporlar from '@/pages/Raporlar'
import Recete from '@/pages/Recete'
import Siseleme from '@/pages/Siseleme'
import Stok from '@/pages/Stok'
import Tanklar from '@/pages/Tanklar'
import YapayZeka from '@/pages/YapayZeka'
import Yedekleme from '@/pages/Yedekleme'

function Korumali({ yetkiler, children }: { yetkiler: string[]; children: React.ReactNode }) {
  const t = useCeviri()
  const { herhangiYetki } = useOturum()
  if (yetkiler.length && !herhangiYetki(...yetkiler)) {
    return <Bos metin={t('genel.yetkiyok')} ipucu={t('genel.yetkiyok.ipucu')} />
  }
  return <>{children}</>
}

export default function App() {
  const t = useCeviri()
  const { kullanici, yukleniyor, beniYukle } = useOturum()
  const konum = useLocation()

  useEffect(() => {
    void beniYukle()
  }, [beniYukle])

  const { data: uyariOzeti } = useQuery({
    queryKey: ['uyari-ozet'],
    queryFn: async () => (await api.get('/alerts/summary')).data as { acik_toplam: number },
    enabled: !!kullanici,
    refetchInterval: 60_000,
  })

  if (yukleniyor) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Yukleniyor metin={t('app.oturumdogrulaniyor')} />
      </div>
    )
  }

  if (!kullanici) {
    return (
      <Routes>
        <Route path="/giris" element={<Giris />} />
        <Route path="*" element={<Navigate to="/giris" replace state={{ from: konum }} />} />
      </Routes>
    )
  }

  // Parola degistirmesi zorunlu tutulan hesap, uygulamanin geri kalanini
  // GOREMEZ. Sunucu zaten butun korumali uc noktalari 403 ile reddeder
  // (bkz. backend/app/core/deps.py); burada kullaniciya cikis yolu gosterilir.
  // Kabuk hic cizilmez ki gezinme menusu bile gorunmesin.
  if (kullanici.must_change_password) {
    return <ParolaDegistir />
  }

  return (
    <Kabuk uyariSayisi={uyariOzeti?.acik_toplam}>
      <Routes>
        <Route path="/giris" element={<Navigate to="/" replace />} />
        <Route path="/" element={<Korumali yetkiler={['lot:read']}><Pano /></Korumali>} />
        <Route path="/bag" element={<Korumali yetkiler={['vineyard:read', 'harvest:read']}><Bag /></Korumali>} />
        <Route path="/partiler" element={<Korumali yetkiler={['lot:read']}><Partiler /></Korumali>} />
        <Route path="/partiler/:id" element={<Korumali yetkiler={['lot:read']}><PartiDetay /></Korumali>} />
        <Route path="/tanklar" element={<Korumali yetkiler={['tank:read']}><Tanklar /></Korumali>} />
        <Route path="/fermantasyon" element={<Korumali yetkiler={['fermentation:read']}><Fermantasyon /></Korumali>} />
        <Route path="/laboratuvar" element={<Korumali yetkiler={['lab:read']}><Laboratuvar /></Korumali>} />
        <Route path="/recete" element={<Korumali yetkiler={['recipe:read']}><Recete /></Korumali>} />
        <Route path="/fici" element={<Korumali yetkiler={['barrel:read']}><Fici /></Korumali>} />
        <Route path="/siseleme" element={<Korumali yetkiler={['bottling:read']}><Siseleme /></Korumali>} />
        <Route path="/stok" element={<Korumali yetkiler={['inventory:read']}><Stok /></Korumali>} />
        <Route path="/bakim" element={<Korumali yetkiler={['maintenance:read']}><Bakim /></Korumali>} />
        <Route path="/raporlar" element={<Korumali yetkiler={['report:read', 'cost:read']}><Raporlar /></Korumali>} />
        <Route
          path="/istatistikler"
          element={
            <Korumali
              yetkiler={[
                'harvest:read', 'lot:read', 'fermentation:read', 'lab:read',
                'bottling:read', 'barrel:read', 'inventory:read', 'maintenance:read',
              ]}
            >
              <Istatistikler />
            </Korumali>
          }
        />
        <Route path="/egitim" element={<Egitim />} />
        <Route path="/yedekleme" element={<Korumali yetkiler={['backup:manage']}><Yedekleme /></Korumali>} />
        <Route path="/yapay-zeka" element={<Korumali yetkiler={['ai:use']}><YapayZeka /></Korumali>} />
        <Route path="/ai-terminal" element={<Korumali yetkiler={['ai:terminal']}><AiTerminal /></Korumali>} />
        <Route path="/denetim" element={<Korumali yetkiler={['audit:read']}><Denetim /></Korumali>} />
        <Route path="/kullanicilar" element={<Korumali yetkiler={['user:read']}><Kullanicilar /></Korumali>} />
        <Route path="/ayarlar" element={<Korumali yetkiler={['settings:read', 'ai:configure']}><Ayarlar /></Korumali>} />
        <Route
          path="*"
          element={<Bos metin={t('genel.sayfabulunamadi')} ipucu={t('genel.sayfabulunamadi.ipucu')} />}
        />
      </Routes>
    </Kabuk>
  )
}
