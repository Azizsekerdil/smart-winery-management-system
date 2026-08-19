import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  Check,
  GitBranch,
  Play,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Terminal as TerminalIcon,
  TestTube,
  X,
} from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Alan, Bos, HataKutusu, Kart, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { api, hataMesaji } from '@/lib/api'
import { etiket, tarihSaat } from '@/lib/bicim'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

interface Gorev {
  id: number
  code: string
  title: string
  request_text: string
  status: string
  risk_level: string
  risk_reasons: string[]
  plan_steps: { no: number; aciklama: string }[]
  affected_paths: string[]
  proposed_commands: string[]
  git_checkpoint: string | null
  git_branch: string | null
  diff_text: string | null
  test_output: string | null
  lint_output: string | null
  tests_passed: boolean | null
  result_summary: string | null
  created_at: string
  command_checks: { command: string; allowed: boolean; risk: string; reason: string }[]
}

interface Calisma {
  id: number
  sequence: number
  command: string
  exit_code: number | null
  allowed: boolean
  block_reason: string | null
  stdout: string | null
  stderr: string | null
  timed_out: boolean
}

export default function AiTerminal() {
  const t = useCeviri()
  const istemci = useQueryClient()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const [secili, setSecili] = useState<number | null>(null)
  const [hata, setHata] = useState('')
  const [istek, setIstek] = useState('')
  const [komutlar, setKomutlar] = useState('')
  const [dosyalar, setDosyalar] = useState('')
  const [llmKullan, setLlmKullan] = useState(true)
  const [denetlenen, setDenetlenen] = useState<{ command: string; allowed: boolean; reason: string; risk: string } | null>(null)
  const [denemeKomut, setDenemeKomut] = useState('')

  const durum = useQuery({
    queryKey: ['/terminal/status'],
    queryFn: async () => (await api.get('/terminal/status')).data,
  })

  const gorevler = useQuery({
    queryKey: ['/terminal'],
    queryFn: async () => (await api.get<Gorev[]>('/terminal')).data,
    refetchInterval: 15_000,
  })

  const detay = useQuery({
    queryKey: ['/terminal', secili],
    queryFn: async () => (await api.get<Gorev>(`/terminal/${secili}`)).data,
    enabled: !!secili,
  })

  const calismalar = useQuery({
    queryKey: ['/terminal', secili, 'runs'],
    queryFn: async () => (await api.get<Calisma[]>(`/terminal/${secili}/runs`)).data,
    enabled: !!secili,
  })

  const planOlustur = useMutation({
    mutationFn: async () =>
      (
        await api.post<Gorev>('/terminal/plan', {
          request_text: istek,
          use_llm: llmKullan,
          proposed_commands: komutlar
            .split('\n')
            .map((k) => k.trim())
            .filter(Boolean),
          affected_paths: dosyalar
            .split('\n')
            .map((d) => d.trim())
            .filter(Boolean),
        })
      ).data,
    onSuccess: (g) => {
      setSecili(g.id)
      void istemci.invalidateQueries({ queryKey: ['/terminal'] })
    },
    onError: (err) => setHata(hataMesaji(err)),
  })

  const eylem = useMutation({
    mutationFn: async ({ yol, govde }: { yol: string; govde?: Record<string, unknown> }) =>
      (await api.post(`/terminal/${secili}${yol}`, govde ?? {})).data,
    onSuccess: () => {
      void istemci.invalidateQueries({ queryKey: ['/terminal'] })
    },
    onError: (err) => setHata(hataMesaji(err)),
  })

  async function komutDenetle(e: FormEvent) {
    e.preventDefault()
    setHata('')
    try {
      const { data } = await api.post('/terminal/check', { command: denemeKomut })
      setDenetlenen(data)
    } catch (err) {
      setHata(hataMesaji(err))
    }
  }

  const g = detay.data

  return (
    <div className="space-y-5">
      <SayfaBasligi baslik={t('aiterminal.baslik')} aciklama={t('aiterminal.aciklama')} />

      {hata && <HataKutusu mesaj={hata} onKapat={() => setHata('')} />}

      {/* --------------------------------------------------------- güvenlik */}
      {durum.data && (
        <Kart
          baslik={
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="h-4 w-4 text-emerald-500" /> {t('aiterminal.kart.guvenlik')}
            </span>
          }
          aciklama={t('aiterminal.kart.guvenlikaciklama')}
        >
          <div className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p style={{ color: 'var(--metin-2)' }}>{t('aiterminal.guvenlik.calismaalani')}</p>
              <p className="font-mono">{durum.data.workspace}</p>
            </div>
            <div>
              <p style={{ color: 'var(--metin-2)' }}>{t('aiterminal.guvenlik.onayzorunlu')}</p>
              <p>
                {durum.data.require_approval
                  ? t('aiterminal.guvenlik.evet')
                  : t('aiterminal.guvenlik.hayir')}
              </p>
            </div>
            <div>
              <p style={{ color: 'var(--metin-2)' }}>{t('aiterminal.guvenlik.sinir')}</p>
              <p>
                {durum.data.timeout_seconds} {t('aiterminal.guvenlik.saniye')} /{' '}
                {Math.round(durum.data.max_output_bytes / 1024)} KB
              </p>
            </div>
            <div>
              <p style={{ color: 'var(--metin-2)' }}>Git</p>
              <p>
                {durum.data.git_repo
                  ? `${durum.data.current_branch}${durum.data.dirty ? ` (${t('aiterminal.guvenlik.degisiklikvar')})` : ''}`
                  : t('aiterminal.guvenlik.depodegil')}
              </p>
            </div>
          </div>

          <details className="mt-3">
            <summary className="cursor-pointer text-xs" style={{ color: 'var(--metin-2)' }}>
              {t('aiterminal.guvenlik.izinliaraclar')} ({durum.data.allowed_commands.length}){' '}
              {t('aiterminal.guvenlik.engellenenislemler')} ({durum.data.blocked_patterns.length})
            </summary>
            <div className="mt-2 grid gap-3 text-xs sm:grid-cols-2">
              <div>
                <p className="mb-1 font-medium text-emerald-600 dark:text-emerald-400">
                  {t('aiterminal.guvenlik.izinli')}
                </p>
                <p className="font-mono">{durum.data.allowed_commands.join(', ')}</p>
              </div>
              <div>
                <p className="mb-1 font-medium text-red-600 dark:text-red-400">
                  {t('aiterminal.guvenlik.engelli')}
                </p>
                <ul className="space-y-0.5">
                  {durum.data.blocked_patterns.map((p: string) => (
                    <li key={p}>• {p}</li>
                  ))}
                </ul>
              </div>
            </div>
          </details>

          <form onSubmit={komutDenetle} className="mt-3 flex gap-2">
            <input
              className="girdi flex-1 font-mono text-xs"
              placeholder={t('aiterminal.denetle.yertutucu')}
              value={denemeKomut}
              onChange={(e) => setDenemeKomut(e.target.value)}
            />
            <button type="submit" className="dugme dugme-ikincil" disabled={!denemeKomut.trim()}>
              {t('aiterminal.dugme.denetle')}
            </button>
          </form>
          {denetlenen && (
            <div
              className={clsx(
                'mt-2 rounded-lg p-2 text-xs',
                denetlenen.allowed
                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                  : 'bg-red-500/10 text-red-700 dark:text-red-300',
              )}
            >
              <strong>
                {denetlenen.allowed
                  ? t('aiterminal.guvenlik.izinli')
                  : t('aiterminal.denetle.engellendi')}
              </strong>{' '}
              ({denetlenen.risk}) — {denetlenen.reason}
            </div>
          )}
        </Kart>
      )}

      <div className="grid gap-5 xl:grid-cols-[340px_1fr]">
        {/* ------------------------------------------------------- yeni görev */}
        <div className="space-y-4">
          <Kart baslik={t('aiterminal.kart.plan')}>
            <div className="space-y-3">
              <Alan etiket={t('aiterminal.alan.istek')} gerekli>
                <textarea
                  className="girdi"
                  rows={4}
                  value={istek}
                  onChange={(e) => setIstek(e.target.value)}
                  placeholder={t('aiterminal.alan.istekyertutucu')}
                />
              </Alan>
              <Alan etiket={t('aiterminal.alan.komutlar')} ipucu={t('aiterminal.alan.komutlaripucu')}>
                <textarea
                  className="girdi font-mono text-xs"
                  rows={3}
                  value={komutlar}
                  onChange={(e) => setKomutlar(e.target.value)}
                  placeholder={'python -m ruff check backend\npython -m pytest -q'}
                />
              </Alan>
              <Alan etiket={t('aiterminal.alan.dosyalar')} ipucu={t('aiterminal.alan.dosyalaripucu')}>
                <textarea
                  className="girdi font-mono text-xs"
                  rows={2}
                  value={dosyalar}
                  onChange={(e) => setDosyalar(e.target.value)}
                  placeholder="frontend/src/pages/Fermantasyon.tsx"
                />
              </Alan>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={llmKullan} onChange={(e) => setLlmKullan(e.target.checked)} />
                {t('aiterminal.alan.llmkullan')}
              </label>
              <button
                type="button"
                className="dugme dugme-birincil w-full"
                onClick={() => planOlustur.mutate()}
                disabled={planOlustur.isPending || !istek.trim()}
              >
                <TerminalIcon className="h-4 w-4" /> {t('aiterminal.dugme.planolustur')}
              </button>
            </div>
          </Kart>

          <Kart baslik={t('aiterminal.kart.gecmis')} govdeSinif="p-0">
            {gorevler.isLoading ? (
              <Yukleniyor metin={t('genel.yukleniyor')} />
            ) : (gorevler.data?.length ?? 0) === 0 ? (
              <Bos metin={t('aiterminal.bos.gorevyok')} />
            ) : (
              <ul className="max-h-96 divide-y overflow-y-auto" style={{ borderColor: 'var(--kenar)' }}>
                {gorevler.data?.map((t2) => (
                  <li key={t2.id}>
                    <button
                      type="button"
                      onClick={() => setSecili(t2.id)}
                      className={clsx(
                        'w-full p-3 text-left transition-colors hover:bg-[var(--yuzey-3)]',
                        secili === t2.id && 'bg-[var(--yuzey-3)]',
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="truncate text-sm font-medium">{t2.title}</span>
                        <Rozet seviye={t2.risk_level}>{t2.risk_level}</Rozet>
                      </div>
                      <p className="mt-0.5 text-[11px]" style={{ color: 'var(--metin-2)' }}>
                        {t2.code} · {etiket(t2.status)} · {tarihSaat(t2.created_at)}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Kart>
        </div>

        {/* --------------------------------------------------------- görev detayı */}
        <div className="space-y-4">
          {!g ? (
            <Kart>
              <Bos metin={t('aiterminal.bos.secilmedi')} ipucu={t('aiterminal.bos.secilmediipucu')} />
            </Kart>
          ) : (
            <>
              <Kart
                baslik={`${g.code} — ${g.title}`}
                aciklama={g.result_summary ?? undefined}
                sag={<Rozet seviye={g.risk_level}>{etiket(g.status)}</Rozet>}
              >
                {g.risk_level === 'engellendi' && (
                  <div className="mb-3 flex items-start gap-2 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300">
                    <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                      <p className="font-medium">{t('aiterminal.gorev.engellendi')}</p>
                      <ul className="mt-1 space-y-0.5 text-xs">
                        {g.risk_reasons.map((r, i) => (
                          <li key={i}>• {r}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {g.risk_level !== 'engellendi' && g.risk_reasons.length > 0 && (
                  <ul className="mb-3 space-y-0.5 text-xs" style={{ color: 'var(--metin-2)' }}>
                    {g.risk_reasons.map((r, i) => (
                      <li key={i}>• {r}</li>
                    ))}
                  </ul>
                )}

                <p className="mb-1 text-xs font-medium">{t('aiterminal.gorev.planadimlari')}</p>
                <ol className="mb-3 space-y-1 text-sm">
                  {g.plan_steps.map((a) => (
                    <li key={a.no}>
                      <span className="mr-1 font-medium">{a.no}.</span>
                      {a.aciklama}
                    </li>
                  ))}
                </ol>

                {g.affected_paths.length > 0 && (
                  <>
                    <p className="mb-1 text-xs font-medium">{t('aiterminal.alan.dosyalar')}</p>
                    <ul className="mb-3 space-y-0.5 font-mono text-xs">
                      {g.affected_paths.map((d) => (
                        <li key={d}>{d}</li>
                      ))}
                    </ul>
                  </>
                )}

                {g.command_checks.length > 0 && (
                  <>
                    <p className="mb-1 text-xs font-medium">{t('aiterminal.gorev.komutdenetimi')}</p>
                    <div className="space-y-1">
                      {g.command_checks.map((k, i) => (
                        <div
                          key={i}
                          className={clsx(
                            'rounded-lg p-2 font-mono text-xs',
                            k.allowed ? 'bg-emerald-500/10' : 'bg-red-500/10',
                          )}
                        >
                          <div className="flex items-start gap-2">
                            {k.allowed ? (
                              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                            ) : (
                              <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600" />
                            )}
                            <div className="min-w-0">
                              <p className="break-all">{k.command}</p>
                              <p className="mt-0.5 font-sans" style={{ color: 'var(--metin-2)' }}>
                                {k.reason}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {/* --------------------------------------------------- eylemler */}
                <div className="mt-4 flex flex-wrap gap-2">
                  {yetkiVar('ai:terminal:approve') && ['plan_hazir', 'onay_bekliyor'].includes(g.status) && (
                    <>
                      <button
                        type="button"
                        className="dugme dugme-birincil"
                        onClick={() => eylem.mutate({ yol: '/approval', govde: { approve: true } })}
                        disabled={g.risk_level === 'engellendi' || eylem.isPending}
                      >
                        <GitBranch className="h-4 w-4" /> {t('aiterminal.dugme.onayla')}
                      </button>
                      <button
                        type="button"
                        className="dugme dugme-ikincil"
                        onClick={() =>
                          eylem.mutate({
                            yol: '/approval',
                            govde: {
                              approve: false,
                              reason: window.prompt(t('aiterminal.uyari.redgerekce')) ?? '',
                            },
                          })
                        }
                      >
                        {t('genel.reddet')}
                      </button>
                    </>
                  )}

                  {yetkiVar('ai:terminal:approve') && g.status === 'onaylandi' && (
                    <button
                      type="button"
                      className="dugme dugme-birincil"
                      onClick={() => eylem.mutate({ yol: '/run' })}
                      disabled={eylem.isPending}
                    >
                      <Play className="h-4 w-4" /> {t('aiterminal.dugme.calistir')}
                    </button>
                  )}

                  {yetkiVar('ai:terminal:approve') &&
                    ['test_ediliyor', 'basarisiz', 'basarili'].includes(g.status) && (
                      <button
                        type="button"
                        className="dugme dugme-ikincil"
                        onClick={() => eylem.mutate({ yol: '/verify' })}
                        disabled={eylem.isPending}
                      >
                        <TestTube className="h-4 w-4" /> {t('aiterminal.dugme.dogrula')}
                      </button>
                    )}

                  {yetkiVar('ai:terminal:approve') && g.git_checkpoint && (
                    <button
                      type="button"
                      className="dugme dugme-tehlike"
                      onClick={() => {
                        if (window.confirm(t('aiterminal.uyari.gerial'))) {
                          eylem.mutate({ yol: '/rollback' })
                        }
                      }}
                      disabled={eylem.isPending}
                    >
                      <RotateCcw className="h-4 w-4" /> {t('aiterminal.dugme.gerial')}
                    </button>
                  )}
                </div>

                {g.git_checkpoint && (
                  <p className="mt-2 text-[11px]" style={{ color: 'var(--metin-2)' }}>
                    {t('aiterminal.gorev.kontrolnoktasi')}{' '}
                    <span className="font-mono">{g.git_checkpoint}</span>
                    {g.git_branch && ` · ${t('aiterminal.gorev.dal')}: ${g.git_branch}`}
                  </p>
                )}
              </Kart>

              {(calismalar.data?.length ?? 0) > 0 && (
                <Kart baslik={t('aiterminal.kart.ciktilar')} govdeSinif="p-0">
                  <div className="divide-y" style={{ borderColor: 'var(--kenar)' }}>
                    {calismalar.data?.map((c) => (
                      <div key={c.id} className="p-3">
                        <div className="flex items-center justify-between gap-2">
                          <code className="text-xs">{c.command}</code>
                          <Rozet seviye={c.allowed && c.exit_code === 0 ? 'dusuk' : 'kritik'}>
                            {!c.allowed
                              ? t('aiterminal.calisma.engellendi')
                              : c.timed_out
                                ? t('aiterminal.calisma.zamanasimi')
                                : `${t('aiterminal.calisma.cikis')} ${c.exit_code}`}
                          </Rozet>
                        </div>
                        {c.block_reason && (
                          <p className="mt-1 text-xs text-red-600 dark:text-red-400">{c.block_reason}</p>
                        )}
                        {(c.stdout || c.stderr) && (
                          <pre
                            className="mt-2 max-h-64 overflow-auto rounded-lg p-2 text-[11px] leading-relaxed"
                            style={{ background: 'var(--yuzey-3)' }}
                          >
                            {c.stdout}
                            {c.stderr && `\n${c.stderr}`}
                          </pre>
                        )}
                      </div>
                    ))}
                  </div>
                </Kart>
              )}

              {g.diff_text && (
                <Kart baslik={t('aiterminal.kart.diff')} govdeSinif="p-0">
                  <pre
                    className="max-h-96 overflow-auto p-3 text-[11px] leading-relaxed"
                    style={{ background: 'var(--yuzey-3)' }}
                  >
                    {g.diff_text}
                  </pre>
                </Kart>
              )}

              {(g.test_output || g.lint_output) && (
                <Kart
                  baslik={t('aiterminal.kart.dogrulama')}
                  sag={
                    g.tests_passed === null ? null : (
                      <Rozet seviye={g.tests_passed ? 'dusuk' : 'kritik'}>
                        {g.tests_passed
                          ? t('aiterminal.dogrulama.gecti')
                          : t('aiterminal.dogrulama.basarisiz')}
                      </Rozet>
                    )
                  }
                  govdeSinif="p-0"
                >
                  <pre
                    className="max-h-96 overflow-auto p-3 text-[11px] leading-relaxed"
                    style={{ background: 'var(--yuzey-3)' }}
                  >
                    {g.lint_output}
                    {g.test_output && `\n\n${g.test_output}`}
                  </pre>
                </Kart>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
