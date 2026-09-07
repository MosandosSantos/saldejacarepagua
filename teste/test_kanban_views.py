"""Testes TDD para views de kanban e board."""
import pytest
from datetime import timedelta
from django.utils import timezone
from django.test import Client
from contatos.models import Contato, Negocio, criar_negocio


def _cliente_web(usuario):
    """Cria cliente Django com sessao autenticada."""
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = ''
    s.save()
    return c


@pytest.mark.django_db
def test_kanban_view_requer_login():
    """RED: kanban view deve redirecionar para login se nao autenticado."""
    c = Client()
    response = c.get('/recepcao/')
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_kanban_view_renderiza_para_logado(usuario_operacional):
    """GREEN: kanban view deve renderizar para usuario logado."""
    c = _cliente_web(usuario_operacional)
    response = c.get('/recepcao/')
    assert response.status_code == 200


@pytest.mark.django_db
def test_kanban_view_mostra_negocios(usuario_operacional, tenant_aurora):
    """GREEN: kanban view deve mostrar negocios do tenant."""
    c = _cliente_web(usuario_operacional)
    
    # Cria negocios para ter dados
    contato = Contato.objects.create(nome='Teste Kanban', tenant=tenant_aurora)
    criar_negocio(contato, stage='suplica', tenant_id=tenant_aurora.id)
    
    response = c.get('/recepcao/')
    assert response.status_code == 200
    assert b'Teste Kanban' in response.content


@pytest.mark.django_db
def test_mover_negocio_atualiza_stage(usuario_operacional, tenant_aurora):
    """GREEN: mover negocio deve atualizar o stage."""
    c = _cliente_web(usuario_operacional)
    
    contato = Contato.objects.create(nome='Mover Teste', tenant=tenant_aurora)
    n = criar_negocio(contato, stage='suplica', tenant_id=tenant_aurora.id)
    
    # Move para proximo stage (URL: /recepcao/<pk>/mover/)
    # Stage valido para clinica-aurora: suplica -> prefeito
    response = c.post(f'/recepcao/{n.id}/mover/', {
        'stage': 'prefeito'
    })
    
    # Verifica se moveu (pode ser 200 ou redirect)
    assert response.status_code in (200, 302)
    
    # Recarrega do banco
    n.refresh_from_db()
    assert n.stage == 'prefeito'


@pytest.mark.django_db
def test_mover_negocio_negado_para_viewer(usuario_viewer, tenant_aurora):
    """RED: viewer nao pode mover negocios."""
    c = _cliente_web(usuario_viewer)
    
    contato = Contato.objects.create(nome='Viewer Teste', tenant=tenant_aurora)
    n = criar_negocio(contato, stage='suplica', tenant_id=tenant_aurora.id)
    
    response = c.post(f'/recepcao/{n.id}/mover/', {
        'stage': 'prefeito'
    })
    
    # Viewer nao pode mover
    assert response.status_code in (403, 302)


@pytest.mark.django_db
def test_excluir_negocio(usuario_operacional, tenant_aurora):
    """GREEN: excluir negocio deve remover do banco."""
    c = _cliente_web(usuario_operacional)
    
    contato = Contato.objects.create(nome='Excluir Teste', tenant=tenant_aurora)
    n = criar_negocio(contato, stage='suplica', tenant_id=tenant_aurora.id)
    negocio_id = n.id
    
    # Exclui (URL: /recepcao/<pk>/excluir/)
    response = c.post(f'/recepcao/{negocio_id}/excluir/')
    
    # Verifica se excluiu
    assert response.status_code in (200, 302)
    assert not Negocio.objects.filter(id=negocio_id).exists()
