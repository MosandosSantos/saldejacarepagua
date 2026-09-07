"""Rotas do projeto.

- A camada REST continua no FastAPI (api/main.py) sob /api/v1.
- Aqui ficam as rotas web que renderizam templates Django (DTL).
"""
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic import RedirectView


def healthz(request):
    """Endpoint de saude para o healthcheck do Railway (sem autenticacao).
    
    Verifica:
    - Status geral
    - Conexao com banco de dados
    """
    from django.db import connection
    
    status = {'status': 'ok', 'servico': 'gprbr'}
    
    # Verifica conexao com banco
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        status['database'] = 'ok'
    except Exception as e:
        status['status'] = 'degraded'
        status['database'] = f'error: {str(e)}'
    
    http_status = 200 if status['status'] == 'ok' else 503
    return JsonResponse(status, status=http_status)

from acesso import views as acesso_views
from contatos import views as contatos_views
from core import views as core_views
from gestao import views as gestao_views

urlpatterns = [
    path('premium/<str:recurso>/', core_views.versao_educativa, name='versao_educativa'),
    path('premium/whatsapp/', lambda r: core_views.versao_educativa(r, 'whatsapp'), name='premium_whatsapp'),
    path('premium/carteiras/', lambda r: core_views.versao_educativa(r, 'carteiras'), name='premium_carteiras'),
    path('premium/campanhas/', lambda r: core_views.versao_educativa(r, 'campanhas'), name='premium_campanhas'),
    path('', lambda request: redirect('dashboard:index')),
    path('healthz/', healthz, name='healthz'),
    path('login/', include('acesso.urls')),
    path('equipe/', acesso_views.equipe, name='equipe'),
    path('equipe/novo/', acesso_views.equipe_novo, name='equipe_novo'),
    path('equipe/<str:user_id>/editar/', acesso_views.equipe_editar, name='equipe_editar'),
    path('equipe/<str:user_id>/excluir/', acesso_views.equipe_excluir, name='equipe_excluir'),
    path('config/', acesso_views.config, name='config'),
    path('config/tema/', acesso_views.alternar_tema, name='alternar_tema'),
    path('convidar/<str:token>/', acesso_views.convidar, name='convidar'),
    path('usuario/ativar/<str:token>/', acesso_views.ativar_conta, name='ativar_conta'),
    path('dashboard/', include('dashboard.urls')),
    path('recepcao/', include('recepcao.urls')),
    path('contatos/', include('contatos.urls')),
    # Agenda foi consolidada em Tarefas — bookmarks antigos redirecionam
    path('agenda/', RedirectView.as_view(pattern_name='tarefas:lista', permanent=False), name='agenda_redirect'),
    path('emails/', include('emails.urls')),
    path('tarefas/', include('tarefas.urls')),
    path('automacoes/', include('automacoes.urls')),
    path('campanhas/', include('campanhas.urls')),
    path('discador/', include('discador.urls')),
    path('relatorios/', include('relatorios.urls')),
    path('gestao/', include('gestao.urls')),  # Dashboard de inscricoes (GEOD-CEOD)
    path('candidato/', include('candidatos.urls')),
    path('comunicacao/', gestao_views.comunicacoes, name='comunicacoes'),
    path('comunicacao/zap-status/', gestao_views.zap_status, name='zap_status'),
    path('comunicacao/zap-qrcode/', gestao_views.zap_qrcode, name='zap_qrcode'),
    path('captura/<str:token>/', contatos_views.captura_lead, name='captura_lead'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
