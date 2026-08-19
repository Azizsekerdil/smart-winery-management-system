import { defineConfig, devices } from '@playwright/test'

/**
 * Uçtan uca test yapılandırması.
 *
 * Testler ÇALIŞAN bir sisteme karşı koşar (backend + frontend). Servisler
 * ayakta değilse `webServer` bölümü frontend'i kendisi başlatır; backend'in
 * ayrı başlatılmış olması gerekir (`scripts\baslat.ps1 -SadeceBackend`).
 */

const TABAN = process.env.E2E_TABAN ?? 'http://localhost:5173'

export default defineConfig({
  testDir: './e2e',
  // Çıktılar `e2e/` DIŞINDA tutulur: Vite bu klasörü izlemediği için koşu
  // sırasında yazılan izleme dosyaları HMR döngüsü tetiklemez.
  outputDir: './.playwright/sonuclar',
  // Testler aynı veritabanını paylaşır; yazma çakışmasını önlemek için sıralı.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },

  reporter: process.env.CI
    ? [['list'], ['html', { outputFolder: './.playwright/rapor', open: 'never' }]]
    : [['list']],

  use: {
    baseURL: TABAN,
    locale: 'tr-TR',
    timezoneId: 'Europe/Istanbul',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
    actionTimeout: 15_000,
  },

  projects: [
    {
      // Doğrulama testleri. Belge görselleri buraya DAHIL DEĞILDIR: görsel
      // üretimi bir test değil, bir çıktı adımıdır ve ayrı çalıştırılır.
      name: 'chromium',
      testIgnore: '**/90-gorseller.spec.ts',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      // `npm run gorseller` — README'deki ekran görüntülerini üretir.
      name: 'gorseller',
      testMatch: '**/90-gorseller.spec.ts',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
  ],

  webServer: process.env.E2E_SUNUCU_BASLATMA
    ? undefined
    : {
        command: 'npm run dev',
        url: TABAN,
        reuseExistingServer: true,
        timeout: 120_000,
      },
})
