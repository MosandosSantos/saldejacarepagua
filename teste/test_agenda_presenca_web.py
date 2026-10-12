"""Registro de presença pós-evento, por loja (lista de membros filiados)."""
import datetime

import pytest
from django.test import Client

SENHA = 'senha123'


def _cliente_web(usuario, tenant_id=None):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id if tenant_id is None else tenant_id}
    s.save()
    return c


def _criar_usuario(nome, email, role, tenant):
    from django.contrib.auth.hashers import make_password

    from acesso.models import Usuario

    return Usuario.objects.create(
        nome=nome, email=email, role=role, tenant=tenant, senha=make_password(SENHA),
    )


@pytest.fixture
def censo(db, tenant_aurora):
    """Evento, loja e três membros filiados (um inativo)."""
    from agenda.models import EventoAgenda, TipoEvento
    from contatos.models import Filiacao, Loja, Membro

    loja = Loja.objects.create(tenant=tenant_aurora, nome='Loja Presença')
    tipo = TipoEvento.objects.get(nome='Outro')
    evento = EventoAgenda.objects.create(
        tenant=tenant_aurora, loja=loja, tipo=tipo, titulo='Sessão',
        data_hora=datetime.datetime(2026, 10, 1, 20, 0, tzinfo=datetime.timezone.utc),
    )
    ativos = []
    for nome in ['Irmão A', 'Irmão B', 'Irmão C']:
        m = Membro.objects.create(tenant=tenant_aurora, nome=nome, situacao='ATIVO')
        Filiacao.objects.create(tenant=tenant_aurora, membro=m, loja=loja)
        ativos.append(m)
    inativo = Membro.objects.create(
        tenant=tenant_aurora, nome='Irmão Z', situacao='INATIVO')
    Filiacao.objects.create(tenant=tenant_aurora, membro=inativo, loja=loja)
    outra = Loja.objects.create(tenant=tenant_aurora, nome='Outra Loja')
    foraneo = Membro.objects.create(tenant=tenant_aurora, nome='Forâneo', situacao='ATIVO')
    Filiacao.objects.create(tenant=tenant_aurora, membro=foraneo, loja=outra)
    return {'evento': evento, 'loja': loja, 'ativos': ativos,
            'inativo': inativo, 'foraneo': foraneo}


@pytest.mark.django_db
def test_lista_somente_ativos_da_loja(tenant_aurora, censo):
    usuario = _criar_usuario('S', 's@pres.com', 'secretario', tenant_aurora)
    html = _cliente_web(usuario).get(
        f'/agenda/{censo["evento"].id}/presenca/').content.decode()
    for ativo in censo['ativos']:
        assert ativo.nome in html
    assert censo['inativo'].nome not in html
    assert censo['foraneo'].nome not in html


@pytest.mark.django_db
def test_salvar_presencas_com_estados(tenant_aurora, censo):
    from agenda.models import PresencaEvento

    usuario = _criar_usuario('S', 's2@pres.com', 'secretario', tenant_aurora)
    a, b, c_ = censo['ativos']
    dados = {
        f'presenca_{a.id}': 'PRESENTE',
        f'presenca_{b.id}': 'AUSENTE',
        f'presenca_{c_.id}': 'JUSTIFICADO',
        f'justificativa_{c_.id}': 'Trabalho',
    }
    r = _cliente_web(usuario).post(
        f'/agenda/{censo["evento"].id}/presenca/salvar/', dados)
    assert r.status_code == 302
    estados = {p.membro_id: p.estado for p in PresencaEvento.objects.all()}
    assert estados[a.id] == 'PRESENTE'
    assert estados[b.id] == 'AUSENTE'
    assert estados[c_.id] == 'JUSTIFICADO'
    reg = PresencaEvento.objects.get(membro=c_)
    assert reg.justificativa == 'Trabalho'
    assert reg.registrado_por_id == usuario.id


@pytest.mark.django_db
def test_reenviar_atualiza_sem_duplicar(tenant_aurora, censo):
    from agenda.models import PresencaEvento

    usuario = _criar_usuario('S', 's3@pres.com', 'secretario', tenant_aurora)
    a = censo['ativos'][0]
    dados = {f'presenca_{a.id}': 'PRESENTE'}
    c = _cliente_web(usuario)
    c.post(f'/agenda/{censo["evento"].id}/presenca/salvar/', dados)
    c.post(
        f'/agenda/{censo["evento"].id}/presenca/salvar/',
        {f'presenca_{a.id}': 'AUSENTE'})
    assert PresencaEvento.objects.count() == 1
    assert PresencaEvento.objects.first().estado == 'AUSENTE'


@pytest.mark.django_db
def test_viewer_nao_salva(tenant_aurora, censo):
    from agenda.models import PresencaEvento

    usuario = _criar_usuario('V', 'v@pres.com', 'viewer', tenant_aurora)
    c = _cliente_web(usuario)
    r_get = c.get(f'/agenda/{censo["evento"].id}/presenca/')
    r_post = c.post(
        f'/agenda/{censo["evento"].id}/presenca/salvar/',
        {f'presenca_{censo["ativos"][0].id}': 'PRESENTE'})
    assert r_get.status_code in (302, 403)
    assert r_post.status_code in (302, 403)
    assert PresencaEvento.objects.count() == 0
