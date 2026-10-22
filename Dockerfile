# ============================================
# STAGE 0: Assets - Compila Tailwind a partir dos templates do projeto
# ============================================
ARG PYTHON_VERSION=3.13
FROM node:22-alpine AS tailwind_builder

WORKDIR /app
COPY theme/static_src/package.json theme/static_src/package-lock.json ./theme/static_src/
WORKDIR /app/theme/static_src
RUN npm ci

WORKDIR /app
COPY . .
WORKDIR /app/theme/static_src
RUN npm run build

# ============================================
# STAGE 1: Build - Instala dependências
# ============================================
FROM python:${PYTHON_VERSION}-slim AS builder

# Evita warnings de buffer
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Cria diretório de trabalho
WORKDIR /build

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================
# STAGE 2: Runtime - Imagem leve de produção
# ============================================
FROM python:${PYTHON_VERSION}-slim

# Evita warnings de buffer
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Diretórios
    APP_HOME=/app \
    # Arquitetura de pasta
    PJ_VERSION=1.0.0

# Cria usuário não-root para segurança
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Instala dependências mínimas do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Cria estrutura de diretórios
RUN mkdir -p ${APP_HOME}/media ${APP_HOME}/staticfiles ${APP_HOME}/logs \
    && chown -R appuser:appuser ${APP_HOME}

WORKDIR ${APP_HOME}

# Copia dependências instaladas do stage de build
COPY --from=builder /root/.local/lib /usr/local/lib
COPY --from=builder /root/.local/bin /usr/local/bin

# Copia código da aplicação
COPY --chown=appuser:appuser . .
COPY --from=tailwind_builder --chown=appuser:appuser /app/theme/static/css /app/theme/static/css

# Permissões
RUN sed -i 's/\r$//' entrypoint.sh \
    && chmod +x manage.py entrypoint.sh \
    && /bin/bash -n entrypoint.sh \
    && DJANGO_DEBUG=1 \
       DJANGO_SECRET_KEY=static-build-placeholder-not-production \
       DATABASE_URL=postgresql://static:static@127.0.0.1:5432/static \
       python manage.py collectstatic --noinput \
    && chown -R appuser:appuser /app/staticfiles \
    && find . -name "*.py" -exec chmod 644 {} \; \
    && find . -type d -exec chmod 755 {} \;

# Troca para usuário não-root
USER appuser

# Expose port
EXPOSE 8111

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8111/healthz/')" || exit 1

# ============================================
# Comandos disponíveis
# ============================================

# Development: rodar servidor de desenvolvimento
# docker run -p 8111:8111 -e DJANGO_DEBUG=True gprbr-app:latest

# Production: uvicorn (ASGI) atrás do Nginx/Caddy do VPS
# docker run -p 8111:8111 gprbr-app:latest

# ============================================
# Default: Entrypoint com migrações e servidor
# ============================================
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "core.asgi:application", "--host", "0.0.0.0", "--port", "8111", "--workers", "2"]
