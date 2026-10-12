"""Permissões da agenda — todos escrevem exceto tesoureiro e viewer."""
import pytest
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory

import agenda.permissions as permissoes
from agenda.permissions import agenda_requer_escrita, pode_escrever_agenda


def _request_com_role(role):
    request = RequestFactory().get('/agenda/')
    request.session = {'usuario': {'role': role, 'nome': 'X'}, 'usuario_id': 1}
    return request


@pytest.mark.parametrize('role', ['tesoureiro', 'viewer'])
def test_nao_escrevem(role):
    assert pode_escrever_agenda(_request_com_role(role)) is False


@pytest.mark.parametrize(
    'role', ['secretario', 'presidente_corpo', 'delegado', 'ADM', 'admin_saas'],
)
def test_escrevem(role):
    assert pode_escrever_agenda(_request_com_role(role)) is True


def test_sem_sessao_nao_escreve():
    request = RequestFactory().get('/agenda/')
    request.session = {}
    assert pode_escrever_agenda(request) is False


@pytest.fixture
def destino_agenda(monkeypatch):
    """Substitui o redirect do decorator por um HttpResponse fixo — evita
    depender do URLconf real (as rotas reais chegam na Task 3)."""
    def _redirect_falso(to, *args, **kwargs):
        return HttpResponse('', status=302, headers={'Location': to})

    monkeypatch.setattr(permissoes, 'redirect', _redirect_falso)
    return _redirect_falso


def _montar_vista():
    return agenda_requer_escrita(lambda request: HttpResponse('ok'))


@pytest.mark.django_db
def test_decorator_get_redireciona_e_post_proibe(destino_agenda):
    vista = _montar_vista()

    r_get = _request_com_role('viewer')
    r_get.method = 'GET'
    resposta = vista(r_get)
    assert resposta.status_code == 302
    assert resposta['Location'] == 'agenda:lista'

    r_post = _request_com_role('viewer')
    r_post.method = 'POST'
    assert vista(r_post).status_code == 403

    r_ok = _request_com_role('secretario')
    assert vista(r_ok).status_code == 200
