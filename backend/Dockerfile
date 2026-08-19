# Akıllı Şaraphane Yönetim Sistemi — backend görüntüsü
# Çok aşamalı: bağımlılıklar ayrı katmanda kurulur, çalışma katmanı ince kalır.

FROM python:3.13-slim AS bagimliliklar

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /uygulama

# argon2-cffi ve cryptography için derleme araçları
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt


# --------------------------------------------------------------- çalışma katmanı
FROM python:3.13-slim AS calisma

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/uygulama/backend \
    PATH="/opt/venv/bin:$PATH" \
    TZ=Europe/Istanbul

WORKDIR /uygulama

COPY --from=bagimliliklar /opt/venv /opt/venv

# Kök olmayan kullanıcı
RUN groupadd --system saraphane \
    && useradd --system --gid saraphane --home /uygulama saraphane

COPY backend/ ./backend/
RUN mkdir -p data/uploads data/backups logs \
    && chown -R saraphane:saraphane /uygulama

USER saraphane

EXPOSE 8010

# Orkestratörün "ayakta ama yanıt vermiyor" durumunu görebilmesi için.
# `python` kullanılır: imajda curl/wget yoktur ve yalnızca bunun için paket
# eklemek saldırı yüzeyini gereksiz büyütür.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=4).status == 200 else 1)"

# Üretimde birden çok işçi kullanılıyorsa hız sınırlama Redis'e taşınmalıdır
# (bkz. ARCHITECTURE.md § Ölçeklenebilirlik).
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8010", \
     "--app-dir", "/uygulama/backend", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
