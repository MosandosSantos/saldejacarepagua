"""Configuracao central do projeto Django (core)."""
from pathlib import Path

from dotenv import load_dotenv
import dj_database_url
import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'chave-dev-nao-usar-em-producao')
DEBUG = os.getenv('DJANGO_DEBUG', '1') == '1'
# S8 — restringe os hosts aceitos (anti host-header spoofing). Em produção,
# defina DJANGO_ALLOWED_HOSTS no .env com a lista separada por vírgula
# (ex.: 'app.empresa.com.br,www.empresa.com.br'). Sem a variável: no dev
# (DEBUG=1) tudo liberado; em produção (DEBUG=0) falha fechado (só localhost)
# para não abrir mão silenciosamente da proteção.
_DJANGO_ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _DJANGO_ALLOWED_HOSTS.split(',') if h.strip()]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['*'] if DEBUG else ['localhost', '127.0.0.1']

INSTALLED_APPS = [
    # Framework web (templates DTL)
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Apps de negocio
    'acesso',
    'contatos',
    'agendamentos',
    'dashboard',
    'funil',
    'emails',
    'tarefas',
    'automacoes',
    'campanhas',
    'discador',
    'acordos',
    'relatorios',
    # Tailwind (gera o CSS com classes utilitarias)
    'tailwind',
    'theme',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Fase D — headers de seguranca (CSP) em todas as respostas web
    'core.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.csrf',
                'acesso.context_processors.web_sessao',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL', 'postgresql://postgres:@localhost:5432/esferacrm'),
        conn_max_age=600,
    )
}

# ---------------------------------------------------------------------------
# Arquivos estaticos + Tailwind
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
TAILWIND_APP_NAME = 'theme'
NPM_BIN_PATH = r'C:\Program Files\nodejs\npm.cmd'

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Porta padrao do web server Django (evita conflito com o FastAPI em 8000)
DEFAULT_PORT = os.getenv('DJANGO_PORT', '8000')

# Autenticacao JWT (camada REST/FastAPI)
JWT_SECRET = os.getenv('JWT_SECRET', 'jwt-dev-secret-nao-usar-em-producao')
TOKEN_TTL_DIAS = int(os.getenv('TOKEN_TTL_DIAS', '7'))

# ---------------------------------------------------------------------------
# Fase D — Seguranca
# ---------------------------------------------------------------------------
# Chave mestre para criptografia de segredos (AES-256-GCM, ver core/segredos.py).
# Por padrao deriva do SECRET_KEY; em producao defina CRYPTO_KEY no .env.
CRYPTO_KEY = os.getenv('CRYPTO_KEY', '')

# Headers de seguranca (aplicados pelo SecurityMiddleware do Django)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True  # o JS le o token do DOM (<input name=csrfmiddlewaretoken>), nao do cookie
CSRF_COOKIE_SAMESITE = 'Lax'

# Rate limiting da API (Fase D): **fail-safe** — ativo por padrao
# (`DJANGO_RATE_LIMIT` default '1'). Para desativar (ex.: testes), defina
# `DJANGO_RATE_LIMIT=0` — o `teste/conftest.py` faz isso automaticamente.
# Leitura ocorre no momento do request (ver api/v1/rate_limit.py), entao o
# valor do .env vale em producao e o do conftest vale na suite de testes.
# Com `DJANGO_TRUST_PROXY=1`, a chave de limitacao usa o X-Forwarded-For
# (use somente atras de proxy que voce controla).

# HSTS + redirect SSL so em producao (DEBUG=0). O navegador ignora HSTS em
# localhost, mas evitamos surpresas no dev definindo os valores condicionalmente.
if not DEBUG:
    SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = os.getenv('DJANGO_SSL_REDIRECT', '0') == '1'
    # Se o Django estiver atras de um proxy (nginx/caddy) que termina o TLS:
    # SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Content-Security-Policy (aplicado pelo core/middleware.SecurityHeadersMiddleware)
# Nota: mantemos 'unsafe-inline' em script-src porque o app usa scripts inline
# nas telas (kanban, dashboard, importador). Quando migrarmos para um front-end
# com bundle (sem inline), trocamos por nonces/`'self'` estrito.
CSP_DIRETIVAS = {
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline'",
    'style-src': "'self' 'unsafe-inline' https://fonts.googleapis.com",
    'font-src': "'self' https://fonts.gstatic.com",
    'img-src': "'self' data:",
    'connect-src': "'self' https://brasilapi.com.br https://fonts.googleapis.com https://fonts.gstatic.com",
    'object-src': "'none'",
    'base-uri': "'self'",
    'frame-ancestors': "'none'",
    'form-action': "'self'",
}

# ---------------------------------------------------------------------------
# Fase E — E-mail marketing (SMTP opcional)
# ---------------------------------------------------------------------------
# Sem EMAIL_HOST configurado, o envio roda em MODO SIMULAÇÃO: os e-mails são
# registrados e rastreados (pixel de abertura) mas não saem de verdade.
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', '1') == '1'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'CRM EsferaDataSci <nao-responder@esferadatasci.com.br>')
EMAIL_CONFIGURADO = bool(EMAIL_HOST)

# ---------------------------------------------------------------------------
# Sprint 5 — Discador (Nation Dialer): integração com o softphone
# ---------------------------------------------------------------------------
# Esquema de URI usado para iniciar a chamada (padrão 'sip' — MicroSIP).
# Cada empresa pode sobrescrever em Configurações → Discador; aqui fica o
# fallback global por ambiente.
SOFTPHONE_SCHEMA = os.getenv('SOFTPHONE_SCHEMA', 'sip')
SOFTPHONE_DOMINIO = os.getenv('SOFTPHONE_DOMINIO', '')
