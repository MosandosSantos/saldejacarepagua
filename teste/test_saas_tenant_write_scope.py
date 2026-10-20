"""Unselected SaaS administrators can read globally but cannot mutate tenants."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from django.test import Client

from automacoes.models import Automacao
from candidatos.models import Candidato
from contatos.models import Contato, Loja, Membro, Vale, criar_negocio
from emails.models import ModeloEmail
from tarefas.models import Tarefa


def _cliente_saas(admin_saas, *, raise_request_exception=True):
    client = Client(raise_request_exception=raise_request_exception)
    session = client.session
    session['usuario_id'] = admin_saas.pk
    session['usuario'] = {
        'id': admin_saas.pk,
        'nome': admin_saas.nome,
        'email': admin_saas.email,
        'role': admin_saas.role,
        'tenant_id': None,
    }
    session['nicho'] = 'saude'
    session.save()
    return client


def _dados_contato(nome):
    return {
        'nome': nome,
        'empresa': 'Empresa X',
        'tel': '(11) 90000-0000',
        'email': 'novo@example.test',
        'seg': 'beleza',
        'stage': 'suplica',
        'valor': '0',
        'origem': 'Instagram',
        'pagamento': 'Pix',
        'procedimento': 'Laser',
        'ultima_consulta': '2026-01-01',
    }


@pytest.mark.django_db
def test_unselected_admin_can_read_global_contacts_and_email_models(admin_saas, tenant_beta):
    contato = Contato.objects.create(nome='Contato Global', seg='beleza', tenant=tenant_beta)
    modelo = ModeloEmail.objects.create(
        tenant=tenant_beta, nome='Modelo Global', assunto='Assunto', corpo='Corpo',
    )
    client = _cliente_saas(admin_saas)

    contato_response = client.get(f'/contatos/{contato.pk}/')
    email_response = client.get('/emails/')

    assert contato_response.status_code == 200
    assert b'Contato Global' in contato_response.content
    assert email_response.status_code == 200
    assert modelo.nome.encode() in email_response.content


@pytest.mark.django_db
def test_unselected_admin_cannot_edit_global_contact(admin_saas, tenant_aurora):
    contato = Contato.objects.create(nome='Antes', seg='beleza', tenant=tenant_aurora)
    client = _cliente_saas(admin_saas)
    path = f'/contatos/{contato.pk}/editar/'

    assert client.get(path).status_code == 200
    # The target view calls save_m2m after save(commit=False) was not used.
    # Stub that unrelated form hook so the request reaches the contact write.
    with patch('contatos.views.crud.ContatoForm.save_m2m', create=True):
        response = client.post(path, _dados_contato('Depois'))

    contato.refresh_from_db()
    assert contato.nome == 'Antes'
    assert response.status_code == 403


@pytest.mark.django_db
def test_unselected_admin_cannot_edit_global_email_model(admin_saas, tenant_aurora):
    modelo = ModeloEmail.objects.create(
        tenant=tenant_aurora, nome='Antes', assunto='Assunto', corpo='Corpo',
    )
    client = _cliente_saas(admin_saas)

    response = client.post(f'/emails/{modelo.pk}/editar/', {
        'nome': 'Depois', 'assunto': 'Novo assunto', 'corpo': 'Novo corpo',
    })

    modelo.refresh_from_db()
    assert (modelo.nome, modelo.assunto, modelo.corpo) == ('Antes', 'Assunto', 'Corpo')
    assert response.status_code == 403


@pytest.mark.django_db
def test_selected_admin_creates_email_model_in_selected_tenant(admin_saas, tenant_aurora):
    client = _cliente_saas(admin_saas, raise_request_exception=False)
    session = client.session
    session['admin_tenant_id'] = tenant_aurora.pk
    session.save()

    response = client.post('/emails/novo/', {
        'nome': 'Modelo selecionado', 'assunto': 'Assunto', 'corpo': 'Corpo',
    })

    assert response.status_code == 302
    modelo = ModeloEmail.objects.get(nome='Modelo selecionado')
    assert modelo.tenant_id == tenant_aurora.pk
    assert client.session['usuario']['tenant_id'] is None


@pytest.mark.django_db
def test_unselected_admin_cannot_edit_global_task(admin_saas, tenant_aurora):
    tarefa = Tarefa.objects.create(tenant=tenant_aurora, titulo='Antes')
    client = _cliente_saas(admin_saas)

    response = client.post(f'/tarefas/{tarefa.pk}/editar/', {
        'titulo': 'Depois', 'prioridade': 'alta', 'vencimento': '', 'hora': '',
    })

    tarefa.refresh_from_db()
    assert tarefa.titulo == 'Antes'
    assert response.status_code == 403


@pytest.mark.django_db
def test_unselected_admin_cannot_create_automation(admin_saas, tenant_aurora):
    client = _cliente_saas(admin_saas)

    response = client.post('/automacoes/nova/', {
        'nome': 'Regra sem contexto',
        'trigger': 'contato_criado',
        'ativa': 'on',
        'passos_json': '[{"acao":"tarefa","titulo":"Ligar"}]',
    })

    assert not Automacao.objects.filter(nome='Regra sem contexto').exists()
    assert response.status_code == 403


@pytest.mark.django_db
def test_unselected_admin_cannot_create_candidate(admin_saas, tenant_aurora):
    client = _cliente_saas(admin_saas)
    total_before = Candidato.objects.count()

    response = client.post('/candidato/criar/', {
        'nome': 'Candidato sem contexto',
        'prefeitura': 'Prefeitura teste',
        'loja': 'Loja teste',
        'cpf': '',
        'celular': '',
        'email': '',
    })

    assert Candidato.objects.count() == total_before
    assert response.status_code == 403


@pytest.mark.django_db
def test_unselected_admin_cannot_edit_existing_vale(
    admin_saas, tenant_beta,
):
    """Sem tenant selecionado, administrador global não altera Vale existente."""
    suffix = uuid4().hex[:6]
    vale = Vale.objects.create(
        tenant=tenant_beta,
        nome=f'Vale protegido {suffix}',
        sigla=f'V{suffix.upper()}',
    )
    client = _cliente_saas(admin_saas)

    edited = client.post(f'/contatos/prefeitura/{vale.pk}/editar/', {
        'nome': 'Vale alterado sem contexto',
        'sigla': vale.sigla,
    })

    vale.refresh_from_db()
    assert edited.status_code == 403
    assert vale.nome == f'Vale protegido {suffix}'
    assert Vale.objects.filter(pk=vale.pk, status='ATIVA').exists()


@pytest.mark.django_db
def test_unselected_admin_can_open_store_form_and_create_for_selected_vale(
    admin_saas, tenant_beta,
):
    suffix = uuid4().hex[:6]
    vale = Vale.objects.create(
        tenant=tenant_beta,
        nome=f'Vale admin {suffix}',
        sigla=f'V{suffix.upper()}',
    )
    client = _cliente_saas(admin_saas)
    form = client.get('/contatos/loja/nova/')

    assert form.status_code == 200
    assert vale.nome in form.content.decode()

    response = client.post('/contatos/loja/nova/', {
        'nome': 'Loja admin sem tenant selecionado',
        'numero': '8',
        'corpo': 'perfeicao',
        'vale_id': str(vale.pk),
    })

    assert response.status_code == 302
    loja = Loja.objects.get(nome='Loja admin sem tenant selecionado')
    assert loja.tenant_id == vale.tenant_id


@pytest.mark.parametrize('vale_id', [None, '999999', 'inactive'])
@pytest.mark.django_db
def test_unselected_admin_requires_active_vale_for_store_create(
    admin_saas, tenant_beta, vale_id,
):
    if vale_id == 'inactive':
        vale = Vale.objects.create(
            tenant=tenant_beta,
            nome=f'Vale inativo {uuid4().hex[:6]}',
            sigla=f'I{uuid4().hex[:4].upper()}',
            status='INATIVA',
        )
        vale_id = str(vale.pk)
    payload = {
        'nome': 'Loja SaaS sem Vale ativo',
        'corpo': 'perfeicao',
    }
    if vale_id is not None:
        payload['vale_id'] = vale_id
    client = _cliente_saas(admin_saas)
    total_antes = Loja.objects.count()

    response = client.post('/contatos/loja/nova/', payload)

    assert response.status_code == 200
    assert Loja.objects.count() == total_antes
    assert 'Vale' in response.content.decode()


@pytest.mark.django_db
def test_unselected_admin_cannot_delete_member_while_vale_archived(
    admin_saas, tenant_beta,
):
    """Consulta de membro de Vale arquivado é permitida; escrita, bloqueada."""
    Vale.objects.create(
        tenant=tenant_beta,
        nome=f'Vale arquivado {uuid4().hex[:4].upper()}',
        sigla=f'A{uuid4().hex[:4].upper()}',
        status='INATIVA',
    )
    membro = Membro.objects.create(tenant=tenant_beta, nome='Membro de Vale arquivado')
    client = _cliente_saas(admin_saas)

    response = client.post(f'/contatos/membro/{membro.pk}/excluir/')

    membro.refresh_from_db()
    assert response.status_code == 403
    assert membro.situacao == 'ATIVO'


@pytest.mark.django_db
def test_unselected_admin_cannot_move_global_kanban_deal(admin_saas, tenant_aurora):
    contato = Contato.objects.create(nome='Negócio Global', seg='beleza', tenant=tenant_aurora)
    negocio = criar_negocio(contato, stage='suplica', tenant_id=tenant_aurora.pk)
    client = _cliente_saas(admin_saas)

    response = client.post(f'/recepcao/{negocio.pk}/mover/', {'stage': 'pagamento'})

    negocio.refresh_from_db()
    assert negocio.stage == 'suplica'
    assert response.status_code == 403


@pytest.mark.django_db
def test_unselected_admin_cannot_create_contact_activity(admin_saas, tenant_aurora):
    client = _cliente_saas(admin_saas, raise_request_exception=False)
    before = Tarefa.objects.count()

    response = client.post('/recepcao/nova-atividade/', {
        'titulo': 'Atividade sem contexto', 'prioridade': 'media',
    })

    assert response.status_code == 403
    assert Tarefa.objects.count() == before
