# ============================================
# STAGE 1: Build - Instala dependências
# ============================================
FROM python:${PYTHON_VERSION:-3.13}-slim AS builder

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
FROM python:${PYTHON_VERSION:-3.13}-slim

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
RUN mkdir -p ${APP_HOME}/{media,staticfiles,logs} \
    && chown -R appuser:appuser ${APP_HOME}

WORKDIR ${APP_HOME}

# Copia dependências instaladas do stage de build
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copia código da aplicação
COPY --chown=appuser:appuser . .

# Permissões
RUN chmod +x manage.py \
    && find . -name "*.py" -exec chmod 644 {} \; \
    && find . -type d -exec chmod 755 {} \;

# Troca para usuário não-root
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/')" || exit 1

# ============================================
# Comandos disponíveis
# ============================================

# Development: rodar servidor de desenvolvimento
# docker run -p 8000:8000 -e DJANGO_DEBUG=True gprbr-app:latest

# Production: rodar com Gunicorn + Uvicorn
# docker run -p 8000:8000 gprbr-app:latest

# ============================================
# Default: Entrypoint com migrações e servidor
# ============================================
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
