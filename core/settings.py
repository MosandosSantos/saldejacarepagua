"""Configuracao central do projeto Django (core)."""
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

def _env_bool(name: str, default: str = '0') -> bool:
    """Lê uma env var como booleana — aceita 1/true/yes/on (case-insensitive)."""
    return os.getenv(name, default).strip().lower() in ('1', 'true', 'yes', 'on', 't')


# --- Fail-closed: DEBUG so e True se explicitamente pedido ---------------
# S8/C1 — padrão seguro. Deploy que esquecer DJANGO_DEBUG=1 roda em modo
# production, nunca o contrario. Aceita `DEBUG` como alias do .env legado.
DEBUG = _env_bool('DJANGO_DEBUG') or _env_bool('DEBUG', '0')

# --- Secrets fail-fast em producao ---------------------------------------
# S8/C2 — fallback so em DEBUG=1; em producao a ausencia das env vars aborta
# o boot em vez de rodar com chave publica/estatica forjavel.
_DEV_SECRET = 'chave-dev-nao-usar-em-producao'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY') or os.getenv('SECRET_KEY') or _DEV_SECRET


def _secret_fraca(chave):
    """True para chaves placeholder (ex.: copiadas do .env.example)."""
    chave = (chave or '').strip().lower()
    marcadores = ('troque', 'change-me', 'change_me', 'placeholder',
                  'nao-usar', 'minha-chave', 'exemplo', 'segredo')
    return not chave or any(m in chave for m in marcadores)


if not DEBUG and (SECRET_KEY == _DEV_SECRET or _secret_fraca(SECRET_KEY)):
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY ausente ou com valor placeholder em producao (DEBUG=0). '
        'Defina uma chave aleatoria via env (ex.: python -c "import secrets; '
        'print(secrets.token_urlsafe(64))").'
    )
_DJANGO_ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _DJANGO_ALLOWED_HOSTS.split(',') if h.strip()]
if not ALLOWED_HOSTS:
    if DEBUG:
        ALLOWED_HOSTS = ['*']
    else:
        # Producao sem DJANGO_ALLOWED_HOSTS explicito: aceita os dominios gerados
        # automaticamente pelo Railway (*.up.railway.app) + localhost/testserver.
        # Para dominio proprio, defina DJANGO_ALLOWED_HOSTS
        # (ex.: 'meusite.com.br,www.meusite.com.br').
        ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver', '.up.railway.app', '.railway.app']

# Origem permitida no check de CSRF via header Origin (deploy atras de proxy
# HTTPS — Railway). Aceita coringa de subdominio (*.) no padrao.
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]
if not CSRF_TRUSTED_ORIGINS and not DEBUG:
    CSRF_TRUSTED_ORIGINS = ['https://*.up.railway.app', 'https://*.railway.app']

# --- Password validators (aplicados via validate_password nas views) -----
# A2 — politica minima de senha. Mensagens em pt-br (acesso.validators).
# Nao usa o User model nativo do Django, portanto nao sao acionados
# automaticamente — views chamam validate_password().
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'acesso.validators.AtributoSimilarValidator'},
    {'NAME': 'acesso.validators.TamanhoMinimoValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'acesso.validators.SenhaComumValidator'},
    {'NAME': 'acesso.validators.SenhaNumericaValidator'},
]

INSTALLED_APPS = [
    # Framework web (templates DTL)
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Apps de negocio
    # App de infraestrutura (templatetags `seguranca`, middleware) — declarado
    # para o {% load seguranca %} funcionar em qualquer template.
    'core',
    'acesso',
    'contatos',
    'dashboard',
    'funil',
    'emails',
    'tarefas',
    'automacoes',
    'campanhas',
    'discador',
    'relatorios',
    'gestao',  # Dashboard de inscricoes (GEOD-CEOD)
    # Tailwind (gera o CSS com classes utilitarias)
    'tailwind',
    'theme',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Fase D — headers de seguranca (CSP) em todas as respostas web
    'core.middleware.SecurityHeadersMiddleware',
    # S8/C3 — valida o usuario da sessao contra o DB a cada request autenticada
    # (revoga acesso quando usuario e deletado/demovido/mudou de tenant).
    'core.middleware.ValidarSessaoMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates', BASE_DIR / 'core' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.csrf',
                'acesso.context_processors.web_sessao',
            ],
            # S1.1 — filtro |js (JSON seguro p/ dentro de <script>) disponivel
            # em todos os templates, sem depender de app no INSTALLED_APPS.
            'builtins': ['core.templatetags.seguranca'],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('PGDATABASE', 'gprbr'),
        'USER': os.getenv('PGUSER', 'postgres'),
        'PASSWORD': os.getenv('PGPASSWORD', ''),
        'HOST': os.getenv('PGHOST', 'localhost'),
        'PORT': os.getenv('PGPORT', '5432'),
    }
}

# Deploy (Railway/Render/Heroku): o Postgres costuma ser fornecido via
# DATABASE_URL (inclui sslmode). DATABASE_URL tem PRIORIDADE sempre que
# estiver definida — isso evita que PGHOST local sobrescreva a config do
# Railway. Em dev, se DATABASE_URL não existir, usa as variáveis PG*.
_URL_BANCO = os.getenv('DATABASE_URL', '')
if _URL_BANCO:
    DATABASES['default'] = dj_database_url.parse(_URL_BANCO, conn_max_age=60)

# Fail-fast claro em producao: sem DATABASE_URL/PGHOST o app tentaria conectar
# em localhost (erro confuso de "connection refused"). Exigimos a configuracao
# do banco — no Railway: DATABASE_URL=${{Postgres.DATABASE_URL}} (ou PG*).
if not DEBUG and not _URL_BANCO and not os.getenv('PGHOST'):
    raise ImproperlyConfigured(
        'Banco de dados nao configurado. No Railway, adicione no servico web a '
        'variavel DATABASE_URL apontando para o Postgres '
        '(ex.: ${{Postgres.DATABASE_URL}}) - ou defina PGHOST/PGPORT/'
        'PGDATABASE/PGUSER/PGPASSWORD.'
    )

# ---------------------------------------------------------------------------
# Arquivos estaticos + Tailwind
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
# WhiteNoise serve os estaticos em producao (sem servidor externo/CDN).
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
TAILWIND_APP_NAME = 'theme'
# NPM do Tailwind: no Windows usa o caminho fixo do npm.cmd; no Linux
# (Docker/Railway) usa o `npm` do PATH do container (override via NPM_BIN_PATH).
if os.name == 'nt':
    NPM_BIN_PATH = os.getenv('NPM_BIN_PATH', r'C:\Program Files\nodejs\npm.cmd')
else:
    NPM_BIN_PATH = os.getenv('NPM_BIN_PATH', 'npm')

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Porta padrao do web server Django (evita conflito com o FastAPI em 8000)
DEFAULT_PORT = os.getenv('DJANGO_PORT', '8000')

# Autenticacao JWT (camada REST/FastAPI)
JWT_SECRET = os.getenv('JWT_SECRET', 'jwt-dev-secret-nao-usar-em-producao')
if not DEBUG and JWT_SECRET == 'jwt-dev-secret-nao-usar-em-producao':
    raise ImproperlyConfigured('JWT_SECRET e obrigatoria em producao (DEBUG=0).')
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
# A3 — cookies só via HTTPS em produção (evita sequestro de sessão por MITM)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Rate limiting da API (Fase D): **fail-safe** — ativo por padrao
# (`DJANGO_RATE_LIMIT` default '1'). Para desativar (ex.: testes), defina
# `DJANGO_RATE_LIMIT=0` — o `teste/conftest.py` faz isso automaticamente.
# Controla tambem o rate limit do login WEB (acesso/views.py::login_web),
# mantendo um unico botao para a suite de testes.
RATE_LIMIT_ATIVO = os.getenv('DJANGO_RATE_LIMIT', '1') != '0'
LOGIN_RATE_LIMITE = int(os.getenv('LOGIN_RATE_LIMITE', '10'))   # tentativas
LOGIN_RATE_JANELA = int(os.getenv('LOGIN_RATE_JANELA', '300'))  # segundos

# Cache (usado pelo rate limit do login web e invalidacao de sessao).
# Padrao: LocMem (dev). Se REDIS_URL estiver definida (producao com varios
# workers), usa o RedisCache embutido do Django — compartilhado entre
# processos, mantendo o rate limit eficaz.
_REDIS_URL = os.getenv('REDIS_URL') or os.getenv('REDIS_TLS_URL')
if _REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _REDIS_URL,
            'KEY_PREFIX': 'gprbr',
            'TIMEOUT': 300,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'gprbr-default',
        }
    }

# Deploy atras de proxy que termina o TLS (Railway/nginx/caddy): o Django
# precisa saber que a requisicao original e HTTPS (request.is_secure()). Fica
# FORA do bloco `if not DEBUG` de proposito: no Django 5.2 o CSRF compara o
# header Origin com scheme://host (is_secure), entao sem isto o login quebra
# atras do proxy mesmo com DEBUG=1 por engano.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS + redirect SSL so em producao (DEBUG=0). O navegador ignora HSTS em
# localhost, mas evitamos surpresas no dev definindo os valores condicionalmente.
if not DEBUG:
    SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Redirect http -> https fica OFF por padrao: o edge do Railway ja termina o
    # TLS e o HSTS acima cobre o restante; o healthcheck interno nem sempre traz
    # X-Forwarded-Proto, entao um 301 poderia derrubar o deploy. Para exigir o
    # redirect, defina DJANGO_SSL_REDIRECT=1.
    SECURE_SSL_REDIRECT = os.getenv('DJANGO_SSL_REDIRECT', '0') == '1'

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
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'GPRBRCRM <nao-responder@esferadatasci.com.br>')
EMAIL_CONFIGURADO = bool(EMAIL_HOST)

# ---------------------------------------------------------------------------
# Sprint 5 — Discador (Nation Dialer): integração com o softphone
# ---------------------------------------------------------------------------
# Esquema de URI usado para iniciar a chamada (padrão 'sip' — MicroSIP).
# Cada empresa pode sobrescrever em Configurações → Discador; aqui fica o
# fallback global por ambiente.
SOFTPHONE_SCHEMA = os.getenv('SOFTPHONE_SCHEMA', 'sip')
SOFTPHONE_DOMINIO = os.getenv('SOFTPHONE_DOMINIO', '')

# ---------------------------------------------------------------------------
# Logging — estrutura padrao para observabilidade
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'acesso': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'core.gprb': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'dashboard': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
