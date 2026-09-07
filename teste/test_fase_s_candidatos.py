"""Testes de regressão do fluxo de Candidatos (Súplica) a partir do funil.

Bug relatado: "em recepção, incluir candidato não está gravando". O candidato
era gravado num tenant (fallback gprbr) enquanto o kanban exibia outro tenant
(fallback Tenant.objects.first()) — o cartão sumia logo após o cadastro.
Estes testes garantem que criação e exibição usam o MESMO tenant de fallback.
"""

import pytest
from django.test import Client

from candidatos.models import Candidato


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


def _criar_candidato(c, nome='Maria Candidata'):
    return c.post('/candidato/criar/', {
        'nome': nome,
        'prefeitura': 'prefeitura-teste',
        'loja': 'Loja Teste',
        'cpf': '',
        'celular': '',
        'email': '',
    })


@pytest.mark.django_db
def test_candidato_criado_por_admin_saas_aparece_no_kanban(tenant_aurora, admin_saas):
    """Admin SaaS (sem tenant na sessão) cria candidato e ele aparece na coluna Súplica.

    Regressão: criar_candidato caía no tenant 'gprbr' (fallback antigo) enquanto o
    kanban resolvia para Tenant.objects.first() — o candidato era salvo mas nunca
    exibido no funil.
    """
    c = _cliente_web(admin_saas)
    r = _criar_candidato(c)
    assert r.status_code == 200
    dados = r.json()
    assert dados['ok'] is True

    candidato = Candidato.objects.get(nome_completo='Maria Candidata')
    # criado no MESMO tenant que o kanban exibe (fallback do admin_saas)
    assert candidato.tenant_id == tenant_aurora.id

    html = c.get('/recepcao/').content.decode()
    assert 'Maria Candidata' in html
    assert 'cand-' in html


@pytest.mark.django_db
def test_candidato_de_outro_tenant_nao_vaza_no_kanban(tenant_aurora, tenant_beta,
                                                      usuario_operacional_beta):
    """Candidato do tenant A não aparece no funil do tenant B (isolamento)."""
    Candidato.objects.create(
        tenant=tenant_aurora, nome_completo='Cand Aurora', status=Candidato.Status.EM_ANALISE,
    )
    Candidato.objects.create(
        tenant=tenant_beta, nome_completo='Cand Beta', status=Candidato.Status.EM_ANALISE,
    )

    c = _cliente_web(usuario_operacional_beta)
    html = c.get('/recepcao/').content.decode()
    assert 'Cand Beta' in html
    assert 'Cand Aurora' not in html
