"""Testes da Fase K — §7.6 do PRD: timestamps padronizados (created_at/updated_at) em todos os modelos.

Valida que cada modelo do projeto tem `created_at` (auto_now_add) e `updated_at`
(auto_now), que os renames (criado_em/criada_em/atualizada_em → created_at/updated_at)
preservaram os dados e que as ordenações e telas continuam funcionando.
"""

import pytest
from django.apps import apps
from django.test import Client
from django.utils import timezone

from contatos.models import Contato, Movimentacao, Nota, criar_negocio


def _sessao_web(client, usuario):
    """Simula o login por sessão usado nas views web."""
    s = client.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {
        'nome': usuario.nome, 'email': usuario.email,
        'role': usuario.role, 'tenant_id': usuario.tenant_id,
    }
    s['nicho'] = 'saude'
    s.save()


# ---------------------------------------------------------------------------
# §7.6 — conformidade: todo modelo tem created_at (auto_now_add) e updated_at (auto_now)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_todos_os_modelos_tem_created_at_e_updated_at():
    apps_do_projeto = {
        'acesso', 'automacoes', 'contatos', 'emails', 'funil', 'tarefas',
    }
    modelos = [m for m in apps.get_models() if m._meta.app_label in apps_do_projeto]
    assert len(modelos) >= 18  # garantia de que a varredura pegou o projeto inteiro
    violacoes = []
    for modelo in modelos:
        campos = {f.name: f for f in modelo._meta.fields}
        rotulo = f'{modelo._meta.app_label}.{modelo.__name__}'
        if 'created_at' not in campos:
            violacoes.append(f'{rotulo}: sem created_at')
        elif not campos['created_at'].auto_now_add:
            violacoes.append(f'{rotulo}: created_at não é auto_now_add')
        if 'updated_at' not in campos:
            violacoes.append(f'{rotulo}: sem updated_at')
        elif not campos['updated_at'].auto_now:
            violacoes.append(f'{rotulo}: updated_at não é auto_now')
    assert not violacoes, '\n'.join(violacoes)


# ---------------------------------------------------------------------------
# Renames preservaram os dados e o comportamento
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_negocio_created_at_nao_muda_e_updated_at_avanca(tenant_aurora):
    c = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    n = criar_negocio(c, stage='interessado', tenant_id=tenant_aurora.id)
    criado = n.created_at
    atualizado = n.updated_at
    assert criado is not None and atualizado is not None
    n.stage = 'orcamento'
    n.save()
    n.refresh_from_db()
    assert n.created_at == criado      # criação preservada após o rename
    assert n.updated_at >= atualizado  # alteração continua sendo registrada


@pytest.mark.django_db
def test_nota_e_movimentacao_tem_created_at_e_ordenacao(tenant_aurora, usuario_operacional):
    c = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    n = criar_negocio(c, stage='interessado', tenant_id=tenant_aurora.id)
    nota = Nota.objects.create(contato=c, autor=usuario_operacional, texto='oi')
    mov = Movimentacao.objects.create(
        negocio=n, de_stage='', para_stage='interessado', autor=usuario_operacional
    )
    assert nota.created_at is not None
    assert mov.created_at is not None
    assert nota.updated_at is not None and mov.updated_at is not None
    # ordering por -created_at (antes era -criada_em) continua valendo
    assert Nota.objects.first().id == nota.id


@pytest.mark.django_db
def test_contato_created_at_preenchido(tenant_aurora):
    c = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    assert c.created_at is not None
    assert c.updated_at is not None


@pytest.mark.django_db
def test_convite_created_at_preenchido(tenant_aurora, admin_company):
    from acesso.models import Convite

    convite = Convite.objects.create(
        token='abc123',
        tenant=tenant_aurora,
        email='x@x.com',
        papel='operacional',
        criado_por=admin_company,
        expira_em=timezone.now() + timezone.timedelta(days=7),
    )
    assert convite.created_at is not None
    assert convite.updated_at is not None


# ---------------------------------------------------------------------------
# Telas continuam exibindo as datas (rename aplicado em views + templates)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ficha_mostra_criado_em(tenant_aurora, usuario_operacional):
    c = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    criar_negocio(c, stage='interessado', tenant_id=tenant_aurora.id)
    cliente = Client()
    _sessao_web(cliente, usuario_operacional)
    html = cliente.get(f'/contatos/{c.id}/').content.decode()
    assert 'criado em' in html
    data = timezone.localtime(c.negocio.created_at).strftime('%d/%m/%Y')
    assert data in html


@pytest.mark.django_db
def test_equipe_mostra_criado_em(tenant_aurora, admin_company):
    cliente = Client()
    _sessao_web(cliente, admin_company)
    html = cliente.get('/equipe/').content.decode()
    data = timezone.localtime(admin_company.created_at).strftime('%d/%m/%Y')
    assert data in html
