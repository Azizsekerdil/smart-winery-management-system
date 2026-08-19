import { useState } from 'react'
import { Kart, Kip, Rozet, SayfaBasligi } from '@/components/Ortak'
import { Tablo } from '@/components/Tablo'
import { etiket, tarihSaat } from '@/lib/bicim'
import { useListe } from '@/lib/hooks'
import { useCeviri } from '@/lib/i18n'

interface Kayit {
  id: number
  created_at: string
  username: string | null
  action: string
  entity_type: string
  entity_code: string | null
  summary: string
  before_data: Record<string, unknown> | null
  after_data: Record<string, unknown> | null
  changed_fields: string[] | null
  ip_address: string | null
  request_path: string | null
  request_method: string | null
  ai_provider: string | null
  ai_model: string | null
  agent_task_id: number | null
  severity: string
}

export default function Denetim() {
  const t = useCeviri()
  const [eylem, setEylem] = useState('')
  const [seviye, setSeviye] = useState('')
  const [secili, setSecili] = useState<Kayit | null>(null)

  const liste = useListe<Kayit>('/audit', {
    action: eylem || undefined,
    severity: seviye || undefined,
  })

  return (
    <div className="space-y-5">
      <SayfaBasligi baslik={t('denetim.baslik')} aciklama={t('denetim.aciklama')} />

      <Tablo
        sutunlar={[
          {
            anahtar: 'created_at',
            baslik: t('denetim.tablo.zaman'),
            genislik: '160px',
            hucre: (r) => tarihSaat(r.created_at),
          },
          {
            anahtar: 'username',
            baslik: t('denetim.tablo.kullanici'),
            hucre: (r) => r.username ?? t('denetim.deger.sistem'),
          },
          {
            anahtar: 'action',
            baslik: t('denetim.tablo.eylem'),
            hucre: (r) => <Rozet>{etiket(r.action)}</Rozet>,
          },
          { anahtar: 'entity_type', baslik: t('denetim.tablo.kayitturu'), gizleKucuk: true },
          { anahtar: 'entity_code', baslik: t('denetim.tablo.kod'), hucre: (r) => r.entity_code ?? '—' },
          { anahtar: 'summary', baslik: t('denetim.tablo.ozet') },
          {
            anahtar: 'severity',
            baslik: t('denetim.tablo.seviye'),
            hucre: (r) => <Rozet seviye={r.severity}>{r.severity}</Rozet>,
          },
          {
            anahtar: 'ai_provider',
            baslik: t('denetim.tablo.ai'),
            gizleKucuk: true,
            hucre: (r) => (r.ai_provider ? `${r.ai_provider}${r.ai_model ? ` · ${r.ai_model}` : ''}` : '—'),
          },
        ]}
        satirlar={liste.satirlar}
        yukleniyor={liste.isLoading}
        toplam={liste.toplam}
        sayfa={liste.sayfa}
        sayfaBoyu={liste.sayfaBoyu}
        onSayfa={liste.setSayfa}
        onSatirTikla={(r) => setSecili(r)}
        bosMetin={t('denetim.bos.metin')}
        ustBar={
          <>
            <select
              className="girdi w-auto"
              value={eylem}
              onChange={(e) => setEylem(e.target.value)}
              aria-label={t('denetim.tablo.eylem')}
            >
              <option value="">{t('denetim.filtre.tumeylemler')}</option>
              {[
                'olustur',
                'guncelle',
                'sil',
                'giris',
                'cikis',
                'giris_basarisiz',
                'onay',
                'red',
                'disa_aktar',
                'ai_istek',
                'ai_oneri',
                'terminal_komut',
                'terminal_onay',
                'terminal_red',
                'terminal_geri_al',
                'ayar_degisikligi',
                'izinsiz_erisim',
              ].map((a) => (
                <option key={a} value={a}>
                  {etiket(a)}
                </option>
              ))}
            </select>
            <select
              className="girdi w-auto"
              value={seviye}
              onChange={(e) => setSeviye(e.target.value)}
              aria-label={t('denetim.tablo.seviye')}
            >
              <option value="">{t('denetim.filtre.tumseviyeler')}</option>
              <option value="bilgi">{t('denetim.seviye.bilgi')}</option>
              <option value="uyari">{t('denetim.seviye.uyari')}</option>
              <option value="kritik">{t('denetim.seviye.kritik')}</option>
            </select>
          </>
        }
      />

      <Kart baslik={t('denetim.kart.degismezlik')}>
        <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
          {t('denetim.degismezlik.oncesi')}
          <code className="mx-1">405 Method Not Allowed</code>
          {t('denetim.degismezlik.sonrasi')}
        </p>
      </Kart>

      <Kip
        acik={secili !== null}
        baslik={`${t('denetim.kip.baslik')} #${secili?.id ?? ''}`}
        onKapat={() => setSecili(null)}
        genis
      >
        {secili && (
          <div className="space-y-3 text-sm">
            <div className="grid gap-2 sm:grid-cols-2">
              {[
                [t('denetim.tablo.zaman'), tarihSaat(secili.created_at)],
                [t('denetim.tablo.kullanici'), secili.username ?? t('denetim.deger.sistem')],
                [t('denetim.tablo.eylem'), etiket(secili.action)],
                [
                  t('denetim.detay.kayit'),
                  `${secili.entity_type}${secili.entity_code ? ` · ${secili.entity_code}` : ''}`,
                ],
                [t('denetim.detay.ip'), secili.ip_address ?? '—'],
                [t('denetim.detay.istek'), `${secili.request_method ?? ''} ${secili.request_path ?? ''}`],
              ].map(([ad, deger]) => (
                <div key={ad}>
                  <p className="text-[11px]" style={{ color: 'var(--metin-2)' }}>
                    {ad}
                  </p>
                  <p>{deger}</p>
                </div>
              ))}
            </div>

            <p className="rounded-lg p-2" style={{ background: 'var(--yuzey-3)' }}>
              {secili.summary}
            </p>

            {secili.changed_fields?.length ? (
              <div>
                <p className="mb-1 text-xs font-medium">{t('denetim.detay.degisenalanlar')}</p>
                <p className="font-mono text-xs">{secili.changed_fields.join(', ')}</p>
              </div>
            ) : null}

            <div className="grid gap-3 lg:grid-cols-2">
              {(
                [
                  [t('denetim.detay.oncekideger'), secili.before_data],
                  [t('denetim.detay.sonrakideger'), secili.after_data],
                ] as const
              ).map(([ad, veri]) =>
                veri ? (
                  <div key={ad}>
                    <p className="mb-1 text-xs font-medium">{ad}</p>
                    <pre
                      className="max-h-64 overflow-auto rounded-lg p-2 text-[11px]"
                      style={{ background: 'var(--yuzey-3)' }}
                    >
                      {JSON.stringify(veri, null, 2)}
                    </pre>
                  </div>
                ) : null,
              )}
            </div>
          </div>
        )}
      </Kip>
    </div>
  )
}
