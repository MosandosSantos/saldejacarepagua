"""Rotas do projeto.

- A camada REST continua no FastAPI (api/main.py) sob /api/v1.
- Aqui ficam as rotas web que renderizam templates Django (DTL).
"""
from django.shortcuts import redirect
from django.urls import include, path

from acesso import views as acesso_views
from contatos import views as contatos_views

urlpatterns = [
    path('', lambda request: redirect('dashboard:index')),
    path('login/', include('acesso.urls')),
    path('equipe/', acesso_views.equipe, name='equipe'),
    path('config/', acesso_views.config, name='config'),
    path('config/tema/', acesso_views.alternar_tema, name='alternar_tema'),
    path('convidar/<str:token>/', acesso_views.convidar, name='convidar'),
    path('dashboard/', include('dashboard.urls')),
    path('funil/', include('funil.urls')),
    path('contatos/', include('contatos.urls')),
    path('agenda/', include('agendamentos.urls')),
    path('emails/', include('emails.urls')),
    path('tarefas/', include('tarefas.urls')),
    path('automacoes/', include('automacoes.urls')),
    path('campanhas/', include('campanhas.urls')),
    path('discador/', include('discador.urls')),
    path('acordos/', include('acordos.urls')),
    path('relatorios/', include('relatorios.urls')),
    path('captura/<str:token>/', contatos_views.captura_lead, name='captura_lead'),
]