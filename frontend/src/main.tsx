import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

const sorguIstemcisi = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (deneme, hata) => {
        // Yetki/doğrulama hatalarında tekrar denemek anlamsızdır.
        const durum = (hata as { response?: { status?: number } })?.response?.status
        if (durum && [400, 401, 403, 404, 409, 412, 422].includes(durum)) return false
        return deneme < 2
      },
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={sorguIstemcisi}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
