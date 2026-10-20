"""Auditoria de rotas: views roteadas sem decorator de autenticação (Spec 005, T5).

Percorre o URLResolver do Django (só rotas reais) e sinaliza views de função
sem `__wrapped__` (marca deixada por @wraps nos decorators do acesso).
Rotas públicas por design estão na ALLOWLIST.

Uso: python scripts/audit_decorators.py  (saída vazia = OK)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django  # noqa: E402

django.setup()

from django.urls import get_resolver  # noqa: E402

# Rotas públicas por design: login/ativação, captura anônima, rastreio de
# e-mail (pixel/clique), portal do candidato (autenticação por token).
ALLOWLIST = {
    'healthz', 'login_web', 'onboarding', 'convidar', 'ativar_conta',
    'captura_lead', 'versao_educativa', 'logout_web',
    'rastreio_abertura', 'rastreio_clique',
    'candidato_dashboard', 'candidato_suplica', 'candidato_formulario',
    'candidato_definir_senha',
    'serve',  # media estática em dev (padrão do Django; produção usa ASGI/nginx)
}
# '<lambda>' — wrappers públicos em core/urls.py (premium/* → versao_educativa; raiz → redirect dashboard)


def _rotas(resolver, prefix=''):
    for p in resolver.url_patterns:
        if hasattr(p, 'url_patterns'):
            yield from _rotas(p, prefix + str(p.pattern))
        else:
            yield prefix + str(p.pattern), p.callback


def varrer():
    problemas = []
    vistos = set()
    for rota, callback in _rotas(get_resolver()):
        if callback in vistos:
            continue
        vistos.add(callback)
        nome = getattr(callback, '__name__', repr(callback))
        if nome in ALLOWLIST or nome == '<lambda>':
            continue
        if hasattr(callback, '__wrapped__'):
            continue  # decorator com @wraps (web_login_required/edicao/admin)
        if hasattr(callback, 'view_class'):
            continue  # class-based view
        problemas.append(f'{rota} -> {callback.__module__}.{nome}() sem decorator')
    return problemas


if __name__ == '__main__':
    achados = varrer()
    if achados:
        print(f'{len(achados)} rota(s) sem decorator de autenticação:')
        for a in achados:
            print(' ', a)
        sys.exit(1)
    print('OK — todas as rotas (exceto allowlist) têm decorator de autenticação.')
