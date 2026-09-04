# =============================================================================
# GPRBRCRM — imagem de producao (Railway)
#
# Servidor: uvicorn (ASGI) servindo Django (painel web) + FastAPI (/api/v1)
# no mesmo processo e porta (core.asgi).
# Build: instala Node.js para compilar o CSS do Tailwind e coleta os estaticos
# (servidos pelo WhiteNoise em runtime).
# =============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false

WORKDIR /app

# Node.js 20 — necessario apenas para o build do Tailwind (django-tailwind).
# Chromium + Xvfb — WhatsApp Web via PyWhatKit (modulo de Comunicacao, PRD_comunicacao):
# o pywhatkit abre o navegador padrao (BROWSER) e o pyautogui precisa de display (Xvfb).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates chromium xvfb python3-xlib fonts-liberation \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python (camada em cache: so muda quando requirements.txt muda).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codigo-fonte do projeto (ver .dockerignore).
COPY . .

# Compila o Tailwind e coleta estaticos. DJANGO_DEBUG=1 SOMENTE neste RUN: as
# env vars de segredo ainda nao existem no build; em runtime o Railway injeta as
# reais (DJANGO_SECRET_KEY/JWT_SECRET), preservando o fail-fast em producao.
RUN DJANGO_DEBUG=1 python manage.py tailwind install \
    && DJANGO_DEBUG=1 python manage.py tailwind build \
    && DJANGO_DEBUG=1 python manage.py collectstatic --noinput

ENV BROWSER="chromium --no-sandbox %s"

EXPOSE 8000

# $PORT e injetado pelo Railway; fallback 8000 para rodar fora da plataforma.
# xvfb-run da display ao pyautogui (envio de WhatsApp via PyWhatKit) no headless.
CMD ["sh", "-c", "xvfb-run -a uvicorn core.asgi:application --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
