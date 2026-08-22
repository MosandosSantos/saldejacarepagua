"""Ponto de entrada do FastAPI (uvicorn api.main:app)."""
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.router import api_router

# CSP da API: e JSON, entao o mais restritivo possivel. O CDN do jsdelivr e
# liberado em script/style/img porque o Swagger UI (/docs) serve seus assets de
# la — sem isso, a documentacao renderizaria quebrada em producao.
API_CSP = (
    "default-src 'none'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://cdn.jsdelivr.net; "
    "connect-src 'self'"
)


def create_app() -> FastAPI:
    app = FastAPI(
        title='CRMCronos.Cloud API',
        version='1.0.0',
        description='API REST do CRM da empresa (FastAPI + Django ORM).',
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.include_router(api_router)

    @app.middleware('http')
    async def headers_seguranca(request, call_next):
        """Adiciona headers de seguranca em toda resposta da API."""
        response = await call_next(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        response.headers.setdefault('Content-Security-Policy', API_CSP)
        if not settings.DEBUG:
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains',
            )
        return response

    @app.get('/', tags=['health'])
    def health():
        return {'api': 'CRMCronos.Cloud', 'version': '1.0.0', 'docs': '/docs'}

    return app


app = create_app()
