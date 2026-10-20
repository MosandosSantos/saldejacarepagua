"""Card 'Sessões no Ano': total de sessões ocorridas + média de presença."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client
from django.utils import timezone

from acesso.models import Tenant, Usuario
from acesso.session import iniciar_sessao
from contatos.models import Loja, Membro
from tarefas.models import Evento, PresencaEvento

pytestmark = pytest.mark.django_db(transaction=True)


def _cliente_admin():
    sufixo = uuid4().hex
    tenant = Tenant.objects.create(nome='Vale Card', slug=f'card-{sufixo}')
    admin = Usuario.objects.create(
        nome='Admin', email=f'card-{sufixo}@example.test',
        senha=make_password('x'), role='admin_saas', tenant=None,
    )
    client = Client(enforce_csrf_checks=False, raise_request_exception=False)
    sess = client.session
    iniciar_sessao(SimpleNamespace(session=sess), admin)
    sess.save()
    client.cookies['sessionid'] = sess.session_key
    return client, tenant


def test_card_sessoes_ocorridas_e_media_presenca():
    client, tenant = _cliente_admin()
    loja = Loja.objects.create(tenant=tenant, nome='Loja Card')
    agora = timezone.now()
    passada = Evento.objects.create(
        titulo='Sessão passada', tipo='sessao',
        data_inicio=agora - timedelta(days=2),
        data_fim=agora - timedelta(days=2, hours=-2),
        loja_id=str(loja.pk),
    )
    futura = Evento.objects.create(
        titulo='Sessão futura', tipo='sessao',
        data_inicio=agora + timedelta(days=2),
        data_fim=agora + timedelta(days=2, hours=2),
        loja_id=str(loja.pk),
    )
    membros = [
        Membro.objects.create(tenant=tenant, nome=f'Irmão Card {i}', situacao='ATIVO')
        for i in range(3)
    ]
    PresencaEvento.objects.create(evento=passada, membro=membros[0], presente=True)
    PresencaEvento.objects.create(evento=passada, membro=membros[1], presente=True)
    PresencaEvento.objects.create(evento=passada, membro=membros[2], presente=False)
    PresencaEvento.objects.create(evento=futura, membro=membros[0], presente=True)

    html = client.get('/gestao/').content.decode()
    assert '>1<' in html  # só a passada conta
    assert '67%' in html  # 2 presentes em 3 registros
    assert 'média de presença' in html


def test_card_sem_chamada_mostra_traco():
    client, tenant = _cliente_admin()
    assert 'média de presença' in client.get('/gestao/').content.decode()
    assert '<span>—</span>' in client.get('/gestao/').content.decode()
