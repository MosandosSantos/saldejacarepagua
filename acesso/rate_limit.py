"""Rate limiting do login WEB (Django), espelhando o padrao da API.

A1/S8 — antes, o POST /login/ aceitava tentativas ilimitadas (brute force).
Agora, conta tentativas falhadas por IP no cache do Django e bloqueia quando
excede o limite. Controlado pela mesma env da API (`DJANGO_RATE_LIMIT`):
- default '1' (fail-safe — ativo em producao)
- '0' desativa (usado pelo `teste/conftest.py`)

A chave combina IP + e-mail: um atacante nao drena as tentativas de uma
vitima legitima martelando outro e-mail a partir do mesmo IP, e vice-versa.
"""
from django.conf import settings
from django.core.cache import cache


def _chave(ip: str, email: str) -> str:
    return f'web_login:{ip}:{(email or "").strip().lower()}'


def _ativo() -> bool:
    return getattr(settings, 'RATE_LIMIT_ATIVO', True)


def tentativas_restantes(ip: str, email: str) -> int:
    """Quantas tentativas ainda cabem antes do bloqueio."""
    if not _ativo():
        return settings.LOGIN_RATE_LIMITE
    limite = settings.LOGIN_RATE_LIMITE
    usadas = cache.get(_chave(ip, email), 0)
    return max(0, limite - usadas)


def registrar_falha(ip: str, email: str) -> None:
    """Incrementa o contador de tentativas falhadas para (ip, email)."""
    if not _ativo():
        return
    chave = _chave(ip, email)
    usadas = cache.get(chave, 0) + 1
    cache.set(chave, usadas, timeout=settings.LOGIN_RATE_JANELA)


def limpar(ip: str, email: str) -> None:
    """Zera o contador apos login bem-sucedido (a janela e so para falhas)."""
    cache.delete(_chave(ip, email))


def bloqueado(ip: str, email: str) -> bool:
    """True quando o par (ip, email) excedeu o limite de tentativas."""
    if not _ativo():
        return False
    return cache.get(_chave(ip, email), 0) >= settings.LOGIN_RATE_LIMITE
