/** Arama, sayfalama ve boş/yükleniyor durumlarını yöneten genel veri tablosu. */
import clsx from 'clsx'
import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import type { ReactNode } from 'react'
import { useCeviri } from '@/lib/i18n'
import { Bos, Yukleniyor } from './Ortak'

export interface Sutun<T> {
  anahtar: string
  baslik: string
  hucre?: (satir: T) => ReactNode
  genislik?: string
  sagaYasli?: boolean
  gizleKucuk?: boolean
}

interface Props<T> {
  sutunlar: Sutun<T>[]
  satirlar: T[]
  yukleniyor?: boolean
  toplam?: number
  sayfa?: number
  sayfaBoyu?: number
  onSayfa?: (s: number) => void
  arama?: string
  onArama?: (q: string) => void
  aramaIpucu?: string
  onSatirTikla?: (satir: T) => void
  bosMetin?: string
  bosIpucu?: string
  ustBar?: ReactNode
  anahtarAl?: (satir: T, i: number) => string | number
}

export function Tablo<T>({
  sutunlar,
  satirlar,
  yukleniyor,
  toplam,
  sayfa = 1,
  sayfaBoyu = 50,
  onSayfa,
  arama,
  onArama,
  aramaIpucu,
  onSatirTikla,
  bosMetin,
  bosIpucu,
  ustBar,
  anahtarAl,
}: Props<T>) {
  const t = useCeviri()
  const sonSayfa = toplam ? Math.max(1, Math.ceil(toplam / sayfaBoyu)) : 1
  const aramaMetni = aramaIpucu ?? t('genel.ara')

  return (
    <div className="kart overflow-hidden">
      {(onArama || ustBar) && (
        <div
          className="flex flex-wrap items-center gap-2 border-b px-3 py-2"
          style={{ borderColor: 'var(--kenar)' }}
        >
          {onArama && (
            <div className="relative min-w-52 flex-1">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 opacity-50"
                aria-hidden
              />
              <input
                className="girdi pl-8"
                placeholder={aramaMetni}
                value={arama ?? ''}
                onChange={(e) => onArama(e.target.value)}
                aria-label={aramaMetni}
              />
            </div>
          )}
          {ustBar}
        </div>
      )}

      <div className="max-h-[65vh] overflow-auto">
        <table className="tablo">
          <thead>
            <tr>
              {sutunlar.map((s) => (
                <th
                  key={s.anahtar}
                  style={{ width: s.genislik }}
                  className={clsx(s.sagaYasli && 'text-right', s.gizleKucuk && 'hidden lg:table-cell')}
                >
                  {s.baslik}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {yukleniyor ? (
              <tr>
                <td colSpan={sutunlar.length}>
                  <Yukleniyor />
                </td>
              </tr>
            ) : satirlar.length === 0 ? (
              <tr>
                <td colSpan={sutunlar.length}>
                  <Bos metin={bosMetin} ipucu={bosIpucu} />
                </td>
              </tr>
            ) : (
              satirlar.map((satir, i) => {
                const kayit = satir as Record<string, unknown>
                return (
                  <tr
                    key={anahtarAl ? anahtarAl(satir, i) : ((kayit.id as number | undefined) ?? i)}
                    onClick={onSatirTikla ? () => onSatirTikla(satir) : undefined}
                    className={onSatirTikla ? 'cursor-pointer' : undefined}
                  >
                    {sutunlar.map((s) => (
                      <td
                        key={s.anahtar}
                        className={clsx(
                          s.sagaYasli && 'text-right tabular-nums',
                          s.gizleKucuk && 'hidden lg:table-cell',
                        )}
                      >
                        {s.hucre ? s.hucre(satir) : String(kayit[s.anahtar] ?? '—')}
                      </td>
                    ))}
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {onSayfa && (toplam ?? 0) > sayfaBoyu && (
        <div
          className="flex items-center justify-between border-t px-3 py-2 text-xs"
          style={{ borderColor: 'var(--kenar)', color: 'var(--metin-2)' }}
        >
          <span>
            {t('genel.toplam')} <strong>{toplam}</strong> {t('tablo.sayfalama.kayit')} ·{' '}
            {t('tablo.sayfalama.sayfa')} {sayfa}/{sonSayfa}
          </span>
          <div className="flex gap-1">
            <button
              type="button"
              className="dugme dugme-ikincil px-2 py-1"
              disabled={sayfa <= 1}
              onClick={() => onSayfa(sayfa - 1)}
              aria-label={t('tablo.sayfalama.onceki')}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              className="dugme dugme-ikincil px-2 py-1"
              disabled={sayfa >= sonSayfa}
              onClick={() => onSayfa(sayfa + 1)}
              aria-label={t('tablo.sayfalama.sonraki')}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
