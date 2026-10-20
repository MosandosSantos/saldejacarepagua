"""Matriz de permissões na CRIAÇÃO de Vale e Loja.

Regras de negócio (definidas com o usuário):
- admin_saas e ADM: criam Vale e Loja para qualquer Vale/Loja.
- delegado: cria Loja somente dentro do Vale dele (Usuario.prefeitura_id),
  "em qualquer loja" do seu Vale; não cria Vale.
- presidente de loja e secretário: não criam nada.
- demais cargos: sem botão e sem acesso (403).
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.models import (
    ROLE_ADM,
    ROLE_ADMIN_SAAS,
    ROLE_DELEGADO,
    ROLE_PRESIDENTE_CORPO,
    ROLE_SECRETARIO,
    ROLE_TESOUREIRO,
    ROLE_VIEWER,
    Tenant,
    Usuario,
)
from acesso.session import iniciar_sessao
from acesso.tenant_context import ADMIN_TENANT_SESSION_KEY
from contatos.models import Loja, Vale

pytestmark = pytest.mark.django_db(transaction=True)


def _tenant_vale(sigla):
    suffix = uuid4().hex
    tenant = Tenant.objects.create(
        nome=sigla,
        slug=f'{sigla.lower()}-{suffix}',
    )
    vale = Vale.objects.create(tenant=tenant, nome=f'Vale {sigla}', sigla=sigla)
    return tenant, vale


def _usuario(tenant, role, prefeitura_id='', loja_id=''):
    suffix = uuid4().hex
    return Usuario.objects.create(
        nome=f'Usuário {suffix}',
        email=f'perm-{suffix}@example.test',
        senha=make_password('senha123'),
        role=role,
        tenant=tenant,
        prefeitura_id=str(prefeitura_id),
        loja_id=str(loja_id),
    )


def _cliente(usuario):
    """Client autenticado com a sessão na mesma forma do login real."""
    client = Client()
    sess = client.session
    iniciar_sessao(SimpleNamespace(session=sess), usuario)
    sess.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = sess.session_key
    return client


def _loja_data(nome):
    return {'nome': nome, 'numero': '1', 'corpo': 'perfeicao'}


# --------------------------------------------------------------------------
# Delegado — só o Vale dele (prefeitura_id), em qualquer loja
# --------------------------------------------------------------------------

def test_delegado_cria_loja_ignorando_vale_de_outro_tenant():
    tenant_a, vale_a = _tenant_vale('PVA')
    _tenant_b, vale_b = _tenant_vale('PVB')
    delegado = _usuario(tenant_a, ROLE_DELEGADO, prefeitura_id=vale_a.pk)
    client = _cliente(delegado)

    # Envia o id do Vale alheio: o backend deve ignorar e usar o dele.
    response = client.post('/contatos/loja/nova/', {
        **_loja_data('Loja do Delegado'), 'vale_id': vale_b.pk,
    })

    assert response.status_code == 302, response.content
    assert response.url == '/lojas/'
    loja = Loja.objects.get(nome='Loja do Delegado')
    assert loja.tenant_id == vale_a.tenant_id


def test_delegado_form_trava_o_vale_dele():
    tenant, vale = _tenant_vale('PVC')
    delegado = _usuario(tenant, ROLE_DELEGADO, prefeitura_id=vale.pk)
    client = _cliente(delegado)

    response = client.get('/contatos/loja/nova/')
    html = response.content.decode()

    assert response.status_code == 200
    assert f'name="vale_id" value="{vale.pk}"' in html  # input fixado
    assert 'fixado ao seu Vale' in html


def test_delegado_sem_vinculo_de_vale_nao_cria():
    tenant, _ = _tenant_vale('PVD')
    delegado = _usuario(tenant, ROLE_DELEGADO)
    client = _cliente(delegado)

    response = client.post('/contatos/loja/nova/', _loja_data('Tentativa'))

    assert response.status_code == 403
    assert not Loja.objects.filter(nome='Tentativa').exists()


def test_delegado_com_vale_inexistente_nao_cria():
    tenant, _ = _tenant_vale('PVE')
    delegado = _usuario(tenant, ROLE_DELEGADO, prefeitura_id=999999)
    client = _cliente(delegado)

    assert client.get('/contatos/loja/nova/').status_code == 403


def test_delegado_usa_o_botao_da_lista_mas_nao_o_de_vale():
    """Delegado vê "Incluir Loja", mas "Incluir Vale" é só de admin."""
    tenant, vale = _tenant_vale('PVF')
    delegado = _usuario(tenant, ROLE_DELEGADO, prefeitura_id=vale.pk)
    client = _cliente(delegado)

    html = client.get('/contatos/lojas/').content.decode()

    assert 'loja/nova' in html  # botão de Loja visível
    assert 'prefeitura/nova' not in html  # botão de Vale não existe p/ ele


# --------------------------------------------------------------------------
# Presidente de loja, secretário e demais cargos — não criam nada
# --------------------------------------------------------------------------

@pytest.mark.parametrize('role', [ROLE_SECRETARIO, ROLE_TESOUREIRO, ROLE_PRESIDENTE_CORPO])
@pytest.mark.django_db(transaction=True)
def test_cargos_de_loja_nao_criam_nada(role):
    tenant, _vale = _tenant_vale('PVG')
    usuario = _usuario(tenant, role, loja_id='1')
    client = _cliente(usuario)

    resposta_vale = client.post('/contatos/prefeitura/nova/', {'nome': 'Vale indevido'})
    resposta_loja = client.post('/contatos/loja/nova/', _loja_data('Loja indevida'))

    assert resposta_vale.status_code == 403
    assert resposta_loja.status_code == 403
    assert not Vale.objects.filter(nome='Vale indevido').exists()
    assert not Loja.objects.filter(nome='Loja indevida').exists()

    html_lojas = client.get('/contatos/lojas/').content.decode()
    assert 'loja/nova' not in html_lojas


def test_cargos_de_loja_nao_veem_botao_de_criacao():
    tenant, _vale = _tenant_vale('PVH')
    secretario = _usuario(tenant, ROLE_SECRETARIO, loja_id='1')
    client = _cliente(secretario)

    html = client.get('/contatos/lojas/').content.decode()

    assert 'loja/nova' not in html


# --------------------------------------------------------------------------
# admin_saas / ADM — qualquer Vale ou Loja
# --------------------------------------------------------------------------

def test_admin_saas_cria_loja_em_qualquer_vale():
    tenant_a, _vale_a = _tenant_vale('PVI')
    tenant_b, vale_b = _tenant_vale('PVJ')
    admin = _usuario(tenant_a, ROLE_ADMIN_SAAS)
    client = _cliente(admin)
    selecao = client.session
    selecao[ADMIN_TENANT_SESSION_KEY] = tenant_b.pk
    selecao.save()

    response = client.post('/contatos/loja/nova/', {
        **_loja_data('Loja admin'), 'vale_id': vale_b.pk,
    })

    assert response.status_code == 302, response.content
    assert Loja.objects.get(nome='Loja admin').tenant_id == vale_b.tenant_id


def test_adm_pode_criar_vale_e_loja():
    tenant, vale = _tenant_vale('PVK')
    adm = _usuario(tenant, ROLE_ADM)
    client = _cliente(adm)

    assert client.get('/contatos/prefeitura/nova/').status_code == 200
    response = client.post('/contatos/prefeitura/nova/', {
        'nome': 'Vale do ADM', 'sigla': f'VA{uuid4().hex[:3]}',
    })
    assert response.status_code == 302
    assert response.url == '/vales/'
    assert Vale.objects.filter(nome='Vale do ADM').exists()

    assert client.post('/contatos/loja/nova/', {
        **_loja_data('Loja do ADM'), 'vale_id': vale.pk,
    }).status_code == 302
    assert Loja.objects.filter(nome='Loja do ADM', tenant=tenant).exists()


@pytest.mark.parametrize('role', [ROLE_ADMIN_SAAS, ROLE_ADM])
def test_admin_e_admin_saas_veem_botao_incluir_vale(role):
    tenant, _ = _tenant_vale(f'BTN{role[:2].upper()}')
    usuario = _usuario(tenant, role)
    client = _cliente(usuario)

    response = client.get('/contatos/prefeituras/')

    assert response.status_code == 200
    assert 'Incluir Vale' in response.content.decode()


def test_delegado_nao_cria_vale():
    tenant, vale = _tenant_vale('PVL')
    delegado = _usuario(tenant, ROLE_DELEGADO, prefeitura_id=vale.pk)
    client = _cliente(delegado)

    response = client.post('/contatos/prefeitura/nova/', {'nome': 'Vale do delegado'})

    assert response.status_code == 403
    assert not Vale.objects.filter(nome='Vale do delegado').exists()


def test_viewer_continua_bloqueado_em_escrita():
    tenant, _ = _tenant_vale('PVM')
    viewer = _usuario(tenant, ROLE_VIEWER)
    client = _cliente(viewer)

    response = client.post('/contatos/loja/nova/', _loja_data('Tentativa viewer'))

    # web_requer_edicao devolve o viewer para a origem (302), como antes.
    assert response.status_code == 302
