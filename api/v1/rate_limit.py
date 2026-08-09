"""Rate limiting da API (Fase D).

Limiter em memoria com janela deslizante, chaveado por IP. Suficiente para
deploy de processo unico; se a API rodar em multiplos workers/instancias,
troque o armazenamento por Redis (mesma interface `permitir/limpar`).

A limitacao e **fail-safe**: ativa por padrao (`DJANGO_RATE_LIMIT=1`), de modo
que um deploy que esqueca de configurar continua protegido. Nos testes, o
``conftest.py`` define ``DJANGO_RATE_LIMIT=0`` antes de qualquer request, entao
a suite roda sem limitacao. (Nao usamos ``settings.DEBUG`` porque o ambiente
de testes do Django forca ``DEBUG=False``.)
"""
import os
import threading
import time

from fastapi import HTTPException, Request, status

MUITAS_REQUISICOES = 'muitas requisicoes — aguarde alguns segundos e tente novamente'


def _rate_limit_ativo() -> bool:
    """Opt-in por env, lido no momento do request (os testes definem 0 no conftest)."""
    return os.getenv('DJANGO_RATE_LIMIT', '1') == '1'


def _chave_do_request(request: Request) -> str:
    """Chave de limitacao: IP real do cliente.

    Por padrao usa ``request.client.host`` (seguro contra spoofing de headers).
    Quando ``DJANGO_TRUST_PROXY=1`` (app atras de nginx/caddy que termina o TLS
    e sobrescreve o X-Forwarded-For), usa o primeiro hop do X-Forwarded-For para
    nao limitar todos os usuarios como se fossem o IP do proxy.
    """
    if os.getenv('DJANGO_TRUST_PROXY', '0') == '1':
        xff = request.headers.get('x-forwarded-for')
        if xff:
            return xff.split(',')[0].strip()
    if request.client:
        return request.client.host
    return 'desconhecido'


class RateLimiter:
    """Janela deslizante: no maximo `limite` chamadas por `janela_segundos` por chave."""

    def __init__(self, limite: int, janela_segundos: int):
        self.limite = limite
        self.janela = janela_segundos
        self._carimbos: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def permitir(self, chave: str) -> bool:
        agora = time.monotonic()
        corte = agora - self.janela
        with self._lock:
            # Guarda de memoria: se o dicionario cresceu demais (muitos IPs
            # distintos), descarta chaves cujos carimbos ja venceram.
            if len(self._carimbos) > 10_000:
                for k in [k for k, v in self._carimbos.items() if not any(t > corte for t in v)]:
                    del self._carimbos[k]
            lista = self._carimbos.setdefault(chave, [])
            lista[:] = [t for t in lista if t > corte]  # descarta janela vencida
            if len(lista) >= self.limite:
                return False
            lista.append(agora)
            return True

    def retry_after(self, chave: str) -> int:
        with self._lock:
            lista = self._carimbos.get(chave, [])
            if not lista:
                return 0
            restante = int(self.janela - (time.monotonic() - lista[0]))
            return max(1, restante)

    def limpar(self) -> None:
        with self._lock:
            self._carimbos.clear()


# Singletons por (limite, janela) — compartilhados entre rotas e requests.
_limitadores: dict[tuple[int, int], RateLimiter] = {}
_lock_singleton = threading.Lock()


def _obter(limite: int, janela: int) -> RateLimiter:
    chave = (limite, janela)
    with _lock_singleton:
        if chave not in _limitadores:
            _limitadores[chave] = RateLimiter(limite, janela)
        return _limitadores[chave]


def limpar_limitadores() -> None:
    """Zera todos os contadores (usado pelos testes entre execucoes)."""
    for limiter in _limitadores.values():
        limiter.limpar()


def limitar(limite: int, janela_segundos: int):
    """Cria uma dependency FastAPI que limita requisicoes por IP.

    Fail-safe: ativa por padrao, desativada nos testes via env (conftest).
    Responde 429 com `Retry-After` quando o limite e excedido.
    """

    def depender(request: Request):
        if not _rate_limit_ativo():
            return
        limiter = _obter(limite, janela_segundos)
        chave = _chave_do_request(request)
        if not limiter.permitir(chave):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=MUITAS_REQUISICOES,
                headers={'Retry-After': str(limiter.retry_after(chave))},
            )

    return depender
