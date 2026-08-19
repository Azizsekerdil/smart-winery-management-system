import { expect, test } from '@playwright/test'
import { girisYap, konsolHatalariniIzle, sayfaHazir } from './yardimcilar'

/**
 * Her ekranın yönetici rolüyle açıldığını, doğru H1 başlığını gösterdiğini ve
 * konsola hata düşürmediğini doğrular. Bu, sürüm öncesi en hızlı duman testidir.
 */

const SAYFALAR: { etiket: string; baslik: string | RegExp }[] = [
  { etiket: 'Kontrol Paneli', baslik: 'Kontrol Paneli' },
  { etiket: 'Bağ ve Üzüm Kabulü', baslik: 'Bağ ve Üzüm Kabulü' },
  { etiket: 'Partiler', baslik: 'Partiler' },
  { etiket: 'Tanklar', baslik: 'Tanklar' },
  { etiket: 'Fermantasyon', baslik: 'Fermantasyon' },
  { etiket: 'Laboratuvar', baslik: 'Laboratuvar' },
  { etiket: 'Reçete ve Kupaj', baslik: 'Reçete ve Kupaj' },
  { etiket: 'Fıçı ve Mahzen', baslik: 'Fıçı ve Mahzen' },
  { etiket: 'Şişeleme', baslik: 'Şişeleme ve Paketleme' },
  { etiket: 'Stok ve Sevkiyat', baslik: 'Stok ve Sevkiyat' },
  { etiket: 'Bakım ve Temizlik', baslik: 'Bakım ve Temizlik' },
  { etiket: 'Raporlar', baslik: 'Raporlar' },
  { etiket: 'İstatistikler', baslik: 'İstatistikler' },
  { etiket: 'Yapay Zekâ Merkezi', baslik: 'Yapay Zekâ Çalışma Merkezi' },
  { etiket: 'AI Terminali', baslik: /AI Terminali/ },
  { etiket: 'Denetim Günlüğü', baslik: 'Denetim Günlüğü' },
  { etiket: 'Kullanıcılar', baslik: 'Kullanıcılar ve Roller' },
  { etiket: 'Yedekleme', baslik: 'Yedekleme' },
  { etiket: 'Ayarlar', baslik: 'Ayarlar' },
]

test.describe('Gezinme', () => {
  test('yönetici tüm ekranları hatasız açar', async ({ page }) => {
    const hatalar = konsolHatalariniIzle(page)
    await girisYap(page, 'admin')

    for (const sayfa of SAYFALAR) {
      await test.step(sayfa.etiket, async () => {
        await page
          .getByRole('navigation')
          .getByRole('link', { name: sayfa.etiket, exact: true })
          .click()
        await expect(page.getByRole('heading', { level: 1, name: sayfa.baslik })).toBeVisible()
        // Boş durum bileşeni "yetkiniz yok" gösteriyorsa yönlendirme yanlıştır
        await expect(page.getByText('Bu sayfayı görüntüleme yetkiniz yok.')).toHaveCount(0)
      })
    }

    expect(hatalar, `Konsol hataları: ${hatalar.join(' | ')}`).toHaveLength(0)
  })

  test('bilinmeyen adres kabuk içinde 404 durumu gösterir', async ({ page }) => {
    await girisYap(page, 'admin')
    await page.goto('/boyle-bir-sayfa-yok')

    await expect(page.getByText('Sayfa bulunamadı.')).toBeVisible()
    // Kullanıcı çıkmaza düşmemeli: menü hâlâ erişilebilir olmalı
    await expect(page.getByRole('navigation')).toBeVisible()
  })

  test('pano temel göstergeleri ve grafikleri çizer', async ({ page }) => {
    await girisYap(page, 'admin')
    await sayfaHazir(page)

    // KPI kartları (etiket birden çok yerde geçebilir; ilki yeterli)
    await expect(page.getByText('Aktif parti').first()).toBeVisible()
    // ECharts canvas'ları
    expect(await page.locator('canvas').count()).toBeGreaterThan(0)
  })

  test('tema değiştirilebilir ve yenilemede korunur', async ({ page }) => {
    await girisYap(page, 'admin')

    const kok = page.locator('html')
    const dugme = page.getByRole('button', { name: 'Temayı değiştir' })
    const koyuMu = async () => (await kok.getAttribute('class'))?.includes('dark') ?? false

    const onceki = await koyuMu()
    await dugme.click()
    await expect.poll(koyuMu, { timeout: 5_000 }).toBe(!onceki)

    // Tercih localStorage'da saklanır (zustand persist)
    await page.reload()
    await expect(page.getByRole('heading', { level: 1, name: 'Kontrol Paneli' })).toBeVisible()
    await expect.poll(koyuMu, { timeout: 5_000 }).toBe(!onceki)
  })

  test('dil İngilizceye çevrilebilir', async ({ page }) => {
    await girisYap(page, 'admin')

    // Seçicinin kendisi de çevrildiği için etiketle değil konumla bulunur:
    // İngilizceye geçtikten sonra `aria-label` "Language" olur.
    const dilSecici = page.locator('header select')

    await dilSecici.selectOption('en')
    await expect(
      page.getByRole('navigation').getByRole('link', { name: 'Dashboard', exact: true }),
    ).toBeVisible()

    // Menü grup başlıkları da çevrilmeli (yalnızca bağlantı adları değil)
    await expect(page.getByRole('navigation').getByText('Production')).toBeVisible()

    // Türkçeye geri dön ki sonraki testler etkilenmesin
    await dilSecici.selectOption('tr')
    await expect(
      page.getByRole('navigation').getByRole('link', { name: 'Kontrol Paneli', exact: true }),
    ).toBeVisible()
  })
})
