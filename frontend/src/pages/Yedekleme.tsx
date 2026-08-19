import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Download, HardDrive, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import {
  BilgiKutusu,
  Bos,
  HataKutusu,
  Kart,
  Kip,
  SayfaBasligi,
  Yukleniyor,
} from '@/components/Ortak'
import { api, dosyaIndir, hataMesaji } from '@/lib/api'
import { sayi } from '@/lib/bicim'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

/**
 * Yedekleme — veritabanının tutarlı kopyasını alır.
 *
 * Geri yükleme bilerek YOKTUR: kullanıcının hazırladığı bir veritabanını
 * sisteme yüklemek doğrudan ayrıcalık yükseltme yoludur (saldırgan kendini
 * yönetici yapan bir dosya yükler). Geri yükleme yordamı SECURITY.md'de
 * belgelenmiştir ve uygulama kapalıyken yapılır.
 */

interface Yedek {
  ad: string
  tur: string
  boyut: number
  boyut_mb: number
  olusturma: string
}

interface Disk {
  dizin: string
  yedek_sayisi: number
  yedek_toplam_bayt: number
  disk_bos_bayt: number
  disk_toplam_bayt: number
}

function mb(bayt: number): string {
  return `${sayi(bayt / 1_048_576, 1)} MB`
}

function gb(bayt: number): string {
  return `${sayi(bayt / 1_073_741_824, 1)} GB`
}

export default function Yedekleme() {
  const t = useCeviri()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const indirebilir = yetkiVar('backup:download')
  const qc = useQueryClient()

  const [hata, setHata] = useState('')
  const [yuklemeler, setYuklemeler] = useState(false)
  const [silinecek, setSilinecek] = useState<Yedek | null>(null)
  const [indirilen, setIndirilen] = useState('')

  const liste = useQuery({
    queryKey: ['/backups'],
    queryFn: async () =>
      (await api.get('/backups')).data as { yedekler: Yedek[]; disk: Disk },
    retry: false,
  })

  const yenile = () => qc.invalidateQueries({ queryKey: ['/backups'] })

  const alma = useMutation({
    mutationFn: async () => (await api.post('/backups', null, { params: { yuklemeler } })).data,
    onSuccess: () => {
      setHata('')
      yenile()
    },
    onError: (e) => setHata(hataMesaji(e)),
  })

  const silme = useMutation({
    mutationFn: async (ad: string) => (await api.delete(`/backups/${ad}`)).data,
    onSuccess: () => {
      setSilinecek(null)
      yenile()
    },
    onError: (e) => {
      setSilinecek(null)
      setHata(hataMesaji(e))
    },
  })

  const temizlik = useMutation({
    mutationFn: async () => (await api.post('/backups/temizle')).data,
    onSuccess: () => yenile(),
    onError: (e) => setHata(hataMesaji(e)),
  })

  async function indir(ad: string) {
    setHata('')
    setIndirilen(ad)
    try {
      await dosyaIndir(`/backups/indir/${ad}`)
    } catch (err) {
      setHata(hataMesaji(err))
    } finally {
      setIndirilen('')
    }
  }

  const disk = liste.data?.disk
  const yedekler = liste.data?.yedekler ?? []

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('yedekleme.baslik')}
        aciklama={t('yedekleme.aciklama')}
        eylemler={
          <>
            <label className="flex items-center gap-1.5 text-xs">
              <input
                type="checkbox"
                checked={yuklemeler}
                onChange={(e) => setYuklemeler(e.target.checked)}
              />
              {t('yedekleme.secenek.belgeler')}
            </label>
            <button
              type="button"
              className="dugme dugme-birincil"
              disabled={alma.isPending}
              onClick={() => alma.mutate()}
            >
              <Plus className="h-4 w-4" />
              {alma.isPending ? t('yedekleme.dugme.aliniyor') : t('yedekleme.dugme.al')}
            </button>
          </>
        }
      />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

      <BilgiKutusu>
        {t('yedekleme.bilgi.kopya1')} <strong>{t('yedekleme.bilgi.kopyavurgu')}</strong>
        {t('yedekleme.bilgi.kopya2')}
        <br />
        {t('yedekleme.bilgi.ortam1')} <strong>{t('yedekleme.bilgi.ortamvurgu')}</strong>{' '}
        {t('yedekleme.bilgi.ortam2')}
      </BilgiKutusu>

      {/* --------------------------------------------------------- disk durumu */}
      {disk && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="kart p-4">
            <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
              {t('yedekleme.disk.sayi')}
            </p>
            <p className="mt-1 text-xl font-semibold">{disk.yedek_sayisi}</p>
          </div>
          <div className="kart p-4">
            <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
              {t('yedekleme.disk.boyut')}
            </p>
            <p className="mt-1 text-xl font-semibold">{mb(disk.yedek_toplam_bayt)}</p>
          </div>
          <div className="kart p-4">
            <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
              {t('yedekleme.disk.bosalan')}
            </p>
            <p className="mt-1 text-xl font-semibold">{gb(disk.disk_bos_bayt)}</p>
            {disk.disk_bos_bayt < 1_073_741_824 && (
              <p className="mt-0.5 flex items-center gap-1 text-[11px] text-red-600 dark:text-red-400">
                <AlertTriangle className="h-3 w-3" /> {t('yedekleme.disk.azaliyor')}
              </p>
            )}
          </div>
          <div className="kart p-4">
            <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
              {t('yedekleme.disk.konum')}
            </p>
            <p
              className="mt-1 break-all font-mono text-[11px]"
              style={{ color: 'var(--metin-2)' }}
            >
              {disk.dizin}
            </p>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- liste */}
      <Kart
        baslik={
          <span className="flex items-center gap-1.5">
            <HardDrive className="h-4 w-4" /> {t('yedekleme.kart.liste')}
          </span>
        }
        aciklama={t('yedekleme.kart.siralama')}
        sag={
          <button
            type="button"
            className="dugme dugme-ikincil"
            disabled={temizlik.isPending || yedekler.length === 0}
            onClick={() => temizlik.mutate()}
            title={t('yedekleme.dugme.temizleipucu')}
          >
            {t('yedekleme.dugme.temizle')}
          </button>
        }
        govdeSinif="p-0"
      >
        {liste.isLoading ? (
          <Yukleniyor metin={t('genel.yukleniyor')} />
        ) : yedekler.length === 0 ? (
          <Bos metin={t('yedekleme.bos.metin')} ipucu={t('yedekleme.bos.ipucu')} />
        ) : (
          <div className="overflow-x-auto">
            <table className="tablo">
              <thead>
                <tr>
                  <th>{t('yedekleme.tablo.dosya')}</th>
                  <th>{t('yedekleme.tablo.tur')}</th>
                  <th className="text-right">{t('yedekleme.tablo.boyut')}</th>
                  <th>{t('yedekleme.tablo.olusturma')}</th>
                  <th className="text-right">{t('yedekleme.tablo.islem')}</th>
                </tr>
              </thead>
              <tbody>
                {yedekler.map((y) => (
                  <tr key={y.ad}>
                    <td className="font-mono text-xs">{y.ad}</td>
                    <td>
                      {y.tur === 'veritabani'
                        ? t('yedekleme.tur.veritabani')
                        : t('yedekleme.tur.belgeler')}
                    </td>
                    <td className="text-right">{y.boyut_mb} MB</td>
                    <td>{y.olusturma.replace('T', ' ').slice(0, 16)}</td>
                    <td className="text-right">
                      <div className="flex justify-end gap-1">
                        {indirebilir && (
                          <button
                            type="button"
                            className="dugme dugme-ikincil px-2 py-1"
                            disabled={indirilen === y.ad}
                            onClick={() => indir(y.ad)}
                            title={t('yedekleme.dugme.indir')}
                          >
                            <Download className="h-4 w-4" />
                          </button>
                        )}
                        <button
                          type="button"
                          className="dugme dugme-ikincil px-2 py-1"
                          onClick={() => setSilinecek(y)}
                          title={t('genel.sil')}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Kart>

      {!indirebilir && (
        <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
          {t('yedekleme.uyari.yetkiyok')}
        </p>
      )}

      <Kip
        acik={silinecek !== null}
        baslik={t('yedekleme.kip.silbaslik')}
        onKapat={() => setSilinecek(null)}
      >
        <p className="text-sm">
          <span className="font-mono">{silinecek?.ad}</span> {t('yedekleme.kip.silmetin')}
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="dugme dugme-ikincil" onClick={() => setSilinecek(null)}>
            {t('genel.iptal')}
          </button>
          <button
            type="button"
            className="dugme dugme-tehlike"
            disabled={silme.isPending}
            onClick={() => silinecek && silme.mutate(silinecek.ad)}
          >
            {t('genel.sil')}
          </button>
        </div>
      </Kip>
    </div>
  )
}
