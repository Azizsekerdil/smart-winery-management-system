import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Grafik } from '@/components/Grafik'
import { Bos, Kart, Rozet, SayfaBasligi, Yukleniyor } from '@/components/Ortak'
import { api } from '@/lib/api'
import { sayi, yuzde } from '@/lib/bicim'
import { useCeviri } from '@/lib/i18n'
import { useOturum } from '@/lib/store'

/**
 * İstatistikler — "işletme nasıl gidiyor?" sorusunu yanıtlar.
 *
 * Kontrol Paneli anlık durumu gösterir; burası verimlilik, kayıp, kalite
 * tutarlılığı ve dönem karşılaştırması sunar.
 *
 * Her sekme KENDİ yetkisiyle korunur ve yetkisiz sekme hiç istenmez: tek bir
 * uç nokta kullanılsaydı `report:read` taşıyan ama `cost:read`/`lab:read`
 * taşımayan roller (satış, depo) maliyet ve laboratuvar verisini görürdü.
 */

interface Sekme {
  kod: string
  /** Çeviri anahtarı — metne render sırasında çevrilir. */
  ad: string
  yetki: string
}

const SEKMELER: Sekme[] = [
  { kod: 'hasat', ad: 'istatistikler.sekme.hasat', yetki: 'harvest:read' },
  { kod: 'fire', ad: 'istatistikler.sekme.fire', yetki: 'lot:read' },
  { kod: 'fermantasyon', ad: 'istatistikler.sekme.fermantasyon', yetki: 'fermentation:read' },
  { kod: 'laboratuvar', ad: 'istatistikler.sekme.laboratuvar', yetki: 'lab:read' },
  { kod: 'siseleme', ad: 'istatistikler.sekme.siseleme', yetki: 'bottling:read' },
  { kod: 'fici', ad: 'istatistikler.sekme.fici', yetki: 'barrel:read' },
  { kod: 'stok', ad: 'istatistikler.sekme.stok', yetki: 'inventory:read' },
  { kod: 'bakim', ad: 'istatistikler.sekme.bakim', yetki: 'maintenance:read' },
]

const RENK = ['#b52a57', '#8c5b2f', '#5f7a4a', '#4a6d8c', '#7a4a7a', '#8c7a2f']

/** API yanıtı `unknown` gelir; grafik verisi kesin tiplere indirgenir. */
type Kayit = Record<string, unknown>

const n = (v: unknown): number => Number(v ?? 0)
const metin = (v: unknown): string => (v === null || v === undefined ? '—' : String(v))
const list = (v: unknown): Kayit[] => (Array.isArray(v) ? (v as Kayit[]) : [])
const obj = (v: unknown): Kayit => (v && typeof v === 'object' ? (v as Kayit) : {})

/** Sayı ya da yoksa null — '0' ile 'veri yok' ayrımı korunur. */
const nOrNull = (v: unknown): number | null =>
  v === null || v === undefined ? null : Number(v)

/** Değer yoksa '—' gösterir; '0' ile 'veri yok' karıştırılmamalı. */
function deger(v: number | null | undefined, bicim: (n: number) => string): string {
  return v === null || v === undefined ? '—' : bicim(v)
}

function Gosterge({ etiket, deger: d, ipucu }: { etiket: string; deger: string; ipucu?: string }) {
  return (
    <div className="kart p-4">
      <p className="text-xs" style={{ color: 'var(--metin-2)' }}>
        {etiket}
      </p>
      <p className="mt-1 text-xl font-semibold">{d}</p>
      {ipucu && (
        <p className="mt-0.5 text-[11px]" style={{ color: 'var(--metin-2)' }}>
          {ipucu}
        </p>
      )}
    </div>
  )
}

export default function Istatistikler() {
  const t = useCeviri()
  const yetkiVar = useOturum((s) => s.yetkiVar)
  const gorunur = SEKMELER.filter((s) => yetkiVar(s.yetki))
  const [aktif, setAktif] = useState(gorunur[0]?.kod ?? '')
  const [yil, setYil] = useState<string>('')

  const yilliKonu = ['hasat', 'fire', 'fermantasyon', 'siseleme'].includes(aktif)

  const sorgu = useQuery({
    queryKey: ['/statistics', aktif, yilliKonu ? yil : ''],
    queryFn: async () =>
      (
        await api.get(`/statistics/${aktif}`, {
          params: yilliKonu && yil ? { yil: Number(yil) } : undefined,
        })
      ).data as Kayit,
    enabled: !!aktif,
    retry: false,
  })

  if (gorunur.length === 0) {
    return (
      <div className="space-y-5">
        <SayfaBasligi baslik={t('istatistikler.baslik')} />
        <Bos metin={t('istatistikler.bos.yetki')} />
      </div>
    )
  }

  const v = sorgu.data as Kayit | undefined

  return (
    <div className="space-y-5">
      <SayfaBasligi
        baslik={t('istatistikler.baslik')}
        aciklama={t('istatistikler.aciklama')}
        eylemler={
          yilliKonu ? (
            <select
              className="girdi w-auto"
              value={yil}
              onChange={(e) => setYil(e.target.value)}
              aria-label={t('istatistikler.filtre.rekolteyili')}
            >
              <option value="">{t('istatistikler.filtre.tumyillar')}</option>
              {Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i).map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          ) : undefined
        }
      />

      {/* ------------------------------------------------------------ sekmeler */}
      <div className="flex flex-wrap gap-1.5" role="tablist">
        {gorunur.map((s) => (
          <button
            key={s.kod}
            type="button"
            role="tab"
            aria-selected={aktif === s.kod}
            onClick={() => setAktif(s.kod)}
            className={
              aktif === s.kod ? 'dugme dugme-birincil' : 'dugme dugme-ikincil'
            }
          >
            {t(s.ad)}
          </button>
        ))}
      </div>

      {sorgu.isLoading && <Yukleniyor metin={t('istatistikler.yukleniyor')} />}

      {v && aktif === 'hasat' && <HasatGorunumu v={v} />}
      {v && aktif === 'fire' && <FireGorunumu v={v} />}
      {v && aktif === 'fermantasyon' && <FermantasyonGorunumu v={v} />}
      {v && aktif === 'laboratuvar' && <LaboratuvarGorunumu v={v} />}
      {v && aktif === 'siseleme' && <SiselemeGorunumu v={v} />}
      {v && aktif === 'fici' && <FiciGorunumu v={v} />}
      {v && aktif === 'stok' && <StokGorunumu v={v} />}
      {v && aktif === 'bakim' && <BakimGorunumu v={v} />}
    </div>
  )
}

/* ------------------------------------------------------------------- hasat */
function HasatGorunumu({ v }: { v: Kayit }) {
  const t = useCeviri()
  const parseller = list(v.parseller)
  const cesitler = list(v.cesitler)
  const yillar = list(v.yillar)
  const kalite = list(v.kalite_dagilimi)

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-2">
        <Kart baslik={t('istatistikler.hasat.yilbaslik')} aciklama={t('istatistikler.hasat.yilaciklama')}>
          {yillar.length ? (
            <Grafik
              yukseklik={280}
              secenek={{
                tooltip: { trigger: 'axis' },
                legend: { data: [t('istatistikler.hasat.uzumkg'), t('istatistikler.hasat.ortbrix')] },
                xAxis: { type: 'category', data: yillar.map((y) => String(y.yil)) },
                yAxis: [
                  { type: 'value', name: 'kg' },
                  { type: 'value', name: 'Brix' },
                ],
                series: [
                  {
                    name: t('istatistikler.hasat.uzumkg'),
                    type: 'bar',
                    data: yillar.map((y) => n(y.kg)),
                    itemStyle: { color: RENK[0] },
                  },
                  {
                    name: t('istatistikler.hasat.ortbrix'),
                    type: 'line',
                    yAxisIndex: 1,
                    data: yillar.map((y) => n(y.ort_brix)),
                    itemStyle: { color: RENK[2] },
                  },
                ],
              }}
            />
          ) : (
            <Bos metin={t('istatistikler.hasat.bos')} />
          )}
        </Kart>

        <Kart baslik={t('istatistikler.hasat.kalitebaslik')}>
          {kalite.length ? (
            <Grafik
              yukseklik={280}
              secenek={{
                tooltip: { trigger: 'item' },
                series: [
                  {
                    type: 'pie',
                    radius: ['45%', '70%'],
                    data: kalite.map((k, i) => ({
                      name: String(k.sinif),
                      value: n(k.kg),
                      itemStyle: { color: RENK[i % RENK.length] },
                    })),
                  },
                ],
              }}
            />
          ) : (
            <Bos metin={t('istatistikler.hasat.kalitebos')} />
          )}
        </Kart>
      </div>

      <Kart
        baslik={t('istatistikler.hasat.parselbaslik')}
        aciklama={t('istatistikler.hasat.parselaciklama')}
        govdeSinif="p-0"
      >
        {parseller.length ? (
          <div className="overflow-x-auto">
            <table className="tablo">
              <thead>
                <tr>
                  <th>{t('istatistikler.hasat.parsel')}</th>
                  <th>{t('istatistikler.hasat.bag')}</th>
                  <th className="text-right">{t('istatistikler.hasat.alan')}</th>
                  <th className="text-right">{t('istatistikler.hasat.uzumkg')}</th>
                  <th className="text-right">{t('istatistikler.hasat.kgdekar')}</th>
                  <th className="text-right">{t('istatistikler.hasat.kgasma')}</th>
                  <th className="text-right">{t('istatistikler.hasat.ortbrix')}</th>
                  <th className="text-right">{t('istatistikler.hasat.curuk')}</th>
                </tr>
              </thead>
              <tbody>
                {parseller.map((p) => (
                  <tr key={metin(p.kod)}>
                    <td>
                      <span className="font-medium">{metin(p.ad)}</span>{' '}
                      <span style={{ color: 'var(--metin-2)' }}>{metin(p.kod)}</span>
                    </td>
                    <td>{metin(p.bag)}</td>
                    <td className="text-right">{deger(nOrNull(p.alan_da), (n) => sayi(n, 1))}</td>
                    <td className="text-right">{sayi(n(p.kg), 0)}</td>
                    <td className="text-right font-medium">
                      {deger(nOrNull(p.kg_dekar), (n) => sayi(n, 0))}
                    </td>
                    <td className="text-right">{deger(nOrNull(p.kg_asma), (n) => sayi(n, 2))}</td>
                    <td className="text-right">{deger(nOrNull(p.ort_brix), (n) => sayi(n, 1))}</td>
                    <td className="text-right">
                      {deger(nOrNull(p.ort_curuk_yuzde), (n) => sayi(n, 1))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Bos
            metin={t('istatistikler.hasat.parselbos')}
            ipucu={t('istatistikler.hasat.parselbosipucu')}
          />
        )}
      </Kart>

      <Kart
        baslik={t('istatistikler.hasat.cesitbaslik')}
        aciklama={t('istatistikler.hasat.cesitaciklama')}
        govdeSinif="p-0"
      >
        {cesitler.length ? (
          <div className="overflow-x-auto">
            <table className="tablo">
              <thead>
                <tr>
                  <th>{t('istatistikler.hasat.cesit')}</th>
                  <th className="text-right">{t('istatistikler.hasat.uzumkg')}</th>
                  <th className="text-right">{t('istatistikler.hasat.ortbrix')}</th>
                  <th>{t('istatistikler.hasat.hedef')}</th>
                  <th>{t('istatistikler.hasat.durum')}</th>
                </tr>
              </thead>
              <tbody>
                {cesitler.map((c) => (
                  <tr key={metin(c.ad)}>
                    <td className="font-medium">{metin(c.ad)}</td>
                    <td className="text-right">{sayi(n(c.kg), 0)}</td>
                    <td className="text-right">{deger(nOrNull(c.ort_brix), (n) => sayi(n, 1))}</td>
                    <td>{metin(c.hedef_brix)}</td>
                    <td>
                      {c.hedefte_mi === null || c.hedefte_mi === undefined ? (
                        '—'
                      ) : (
                        <Rozet seviye={c.hedefte_mi ? 'dusuk' : 'uyari'}>
                          {c.hedefte_mi
                            ? t('istatistikler.hasat.hedefte')
                            : t('istatistikler.hasat.hedefdisi')}
                        </Rozet>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Bos metin={t('istatistikler.hasat.cesitbos')} />
        )}
      </Kart>
    </div>
  )
}

/* -------------------------------------------------------------------- fire */
function FireGorunumu({ v }: { v: Kayit }) {
  const t = useCeviri()
  const ozet = obj(v.ozet)
  const huni = list(v.huni)
  const kayiplar = list(v.kayiplar)

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Gosterge etiket={t('istatistikler.fire.uzum')} deger={`${sayi(ozet.uzum_kg ?? 0, 0)} kg`} />
        <Gosterge etiket={t('istatistikler.fire.sira')} deger={`${sayi(ozet.sira_l ?? 0, 0)} L`} />
        <Gosterge
          etiket={t('istatistikler.fire.siraverimi')}
          deger={deger(nOrNull(ozet.sira_verimi_l_kg), (n) => `${sayi(n, 3)} L/kg`)}
          ipucu={t('istatistikler.fire.siraverimiipucu')}
        />
        <Gosterge
          etiket={t('istatistikler.fire.toplamkayip')}
          deger={`${sayi(ozet.toplam_kayip_l ?? 0, 1)} L`}
          ipucu={`${sayi(ozet.fire_sise ?? 0, 0)} ${t('istatistikler.fire.firesise')}`}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Kart baslik={t('istatistikler.fire.hunibaslik')} aciklama={t('istatistikler.fire.huniaciklama')}>
          <Grafik
            yukseklik={300}
            secenek={{
              tooltip: { trigger: 'axis' },
              xAxis: { type: 'category', data: huni.map((h) => metin(h.asama)) },
              yAxis: { type: 'value' },
              series: [
                {
                  type: 'bar',
                  data: huni.map((h, i) => ({
                    value: n(h.deger),
                    itemStyle: { color: RENK[i % RENK.length] },
                  })),
                },
              ],
            }}
          />
        </Kart>

        <Kart baslik={t('istatistikler.fire.kayipbaslik')} aciklama={t('istatistikler.fire.kayipaciklama')}>
          <Grafik
            yukseklik={300}
            secenek={{
              tooltip: { trigger: 'item', formatter: '{b}: {c} L' },
              series: [
                {
                  type: 'pie',
                  radius: ['45%', '70%'],
                  data: kayiplar.map((k, i) => ({
                    name: String(k.asama),
                    value: n(k.litre),
                    itemStyle: { color: RENK[i % RENK.length] },
                  })),
                },
              ],
            }}
          />
        </Kart>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------ fermantasyon */
function FermantasyonGorunumu({ v }: { v: Kayit }) {
  const t = useCeviri()
  const sure = obj(v.sure)
  const brix = obj(v.brix)
  const durumlar = list(v.durumlar)

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Gosterge etiket={t('istatistikler.fermantasyon.tamamlanan')} deger={sayi(sure.tamamlanan ?? 0, 0)} />
        <Gosterge
          etiket={t('istatistikler.fermantasyon.ortalamasure')}
          deger={deger(nOrNull(sure.ortalama_gun), (n) => `${sayi(n, 1)} ${t('istatistikler.birim.gun')}`)}
        />
        <Gosterge
          etiket={t('istatistikler.fermantasyon.surearaligi')}
          deger={
            sure.en_kisa_gun === null || sure.en_kisa_gun === undefined
              ? '—'
              : `${sayi(sure.en_kisa_gun, 0)}–${sayi(sure.en_uzun_gun ?? 0, 0)} ${t('istatistikler.birim.gun')}`
          }
        />
        <Gosterge
          etiket={t('istatistikler.fermantasyon.gunlukbrix')}
          deger={deger(nOrNull(brix.gunluk_dusus), (n) => sayi(n, 2))}
        />
      </div>

      <Kart baslik={t('istatistikler.fermantasyon.durumbaslik')}>
        {durumlar.length ? (
          <Grafik
            yukseklik={280}
            secenek={{
              tooltip: { trigger: 'item' },
              series: [
                {
                  type: 'pie',
                  radius: ['45%', '70%'],
                  data: durumlar.map((d, i) => ({
                    name: String(d.durum),
                    value: n(d.adet),
                    itemStyle: { color: RENK[i % RENK.length] },
                  })),
                },
              ],
            }}
          />
        ) : (
          <Bos metin={t('istatistikler.fermantasyon.bos')} />
        )}
      </Kart>
    </div>
  )
}

/* ------------------------------------------------------------- laboratuvar */
function LaboratuvarGorunumu({ v }: { v: Kayit }) {
  const t = useCeviri()
  const ozet = obj(v.ozet)
  const aylik = list(v.aylik)
  const parametreler = list(v.parametreler)

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <Gosterge etiket={t('istatistikler.laboratuvar.analizsayisi')} deger={sayi(ozet.analiz_sayisi ?? 0, 0)} />
        <Gosterge
          etiket={t('istatistikler.laboratuvar.specdisi')}
          deger={deger(nOrNull(ozet.spec_disi_orani), (n) => yuzde(n * 100))}
          ipucu={`${sayi(ozet.spec_disi ?? 0, 0)} ${t('istatistikler.laboratuvar.analizbirim')}`}
        />
        <Gosterge
          etiket={t('istatistikler.laboratuvar.ortonaysuresi')}
          deger={deger(nOrNull(ozet.ort_onay_suresi_gun), (n) => `${sayi(n, 1)} ${t('istatistikler.birim.gun')}`)}
        />
      </div>

      <Kart baslik={t('istatistikler.laboratuvar.aylikbaslik')}>
        {aylik.length ? (
          <Grafik
            yukseklik={280}
            secenek={{
              tooltip: { trigger: 'axis' },
              xAxis: { type: 'category', data: aylik.map((a) => metin(a.ay)) },
              yAxis: [
                { type: 'value', name: t('istatistikler.laboratuvar.analiz') },
                { type: 'value', name: '%', max: 100 },
              ],
              series: [
                {
                  name: t('istatistikler.laboratuvar.analiz'),
                  type: 'bar',
                  data: aylik.map((a) => n(a.analiz)),
                  itemStyle: { color: RENK[3] },
                },
                {
                  name: t('istatistikler.laboratuvar.specdisiyuzde'),
                  type: 'line',
                  yAxisIndex: 1,
                  data: aylik.map((a) => n(a.oran) * 100),
                  itemStyle: { color: RENK[0] },
                },
              ],
            }}
          />
        ) : (
          <Bos metin={t('istatistikler.laboratuvar.bos')} />
        )}
      </Kart>

      <Kart baslik={t('istatistikler.laboratuvar.parametrebaslik')} govdeSinif="p-0">
        {parametreler.length ? (
          <div className="overflow-x-auto">
            <table className="tablo">
              <thead>
                <tr>
                  <th>{t('istatistikler.laboratuvar.parametre')}</th>
                  <th className="text-right">{t('istatistikler.laboratuvar.ortalama')}</th>
                  <th className="text-right">{t('istatistikler.laboratuvar.enaz')}</th>
                  <th className="text-right">{t('istatistikler.laboratuvar.encok')}</th>
                  <th className="text-right">{t('istatistikler.laboratuvar.olcum')}</th>
                </tr>
              </thead>
              <tbody>
                {parametreler.map((p) => (
                  <tr key={metin(p.ad)}>
                    <td className="font-medium">
                      {metin(p.ad)}{' '}
                      {p.birim ? (
                        <span style={{ color: 'var(--metin-2)' }}>{metin(p.birim)}</span>
                      ) : null}
                    </td>
                    <td className="text-right">{sayi(n(p.ortalama), 3)}</td>
                    <td className="text-right">{sayi(n(p.en_az), 3)}</td>
                    <td className="text-right">{sayi(n(p.en_cok), 3)}</td>
                    <td className="text-right">{sayi(n(p.olcum), 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Bos metin={t('istatistikler.laboratuvar.parametrebos')} />
        )}
      </Kart>
    </div>
  )
}

/* ---------------------------------------------------------------- şişeleme */
function SiselemeGorunumu({ v }: { v: Kayit }) {
  const t = useCeviri()
  const ozet = obj(v.ozet)
  const aylik = list(v.aylik)
  const ambalaj = list(v.ambalaj)
  const hatlar = list(v.hatlar)

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Gosterge etiket={t('istatistikler.siseleme.uretilensise')} deger={sayi(ozet.uretilen_sise ?? 0, 0)} />
        <Gosterge etiket={t('istatistikler.siseleme.planlanan')} deger={sayi(ozet.planlanan_sise ?? 0, 0)} />
        <Gosterge
          etiket={t('istatistikler.siseleme.verim')}
          deger={deger(nOrNull(ozet.verim_orani), (n) => yuzde(n * 100))}
        />
        <Gosterge
          etiket={t('istatistikler.siseleme.fireorani')}
          deger={deger(nOrNull(ozet.fire_orani), (n) => yuzde(n * 100))}
          ipucu={`${sayi(ozet.fire_sise ?? 0, 0)} ${t('istatistikler.birim.sise')}`}
        />
      </div>

      <Kart baslik={t('istatistikler.siseleme.aylikbaslik')}>
        {aylik.length ? (
          <Grafik
            yukseklik={280}
            secenek={{
              tooltip: { trigger: 'axis' },
              xAxis: { type: 'category', data: aylik.map((a) => metin(a.ay)) },
              yAxis: { type: 'value', name: t('istatistikler.siseleme.sise') },
              series: [
                { type: 'bar', data: aylik.map((a) => n(a.sise)), itemStyle: { color: RENK[0] } },
              ],
            }}
          />
        ) : (
          <Bos metin={t('istatistikler.siseleme.bos')} />
        )}
      </Kart>

      <div className="grid gap-5 lg:grid-cols-2">
        <Kart baslik={t('istatistikler.siseleme.ambalajbaslik')}>
          {ambalaj.length ? (
            <Grafik
              yukseklik={260}
              secenek={{
                tooltip: { trigger: 'item' },
                series: [
                  {
                    type: 'pie',
                    radius: ['45%', '70%'],
                    data: ambalaj.map((a, i) => ({
                      name: `${metin(a.hacim_ml)} ml`,
                      value: n(a.sise),
                      itemStyle: { color: RENK[i % RENK.length] },
                    })),
                  },
                ],
              }}
            />
          ) : (
            <Bos metin={t('istatistikler.siseleme.ambalajbos')} />
          )}
        </Kart>

        <Kart baslik={t('istatistikler.siseleme.hatbaslik')} govdeSinif="p-0">
          {hatlar.length ? (
            <div className="overflow-x-auto">
              <table className="tablo">
                <thead>
                  <tr>
                    <th>{t('istatistikler.siseleme.hat')}</th>
                    <th className="text-right">{t('istatistikler.siseleme.uretilen')}</th>
                    <th className="text-right">{t('istatistikler.siseleme.fire')}</th>
                    <th className="text-right">{t('istatistikler.siseleme.fireorani')}</th>
                  </tr>
                </thead>
                <tbody>
                  {hatlar.map((h) => (
                    <tr key={metin(h.hat)}>
                      <td className="font-medium">{metin(h.hat)}</td>
                      <td className="text-right">{sayi(n(h.sise), 0)}</td>
                      <td className="text-right">{sayi(n(h.fire), 0)}</td>
                      <td className="text-right">
                        {deger(nOrNull(h.fire_orani), (n) => yuzde(n * 100))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Bos metin={t('istatistikler.siseleme.hatbos')} />
          )}
        </Kart>
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------- fıçı */
function FiciGorunumu({ v }: { v: Kayit }) {
  const t = useCeviri()
  const ozet = obj(v.ozet)
  const yas = list(v.yas_dagilimi)
  const kullanim = list(v.kullanim_dagilimi)

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Gosterge etiket={t('istatistikler.fici.sayisi')} deger={sayi(ozet.fici_sayisi ?? 0, 0)} />
        <Gosterge etiket={t('istatistikler.fici.kapasite')} deger={`${sayi(ozet.toplam_kapasite_l ?? 0, 0)} L`} />
        <Gosterge
          etiket={t('istatistikler.fici.doluluk')}
          deger={deger(nOrNull(ozet.doluluk_orani), (n) => yuzde(n * 100))}
        />
        <Gosterge
          etiket={t('istatistikler.fici.buharlasma')}
          deger={`${sayi(ozet.toplam_kayip_l ?? 0, 1)} L`}
          ipucu={t('istatistikler.fici.buharlasmaipucu')}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Kart baslik={t('istatistikler.fici.yasbaslik')}>
          {yas.length ? (
            <Grafik
              yukseklik={280}
              secenek={{
                tooltip: { trigger: 'axis' },
                xAxis: {
                  type: 'category',
                  data: yas.map((y) =>
                    y.yas === null || y.yas === undefined
                      ? '—'
                      : `${metin(y.yas)} ${t('istatistikler.fici.yas')}`,
                  ),
                },
                yAxis: { type: 'value', name: t('istatistikler.birim.adet') },
                series: [{ type: 'bar', data: yas.map((y) => n(y.adet)), itemStyle: { color: RENK[1] } }],
              }}
            />
          ) : (
            <Bos metin={t('istatistikler.fici.bos')} />
          )}
        </Kart>

        <Kart baslik={t('istatistikler.fici.kullanimbaslik')} aciklama={t('istatistikler.fici.kullanimaciklama')}>
          {kullanim.length ? (
            <Grafik
              yukseklik={280}
              secenek={{
                tooltip: { trigger: 'axis' },
                xAxis: { type: 'category', data: kullanim.map((k) => `${metin(k.dolum_sayisi)}.`) },
                yAxis: { type: 'value', name: t('istatistikler.birim.adet') },
                series: [
                  { type: 'bar', data: kullanim.map((k) => n(k.adet)), itemStyle: { color: RENK[4] } },
                ],
              }}
            />
          ) : (
            <Bos metin={t('istatistikler.fici.kullanimbos')} />
          )}
        </Kart>
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------- stok */
function StokGorunumu({ v }: { v: Kayit }) {
  const t = useCeviri()
  const encok = list(v.en_cok_tuketilen)
  const olu = list(v.hareketsiz)

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <Gosterge etiket={t('istatistikler.stok.aktifkalem')} deger={sayi((nOrNull(v.kalem_sayisi)) ?? 0, 0)} />
        <Gosterge
          etiket={t('istatistikler.stok.hareketsizkalem')}
          deger={sayi((nOrNull(v.hareketsiz_sayisi)) ?? 0, 0)}
          ipucu={t('istatistikler.stok.hareketsizipucu')}
        />
        <Gosterge
          etiket={t('istatistikler.stok.donem')}
          deger={`${sayi((nOrNull(v.gun)) ?? 0, 0)} ${t('istatistikler.birim.gun')}`}
        />
      </div>

      <Kart baslik={t('istatistikler.stok.encokbaslik')} govdeSinif="p-0">
        {encok.length ? (
          <div className="overflow-x-auto">
            <table className="tablo">
              <thead>
                <tr>
                  <th>{t('istatistikler.stok.kalem')}</th>
                  <th>{t('istatistikler.stok.kategori')}</th>
                  <th className="text-right">{t('istatistikler.stok.donemcikisi')}</th>
                  <th className="text-right">{t('istatistikler.stok.gunlukort')}</th>
                  <th>{t('istatistikler.stok.sonhareket')}</th>
                </tr>
              </thead>
              <tbody>
                {encok.map((k) => (
                  <tr key={metin(k.kod)}>
                    <td>
                      <span className="font-medium">{metin(k.ad)}</span>{' '}
                      <span style={{ color: 'var(--metin-2)' }}>{metin(k.kod)}</span>
                    </td>
                    <td>{metin(k.kategori)}</td>
                    <td className="text-right">
                      {sayi(n(k.donem_cikis), 2)} {metin(k.birim)}
                    </td>
                    <td className="text-right">{deger(nOrNull(k.gunluk_ortalama), (n) => sayi(n, 3))}</td>
                    <td>{k.son_hareket ? String(k.son_hareket).slice(0, 10) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Bos metin={t('istatistikler.stok.bos')} />
        )}
      </Kart>

      {olu.length > 0 && (
        <Kart
          baslik={t('istatistikler.stok.hareketsizbaslik')}
          aciklama={t('istatistikler.stok.hareketsizaciklama')}
          govdeSinif="p-0"
        >
          <div className="overflow-x-auto">
            <table className="tablo">
              <thead>
                <tr>
                  <th>{t('istatistikler.stok.kalem')}</th>
                  <th>{t('istatistikler.stok.kategori')}</th>
                  <th>{t('istatistikler.stok.sonhareket')}</th>
                </tr>
              </thead>
              <tbody>
                {olu.map((k) => (
                  <tr key={metin(k.kod)}>
                    <td>
                      <span className="font-medium">{metin(k.ad)}</span>{' '}
                      <span style={{ color: 'var(--metin-2)' }}>{metin(k.kod)}</span>
                    </td>
                    <td>{metin(k.kategori)}</td>
                    <td>{k.son_hareket ? String(k.son_hareket).slice(0, 10) : t('istatistikler.stok.hic')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Kart>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------- bakım */
function BakimGorunumu({ v }: { v: Kayit }) {
  const t = useCeviri()
  const turler = list(v.turler)
  const ekipmanlar = list(v.ekipmanlar)
  const cip = obj(v.cip)

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <Gosterge
          etiket={t('istatistikler.bakim.gecikenbakim')}
          deger={sayi((nOrNull(v.geciken_bakim)) ?? 0, 0)}
          ipucu={t('istatistikler.bakim.gecikenipucu')}
        />
        <Gosterge etiket={t('istatistikler.bakim.cipkaydi')} deger={sayi(cip.kayit ?? 0, 0)} />
        <Gosterge
          etiket={t('istatistikler.bakim.cipdogrulama')}
          deger={deger(nOrNull(cip.dogrulama_orani), (n) => yuzde(n * 100))}
          ipucu={t('istatistikler.bakim.cipipucu')}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Kart baslik={t('istatistikler.bakim.durusbaslik')} aciklama={t('istatistikler.bakim.durusaciklama')}>
          {turler.length ? (
            <Grafik
              yukseklik={280}
              secenek={{
                tooltip: { trigger: 'axis' },
                xAxis: { type: 'category', data: turler.map((tur) => metin(tur.tur)) },
                yAxis: { type: 'value', name: t('istatistikler.birim.dakika') },
                series: [
                  {
                    type: 'bar',
                    data: turler.map((tur) => n(tur.durus_dakika)),
                    itemStyle: { color: RENK[0] },
                  },
                ],
              }}
            />
          ) : (
            <Bos metin={t('istatistikler.bakim.bos')} />
          )}
        </Kart>

        <Kart baslik={t('istatistikler.bakim.ekipmanbaslik')} govdeSinif="p-0">
          {ekipmanlar.length ? (
            <div className="overflow-x-auto">
              <table className="tablo">
                <thead>
                  <tr>
                    <th>{t('istatistikler.bakim.ekipman')}</th>
                    <th className="text-right">{t('istatistikler.bakim.kayit')}</th>
                    <th className="text-right">{t('istatistikler.bakim.durus')}</th>
                  </tr>
                </thead>
                <tbody>
                  {ekipmanlar.map((e) => (
                    <tr key={metin(e.kod)}>
                      <td>
                        <span className="font-medium">{metin(e.ad)}</span>{' '}
                        <span style={{ color: 'var(--metin-2)' }}>{metin(e.kod)}</span>
                      </td>
                      <td className="text-right">{sayi(n(e.kayit), 0)}</td>
                      <td className="text-right">{sayi(n(e.durus_dakika), 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Bos metin={t('istatistikler.bakim.ekipmanbos')} />
          )}
        </Kart>
      </div>
    </div>
  )
}
