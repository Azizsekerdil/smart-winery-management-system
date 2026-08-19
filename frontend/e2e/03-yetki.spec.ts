import { expect, test } from '@playwright/test'
import { erisimBelirteci, girisYap } from './yardimcilar'

/**
 * Rol tabanlı erişim denetimi.
 *
 * İki katman ayrı ayrı doğrulanır:
 *  1. Menüde yalnızca yetkili ekranların bağlantısı görünür (kullanılabilirlik).
 *  2. Adres çubuğuna doğrudan yazılsa bile sayfa açılmaz (güvenlik).
 *
 * İkincisi kritiktir: menüyü gizlemek tek başına bir yetkilendirme değildir.
 */

test.describe('Rol tabanlı erişim', () => {
  test('laboratuvar teknisyeni yalnızca kendi ekranlarını görür', async ({ page }) => {
    await girisYap(page, 'lab')
    const menu = page.getByRole('navigation')

    await expect(menu.getByRole('link', { name: 'Laboratuvar', exact: true })).toBeVisible()
    await expect(menu.getByRole('link', { name: 'Fermantasyon', exact: true })).toBeVisible()

    // Yetkisi olmayan ekranlar menüde bulunmamalı
    await expect(menu.getByRole('link', { name: 'Kullanıcılar', exact: true })).toHaveCount(0)
    await expect(menu.getByRole('link', { name: 'Denetim Günlüğü', exact: true })).toHaveCount(0)
    await expect(menu.getByRole('link', { name: 'Stok ve Sevkiyat', exact: true })).toHaveCount(0)
  })

  test('yetkisiz ekrana doğrudan adresle girilemez', async ({ page }) => {
    await girisYap(page, 'lab')

    await page.goto('/kullanicilar')
    await expect(page.getByText('Bu sayfayı görüntüleme yetkiniz yok.')).toBeVisible()
    // Kullanıcı listesi hiçbir biçimde sızmamalı
    await expect(page.getByRole('heading', { name: 'Kullanıcılar ve Roller' })).toHaveCount(0)
  })

  test('satış personeli üretim ekranlarına erişemez', async ({ page }) => {
    await girisYap(page, 'satis')

    await expect(
      page.getByRole('navigation').getByRole('link', { name: 'Stok ve Sevkiyat', exact: true }),
    ).toBeVisible()

    await page.goto('/laboratuvar')
    await expect(page.getByText('Bu sayfayı görüntüleme yetkiniz yok.')).toBeVisible()
  })

  test('denetçi her şeyi okur ama yazma düğmesi görmez', async ({ page }) => {
    await girisYap(page, 'denetci')

    await page.goto('/tanklar')
    await expect(page.getByRole('heading', { level: 1, name: 'Tanklar' })).toBeVisible()

    // Salt okunur rol: kayıt oluşturma eylemi sunulmamalı
    await expect(page.getByRole('button', { name: /Yeni tank|Tank ekle/i })).toHaveCount(0)

    // Denetim günlüğüne erişimi vardır
    await page.goto('/denetim')
    await expect(page.getByRole('heading', { level: 1, name: 'Denetim Günlüğü' })).toBeVisible()
  })

  test('yönetici olmayan kullanıcı AI terminaline erişemez', async ({ page }) => {
    await girisYap(page, 'operator')

    await page.goto('/ai-terminal')
    await expect(page.getByText('Bu sayfayı görüntüleme yetkiniz yok.')).toBeVisible()
  })

  test('oturum yokken korumalı adres giriş sayfasına yönlendirir', async ({ page }) => {
    await page.goto('/tanklar')
    await expect(page.getByRole('button', { name: 'Giriş yap' })).toBeVisible()
    await expect(page).toHaveURL(/\/giris/)
  })

  test('API yetkisiz isteği 403 döner', async ({ page, request }) => {
    // Arayüzden bağımsız olarak sunucu tarafı yetkilendirmeyi doğrular.
    await girisYap(page, 'lab')
    const belirtec = await erisimBelirteci(page)

    const yanit = await request.get('http://127.0.0.1:8010/api/v1/users', {
      headers: { Authorization: `Bearer ${belirtec}` },
    })
    expect(yanit.status()).toBe(403)
  })
})
