import { expect, type Page } from '@playwright/test'

/** Demo kullanıcı parolası — yalnızca geliştirme ortamında geçerlidir. */
export const DEMO_PAROLA = process.env.E2E_PAROLA ?? 'Saraphane2026!'

export type DemoKullanici =
  | 'admin'
  | 'mudur'
  | 'enolog'
  | 'bagci'
  | 'lab'
  | 'mahzen'
  | 'operator'
  | 'siseleme'
  | 'depo'
  | 'satis'
  | 'muhasebe'
  | 'denetci'

const ERISIM_ANAHTARI = 'saraphane.erisim'
const YENILEME_ANAHTARI = 'saraphane.yenileme'

interface Oturum {
  erisim: string
  yenileme: string | null
}

/**
 * Rol başına bir kez gerçek giriş yapılır, belirteç sonraki testlerde yeniden
 * kullanılır.
 *
 * Sebep yalnızca hız değil: sunucu kaba kuvvete karşı `/auth/login` isteklerini
 * dakikada 10 ile sınırlar. Her test yeniden giriş yaparsa testler kendi
 * güvenlik korumamıza takılır ve 429 alır. Bu koruma doğrudur; testlerin
 * gerçek bir kullanıcı gibi oturumu sürdürmesi gerekir.
 */
const oturumOnbellegi = new Map<DemoKullanici, Oturum>()

/** Verilen kullanıcıyla giriş yapar ve kontrol panelinin yüklenmesini bekler. */
export async function girisYap(page: Page, kullanici: DemoKullanici = 'admin') {
  const onbellek = oturumOnbellegi.get(kullanici)

  if (onbellek) {
    // Belirteci sayfa açılmadan yerleştir: uygulama ilk render'da okur.
    await page.addInitScript(
      ([erisimAnahtari, yenilemeAnahtari, erisim, yenileme]) => {
        localStorage.setItem(erisimAnahtari, erisim)
        if (yenileme) localStorage.setItem(yenilemeAnahtari, yenileme)
      },
      [ERISIM_ANAHTARI, YENILEME_ANAHTARI, onbellek.erisim, onbellek.yenileme ?? ''] as const,
    )
    await page.goto('/')
    await expect(page.getByRole('navigation')).toBeVisible({ timeout: 20_000 })
    return
  }

  await page.goto('/')
  await page.getByRole('textbox').first().fill(kullanici)
  await page.locator('input[type="password"]').fill(DEMO_PAROLA)
  await page.getByRole('button', { name: 'Giriş yap' }).click()
  // Kabuk yüklendiğinde yan menü görünür olur
  await expect(page.getByRole('navigation')).toBeVisible({ timeout: 20_000 })

  const oturum = await page.evaluate(
    ([e, y]) => ({
      erisim: localStorage.getItem(e),
      yenileme: localStorage.getItem(y),
    }),
    [ERISIM_ANAHTARI, YENILEME_ANAHTARI] as const,
  )
  if (oturum.erisim) {
    oturumOnbellegi.set(kullanici, { erisim: oturum.erisim, yenileme: oturum.yenileme })
  }
}

/**
 * Önbelleği temizler. Oturum kapatmayı sınayan testler bunu çağırmalıdır;
 * aksi hâlde sonraki test iptal edilmiş bir yenileme belirteci kullanır.
 */
export function oturumuUnut(kullanici?: DemoKullanici) {
  if (kullanici) oturumOnbellegi.delete(kullanici)
  else oturumOnbellegi.clear()
}

/** Geçerli sayfanın erişim belirtecini döner (API doğrulamaları için). */
export async function erisimBelirteci(page: Page): Promise<string> {
  const t = await page.evaluate((a) => localStorage.getItem(a), ERISIM_ANAHTARI)
  expect(t, 'Erişim belirteci bulunamadı').toBeTruthy()
  return t as string
}

/** Yan menüden bir bölüme geçer. */
export async function menudenGit(page: Page, etiket: string) {
  await page.getByRole('navigation').getByRole('link', { name: etiket, exact: true }).click()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
}

/** Sayfadaki tüm ağ isteklerinin durulmasını ve grafiklerin çizilmesini bekler. */
export async function sayfaHazir(page: Page) {
  await page.waitForLoadState('networkidle')
  // ECharts canvas'ları asenkron çizilir
  await page.waitForTimeout(600)
}

/**
 * Zararsız olduğu bilinen konsol gürültüsü.
 *
 * Vite geliştirme sunucusu ve tarayıcı eklentileri, uygulamayla ilgisi olmayan
 * mesajlar üretebilir. Bunlar testi başarısız kılmamalıdır.
 */
const YOKSAYILAN_KONSOL = [
  /\[vite\] connect/i,
  /Download the React DevTools/i,
  /favicon\.ico/i,
]

/**
 * Konsolda hata olup olmadığını izler; testler sonunda doğrulanır.
 *
 * @param ekYoksay Bu teste özgü, beklenen hata kalıpları.
 */
export function konsolHatalariniIzle(page: Page, ekYoksay: RegExp[] = []): string[] {
  const yoksay = [...YOKSAYILAN_KONSOL, ...ekYoksay]
  const hatalar: string[] = []
  const ekle = (metin: string) => {
    if (!yoksay.some((k) => k.test(metin))) hatalar.push(metin)
  }
  page.on('console', (msg) => {
    if (msg.type() === 'error') ekle(msg.text())
  })
  page.on('pageerror', (err) => ekle(String(err)))
  return hatalar
}
