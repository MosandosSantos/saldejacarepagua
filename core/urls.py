"""Rotas do projeto.

- A camada REST continua no FastAPI (api/main.py) sob /api/v1.
- Aqui ficam as rotas web que renderizam templates Django (DTL).
"""
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic import RedirectView


def healthz(request):
    """Endpoint de saude para o healthcheck do Railway (sem autenticacao)."""
    return JsonResponse({'status': 'ok', 'servico': 'cronoscrm'})

from acesso import views as acesso_views
from contatos import views as contatos_views
from core import views as core_views

urlpatterns = [
    path('premium/<str:recurso>/', core_views.versao_educativa, name='versao_educativa'),
    path('premium/whatsapp/', lambda r: core_views.versao_educativa(r, 'whatsapp'), name='premium_whatsapp'),
    path('premium/carteiras/', lambda r: core_views.versao_educativa(r, 'carteiras'), name='premium_carteiras'),
    path('premium/campanhas/', lambda r: core_views.versao_educativa(r, 'campanhas'), name='premium_campanhas'),
    path('', lambda request: redirect('dashboard:index')),
    path('healthz/', healthz, name='healthz'),
    path('login/', include('acesso.urls')),
    path('equipe/', acesso_views.equipe, name='equipe'),
    path('config/', acesso_views.config, name='config'),
    path('config/tema/', acesso_views.alternar_tema, name='alternar_tema'),
    path('convidar/<str:token>/', acesso_views.convidar, name='convidar'),
    path('dashboard/', include('dashboard.urls')),
    path('funil/', include('funil.urls')),
    path('contatos/', include('contatos.urls')),
    # Agenda foi consolidada em Tarefas — bookmarks antigos redirecionam
    path('agenda/', RedirectView.as_view(pattern_name='tarefas:lista', permanent=False), name='agenda_redirect'),
    path('emails/', include('emails.urls')),
    path('tarefas/', include('tarefas.urls')),
    path('automacoes/', include('automacoes.urls')),
    path('campanhas/', include('campanhas.urls')),
    path('discador/', include('discador.urls')),
    path('relatorios/', include('relatorios.urls')),
    path('captura/<str:token>/', contatos_views.captura_lead, name='captura_lead'),
]