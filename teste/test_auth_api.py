"""Testes de autenticacao JWT (/api/v1/auth) — login, /me, validade de 7 dias."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from django.conf import settings

from api.v1.services.auth_service import AuthService


@pytest.mark.django_db(transaction=True)
def test_login_retorna_token(client, usuario_operacional):
    resp = client.post('/api/v1/auth/login', json={
        'email': 'oper@aurora.com', 'senha': 'senha123',
    })

    assert resp.status_code == 200
    dados = resp.json()
    assert dados['token_type'] == 'bearer'
    assert dados['access_token']
    assert dados['usuario']['email'] == 'oper@aurora.com'
    assert dados['usuario']['role'] == 'operacional'
    assert dados['usuario']['tenant_id'] == usuario_operacional.tenant_id


@pytest.mark.django_db(transaction=True)
def test_login_senha_errada(client, usuario_operacional):
    resp = client.post('/api/v1/auth/login', json={
        'email': 'oper@aurora.com', 'senha': 'errada123',
    })

    assert resp.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_login_email_inexistente(client):
    resp = client.post('/api/v1/auth/login', json={
        'email': 'ninguem@aurora.com', 'senha': 'senha123',
    })

    assert resp.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_login_email_malformado_rejeitado(client):
    resp = client.post('/api/v1/auth/login', json={'email': 'nao-e-email', 'senha': 'senha123'})

    assert resp.status_code == 422


@pytest.mark.django_db(transaction=True)
def test_me_com_token_valido(client, usuario_operacional, headers_operacional):
    resp = client.get('/api/v1/auth/me', headers=headers_operacional)

    assert resp.status_code == 200
    assert resp.json()['email'] == 'oper@aurora.com'
    assert resp.json()['role'] == 'operacional'


@pytest.mark.django_db(transaction=True)
def test_me_sem_token(client):
    resp = client.get('/api/v1/auth/me')

    assert resp.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_me_com_token_invalido(client):
    resp = client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer token-qualquer'})

    assert resp.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_token_expirado_rejeitado(client, usuario_operacional):
    agora = datetime.now(timezone.utc)
    expirado = jwt.encode(
        {
            'sub': str(usuario_operacional.id),
            'role': usuario_operacional.role,
            'tenant_id': usuario_operacional.tenant_id,
            'iss': 'gprbr',
            'iat': agora - timedelta(days=8),
            'exp': agora - timedelta(days=1),
        },
        settings.JWT_SECRET,
        algorithm='HS256',
    )

    resp = client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {expirado}'})

    assert resp.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_token_tem_validade_de_7_dias(client, usuario_operacional):
    payload = AuthService().decodificar_token(
        AuthService().gerar_token(usuario_operacional)
    )

    exp = payload['exp']
    assert isinstance(exp, int) or isinstance(exp, float)
    assert exp - payload['iat'] == 7 * 24 * 60 * 60
