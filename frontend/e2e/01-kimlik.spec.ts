import { expect, test } from '@playwright/test'
import { DEMO_PAROLA, girisYap, konsolHatalariniIzle, oturumuUnut } from './yardimcilar'

test.describe('Kimlik doğrulama', () => {
  test('giriş sayfası Türkçe görünür', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /Akıllı Şaraphane Yönetim Sistemi/ })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Giriş yap' })).toBeVisible()
  })

  test('hatalı parola anlaşılır hata gösterir', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('textbox').first().fill('enolog')
    await page.locator('input[type="password"]').fill('YanlisParola123!')
    await page.getByRole('button', { name: 'Giriş yap' }).click()

    await expect(page.getByRole('alert')).toContainText(/hatalı/i, { timeout: 15_000 })
  })

  test('geçerli kullanıcı giriş yapıp panele ulaşır', async ({ page }) => {
    const hatalar = konsolHatalariniIzle(page)
    await girisYap(page, 'enolog')

    await expect(page.getByRole('heading', { name: 'Kontrol Paneli' })).toBeVisible()
    await expect(page.getByText('Dr. Mehmet Aksoy')).toBeVisible()
    expect(hatalar, `Konsol hataları: ${hatalar.join(' | ')}`).toHaveLength(0)
  })

  test('oturum kapatınca giriş sayfasına dönülür', async ({ page }) => {
    await girisYap(page, 'admin')
    await page.getByRole('button', { name: 'Oturumu kapat' }).click()
    await expect(page.getByRole('button', { name: 'Giriş yap' })).toBeVisible({ timeout: 15_000 })

    // Yerel belirteçler de silinmeli; yalnızca yönlendirme yeterli değildir.
    const kalan = await page.evaluate(() => ({
      erisim: localStorage.getItem('saraphane.erisim'),
      yenileme: localStorage.getItem('saraphane.yenileme'),
    }))
    expect(kalan.erisim, 'Çıkışta erişim belirteci silinmeli').toBeNull()
    expect(kalan.yenileme, 'Çıkışta yenileme belirteci silinmeli').toBeNull()

    // Yenileme belirteci sunucuda iptal edildi; önbelleği tazele.
    oturumuUnut('admin')
  })

  test('oturum yenilemeden sonra korunur', async ({ page }) => {
    await girisYap(page, 'admin')
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Kontrol Paneli' })).toBeVisible({
      timeout: 20_000,
    })
  })

  test('parola alanı maskelidir', async ({ page }) => {
    await page.goto('/')
    const parola = page.locator('input[type="password"]')
    await parola.fill(DEMO_PAROLA)
    await expect(parola).toHaveAttribute('type', 'password')
  })
})
