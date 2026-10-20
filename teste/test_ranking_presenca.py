"""Página de presença das sessões do ranking — por membro com grau 4-33.

Cada sessão (tarefas.Evento) recebe presença por membro ativo do tenant.
Um membro tem no máximo uma presença por evento (unique). O select de
grau registra o grau conquistado na sessão: valor diferente do grau
atual insere no histórico oficial (contatos.GrauMembro).
"""
import datetime
import json
from uuid import uuid4

import pytest
from django.test import Client

SENHA = 'senha123'


def _cliente_web(usuario, loja_id='loja-uuid-x'):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {
        'nome': usuario.nome, 'email': usuario.email,
        'role': usuario.role, 'tenant_id': usuario.tenant_id,
        'loja_id': loja_id,
    }
    s.save()
    return c


def _criar_usuario(nome, email, role, tenant):
    from django.contrib.auth.hashers import make_password
    from acesso.models import Usuario

    return Usuario.objects.create(
        nome=nome, email=email, role=role, tenant=tenant, senha=make_password(SENHA),
    )


@pytest.fixture
def membro_e_grau(tenant_aurora):
    """Membro ativo com grau inicial 7 no histórico."""
    from contatos.models import Grau, GrauMembro, Loja, Membro

    loja = Loja.objects.create(tenant=tenant_aurora, nome='Loja Presença')
    grau7 = Grau.objects.get(numero=7)
    grau14 = Grau.objects.get(numero=14)
    membro = Membro.objects.create(tenant=tenant_aurora, nome='Irmão Presença')
    membro.lojas.add(loja)
    GrauMembro.objects.create(
        tenant=tenant_aurora, membro=membro, grau=grau7,
        data=datetime.date(2025, 6, 1),
    )
    return {'loja': loja, 'membro': membro, 'grau7': grau7, 'grau14': grau14}


@pytest.fixture
def usuario_sec(tenant_aurora):
    return _criar_usuario('Sec Pres', f'sp-{uuid4().hex[:6]}@g.cal', 'secretario', tenant_aurora)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_presenca_unica_por_evento(membro_e_grau, usuario_sec):
    """Membro não pode ter duas presenças no mesmo evento."""
    from django.db import IntegrityError, transaction
    from tarefas.models import Evento, PresencaSessao

    evento = Evento.objects.create(
        titulo='Sessão P', tipo='sessao',
        data_inicio=datetime.datetime(2026, 11, 2, 20, 0),
        data_fim=datetime.datetime(2026, 11, 2, 22, 0),
        loja_id='loja-uuid-x',
    )
    audit = {'membro': membro_e_grau['membro'], 'evento': evento}
    PresencaSessao.objects.create(**audit, estado='PRESENTE')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PresencaSessao.objects.create(**audit, estado='AUSENTE')


@pytest.mark.django_db
def test_justificado_limites_do_model(membro_e_grau, usuario_sec):
    from tarefas.models import Evento, PresencaSessao

    evento = Evento.objects.create(
        titulo='Sessão J', tipo='sessao',
        data_inicio=datetime.datetime(2026, 11, 2, 20, 0),
        data_fim=datetime.datetime(2026, 11, 2, 22, 0),
        loja_id='loja-uuid-x',
    )
    p = PresencaSessao.objects.create(
        evento=evento, membro=membro_e_grau['membro'],
        estado='JUSTIFICADO', justificativa='Viagem',
    )
    assert p.estado == 'JUSTIFICADO'
    assert p.grau_registrado is None  # grau opcional
    assert p.registrado_por is None


# ---------------------------------------------------------------------------
# View: lista da loja com rádio + select de grau
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_pagina_lista_membros_ativos_do_tenant(membro_e_grau, usuario_sec):
    """A página exibe a relação completa da loja (membros ativos do tenant)."""
    from tarefas.models import Evento

    evento = Evento.objects.create(
        titulo='Sessão Sgt P', tipo='sessao',
        data_inicio=datetime.datetime(2026, 11, 2, 20, 0),
        data_fim=datetime.datetime(2026, 11, 2, 22, 0),
        loja_id='loja-uuid-x',
    )
    r = _cliente_web(usuario_sec).get(f'/tarefas/eventos/{evento.id}/presenca/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Irmão Presença' in html
    # Rádio de presente e select de grau na linha
    assert f'presenca_{membro_e_grau["membro"].id}' in html
    assert 'grau_' in html


@pytest.mark.django_db
def test_pagina_mostra_estado_salvo_e_grau_atual(membro_e_grau, usuario_sec):
    """Reabrir a página mostra a presença anterior e o grau atual no select."""
    from tarefas.models import Evento, PresencaSessao

    evento = Evento.objects.create(
        titulo='Sessão Req', tipo='sessao',
        data_inicio=datetime.datetime(2026, 11, 2, 20, 0),
        data_fim=datetime.datetime(2026, 11, 2, 22, 0),
        loja_id='loja-uuid-x',
    )
    PresencaSessao.objects.create(
        evento=evento, membro=membro_e_grau['membro'], estado='JUSTIFICADO',
        justificativa='Doente',
    )
    r = _cliente_web(usuario_sec).get(f'/tarefas/eventos/{evento.id}/presenca/')
    html = r.content.decode()
    assert 'Doente' in html
    # Rádio jusificado marcado
    assert f'value="JUSTIFICADO" checked' in html
    # Grau atual (7) aparece como badge
    assert '7°' in html


# ---------------------------------------------------------------------------
# View: salvar
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_salvar_presenca_e_grau_novo(membro_e_grau, usuario_sec):
    """Salva presença e muda o grau do membro quando valor difere do atual."""
    from contatos.models import GrauMembro
    from tarefas.models import Evento, PresencaSessao

    evento = Evento.objects.create(
        titulo='Sessão Salva', tipo='sessao',
        data_inicio=datetime.datetime(2026, 11, 2, 20, 0),
        data_fim=datetime.datetime(2026, 11, 2, 22, 0),
        loja_id='loja-uuid-x',
    )
    r = _cliente_web(usuario_sec).post(
        f'/tarefas/eventos/{evento.id}/presenca/salvar/', {
            f'presenca_{membro_e_grau["membro"].id}': 'PRESENTE',
            f'grau_{membro_e_grau["membro"].id}': '14',
        })
    assert r.status_code == 302
    p = PresencaSessao.objects.get(evento=evento, membro=membro_e_grau['membro'])
    assert p.estado == 'PRESENTE'
    # Histórico novo com data da sessão
    graus = list(GrauMembro.objects.filter(
        membro=membro_e_grau['membro']).values_list('grau__numero', 'data'))
    assert (7, datetime.date(2025, 6, 1)) in graus
    assert (14, evento.data_inicio.date()) in graus
    assert p.grau_registrado.numero == 14


@pytest.mark.django_db
def test_salvar_sem_grau_nao_muda_historico(membro_e_grau, usuario_sec):
    from contatos.models import GrauMembro
    from tarefas.models import Evento, PresencaSessao

    evento = Evento.objects.create(
        titulo='Sessão SemG', tipo='sessao',
        data_inicio=datetime.datetime(2026, 11, 2, 20, 0),
        data_fim=datetime.datetime(2026, 11, 2, 22, 0),
        loja_id='loja-uuid-x',
    )
    antes = GrauMembro.objects.filter(membro=membro_e_grau['membro']).count()
    r = _cliente_web(usuario_sec).post(
        f'/tarefas/eventos/{evento.id}/presenca/salvar/', {
            f'presenca_{membro_e_grau["membro"].id}': 'AUSENTE',
        })
    assert r.status_code == 302
    assert PresencaSessao.objects.filter(evento=evento).count() == 1
    assert GrauMembro.objects.filter(membro=membro_e_grau['membro']).count() == antes


@pytest.mark.django_db
def test_salvar_grau_igual_nao_duplica_historico(membro_e_grau, usuario_sec):
    from contatos.models import GrauMembro
    from tarefas.models import Evento

    evento = Evento.objects.create(
        titulo='Sessão Igual', tipo='sessao',
        data_inicio=datetime.datetime(2026, 11, 2, 20, 0),
        data_fim=datetime.datetime(2026, 11, 2, 22, 0),
        loja_id='loja-uuid-x',
    )
    r = _cliente_web(usuario_sec).post(
        f'/tarefas/eventos/{evento.id}/presenca/salvar/', {
            f'presenca_{membro_e_grau["membro"].id}': 'PRESENTE',
            f'grau_{membro_e_grau["membro"].id}': '7',  # igual ao atual
        })
    assert r.status_code == 302
    assert GrauMembro.objects.filter(
        membro=membro_e_grau['membro'], grau__numero=7).count() == 1


@pytest.mark.django_db
def test_salvar_justificado_sem_texto_rejeita(membro_e_grau, usuario_sec):
    from tarefas.models import Evento, PresencaSessao

    evento = Evento.objects.create(
        titulo='Sessão SemJust', tipo='sessao',
        data_inicio=datetime.datetime(2026, 11, 2, 20, 0),
        data_fim=datetime.datetime(2026, 11, 2, 22, 0),
        loja_id='loja-uuid-x',
    )
    r = _cliente_web(usuario_sec).post(
        f'/tarefas/eventos/{evento.id}/presenca/salvar/', {
            f'presenca_{membro_e_grau["membro"].id}': 'JUSTIFICADO',
        }, follow=True)
    assert r.status_code == 200
    assert 'justificativa' in r.content.decode().lower()
    assert not PresencaSessao.objects.filter(evento=evento).exists()


@pytest.mark.django_db
def test_re_salvar_atualiza_estado_nao_duplica(membro_e_grau, usuario_sec):
    from tarefas.models import Evento, PresencaSessao

    evento = Evento.objects.create(
        titulo='Sessão Redo', tipo='sessao',
        data_inicio=datetime.datetime(2026, 11, 2, 20, 0),
        data_fim=datetime.datetime(2026, 11, 2, 22, 0),
        loja_id='loja-uuid-x',
    )
    client = _cliente_web(usuario_sec)
    client.post(f'/tarefas/eventos/{evento.id}/presenca/salvar/', {
        f'presenca_{membro_e_grau["membro"].id}': 'PRESENTE',
    })
    client.post(f'/tarefas/eventos/{evento.id}/presenca/salvar/', {
        f'presenca_{membro_e_grau["membro"].id}': 'AUSENTE',
    })
    assert PresencaSessao.objects.filter(
        evento=evento, membro=membro_e_grau['membro']).count() == 1
    assert PresencaSessao.objects.get(
        evento=evento, membro=membro_e_grau['membro']).estado == 'AUSENTE'


# ---------------------------------------------------------------------------
# Permissões
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('role,status', [('viewer', 302), ('tesoureiro', 302)])
@pytest.mark.django_db
def test_roles_sem_escrita_nao_registram(membro_e_grau, tenant_aurora, role, status):
    from tarefas.models import Evento

    usuario = _criar_usuario(role, f'{role}-{uuid4().hex[:6]}@g.cal', role, tenant_aurora)
    evento = Evento.objects.create(
        titulo='Sessão Role', tipo='sessao',
        data_inicio=datetime.datetime(2026, 11, 2, 20, 0),
        data_fim=datetime.datetime(2026, 11, 2, 22, 0),
        loja_id='loja-uuid-x',
    )
    r = _cliente_web(usuario).post(
        f'/tarefas/eventos/{evento.id}/presenca/salvar/', {
            f'presenca_{membro_e_grau["membro"].id}': 'PRESENTE',
        })
    assert r.status_code == status
    assert not Evento.objects.get(pk=evento.id).presencas.exists()
