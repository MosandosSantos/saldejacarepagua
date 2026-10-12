"""Smoke: rota da agenda ativa, login exigido, e-suite sem regressão."""
import pytest
from django.test import Client


@pytest.mark.django_db
def test_agenda_responde_ao_app(tenant_aurora):
    """`/agenda/` não redireciona mais para tarefas; responde 200 do app."""
    from django.contrib.auth.hashers import make_password
    from acesso.models import Usuario

    usuario = Usuario.objects.create(
        nome='S Smoke', email='smoke@agenda.com', role='secretario',
        tenant=tenant_aurora, senha=make_password('senha123'),
    )
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email,
                    'role': usuario.role, 'tenant_id': usuario.tenant_id}
    s.save()
    r = c.get('/agenda/')
    assert r.status_code == 200
    assert b'Agenda' in r.content or r.template_name[0].startswith('agenda/')


@pytest.mark.django_db
def test_agenda_exige_login():
    r = Client().get('/agenda/')
    assert r.status_code == 302
    assert '/login' in r.url
