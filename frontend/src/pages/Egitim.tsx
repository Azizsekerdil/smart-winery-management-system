import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock,
  ExternalLink,
  GraduationCap,
  Lightbulb,
  RotateCcw,
  Users,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bos, Kart, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { api } from '@/lib/api'
import { MODULLER } from '@/lib/egitim-icerik'
import { GECME_ESIGI, ikiDil, ikiDilListe, type EgitimModulu } from '@/lib/egitim-tip'
import { useCeviri } from '@/lib/i18n'
import { useAyarlar, useOturum } from '@/lib/store'

/**
 * Eğitim ve Kullanım Kılavuzu.
 *
 * Yeni bir çalışanın sistemi öğrenmesi için rol bazlı, adım adım modüller.
 * Her modül gerçek ekranlara bağlantı verir; sonunda kısa bir sınav vardır ve
 * sonuç sunucuda saklanır — gıda güvenliği denetiminde "personel eğitildi mi"
 * sorusunun cevabı budur.
 */

interface Ilerleme {
  module_code: string
  correct_count: number
  question_count: number
  score_percent: number
  passed: boolean
  attempt_count: number
  completed_at: string | null
}

export default function Egitim() {
  const t = useCeviri()
  const dil = useAyarlar((s) => s.dil)
  const { kullanici, yetkiVar } = useOturum()
  const qc = useQueryClient()

  const [acik, setAcik] = useState<EgitimModulu | null>(null)
  const [sadeceRolum, setSadeceRolum] = useState(true)
  const [ekipGoster, setEkipGoster] = useState(false)

  const ilerleme = useQuery({
    queryKey: ['/training/progress'],
    queryFn: async () => (await api.get('/training/progress')).data as Ilerleme[],
  })

  const ekip = useQuery({
    queryKey: ['/training/team'],
    queryFn: async () => (await api.get('/training/team')).data as EkipSatiri[],
    enabled: ekipGoster && yetkiVar('user:read'),
    retry: false,
  })

  const durum = useMemo(() => {
    const harita = new Map<string, Ilerleme>()
    for (const i of ilerleme.data ?? []) harita.set(i.module_code, i)
    return harita
  }, [ilerleme.data])

  const roller = kullanici?.roles ?? []
  const listelenen = useMemo(
    () =>
      sadeceRolum
        ? MODULLER.filter((m) => m.roller.length === 0 || m.roller.some((r) => roller.includes(r)))
        : MODULLER,
    [sadeceRolum, roller],
  )

  // İlerleme sayacı GÖRÜNEN listeyi izler: kullanıcı 10 kart görürken sayacın
  // 12 demesi kafa karıştırır.
  const tamamlanan = listelenen.filter((m) => durum.get(m.kod)?.passed).length
  const oran = listelenen.length ? Math.round((100 * tamamlanan) / listelenen.length) : 0

  if (acik) {
    return (
      <ModulGorunumu
        modul={acik}
        dil={dil}
        onKapat={() => {
          setAcik(null)
          void qc.invalidateQueries({ queryKey: ['/training/progress'] })
        }}
      />
    )
  }

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('egitim.baslik')}
        aciklama={t('egitim.aciklama')}
        eylemler={
          <>
            <label className="flex items-center gap-1.5 text-xs">
              <input
                type="checkbox"
                checked={sadeceRolum}
                onChange={(e) => setSadeceRolum(e.target.checked)}
              />
              {t('egitim.sadecerolum')}
            </label>
            {yetkiVar('user:read') && (
              <button
                type="button"
                className="dugme dugme-ikincil"
                onClick={() => setEkipGoster((v) => !v)}
              >
                <Users className="h-4 w-4" />
                {t('egitim.ekip')}
              </button>
            )}
          </>
        }
      />

      {/* ---------------------------------------------------------- ilerleme */}
      <div className="kart p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
              {t('egitim.genelilerleme')}
            </p>
            <p className="mt-1 text-xl font-semibold">
              {tamamlanan} / {listelenen.length}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <GraduationCap className="h-8 w-8" style={{ color: 'var(--vurgu)' }} />
            <span className="text-2xl font-semibold">%{oran}</span>
          </div>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full" style={{ background: 'var(--yuzey-3)' }}>
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${oran}%`, background: 'var(--vurgu)' }}
          />
        </div>
      </div>

      {ekipGoster && yetkiVar('user:read') && (
        <Kart baslik={t('egitim.ekipdurumu')} aciklama={t('egitim.ekipaciklama')} govdeSinif="p-0">
          {ekip.isLoading ? (
            <Yukleniyor />
          ) : (
            <div className="overflow-x-auto">
              <table className="tablo">
                <thead>
                  <tr>
                    <th>{t('egitim.kisi')}</th>
                    <th>{t('egitim.rol')}</th>
                    <th className="text-right">{t('egitim.tamamlanan')}</th>
                    <th className="text-right">{t('egitim.denenen')}</th>
                  </tr>
                </thead>
                <tbody>
                  {(ekip.data ?? []).map((k) => (
                    <tr key={k.user_id}>
                      <td>
                        <span className="font-medium">{k.full_name}</span>{' '}
                        <span style={{ color: 'var(--metin-2)' }}>{k.username}</span>
                      </td>
                      <td className="text-xs">{k.roles.join(', ')}</td>
                      <td className="text-right font-medium">{k.tamamlanan}</td>
                      <td className="text-right">{k.denenen}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Kart>
      )}

      {/* ----------------------------------------------------------- modüller */}
      {listelenen.length === 0 ? (
        <Bos metin={t('egitim.modulyok')} ipucu={t('egitim.modulyok.ipucu')} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {listelenen.map((m) => {
            const d = durum.get(m.kod)
            return (
              <button
                key={m.kod}
                type="button"
                onClick={() => setAcik(m)}
                className="kart p-4 text-left transition hover:border-[var(--vurgu)]"
              >
                <div className="flex items-start justify-between gap-2">
                  <BookOpen className="h-5 w-5 shrink-0" style={{ color: 'var(--vurgu)' }} />
                  {d?.passed ? (
                    <Rozet seviye="dusuk">
                      <CheckCircle2 className="mr-1 inline h-3 w-3" />%{d.score_percent}
                    </Rozet>
                  ) : d ? (
                    <Rozet seviye="uyari">%{d.score_percent}</Rozet>
                  ) : null}
                </div>
                <p className="mt-2 font-medium">{ikiDil(m.baslik, dil)}</p>
                <p className="mt-1 text-xs" style={{ color: 'var(--metin-2)' }}>
                  {ikiDil(m.ozet, dil)}
                </p>
                <p
                  className="mt-2 flex items-center gap-1 text-[11px]"
                  style={{ color: 'var(--metin-2)' }}
                >
                  <Clock className="h-3 w-3" /> {m.sureDk} {t('egitim.dakika')} ·{' '}
                  {m.adimlar.length} {t('egitim.adim')} · {m.sorular.length} {t('egitim.soru')}
                </p>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

interface EkipSatiri {
  user_id: number
  username: string
  full_name: string
  roles: string[]
  tamamlanan: number
  denenen: number
}

/* ------------------------------------------------------------ modül görünümü */
function ModulGorunumu({
  modul,
  dil,
  onKapat,
}: {
  modul: EgitimModulu
  dil: string
  onKapat: () => void
}) {
  const t = useCeviri()
  const [adim, setAdim] = useState(0)
  const [sinavda, setSinavda] = useState(false)
  const [cevaplar, setCevaplar] = useState<Record<number, number>>({})
  const [sonuc, setSonuc] = useState<number | null>(null)

  const kaydet = useMutation({
    mutationFn: async (dogru: number) =>
      (
        await api.post(`/training/progress/${modul.kod}`, {
          correct_count: dogru,
          question_count: modul.sorular.length,
        })
      ).data,
  })

  const sonAdim = adim >= modul.adimlar.length - 1
  const a = modul.adimlar[adim]

  function sinaviBitir() {
    const dogru = modul.sorular.reduce(
      (t2, s, i) => t2 + (cevaplar[i] === s.dogru ? 1 : 0),
      0,
    )
    setSonuc(dogru)
    kaydet.mutate(dogru)
  }

  const yuzde = sonuc === null ? 0 : Math.round((100 * sonuc) / modul.sorular.length)

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={ikiDil(modul.baslik, dil)}
        aciklama={ikiDil(modul.ozet, dil)}
        eylemler={
          <button type="button" className="dugme dugme-ikincil" onClick={onKapat}>
            <ArrowLeft className="h-4 w-4" />
            {t('egitim.tumumoduller')}
          </button>
        }
      />

      {/* ---------------------------------------------------------- sonuç */}
      {sonuc !== null ? (
        <Kart baslik={t('egitim.sonuc')}>
          <div className="py-4 text-center">
            <p className="text-4xl font-semibold">%{yuzde}</p>
            <p className="mt-1 text-sm" style={{ color: 'var(--metin-2)' }}>
              {modul.sorular.length} {t('egitim.soruda')} {sonuc} {t('egitim.dogru')}
            </p>
            <div className="mt-3">
              {yuzde >= GECME_ESIGI ? (
                <Rozet seviye="dusuk">{t('egitim.gecti')}</Rozet>
              ) : (
                <Rozet seviye="uyari">{t('egitim.kaldi')}</Rozet>
              )}
            </div>
          </div>

          <div className="mt-4 space-y-3">
            {modul.sorular.map((s, i) => {
              const secilen = cevaplar[i]
              const dogruMu = secilen === s.dogru
              const secenekler = ikiDilListe(s.secenekler, dil)
              return (
                <div key={i} className="rounded-lg border p-3" style={{ borderColor: 'var(--kenar)' }}>
                  <p className="text-sm font-medium">{ikiDil(s.soru, dil)}</p>
                  <p className="mt-1 text-xs" style={{ color: dogruMu ? undefined : 'var(--metin-2)' }}>
                    {dogruMu ? '✓ ' : '✗ '}
                    {secenekler[secilen] ?? '—'}
                    {!dogruMu && (
                      <>
                        {' · '}
                        <span className="font-medium">{t('egitim.dogrucevap')}:</span>{' '}
                        {secenekler[s.dogru]}
                      </>
                    )}
                  </p>
                  {s.aciklama && (
                    <p className="mt-1 text-xs" style={{ color: 'var(--metin-2)' }}>
                      {ikiDil(s.aciklama, dil)}
                    </p>
                  )}
                </div>
              )
            })}
          </div>

          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              className="dugme dugme-ikincil"
              onClick={() => {
                setSonuc(null)
                setCevaplar({})
                setSinavda(false)
                setAdim(0)
              }}
            >
              <RotateCcw className="h-4 w-4" />
              {t('egitim.tekrar')}
            </button>
            <button type="button" className="dugme dugme-birincil" onClick={onKapat}>
              {t('egitim.bitir')}
            </button>
          </div>
        </Kart>
      ) : sinavda ? (
        /* --------------------------------------------------------- sınav */
        <Kart baslik={t('egitim.sinav')} aciklama={t('egitim.sinavaciklama')}>
          <div className="space-y-4">
            {modul.sorular.map((s, i) => {
              const secenekler = ikiDilListe(s.secenekler, dil)
              return (
                <div key={i}>
                  <p className="text-sm font-medium">
                    {i + 1}. {ikiDil(s.soru, dil)}
                  </p>
                  <div className="mt-2 space-y-1.5">
                    {secenekler.map((se, j) => (
                      <label key={j} className="flex cursor-pointer items-start gap-2 text-sm">
                        <input
                          type="radio"
                          name={`soru-${i}`}
                          checked={cevaplar[i] === j}
                          onChange={() => setCevaplar((c) => ({ ...c, [i]: j }))}
                          className="mt-1"
                        />
                        <span>{se}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <button type="button" className="dugme dugme-ikincil" onClick={() => setSinavda(false)}>
              <ArrowLeft className="h-4 w-4" />
              {t('genel.geri')}
            </button>
            <button
              type="button"
              className="dugme dugme-birincil"
              disabled={Object.keys(cevaplar).length < modul.sorular.length}
              onClick={sinaviBitir}
            >
              {t('egitim.sinavibitir')}
            </button>
          </div>
        </Kart>
      ) : (
        /* --------------------------------------------------------- adımlar */
        <Kart
          baslik={`${adim + 1}. ${ikiDil(a.baslik, dil)}`}
          aciklama={`${t('egitim.adim')} ${adim + 1} / ${modul.adimlar.length}`}
          sag={
            a.ekran ? (
              <Link to={a.ekran} className="dugme dugme-ikincil">
                <ExternalLink className="h-4 w-4" />
                {t('egitim.ekranaGit')}
              </Link>
            ) : undefined
          }
        >
          <p className="whitespace-pre-line text-sm leading-relaxed">{ikiDil(a.metin, dil)}</p>

          {a.ipucu && (
            <div
              className="mt-3 flex gap-2 rounded-lg p-3 text-xs"
              style={{ background: 'var(--yuzey-3)' }}
            >
              <Lightbulb className="h-4 w-4 shrink-0" style={{ color: 'var(--vurgu)' }} />
              <span>{ikiDil(a.ipucu, dil)}</span>
            </div>
          )}

          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              className="dugme dugme-ikincil"
              disabled={adim === 0}
              onClick={() => setAdim((s) => s - 1)}
            >
              <ArrowLeft className="h-4 w-4" />
              {t('genel.geri')}
            </button>

            <div className="flex gap-1">
              {modul.adimlar.map((_, i) => (
                <span
                  key={i}
                  className="h-1.5 w-6 rounded-full"
                  style={{ background: i <= adim ? 'var(--vurgu)' : 'var(--yuzey-3)' }}
                />
              ))}
            </div>

            {sonAdim ? (
              <button
                type="button"
                className="dugme dugme-birincil"
                onClick={() => setSinavda(true)}
              >
                {t('egitim.sinavabasla')}
                <ArrowRight className="h-4 w-4" />
              </button>
            ) : (
              <button
                type="button"
                className="dugme dugme-birincil"
                onClick={() => setAdim((s) => s + 1)}
              >
                {t('egitim.ileri')}
                <ArrowRight className="h-4 w-4" />
              </button>
            )}
          </div>
        </Kart>
      )}
    </div>
  )
}
