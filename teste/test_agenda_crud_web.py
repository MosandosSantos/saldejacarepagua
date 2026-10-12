"""CRUD web da agenda — lista, novo, editar, excluir, escopo por tenant."""
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


def _evento(dados_base, tenant, loja, tipo, titulo):
    from agenda.models import EventoAgenda

    return EventoAgenda.objects.create(
        tenant=tenant, loja=loja, tipo=tipo, titulo=titulo,
        data_hora=dados_base,
    )


@pytest.fixture
def dados_base():
    return datetime.datetime(2026, 12, 1, 20, 0, tzinfo=datetime.timezone.utc)


def _dados_form(loja_id, tipo_id, dados_base, titulo='Sessão Magna de Dezembro'):
    return {
        'loja': str(loja_id), 'tipo': str(tipo_id), 'titulo': titulo,
        'data_hora': '2026-12-01T20:00', 'local': 'Templo', 'descricao': 'x',
    }


@pytest.fixture
def tipo(db):
    from agenda.models import TipoEvento

    return TipoEvento.objects.get(nome='Sessão Magna')


@pytest.mark.django_db
def test_lista_mostra_eventos_do_tenant(tenant_aurora, dados_base, tipo):
    from contatos.models import Loja
    from acesso.models import Tenant

    usuario = _criar_usuario('Sec', 'sec@agenda.com', 'secretario', tenant_aurora)
    loja = Loja.objects.create(tenant=tenant_aurora, nome='LS')
    outro = Tenant.objects.get_or_create(
        slug='agenda-outro', defaults={'nome': 'Outro'})[0]
    loja_outro = Loja.objects.create(tenant=outro, nome='LO')
    _evento(dados_base, tenant_aurora, loja, tipo, 'Meu evento')
    _evento(dados_base, outro, loja_outro, tipo, 'Evento alheio')

    html = _cliente_web(usuario).get('/agenda/').content.decode()
    assert 'Meu evento' in html
    assert 'Evento alheio' not in html


@pytest.mark.django_db
def test_secretario_cria_evento(tenant_aurora, dados_base, tipo):
    from contatos.models import Loja
    from agenda.models import EventoAgenda

    usuario = _criar_usuario('Sec', 'sec2@agenda.com', 'secretario', tenant_aurora)
    loja = Loja.objects.create(tenant=tenant_aurora, nome='LS2')
    r = _cliente_web(usuario).post(
        '/agenda/novo/', _dados_form(loja.id, tipo.id, dados_base))
    assert r.status_code == 302
    assert EventoAgenda.objects.count() == 1
    assert EventoAgenda.objects.first().titulo == 'Sessão Magna de Dezembro'


@pytest.mark.parametrize('role', ['viewer', 'tesoureiro'])
@pytest.mark.django_db
def test_roles_sem_escrita_nao_criam(tenant_aurora, dados_base, tipo, role):
    from contatos.models import Loja
    from agenda.models import EventoAgenda

    usuario = _criar_usuario(role, f'{role}@agenda.com', role, tenant_aurora)
    loja = Loja.objects.create(tenant=tenant_aurora, nome='L3')
    r = _cliente_web(usuario).post(
        '/agenda/novo/', _dados_form(loja.id, tipo.id, dados_base))
    assert r.status_code == 403
    assert EventoAgenda.objects.count() == 0


@pytest.mark.django_db
def test_admin_saas_sem_tenant_nao_escreve(tenant_aurora, dados_base, tipo):
    from acesso.models import Tenant
    from contatos.models import Loja
    from agenda.models import EventoAgenda

    usuario = _criar_usuario('SaaS', 'saas@agenda.com', 'admin_saas', None)
    cliente = _cliente_web(usuario)
    # sessão sem tenant selecionado (chave admin_tenant_id ausente)
    outro = Tenant.objects.get_or_create(
        slug='agenda-outro-saas', defaults={'nome': 'Outro'})[0]
    loja = Loja.objects.create(tenant=outro, nome='L4')
    r = cliente.post('/agenda/novo/', _dados_form(loja.id, tipo.id, dados_base))
    assert r.status_code == 403
    assert EventoAgenda.objects.count() == 0


@pytest.mark.django_db
def test_editar_e_excluir(tenant_aurora, dados_base, tipo):
    from contatos.models import Loja
    from agenda.models import EventoAgenda

    usuario = _criar_usuario('Sec', 'sec3@agenda.com', 'secretario', tenant_aurora)
    loja = Loja.objects.create(tenant=tenant_aurora, nome='L5')
    evento = _evento(dados_base, tenant_aurora, loja, tipo, 'Original')
    c = _cliente_web(usuario)

    r = c.post(
        f'/agenda/{evento.id}/editar/',
        _dados_form(loja.id, tipo.id, dados_base, titulo='Editado'))
    assert r.status_code == 302
    evento.refresh_from_db()
    assert evento.titulo == 'Editado'

    r = c.post(f'/agenda/{evento.id}/excluir/')
    assert r.status_code == 302
    assert EventoAgenda.objects.count() == 0
