"""Simulação de pagamento de graus (Asaas fake).

Regras: 9 exige 4, 14 exige 9 + 4 (cadeia); 'todos' é exclusivo (R$ 900).
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.models import Tenant, Usuario
from acesso.session import iniciar_sessao
from contatos.models import Loja, Membro, Vale
from contatos.views.pagamento import normalizar_itens

pytestmark = pytest.mark.django_db(transaction=True)


def test_normalizar_cadeia_e_todos_exclusivo():
    assert normalizar_itens(['4']) == (['4'], 350)
    assert normalizar_itens(['9']) == (['4', '9'], 700)
    assert normalizar_itens(['14']) == (['4', '9', '14'], 1050)
    assert normalizar_itens(['todos']) == (['todos'], 900)
    assert normalizar_itens(['todos', '4', '9']) == (['todos'], 900)
    assert normalizar_itens([]) == ([], 0)
    assert normalizar_itens(['invalido']) == ([], 0)


def _mundo():
    sufixo = uuid4().hex
    tenant = Tenant.objects.create(nome='Vale Pag', slug=f'pag-{sufixo}')
    Vale.objects.create(tenant=tenant, nome='Vale Pag', sigla='VP')
    loja = Loja.objects.create(tenant=tenant, nome='Loja Pag')
    membro = Membro.objects.create(tenant=tenant, nome='Irmão Pag', situacao='ATIVO')
    membro.lojas.add(loja)
    admin = Usuario.objects.create(
        nome='Admin', email=f'pag-{sufixo}@example.test',
        senha=make_password('x'), role='admin_saas', tenant=None,
    )
    return SimpleNamespace(tenant=tenant, loja=loja, membro=membro, admin=admin)


def _cliente(usuario):
    client = Client(enforce_csrf_checks=False, raise_request_exception=False)
    sess = client.session
    iniciar_sessao(SimpleNamespace(session=sess), usuario)
    sess.save()
    client.cookies['sessionid'] = sess.session_key
    return client


def test_fluxo_selecao_ate_asaas_fake():
    mundo = _mundo()
    client = _cliente(mundo.admin)

    get = client.get(f'/membros/{mundo.membro.pk}/pagamento/')
    assert get.status_code == 200
    assert 'Grau 9' in get.content.decode()

    vazio = client.post(f'/membros/{mundo.membro.pk}/pagamento/', {})
    assert vazio.status_code == 200
    assert 'Selecione ao menos um grau' in vazio.content.decode()

    # Só o 9 marcado → cadeia completa 4 + 9 = R$ 700,00 no Asaas fake.
    post = client.post(
        f'/membros/{mundo.membro.pk}/pagamento/', {'itens': ['9']},
    )
    assert post.status_code == 302
    checkout = client.get(f'/membros/{mundo.membro.pk}/pagamento/asaas/')
    assert checkout.status_code == 200
    html = checkout.content.decode()
    assert 'R$ 700,00' in html
    assert 'simulação' in html.lower()

    pago = client.post(
        f'/membros/{mundo.membro.pk}/pagamento/asaas/', {'metodo': 'pix'},
    )
    assert pago.status_code == 200
    assert 'Pagamento simulado aprovado' in pago.content.decode()


def test_todos_exclusivo_no_checkout():
    mundo = _mundo()
    client = _cliente(mundo.admin)
    client.post(f'/membros/{mundo.membro.pk}/pagamento/', {'itens': ['4', 'todos']})
    html = client.get(f'/membros/{mundo.membro.pk}/pagamento/asaas/').content.decode()
    assert 'R$ 900,00' in html
    assert 'Todos os graus' in html


def test_asaas_sem_selecao_volta():
    mundo = _mundo()
    client = _cliente(mundo.admin)
    resposta = client.get(f'/membros/{mundo.membro.pk}/pagamento/asaas/')
    assert resposta.status_code == 302
