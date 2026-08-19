# Akıllı Şaraphane Yönetim Sistemi — arayüz görüntüsü
# Vite ile derlenir, nginx ile statik olarak sunulur; /api backend'e vekillenir.

FROM node:22-alpine AS derleme

WORKDIR /uygulama

COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# ------------------------------------------------------------------ sunum
FROM nginx:1.27-alpine AS sunum

COPY --from=derleme /uygulama/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
# Guvenlik basliklari parcacigi. nginx'te `add_header` miras alinmadigi icin
# basliklar tek dosyada tutulur ve baslik ekleyen her `location` bloğunda
# yeniden `include` edilir; aksi halde o konum sessizce korumasiz kalir.
COPY frontend/nginx-snippets/ /etc/nginx/snippets/

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
