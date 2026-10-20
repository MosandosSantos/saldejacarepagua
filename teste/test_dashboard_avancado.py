"""Testes da Fase C (dashboard avançado) — receita projetada, meta, melhores, atividade, velocidade e auto-refresh."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from contatos.models import (
    Contato,
    Negocio,
    Nota,
    criar_negocio,
    registrar_movimentacao,
)


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


def _contato_com_negocio(nome, tenant, stage='suplica', valor=100, **kwargs):
    contato = Contato.objects.create(nome=nome, seg='', tenant=tenant, **kwargs)
    criar_negocio(contato, stage=stage, valor=valor, tenant_id=tenant.id)
    return contato


# --- Renderização dos novos blocos ---

@pytest.mark.django_db
def test_dashboard_renderiza_blocos_avancados(tenant_aurora, usuario_operacional):
    _contato_com_negocio('Ana', tenant_aurora, stage='comunicacao', valor=1000)
    c = _cliente_web(usuario_operacional)
    html = c.get('/dashboard/').content.decode('utf-8')
    for trecho in ['Receita projetada', 'Meta do mês', 'Tempo médio de fechamento',
                   'Melhores negócios', 'Atividade do time', 'Velocidade média por etapa']:
        assert trecho in html, trecho


# --- Receita projetada (pipeline ponderado) ---

@pytest.mark.django_db
def test_receita_projetada_ponderada(tenant_aurora, usuario_operacional):
    from dashboard.views import _brl_curto

    _contato_com_negocio('A', tenant_aurora, stage='comunicacao', valor=1000)   # 0.65
    _contato_com_negocio('B', tenant_aurora, stage='suplica', valor=2000)  # 0.10
    _contato_com_negocio('C', tenant_aurora, stage='diploma', valor=500)      # 1.00
    _contato_com_negocio('D', tenant_aurora, stage='perdido', valor=9999)     # 0.00 (fora)
    c = _cliente_web(usuario_operacional)
    r = c.get('/dashboard/dados/')
    assert r.status_code == 200
    dados = r.json()
    esperado = 1000 * 0.65 + 2000 * 0.10 + 500 * 1.0  # 1350
    assert dados['receita_projetada'] == _brl_curto(esperado)


# --- Meta do mês ---

@pytest.mark.django_db
def test_meta_do_mes_progresso(tenant_aurora, admin_company):
    tenant_aurora.meta_mensal = Decimal(10000)
    tenant_aurora.save(update_fields=['meta_mensal'])
    _contato_com_negocio('Ana', tenant_aurora, stage='diploma', valor=2500)
    c = _cliente_web(admin_company)
    dados = c.get('/dashboard/dados/').json()
    assert dados['meta_pct'] == 25
    assert dados['meta_valor'] == 'R$ 10.000,00'


@pytest.mark.django_db
def test_meta_sem_valor_nao_quebra(tenant_aurora, usuario_operacional):
    _contato_com_negocio('Ana', tenant_aurora, stage='diploma', valor=500)
    c = _cliente_web(usuario_operacional)
    dados = c.get('/dashboard/dados/').json()
    assert dados['meta_pct'] is None
    assert dados['meta_valor'] is None


@pytest.mark.django_db
def test_admin_salva_meta_no_config(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/config/', {'acao': 'meta', 'meta_mensal': '50.000,00'})
    assert r.status_code == 200
    assert b'Meta de faturamento atualizada' in r.content
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.meta_mensal == Decimal(50000)


@pytest.mark.django_db
def test_operacional_nao_altera_meta(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    c.post('/config/', {'acao': 'meta', 'meta_mensal': '99999'})
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.meta_mensal is None


# --- Fechados no mês (escopo mensal) ---

@pytest.mark.django_db
def test_fechados_do_mes_ignora_meses_anteriores(tenant_aurora, usuario_operacional):
    _contato_com_negocio('Nova', tenant_aurora, stage='diploma', valor=500)
    antigo = _contato_com_negocio('Antiga', tenant_aurora, stage='diploma', valor=500)
    # backdate do fechado antigo para o mês passado (update ignora auto_now)
    Negocio.objects.filter(pk=antigo.negocio.id).update(
        updated_at=timezone.now() - timedelta(days=45)
    )
    c = _cliente_web(usuario_operacional)
    dados = c.get('/dashboard/dados/').json()
    assert dados['fechados_qtd'] == 1
    assert dados['valor_fechados'] == 'R$ 500,00'


# --- Melhores negócios ---

@pytest.mark.django_db
def test_melhores_negocios_ordenados(tenant_aurora, usuario_operacional):
    _contato_com_negocio('Pequeno', tenant_aurora, stage='suplica', valor=100)
    _contato_com_negocio('Grande', tenant_aurora, stage='comunicacao', valor=9000)
    _contato_com_negocio('Medio', tenant_aurora, stage='iniciacao', valor=3000)
    c = _cliente_web(usuario_operacional)
    html = c.get('/dashboard/').content.decode('utf-8')
    pos_grande = html.find('Grande')
    pos_medio = html.find('Medio')
    pos_pequeno = html.find('Pequeno')
    assert pos_grande < pos_medio < pos_pequeno  # top por valor


# --- Atividade do time ---

@pytest.mark.django_db
def test_atividade_do_time_conta_movs_e_notas(tenant_aurora, usuario_operacional):
    negocio = _contato_com_negocio('Ana', tenant_aurora, stage='suplica', valor=100).negocio
    registrar_movimentacao(negocio, 'suplica', 'comunicacao', usuario_operacional.id)
    registrar_movimentacao(negocio, 'comunicacao', 'diploma', usuario_operacional.id)
    contato = negocio.contato
    Nota.objects.create(contato=contato, texto='x', autor=usuario_operacional)
    c = _cliente_web(usuario_operacional)
    html = c.get('/dashboard/').content.decode('utf-8')
    assert 'Atividade do time' in html
    assert '2 mov.' in html
    assert '1 notas' in html
    assert usuario_operacional.nome in html


@pytest.mark.django_db
def test_atividade_isolada_por_tenant(tenant_aurora, tenant_beta, usuario_operacional, usuario_operacional_beta):
    negocio_beta = _contato_com_negocio('Beta', tenant_beta, stage='suplica').negocio
    registrar_movimentacao(negocio_beta, 'suplica', 'diploma', usuario_operacional_beta.id)
    negocio = _contato_com_negocio('Aurora', tenant_aurora, stage='suplica').negocio
    registrar_movimentacao(negocio, 'suplica', 'diploma', usuario_operacional.id)
    c = _cliente_web(usuario_operacional)
    html = c.get('/dashboard/').content.decode('utf-8')
    assert usuario_operacional.nome in html
    assert usuario_operacional_beta.nome not in html  # beta não vaza


# --- Endpoint de auto-refresh ---

@pytest.mark.django_db
def test_endpoint_dados_json(tenant_aurora, usuario_operacional):
    _contato_com_negocio('Ana', tenant_aurora, stage='comunicacao', valor=1000)
    c = _cliente_web(usuario_operacional)
    r = c.get('/dashboard/dados/')
    assert r.status_code == 200
    dados = r.json()
    for chave in ['ativos', 'novos_mes', 'valor_funil', 'fechados_qtd', 'conversao',
                  'receita_projetada', 'tempo_medio_fechamento', 'atualizado_em']:
        assert chave in dados, chave
    assert dados['ativos'] == 1
    assert len(dados['atualizado_em']) == 8  # HH:MM:SS


@pytest.mark.django_db
def test_dados_isolado_por_tenant(tenant_aurora, tenant_beta, usuario_operacional, usuario_operacional_beta):
    _contato_com_negocio('Beta', tenant_beta, stage='diploma', valor=9999)
    c = _cliente_web(usuario_operacional)
    dados = c.get('/dashboard/dados/').json()
    assert dados['ativos'] == 0
    assert dados['fechados_qtd'] == 0
