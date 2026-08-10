"""ASGI — servidor unico (uvicorn) para Django + FastAPI.

Em producao (Railway) o processo web e:
    uvicorn core.asgi:application

Roteamento por prefixo de caminho:
    /api/*, /docs, /redoc, /openapi.json  →  FastAPI (API REST /api/v1)
    demais                                →  Django (painel web DTL)

Assim o painel e a API compartilham o mesmo processo/porta/dominio, com um unico
servico no Railway. Em dev, o `runserver` continua usando o WSGI (core.wsgi) —
este modulo so e usado quando o servidor e o uvicorn.
"""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# 1) Sobe o Django primeiro — get_asgi_application() chama django.setup().
from django.core.asgi import get_asgi_application

django_asgi = get_asgi_application()

# 2) Depois importa o FastAPI, que usa o ORM do Django ja configurado.
from api.main import app as fastapi_app  # noqa: E402

_PREFIXOS_API = ('/api/', '/docs', '/redoc', '/openapi.json')


async def application(scope, receive, send):
    if scope.get('type') == 'http':
        caminho = scope.get('path', '')
        if caminho.startswith(_PREFIXOS_API):
            await fastapi_app(scope, receive, send)
            return
    await django_asgi(scope, receive, send)
