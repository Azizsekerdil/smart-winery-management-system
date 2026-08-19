import { expect, test } from '@playwright/test'
import { girisYap, sayfaHazir } from './yardimcilar'

/**
 * Belge görsellerini üretir: `npm run gorseller`
 *
 * Çıktılar `docs/screenshots/` altına yazılır ve README'deki tabloya karşılık
 * gelir. Bu dosya bir doğrulama testi DEĞİLDİR; ayrı bir Playwright projesine
 * ("gorseller") aittir ve `npm run e2e` koşusuna dahil edilmez.
 *
 * Görseller demo veriyle üretilir; gerçek müşteri verisi içermez.
 */

const KLASOR = '../docs/screenshots'

test.describe('Belge görselleri', () => {
  // Görseller tek oturumda, sıralı üretilir
  test.describe.configure({ mode: 'serial' })

  test('kontrol paneli', async ({ page }) => {
    await girisYap(page, 'admin')
    await sayfaHazir(page)
    await expect(page.getByRole('heading', { level: 1, name: 'Kontrol Paneli' })).toBeVisible()
    await page.screenshot({ path: `${KLASOR}/pano.png`, fullPage: true })
  })

  test('fermantasyon eğrisi', async ({ page }) => {
    await girisYap(page, 'enolog')
    await page.goto('/fermantasyon')
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/fermantasyon.png`, fullPage: true })
  })

  test('izlenebilirlik çizgesi', async ({ page }) => {
    await girisYap(page, 'enolog')
    await page.goto('/partiler')
    await page.getByRole('row').nth(1).click()
    await expect(page.getByText('İzlenebilirlik çizgesi')).toBeVisible()
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/izlenebilirlik.png`, fullPage: true })
  })

  test('tank yerleşimi', async ({ page }) => {
    await girisYap(page, 'enolog')
    await page.goto('/tanklar')
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/tanklar.png`, fullPage: true })
  })

  test('mahzen haritası', async ({ page }) => {
    await girisYap(page, 'mahzen')
    await page.goto('/fici')
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/mahzen.png`, fullPage: true })
  })

  test('yapay zekâ merkezi', async ({ page }) => {
    await girisYap(page, 'enolog')
    await page.goto('/yapay-zeka')
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/yapay-zeka.png`, fullPage: true })
  })

  test('ai terminali', async ({ page }) => {
    await girisYap(page, 'admin')
    await page.goto('/ai-terminal')
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/ai-terminal.png`, fullPage: true })
  })

  test('sağlayıcı ayarları', async ({ page }) => {
    await girisYap(page, 'admin')
    await page.goto('/ayarlar')
    await sayfaHazir(page)

    // Arayüz anahtarı zaten maskeler, ancak maskeli gösterim bile gerçek
    // anahtarın son karakterlerini ve parmak izini içerir. Bu görsel depoya
    // işlendiği için o türev bilgiyi de dışarı çıkarmayız: yakalamadan önce
    // yer tutucuyla değiştiririz. Değişiklik yalnızca görseldedir; uygulamanın
    // kendi maskeleme davranışı 05-yapay-zeka.spec.ts'te doğrulanır.
    await page.evaluate(() => {
      // Maskeli anahtar ve parmak izi ayrı DOM düğümlerinde durur; bu yüzden
      // her düğüm kendi başına da değerlendirilir.
      const yerTutucu = (metin: string) =>
        metin
          .replace(/\*{4,}[A-Za-z0-9]{2,}/g, '••••••••••••••••••••••••••••')
          .replace(/parmak izi\s+[a-f0-9]{6,}/gi, 'parmak izi ••••••••••••')
          .replace(/^\s*[a-f0-9]{8,}\s*$/i, '••••••••••••')
      const gez = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
      const dugumler: Text[] = []
      while (gez.nextNode()) dugumler.push(gez.currentNode as Text)
      for (const d of dugumler) {
        const yeni = yerTutucu(d.data)
        if (yeni !== d.data) d.data = yeni
      }
    })

    // Güvenlik ağı: görselde anahtar biçimi hiçbir şekilde kalmamalı
    const govde = (await page.textContent('body')) ?? ''
    expect(govde).not.toMatch(/nvapi-[A-Za-z0-9_-]{10,}/)
    expect(govde).not.toMatch(/sk-ant-[A-Za-z0-9_-]{10,}/)
    expect(govde, 'Maskelenmiş anahtarın son karakterleri görselde kalmamalı').not.toMatch(
      /\*{4,}[A-Za-z0-9]{2,}/,
    )
    expect(govde, 'Parmak izi görselde kalmamalı').not.toMatch(/parmak izi\s+[a-f0-9]{6,}/i)

    await page.screenshot({ path: `${KLASOR}/ayarlar.png`, fullPage: true })
  })

  test('istatistikler', async ({ page }) => {
    await girisYap(page, 'mudur')
    await page.goto('/istatistikler')
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/istatistikler.png`, fullPage: true })
  })

  test('yedekleme', async ({ page }) => {
    await girisYap(page, 'admin')
    await page.goto('/yedekleme')
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/yedekleme.png`, fullPage: true })
  })

  test('eğitim modülleri', async ({ page }) => {
    await girisYap(page, 'enolog')
    await page.goto('/egitim')
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/egitim.png`, fullPage: true })
  })

  test('eğitim modül içeriği', async ({ page }) => {
    await girisYap(page, 'enolog')
    await page.goto('/egitim')
    // İlk modül kartını aç
    await page.locator('button.kart').first().click()
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/egitim-modul.png`, fullPage: true })
  })

  test('ingilizce arayüz', async ({ page }) => {
    await girisYap(page, 'admin')
    await page.getByLabel('Dil').selectOption('en')
    await expect(
      page.getByRole('navigation').getByRole('link', { name: 'Dashboard', exact: true }),
    ).toBeVisible()
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/ingilizce.png`, fullPage: true })
    // Sonraki görseller Türkçe olsun
    await page.getByLabel('Language').selectOption('tr')
  })

  test('giriş ekranı (aydınlık tema)', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('button', { name: 'Giriş yap' })).toBeVisible()
    await sayfaHazir(page)
    await page.screenshot({ path: `${KLASOR}/giris.png`, fullPage: true })
  })
})
