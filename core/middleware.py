"""Middlewares de seguranca do projeto (Fase D)."""
from django.conf import settings


def montar_csp() -> str:
    """Monta a string do header Content-Security-Policy a partir do settings."""
    diretivas = getattr(settings, 'CSP_DIRETIVAS', {})
    return '; '.join(f'{chave} {valor}' for chave, valor in diretivas.items())


class SecurityHeadersMiddleware:
    """Aplica o header Content-Security-Policy em todas as respostas web.

    Usa `setdefault` para nao sobrescrever um CSP que alguma view ja tenha definido.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault('Content-Security-Policy', montar_csp())
        return response
