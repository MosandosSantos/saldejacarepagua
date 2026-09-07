"""Testes do fluxo de ativacao de usuario criado sem senha (PRD-USUARIOS-SEM-SENHA).

Cobre: criacao pendente (sem senha utilizavel, token 256 bits, validade 72h),
login bloqueado enquanto pendente, ativacao pela pagina publica (senha + login
automatico), uso unico do token, expiracao e limite de reenvios.
"""
from datetime import timedelta

import pytest
from django.contrib.auth.hashers import check_password
from django.test import Client
from django.utils import timezone

from acesso.ativacao import (
    LIMITE_REENVIOS,
    PRAZO_ATIVACAO,
    ativar_senha,
    criar_usuario_pendente,
    reenviar_ativacao,
)
from acesso.models import ROLE_OPERACIONAL, USUARIO_ATIVO, USUARIO_PENDENTE_SENHA


@pytest.mark.django_db(transaction=True)
def test_criar_pendente_sem_senha(tenant_aurora, admin_company):
    pend = criar_usuario_pendente(
        nome='Ana Nova', email='ana@aurora.com', celular='(11) 99999-0000',
        papel=ROLE_OPERACIONAL, criado_por=admin_company, tenant_id=tenant_aurora.id,
    )
    assert pend.status == USUARIO_PENDENTE_SENHA
    assert pend.senha == '!'  # hash inutilizavel — nenhuma senha confere
    assert pend.celular == '(11) 99999-0000'
    assert pend.criado_por_id == admin_company.id
    assert pend.token_ativacao and len(pend.token_ativacao) >= 32
    assert pend.ativacao_expira_em > timezone.now() + PRAZO_ATIVACAO - timedelta(minutes=1)


@pytest.mark.django_db(transaction=True)
def test_pendente_nao_loga_antes_de_ativar(tenant_aurora, admin_company):
    criar_usuario_pendente(
        nome='Ana Nova', email='ana@aurora.com', papel=ROLE_OPERACIONAL,
        criado_por=admin_company, tenant_id=tenant_aurora.id,
    )
    c = Client()
    resp = c.post('/login/', {'email': 'ana@aurora.com', 'senha': 'qualquer123'})
    assert resp.status_code == 200  # re-render do form com erro
    assert c.session.get('usuario_id') is None


@pytest.mark.django_db(transaction=True)
def test_ativar_pela_pagina_publica_loga(tenant_aurora, admin_company):
    pend = criar_usuario_pendente(
        nome='Ana Nova', email='ana@aurora.com', papel=ROLE_OPERACIONAL,
        criado_por=admin_company, tenant_id=tenant_aurora.id,
    )
    url = f'/usuario/ativar/{pend.token_ativacao}/'
    c = Client()
    resp = c.post(url, {'senha': 'senha-forte-1', 'confirma': 'senha-forte-1'})
    assert resp.status_code == 302  # redirect ao dashboard
    pend.refresh_from_db()
    assert pend.status == USUARIO_ATIVO
    assert pend.token_ativacao is None
    assert check_password('senha-forte-1', pend.senha)
    assert c.session.get('usuario_id') == pend.id


@pytest.mark.django_db(transaction=True)
def test_token_uso_unico(tenant_aurora, admin_company):
    pend = criar_usuario_pendente(
        nome='Ana Nova', email='ana@aurora.com', papel=ROLE_OPERACIONAL,
        criado_por=admin_company, tenant_id=tenant_aurora.id,
    )
    url = f'/usuario/ativar/{pend.token_ativacao}/'
    ativar_senha(pend, 'senha-forte-1')  # token limpo (uso unico)
    c = Client()
    resp = c.get(url)
    assert resp.status_code == 200
    # Token ja consumido nao ativa de novo: mostra motivo (invalido/já ativada)
    assert b'j\xc3\xa1 foi ativada' in resp.content or b'inv\xc3\xa1lido' in resp.content


@pytest.mark.django_db(transaction=True)
def test_token_expirado_nao_ativa(tenant_aurora, admin_company):
    pend = criar_usuario_pendente(
        nome='Ana Nova', email='ana@aurora.com', papel=ROLE_OPERACIONAL,
        criado_por=admin_company, tenant_id=tenant_aurora.id,
    )
    pend.ativacao_expira_em = timezone.now() - timedelta(hours=1)
    pend.save(update_fields=['ativacao_expira_em'])
    c = Client()
    resp = c.get(f'/usuario/ativar/{pend.token_ativacao}/')
    assert b'expi' in resp.content.lower() or b'expi' in resp.content


@pytest.mark.django_db(transaction=True)
def test_reenvio_respeita_limite(tenant_aurora, admin_company):
    pend = criar_usuario_pendente(
        nome='Ana Nova', email='ana@aurora.com', papel=ROLE_OPERACIONAL,
        criado_por=admin_company, tenant_id=tenant_aurora.id,
    )
    token_inicial = pend.token_ativacao
    for _ in range(LIMITE_REENVIOS):
        assert reenviar_ativacao(pend) is not None
    assert reenviar_ativacao(pend) is None
    pend.refresh_from_db()
    assert pend.reenvios_ativacao == LIMITE_REENVIOS
    # cada reenvio gera token novo (o anterior deixa de valer)
    assert pend.token_ativacao != token_inicial
