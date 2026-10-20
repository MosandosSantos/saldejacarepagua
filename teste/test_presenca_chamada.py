"""Presença (lista de chamada) nos eventos da Agenda de Sessões.

Modelo SOLID/TDD:
- `PresencaEvento` (tarefas): tabela auxiliar evento × membro × presente/falta;
- `PresencaServico` (tarefas.presencas): única responsável por chamada e
  percentual (SRP), dependendo só do ORM;
- API JSON GET/POST `/tarefas/eventos/<id>/presenca/` com permissões por cargo;
- Percentual de presença vira coluna na tabela de membros (/contatos/).
"""
import json
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.models import (
    ROLE_DELEGADO, ROLE_SECRETARIO, ROLE_TESOUREIRO, Tenant, Usuario,
)
from acesso.session import iniciar_sessao
from contatos.models import Loja, Membro, Vale
from tarefas.models import Evento, PresencaEvento

pytestmark = pytest.mark.django_db(transaction=True)


def _mundo():
    sufixo = uuid4().hex
    tenant = Tenant.objects.create(nome='Vale Presença', slug=f'pres-{sufixo}')
    vale = Vale.objects.create(tenant=tenant, nome='Vale P', sigla='VP')
    loja = Loja.objects.create(tenant=tenant, nome='Loja Presença')
    loja_outra = Loja.objects.create(tenant=tenant, nome='Loja Outra')

    def _usuario(role, **kw):
        return Usuario.objects.create(
            nome=f'Usuário {role} {sufixo}',
            email=f'pres-{sufixo}-{role}@example.test',
            senha=make_password('senha123'),
            role=role,
            tenant=tenant,
            loja_id=str(kw.get('loja_id', '')),
            prefeitura_id=str(kw.get('prefeitura_id', '')),
        )

    admin = _usuario('admin_saas')
    delegado = _usuario('delegado', prefeitura_id=vale.pk)
    secretario = _usuario('secretario', loja_id=loja.pk)
    tesoureiro = _usuario('tesoureiro', loja_id=loja.pk)

    membros = [
        Membro.objects.create(tenant=tenant, nome=f'Irmão {i}', situacao='ATIVO')
        for i in range(3)
    ]
    for m in membros:
        m.lojas.add(loja)
    membro_outra_loja = Membro.objects.create(
        tenant=tenant, nome='Irmão Outra Loja', situacao='ATIVO',
    )
    membro_outra_loja.lojas.add(loja_outra)
    inativo = Membro.objects.create(
        tenant=tenant, nome='Irmão Inativo', situacao='INATIVO',
    )
    inativo.lojas.add(loja)

    agoraием = None
    # Datas relativas ao passado: a chamada só abre após o término da sessão.
    anteontem = (date.today() - timedelta(days=2)).isoformat()
    evento = Evento.objects.create(
        titulo='Sessão Chamada', tipo='sessao',
        data_inicio=f'{anteontem}T19:00', data_fim=f'{anteontem}T21:00',
        loja_id=str(loja.pk),
    )
    return SimpleNamespace(
        tenant=tenant, vale=vale, loja=loja, loja_outra=loja_outra,
        admin=admin, delegado=delegado, secretario=secretario, tesoureiro=tesoureiro,
        membros=membros, membro_outra_loja=membro_outra_loja, inativo=inativo,
        evento=evento,
    )


def _cliente(usuario):
    client = Client(enforce_csrf_checks=False, raise_request_exception=False)
    sess = client.session
    iniciar_sessao(SimpleNamespace(session=sess), usuario)
    sess.save()
    client.cookies['sessionid'] = sess.session_key
    return client


# ── Model ────────────────────────────────────────────────────────────────

def test_model_presenca_evento_registra_e_eh_unico_por_evento_membro():

    mundo = _mundo()
    PresencaEvento.objects.create(
        evento=mundo.evento, membro=mundo.membros[0], presente=True,
    )
    # Mesma dupla não duplica (constraint), mas presente/falta convive por evento
    assert (
        PresencaEvento.objects.filter(
            evento=mundo.evento, membro=mundo.membros[0],
        ).count() == 1
    )
    outro = Evento.objects.create(
        titulo='Outra sessão', data_inicio=f'{_ontem_iso()}T19:00',
        data_fim=f'{_ontem_iso()}T21:00', loja_id=mundo.evento.loja_id,
    )
    PresencaEvento.objects.create(
        evento=outro, membro=mundo.membros[0], presente=False,
    )
    assert PresencaEvento.objects.filter(membro=mundo.membros[0]).count() == 2


def _ontem_iso():
    """Dia anterior no formato da fixture (chamada exige sessão encerrada)."""
    return (date.today() - timedelta(days=1)).isoformat()


# ── Serviço ──────────────────────────────────────────────────────────────

def test_servico_lista_apenas_membros_ativos_da_loja_do_evento():
    from tarefas.presencas import PresencaServico

    mundo = _mundo()
    nomes = [
        m['nome'] for m in PresencaServico.membros_da_loja(mundo.evento)
    ]
    assert nomes == ['Irmão 0', 'Irmão 1', 'Irmão 2']
    assert 'Irmão Outra Loja' not in nomes
    assert 'Irmão Inativo' not in nomes


def test_servico_registrar_chamada_e_idempotente():
    from tarefas.presencas import PresencaServico

    mundo = _mundo()
    chamada = [
        {'membro': mundo.membros[0].pk, 'presente': True},
        {'membro': mundo.membros[1].pk, 'presente': False},
    ]
    PresencaServico.registrar_chamada(mundo.evento, chamada)
    PresencaServico.registrar_chamada(mundo.evento, chamada)  # idempotente

    assert PresencaEvento.objects.filter(evento=mundo.evento).count() == 2
    assert PresencaEvento.objects.get(
        evento=mundo.evento, membro=mundo.membros[0],
    ).presente is True
    assert PresencaEvento.objects.get(
        evento=mundo.evento, membro=mundo.membros[1],
    ).presente is False

    # Mudou de ideia: falta do 0 vira presença sem duplicar
    PresencaServico.registrar_chamada(
        mundo.evento, [{'membro': mundo.membros[0].pk, 'presente': False}],
    )
    assert PresencaEvento.objects.filter(evento=mundo.evento).count() == 2
    assert PresencaEvento.objects.get(
        evento=mundo.evento, membro=mundo.membros[0],
    ).presente is False


def test_servico_estado_da_chamada_para_get():
    from tarefas.presencas import PresencaServico

    mundo = _mundo()
    PresencaEvento.objects.create(
        evento=mundo.evento, membro=mundo.membros[1], presente=True,
    )

    membros = PresencaServico.membros_da_loja(mundo.evento)
    estado = {m['id']: m['presente'] for m in membros}
    assert estado[mundo.membros[0].pk] is None  # sem chamada ainda
    assert estado[mundo.membros[1].pk] is True


def test_percentual_por_membro_e_none_sem_chamada():
    from tarefas.presencas import PresencaServico

    mundo = _mundo()
    outro = Evento.objects.create(
        titulo='Sessão 2', data_inicio=f'{_ontem_iso()}T19:00',
        data_fim=f'{_ontem_iso()}T21:00', loja_id=mundo.evento.loja_id,
    )
    PresencaEvento.objects.create(  # presente em 1 de 2 chamadas
        evento=mundo.evento, membro=mundo.membros[0], presente=True,
    )
    PresencaEvento.objects.create(
        evento=outro, membro=mundo.membros[0], presente=False,
    )

    percentuais = PresencaServico.percentuais(
        [mundo.membros[0], mundo.membros[1], mundo.membro_outra_loja],
    )
    assert percentuais[mundo.membros[0].pk] == 50
    assert percentuais[mundo.membros[1].pk] is None
    assert percentuais[mundo.membro_outra_loja.pk] is None


# ── API ──────────────────────────────────────────────────────────────────

def test_get_presenca_retorna_membros_e_404_para_evento_ajeno():
    mundo = _mundo()
    client = _cliente(mundo.secretario)

    resposta = client.get(f'/tarefas/eventos/{mundo.evento.pk}/presenca/')
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados['evento']['titulo'] == 'Sessão Chamada'
    assert len(dados['membros']) == 3

    inexistente = client.get('/tarefas/eventos/999999/presenca/')
    assert inexistente.status_code == 404


def test_post_presenca_salva_e_get_devolve_estado():
    mundo = _mundo()
    client = _cliente(mundo.secretario)

    payload = {'presencas': [
        {'membro': mundo.membros[0].pk, 'presente': True},
        {'membro': mundo.membros[1].pk, 'presente': False},
    ]}
    resposta = client.post(
        f'/tarefas/eventos/{mundo.evento.pk}/presenca/',
        json.dumps(payload), content_type='application/json',
    )
    assert resposta.status_code == 200
    assert resposta.json()['ok'] is True

    estado = client.get(f'/tarefas/eventos/{mundo.evento.pk}/presenca/').json()
    por_id = {m['id']: m['presente'] for m in estado['membros']}
    assert por_id[mundo.membros[0].pk] is True
    assert por_id[mundo.membros[1].pk] is False
    assert por_id[mundo.membros[2].pk] is None


@pytest.mark.parametrize('usuario_attr,esperado', [
    ('secretario', 200), ('delegado', 200), ('admin', 200), ('tesoureiro', 403),
])
def test_post_presenca_permissoes_por_cargo(usuario_attr, esperado):
    mundo = _mundo()
    client = _cliente(getattr(mundo, usuario_attr))
    payload = {'presencas': [{'membro': mundo.membros[0].pk, 'presente': True}]}
    resposta = client.post(
        f'/tarefas/eventos/{mundo.evento.pk}/presenca/',
        json.dumps(payload), content_type='application/json',
    )
    assert resposta.status_code == esperado


# ── Coluna de percentual na tabela de membros (/contatos/) ───────────────

def test_percentual_de_presenca_aparece_na_tabela_de_membros():
    """1 presença em 2 chamadas → 50% na coluna "Presença" da listagem."""

    mundo = _mundo()
    outro = Evento.objects.create(
        titulo='Sessão 2 da mesma loja', data_inicio=f'{_ontem_iso()}T19:00',
        data_fim=f'{_ontem_iso()}T21:00', loja_id=mundo.evento.loja_id,
    )
    PresencaEvento.objects.create(
        evento=mundo.evento, membro=mundo.membros[0], presente=True,
    )
    PresencaEvento.objects.create(
        evento=outro, membro=mundo.membros[0], presente=False,
    )

    client = _cliente(mundo.secretario)
    resposta = client.get('/contatos/')

    assert resposta.status_code == 200
    html = resposta.content.decode()
    linha = _linha_do_irmao(html, mundo.membros[0].nome)
    assert linha is not None, 'irmão não está na listagem'
    assert 'data-presenca="50"' in linha, linha[:600]


def _linha_do_irmao(html, nome):
    """Retorna o <tr> da tabela de membros que contém o nome informado."""
    import re

    for trecho in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S):
        if nome in trecho:
            return trecho
    return None


def test_membro_sem_chamada_mostra_traco_na_coluna_presenca():
    mundo = _mundo()
    client = _cliente(mundo.secretario)

    resposta = client.get('/contatos/')

    assert resposta.status_code == 200
    html = resposta.content.decode()
    linha = _linha_do_irmao(html, mundo.membros[0].nome)
    assert linha is not None
    assert 'data-presenca="-"' in linha, linha[:600]


# ── Trava de data: chamada só após o término da sessão ─────────────────

def test_post_presenca_antes_do_termino_recusado():

    mundo = _mundo()
    futuro = Evento.objects.create(
        titulo='Sessão futura', tipo='sessao',
        data_inicio='2099-01-10T19:00', data_fim='2099-01-10T21:00',
        loja_id=mundo.evento.loja_id,
    )
    client = _cliente(mundo.secretario)

    payload = {'presencas': [{'membro': mundo.membros[0].pk, 'presente': True}]}
    resposta = client.post(
        f'/tarefas/eventos/{futuro.pk}/presenca/',
        json.dumps(payload), content_type='application/json',
    )
    assert resposta.status_code == 400
    assert PresencaEvento.objects.filter(evento=futuro).count() == 0

    # Leitura segue liberada (o bloqueio é só na gravação).
    assert client.get(f'/tarefas/eventos/{futuro.pk}/presenca/').status_code == 200


# ── Guardrail: excluir a sessão apaga as presenças junto ───────────────

def test_excluir_evento_apaga_presencas_junto():

    mundo = _mundo()
    PresencaEvento.objects.create(
        evento=mundo.evento, membro=mundo.membros[0], presente=True,
    )
    PresencaEvento.objects.create(
        evento=mundo.evento, membro=mundo.membros[1], presente=False,
    )
    assert PresencaEvento.objects.filter(evento_id=mundo.evento.pk).count() == 2

    client = _cliente(mundo.admin)
    resposta = client.post(f'/tarefas/eventos/{mundo.evento.pk}/excluir/')
    assert resposta.status_code == 200
    assert not Evento.objects.filter(pk=mundo.evento.pk).exists()
    assert PresencaEvento.objects.filter(evento_id=mundo.evento.pk).count() == 0
