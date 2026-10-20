"""Testes da Fase D — qualidade e seguranca (cripto de segredos, headers, rate limit)."""
import pytest
from django.test import Client, override_settings

from api.v1.rate_limit import _chave_do_request, limpar_limitadores, RateLimiter
from core import segredos


@pytest.fixture(autouse=True)
def _zera_limitadores():
    """Nunca deixar contadores de rate limit vazarem entre testes."""
    limpar_limitadores()
    yield
    limpar_limitadores()


# ---------------------------------------------------------------------------
# Criptografia de segredos (AES-256-GCM)
# ---------------------------------------------------------------------------

class TestCriptografia:
    def test_roundtrip(self):
        assert segredos.desencriptar(segredos.encriptar('token-meta-secreto')) == 'token-meta-secreto'

    def test_roundtrip_texto_unicode(self):
        texto = 'clínica ção & símbolos ¥'
        assert segredos.desencriptar(segredos.encriptar(texto)) == texto

    def test_mesmo_texto_gera_tokens_diferentes(self):
        """Nonce unico por operacao: nunca cifrar igual duas vezes."""
        assert segredos.encriptar('abc') != segredos.encriptar('abc')

    def test_token_adulterado_falha(self):
        token = segredos.encriptar('segredo')
        adulterado = token[:-4] + ('AAAA' if token[-4:] != 'AAAA' else 'BBBB')
        with pytest.raises(ValueError):
            segredos.desencriptar(adulterado)

    def test_chave_diferente_falha(self):
        token = segredos.encriptar('segredo')
        with override_settings(CRYPTO_KEY='outra-chave-mestra'), pytest.raises(ValueError):
            segredos.desencriptar(token)

    def test_formato_invalido_falha(self):
        for lixo in ('', 'abc', 'v2:xyz', 'v1:###'):
            with pytest.raises(ValueError):
                segredos.desencriptar(lixo)

    def test_encriptar_rejeita_nao_string(self):
        with pytest.raises(TypeError):
            segredos.encriptar(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Headers de seguranca na web (Django)
# ---------------------------------------------------------------------------

class TestHeadersWeb:
    # A pagina publica de login consulta o banco (agenda publica e contagem
    # de Vales) — o teste precisa de acesso ao banco para exercita-la.
    @pytest.mark.django_db
    def test_pagina_publica_tem_headers(self):
        r = Client().get('/login/')
        assert r.status_code == 200
        assert r.headers['X-Content-Type-Options'] == 'nosniff'
        assert r.headers['X-Frame-Options'] == 'DENY'
        assert r.headers['Referrer-Policy'] == 'same-origin'
        csp = r.headers['Content-Security-Policy']
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "base-uri 'self'" in csp
        # recursos que o app usa de verdade devem estar liberados
        assert 'https://fonts.googleapis.com' in csp
        assert 'https://fonts.gstatic.com' in csp
        assert 'https://brasilapi.com.br' in csp

    @pytest.mark.django_db
    def test_hsts_ausente_em_dev(self):
        """Em DEBUG=1 (dev/testes) o HSTS nao e enviado — nao quebra o localhost."""
        r = Client().get('/login/', secure=True)
        assert 'Strict-Transport-Security' not in r.headers

    @override_settings(
        DEBUG=False,
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
    )
    @pytest.mark.django_db
    def test_hsts_presente_em_producao(self):
        r = Client().get('/login/', secure=True)
        assert 'Strict-Transport-Security' in r.headers
        assert 'max-age=31536000' in r.headers['Strict-Transport-Security']


# ---------------------------------------------------------------------------
# Headers de seguranca na API (FastAPI)
# ---------------------------------------------------------------------------

class TestHeadersApi:
    def test_resposta_api_tem_headers(self, client):
        r = client.get('/api/v1/auth/me')  # sem token -> 401, mas headers sempre presentes
        assert r.status_code == 401
        assert r.headers.get('x-content-type-options') == 'nosniff'
        assert r.headers.get('x-frame-options') == 'DENY'
        assert r.headers.get('referrer-policy') == 'same-origin'
        csp = r.headers.get('content-security-policy', '')
        assert "default-src 'none'" in csp
        # Swagger UI (/docs) serve os assets do CDN — sem isso a doc quebra em prod
        assert 'cdn.jsdelivr.net' in csp


# ---------------------------------------------------------------------------
# Rate limiting (API)
# ---------------------------------------------------------------------------

class TestRateLimit:
    def test_limiter_janela_deslizante(self):
        limiter = RateLimiter(limite=3, janela_segundos=60)
        assert limiter.permitir('ip-x')
        assert limiter.permitir('ip-x')
        assert limiter.permitir('ip-x')
        assert not limiter.permitir('ip-x')  # 4a chamada bloqueada
        # outra chave (outro IP) nao e afetada
        assert limiter.permitir('ip-y')
        assert limiter.retry_after('ip-x') >= 1

    def test_limiter_limpar(self):
        limiter = RateLimiter(limite=1, janela_segundos=60)
        limiter.permitir('ip-x')
        limiter.limpar()
        assert limiter.permitir('ip-x')

    @pytest.mark.django_db(transaction=True)
    def test_login_429_apos_limite(self, client, monkeypatch):
        """Forca bruta no login: 10 tentativas/min; a 11a responde 429."""
        monkeypatch.setenv('DJANGO_RATE_LIMIT', '1')
        for _ in range(10):
            r = client.post('/api/v1/auth/login', json={'email': 'x@y.com', 'senha': 'errada'})
            assert r.status_code == 401
        r = client.post('/api/v1/auth/login', json={'email': 'x@y.com', 'senha': 'errada'})
        assert r.status_code == 429
        assert 'Retry-After' in r.headers

    @pytest.mark.django_db(transaction=True)
    def test_login_funciona_dentro_do_limite(self, client, admin_company, monkeypatch):
        """Limite nao bloqueia usuario legitimo dentro da janela."""
        monkeypatch.setenv('DJANGO_RATE_LIMIT', '1')
        r = client.post(
            '/api/v1/auth/login',
            json={'email': admin_company.email, 'senha': 'senha123'},
        )
        assert r.status_code == 200

    @pytest.mark.django_db(transaction=True)
    def test_limite_desativado_nos_testes(self, client):
        """O conftest define DJANGO_RATE_LIMIT=0: a suite roda sem rate limit."""
        for _ in range(15):  # acima do limite de login (10)
            r = client.post('/api/v1/auth/login', json={'email': 'x@y.com', 'senha': 'errada'})
            assert r.status_code == 401

    @pytest.mark.django_db(transaction=True)
    def test_rate_limit_ligado_por_padrao(self, client, monkeypatch):
        """Fail-safe: sem a env definida, o rate limit esta ATIVO."""
        monkeypatch.delenv('DJANGO_RATE_LIMIT')
        for _ in range(11):
            client.post('/api/v1/auth/login', json={'email': 'x@y.com', 'senha': 'errada'})
        r = client.post('/api/v1/auth/login', json={'email': 'x@y.com', 'senha': 'errada'})
        assert r.status_code == 429

    def test_chave_por_ip_ignora_xff_por_padrao(self, monkeypatch):
        """Sem DJANGO_TRUST_PROXY, a chave e o client.host (anti-spoofing)."""
        from starlette.requests import Request


        monkeypatch.delenv('DJANGO_TRUST_PROXY', raising=False)
        request = Request({
            'type': 'http',
            'client': ('203.0.113.9', 1234),
            'headers': [(b'x-forwarded-for', b'198.51.100.7, 10.0.0.1')],
        })
        assert _chave_do_request(request) == '203.0.113.9'

    def test_chave_usa_xff_com_proxy_confiavel(self, monkeypatch):
        """Com DJANGO_TRUST_PROXY=1, usa o primeiro hop do X-Forwarded-For."""
        from starlette.requests import Request


        monkeypatch.setenv('DJANGO_TRUST_PROXY', '1')
        request = Request({
            'type': 'http',
            'client': ('127.0.0.1', 1234),  # IP do proxy
            'headers': [(b'x-forwarded-for', b'198.51.100.7, 10.0.0.1')],
        })
        assert _chave_do_request(request) == '198.51.100.7'
