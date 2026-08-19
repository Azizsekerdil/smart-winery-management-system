import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const API_HEDEF = process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8010'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // `import.meta.dirname` kullanılır: Vite'ın yeni yerel config yükleyicisi
    // `__dirname` desteklemez.
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    port: 5173,
    strictPort: false,
    watch: {
      // Playwright, koşu sırasında izleme/ekran görüntüsü dosyalarını proje
      // içine yazar. İzlemeye dahil olurlarsa Vite her dosyada HMR yeniden
      // yüklemesi tetikler; bu, testleri bozar ve sunucuyu çökertir.
      ignored: ['**/.playwright/**', '**/e2e/.sonuclar/**', '**/test-results/**'],
    },
    // Geliştirmede API aynı köken üzerinden sunulur; böylece CORS ve çerez
    // sorunları yaşanmaz ve üretimdeki ters vekil düzeniyle aynı davranış olur.
    proxy: {
      '/api': { target: API_HEDEF, changeOrigin: true },
      '/health': { target: API_HEDEF, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        // Grafik kütüphanesi büyük ve her sayfada gerekmiyor; ayrı parçaya alınır.
        manualChunks(id) {
          if (id.includes('node_modules/echarts')) return 'grafik'
          if (id.includes('node_modules/react')) return 'cekirdek'
          return undefined
        },
      },
    },
  },
})
