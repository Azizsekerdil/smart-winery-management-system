/** Yeniden kullanılan küçük arayüz parçaları. */
import clsx from 'clsx'
import { AlertTriangle, Inbox, Loader2, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { SEVIYE_RENK } from '@/lib/bicim'
import { useCeviri } from '@/lib/i18n'

export function Kart({
  baslik,
  aciklama,
  sag,
  children,
  className,
  govdeSinif,
}: {
  baslik?: ReactNode
  aciklama?: ReactNode
  sag?: ReactNode
  children?: ReactNode
  className?: string
  govdeSinif?: string
}) {
  return (
    <section className={clsx('kart animasyon-gir', className)}>
      {(baslik || sag) && (
        <header
          className="flex items-start justify-between gap-3 border-b px-4 py-3"
          style={{ borderColor: 'var(--kenar)' }}
        >
          <div className="min-w-0">
            {baslik && <h2 className="truncate text-sm font-semibold">{baslik}</h2>}
            {aciklama && (
              <p className="mt-0.5 text-xs" style={{ color: 'var(--metin-2)' }}>
                {aciklama}
              </p>
            )}
          </div>
          {sag && <div className="shrink-0">{sag}</div>}
        </header>
      )}
      <div className={govdeSinif ?? 'p-4'}>{children}</div>
    </section>
  )
}

export function Rozet({
  children,
  seviye,
  className,
}: {
  children: ReactNode
  seviye?: string
  className?: string
}) {
  return (
    <span
      className={clsx(
        'rozet',
        seviye ? SEVIYE_RENK[seviye] : 'bg-[var(--yuzey-3)] text-[var(--metin-2)]',
        className,
      )}
    >
      {children}
    </span>
  )
}

export function Yukleniyor({ metin }: { metin?: string }) {
  const t = useCeviri()
  return (
    <div
      className="flex items-center justify-center gap-2 py-10 text-sm"
      style={{ color: 'var(--metin-2)' }}
      role="status"
      aria-live="polite"
    >
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {metin ?? t('genel.yukleniyor')}
    </div>
  )
}

export function Bos({
  metin,
  ipucu,
  eylem,
}: {
  metin?: string
  ipucu?: string
  eylem?: ReactNode
}) {
  const t = useCeviri()
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      <Inbox className="h-8 w-8 opacity-40" aria-hidden />
      <p className="text-sm font-medium">{metin ?? t('genel.kayityok')}</p>
      {ipucu && (
        <p className="max-w-md text-xs" style={{ color: 'var(--metin-2)' }}>
          {ipucu}
        </p>
      )}
      {eylem}
    </div>
  )
}

export function HataKutusu({ mesaj, onKapat }: { mesaj: string; onKapat?: () => void }) {
  const t = useCeviri()
  return (
    <div
      className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300"
      role="alert"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span className="flex-1 whitespace-pre-wrap">{mesaj}</span>
      {onKapat && (
        <button type="button" onClick={onKapat} aria-label={t('genel.kapat')} className="shrink-0">
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}

export function BilgiKutusu({ children }: { children: ReactNode }) {
  return (
    <div
      className="rounded-lg border px-3 py-2 text-xs"
      style={{ borderColor: 'var(--kenar)', background: 'var(--yuzey-3)', color: 'var(--metin-2)' }}
    >
      {children}
    </div>
  )
}

export function Alan({
  etiket,
  ipucu,
  gerekli,
  children,
  className,
}: {
  etiket: string
  ipucu?: string
  gerekli?: boolean
  children: ReactNode
  className?: string
}) {
  return (
    <label className={clsx('block', className)}>
      <span className="mb-1 block text-xs font-medium">
        {etiket}
        {gerekli && <span className="ml-0.5 text-red-500">*</span>}
      </span>
      {children}
      {ipucu && (
        <span className="mt-1 block text-[11px]" style={{ color: 'var(--metin-2)' }}>
          {ipucu}
        </span>
      )}
    </label>
  )
}

export function SayfaBasligi({
  baslik,
  aciklama,
  eylemler,
}: {
  baslik: string
  aciklama?: string
  eylemler?: ReactNode
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{baslik}</h1>
        {aciklama && (
          <p className="mt-1 text-sm" style={{ color: 'var(--metin-2)' }}>
            {aciklama}
          </p>
        )}
      </div>
      {eylemler && <div className="flex flex-wrap gap-2">{eylemler}</div>}
    </div>
  )
}

export function Ilerleme({ deger, seviye }: { deger: number; seviye?: string }) {
  const oran = Math.max(0, Math.min(100, deger))
  const renk =
    seviye === 'kritik'
      ? 'bg-red-500'
      : seviye === 'uyari'
        ? 'bg-amber-500'
        : 'bg-[var(--vurgu)]'
  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full"
      style={{ background: 'var(--yuzey-3)' }}
      role="progressbar"
      aria-valuenow={Math.round(oran)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className={clsx('h-full rounded-full transition-all', renk)} style={{ width: `${oran}%` }} />
    </div>
  )
}

export function Kip({
  acik,
  baslik,
  onKapat,
  children,
  genis,
}: {
  acik: boolean
  baslik: string
  onKapat: () => void
  children: ReactNode
  genis?: boolean
}) {
  // Kanca sırası bozulmasın diye erken dönüşten önce çağrılır.
  const t = useCeviri()
  if (!acik) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onKapat()
      }}
      role="dialog"
      aria-modal="true"
      aria-label={baslik}
    >
      <div
        className={clsx('kart animasyon-gir my-8 w-full', genis ? 'max-w-4xl' : 'max-w-lg')}
      >
        <header
          className="flex items-center justify-between border-b px-4 py-3"
          style={{ borderColor: 'var(--kenar)' }}
        >
          <h2 className="text-sm font-semibold">{baslik}</h2>
          <button
            type="button"
            onClick={onKapat}
            aria-label={t('genel.kapat')}
            className="rounded p-1 hover:bg-[var(--yuzey-3)]"
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="p-4">{children}</div>
      </div>
    </div>
  )
}
