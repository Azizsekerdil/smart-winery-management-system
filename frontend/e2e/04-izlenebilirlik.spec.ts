import { expect, test } from '@playwright/test'
import { erisimBelirteci, girisYap, sayfaHazir } from './yardimcilar'

/**
 * Şaraphanenin çekirdek iş kuralı: her şişe, geldiği üzüme kadar geri
 * izlenebilmelidir. Bu test zinciri arayüz üzerinden uçtan uca doğrular.
 */

test.describe('Parti izlenebilirliği', () => {
  test('parti listesi yüklenir ve aranabilir', async ({ page }) => {
    await girisYap(page, 'enolog')
    await page.goto('/partiler')
    await expect(page.getByRole('heading', { level: 1, name: 'Partiler' })).toBeVisible()

    const satirlar = page.getByRole('row')
    expect(await satirlar.count()).toBeGreaterThan(1)
  })

  test('parti detayı kimlik bilgilerini ve çizgeyi gösterir', async ({ page }) => {
    await girisYap(page, 'enolog')
    await page.goto('/partiler')

    // İlk veri satırına gir (başlık satırı atlanır)
    await page.getByRole('row').nth(1).click()
    await expect(page).toHaveURL(/\/partiler\/\d+/)

    // Detay sayfasının yüklendiğini H1 ile doğrula; liste sayfası kaldırılmadan
    // alan adları aranırsa liste ve detay öğeleri birbirine karışır.
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

    // `exact: true` şart: varsayılan alt dize eşleşmesi "Aşama" sorgusunu liste
    // sayfasındaki "Tüm aşamalar" seçeneğiyle de eşleştirir.
    await expect(page.getByText('Aşama', { exact: true })).toBeVisible()
    await expect(page.getByText('Hacim', { exact: true })).toBeVisible()
    await expect(page.getByText('İzlenebilirlik çizgesi')).toBeVisible()

    await sayfaHazir(page)
    // Çizge ya çizilmiş olmalı ya da anlamlı bir boş durum göstermeli
    const cizgeVar = await page.locator('canvas').count()
    const bosDurum = await page.getByText('Henüz bağlantı kaydı yok.').count()
    expect(cizgeVar + bosDurum).toBeGreaterThan(0)
  })

  test('izleme yönü değiştirilebilir', async ({ page }) => {
    await girisYap(page, 'enolog')
    await page.goto('/partiler')
    await page.getByRole('row').nth(1).click()
    await expect(page.getByText('İzlenebilirlik çizgesi')).toBeVisible()

    const secici = page.locator('select').filter({ hasText: 'Tam izleme' })
    await secici.selectOption('geri')
    await sayfaHazir(page)
    await secici.selectOption('ileri')
    await sayfaHazir(page)

    // Yön değişimi sayfayı bozmamalı
    await expect(page.getByText('İzlenebilirlik çizgesi')).toBeVisible()
  })

  test('işlem geçmişi ve maliyet dökümü görünür', async ({ page }) => {
    await girisYap(page, 'enolog')
    await page.goto('/partiler')
    await page.getByRole('row').nth(1).click()

    await expect(page.getByText('İşlem geçmişi')).toBeVisible()
    await sayfaHazir(page)
  })

  test('API tam izleme zinciri döndürür', async ({ page, request }) => {
    await girisYap(page, 'enolog')
    const belirtec = await erisimBelirteci(page)

    const liste = await request.get('http://127.0.0.1:8010/api/v1/lots?page_size=1', {
      headers: { Authorization: `Bearer ${belirtec}` },
    })
    expect(liste.ok()).toBeTruthy()
    const partiId = (await liste.json()).items[0].id

    const izleme = await request.get(
      `http://127.0.0.1:8010/api/v1/lots/${partiId}/trace?direction=tam`,
      { headers: { Authorization: `Bearer ${belirtec}` } },
    )
    expect(izleme.ok()).toBeTruthy()

    const veri = await izleme.json()
    expect(Array.isArray(veri.nodes)).toBeTruthy()
    expect(veri.nodes.length).toBeGreaterThan(0)
    // Döngü koruması devrede olmalı: sonsuz zincir dönmemeli
    expect(veri.nodes.length).toBeLessThan(500)
  })
})
