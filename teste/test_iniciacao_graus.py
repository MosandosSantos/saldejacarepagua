"""Eligibility for the first degree-candidate column (Grau 9)."""
import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.context_processors import _nav_itens
from acesso.models import Tenant, Usuario
from acesso.session import iniciar_sessao
from contatos.models import Grau, GrauMembro, Loja, Membro, Vale
from tarefas.models import Evento, PresencaEvento

pytestmark = pytest.mark.django_db

HOJE = datetime.date(2026, 10, 17)
LIMITE_SEIS_MESES = datetime.date(2026, 4, 17)


@pytest.fixture
def vales_e_lojas():
    sufixo = uuid4().hex[:10]
    tenant = Tenant.objects.create(
        nome='Vale Iniciação', slug=f'iniciacao-{sufixo}',
    )
    Vale.objects.create(
        tenant=tenant, nome='Vale Iniciação', sigla=f'VI{sufixo[:4]}',
    )
    tenant_externo = Tenant.objects.create(
        nome='Vale Externo', slug=f'iniciacao-externo-{sufixo}',
    )
    Vale.objects.create(
        tenant=tenant_externo,
        nome='Vale Externo',
        sigla=f'VE{sufixo[:4]}',
    )
    return {
        'tenant': tenant,
        'loja_1': Loja.objects.create(tenant=tenant, nome='Loja Iniciação 1'),
        'loja_2': Loja.objects.create(tenant=tenant, nome='Loja Iniciação 2'),
        'tenant_externo': tenant_externo,
        'loja_externa': Loja.objects.create(
            tenant=tenant_externo, nome='Loja de Outro Vale',
        ),
    }


def _registrar_grau(membro, numero, data):
    grau, _ = Grau.objects.get_or_create(
        numero=numero, defaults={'nome': f'Grau {numero}'},
    )
    return GrauMembro.objects.create(
        tenant=membro.tenant,
        membro=membro,
        grau=grau,
        data=data,
    )


def _membro(
    tenant,
    nome,
    *,
    grau_atual=8,
    data_grau_4=datetime.date(2010, 1, 1),
    situacao='ATIVO',
):
    membro = Membro.objects.create(
        tenant=tenant,
        nome=nome,
        situacao=situacao,
    )
    if data_grau_4 is not None:
        _registrar_grau(membro, 4, data_grau_4)
    if grau_atual != 4:
        _registrar_grau(membro, grau_atual, datetime.date(2026, 5, 1))
    return membro


def _candidatos_grau_9(tenant_ids, hoje):
    from contatos.iniciacao_graus import candidatos_grau_9

    return candidatos_grau_9(tenant_ids, hoje=hoje)


def _cliente(tenant):
    sufixo = uuid4().hex
    usuario = Usuario.objects.create(
        nome='Usuário Iniciação',
        email=f'iniciacao-{sufixo}@example.test',
        senha=make_password('senha123'),
        role='delegado',
        tenant=tenant,
    )
    cliente = Client(raise_request_exception=False)
    sessao = cliente.session
    iniciar_sessao(SimpleNamespace(session=sessao), usuario)
    sessao.save()
    cliente.cookies[settings.SESSION_COOKIE_NAME] = sessao.session_key
    return cliente


def test_pagina_iniciacao_mostra_candidato_grau9_com_dados_de_elegibilidade(
    vales_e_lojas,
):
    mundo = vales_e_lojas
    membro = _membro(
        mundo['tenant'],
        'Candidato Visível Grau 9',
        data_grau_4=LIMITE_SEIS_MESES - datetime.timedelta(days=1),
    )
    membro_externo = _membro(
        mundo['tenant_externo'],
        'Candidato Sigiloso de Outro Vale',
        data_grau_4=LIMITE_SEIS_MESES - datetime.timedelta(days=1),
    )
    data_grau_4 = LIMITE_SEIS_MESES - datetime.timedelta(days=1)
    _chamada(mundo['loja_1'], membro, True)
    _chamada(mundo['loja_2'], membro, False)
    _chamada(mundo['loja_externa'], membro_externo, True)

    resposta = _cliente(mundo['tenant']).get('/membros/iniciacao/')

    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert 'Candidatos ao Grau 9' in html
    assert 'Candidato Visível Grau 9' in html
    assert 'Vale Iniciação' in html
    assert 'Candidato Sigiloso de Outro Vale' not in html
    assert '50%' in html
    assert data_grau_4.strftime('%d/%m/%Y') in html


def test_pagina_iniciacao_exige_login():
    resposta = Client(raise_request_exception=False).get('/membros/iniciacao/')

    assert resposta.status_code == 302
    assert '/login/' in resposta.url


def test_pagina_iniciacao_exige_vale_ativo():
    tenant = Tenant.objects.create(
        nome='Tenant sem Vale', slug=f'sem-vale-{uuid4().hex}',
    )

    resposta = _cliente(tenant).get('/membros/iniciacao/')

    assert resposta.status_code == 403


def test_navegacao_sem_iniciacao_a_graus():
    """O link 'Iniciação a Graus' saiu do menu (o quadro é /iniciacao/)."""
    itens = _nav_itens(url_name='iniciacao', app_atual='membros', role='delegado')

    ativos = [item['label'] for item in itens if item['ativa']]

    assert 'Iniciação a Graus' not in ativos


def _chamada(loja, membro, presente, dia=datetime.date(2026, 8, 1)):
    inicio = datetime.datetime.combine(
        dia, datetime.time(19, tzinfo=datetime.UTC),
    )
    evento = Evento.objects.create(
        titulo=f'Sessão de {loja.nome}',
        data_inicio=inicio,
        data_fim=inicio + datetime.timedelta(hours=2),
        loja_id=str(loja.pk),
    )
    return PresencaEvento.objects.create(
        evento=evento, membro=membro, presente=presente,
    )


def test_candidato_grau9_qualifica_com_grau8_data_e_presenca(vales_e_lojas):
    mundo = vales_e_lojas
    membro = _membro(
        mundo['tenant'],
        'Candidato Grau 9',
        data_grau_4=LIMITE_SEIS_MESES - datetime.timedelta(days=1),
    )
    # A segunda chamada é em outra Loja do mesmo Vale; a taxa do Vale é 1/2.
    _chamada(mundo['loja_1'], membro, True)
    _chamada(mundo['loja_2'], membro, False)

    candidatos = _candidatos_grau_9([mundo['tenant'].pk], hoje=HOJE)

    assert len(candidatos) == 1
    assert candidatos[0].membro == membro
    assert candidatos[0].vale_nome == 'Vale Iniciação'
    assert candidatos[0].data_grau_4 == LIMITE_SEIS_MESES - datetime.timedelta(days=1)
    assert candidatos[0].presenca_percentual == 50


def test_grau9_requer_maior_grau_exatamente_8(vales_e_lojas):
    mundo = vales_e_lojas
    grau_7 = _membro(mundo['tenant'], 'Ainda no 7', grau_atual=7)
    grau_9 = _membro(mundo['tenant'], 'Já passou do 8', grau_atual=9)
    for membro in (grau_7, grau_9):
        _chamada(mundo['loja_1'], membro, True)

    assert _candidatos_grau_9([mundo['tenant'].pk], hoje=HOJE) == []


def test_grau9_requer_grau4_mais_antigo_que_seis_meses(vales_e_lojas):
    mundo = vales_e_lojas
    exatamente_seis_meses = _membro(
        mundo['tenant'], 'Exatamente seis meses', data_grau_4=LIMITE_SEIS_MESES,
    )
    sem_grau_4 = _membro(
        mundo['tenant'], 'Sem Grau 4', data_grau_4=None,
    )
    _chamada(mundo['loja_1'], exatamente_seis_meses, True)
    _chamada(mundo['loja_1'], sem_grau_4, True)

    assert _candidatos_grau_9([mundo['tenant'].pk], hoje=HOJE) == []


def test_grau9_requer_chamadas_e_presenca_minima(vales_e_lojas):
    mundo = vales_e_lojas
    _membro(mundo['tenant'], 'Sem chamadas')
    abaixo_50 = _membro(mundo['tenant'], 'Abaixo de 50')
    for indice in range(100):
        _chamada(mundo['loja_1'], abaixo_50, indice < 49)

    candidatos = _candidatos_grau_9([mundo['tenant'].pk], hoje=HOJE)

    assert candidatos == []


def test_grau9_agrega_lojas_do_vale_sem_vazar_tenant(vales_e_lojas):
    mundo = vales_e_lojas
    membro = _membro(
        mundo['tenant'],
        'Presença abaixo só no Vale',
        data_grau_4=LIMITE_SEIS_MESES - datetime.timedelta(days=1),
    )
    # 49/100 no Vale não qualifica; presenças externas não podem elevá-lo a 50%.
    for indice in range(100):
        _chamada(mundo['loja_1'], membro, indice < 49)
    _chamada(mundo['loja_externa'], membro, True)
    _chamada(mundo['loja_externa'], membro, True)

    assert _candidatos_grau_9([mundo['tenant'].pk], hoje=HOJE) == []
