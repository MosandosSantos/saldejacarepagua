"""Testes da Fase S — S7 do PRD HAZON (Dashboard e relatórios).

KPIs de cobrança (base, CPC, retornos e produtividade por operador), filtros de
período (hoje/7/30/mês) e exportação em CSV e PDF (7.1, 7.2, 7.3). Tudo
escopado por tenant e respeitando permissões.
"""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from acesso.models import Tenant, Usuario
from contatos.models import Contato
from discador.models import Chamada, Fila

SENHA = 'senha123'

_fila_seq = [0]


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


def _contato(tenant, nome='Ana', tel='(11) 98888-7777', dias_atras=0):
    created = timezone.now() - timedelta(days=dias_atras)
    c = Contato.objects.create(
        nome=nome, empresa='X', tel=tel, email=f'{nome.lower()}@x.com',
        seg='geral', tenant=tenant,
    )
    Contato.objects.filter(pk=c.pk).update(created_at=created)
    return c


def _chamada(tenant, operador, status='realizada', dias_atras=0, retorno_em=None):
    _fila_seq[0] += 1
    fila = Fila.objects.create(nome=f'Fila {status} {dias_atras} {_fila_seq[0]}', tenant=tenant)
    contato = _contato(tenant, nome=f'C{status}{dias_atras}', tel=f'(11) 97777-{dias_atras:04d}')
    chamada = Chamada.objects.create(
        fila=fila, contato=contato, operador_id=operador.id,
        status=status, tenant=tenant, retorno_em=retorno_em,
    )
    created = timezone.now() - timedelta(days=dias_atras)
    Chamada.objects.filter(pk=chamada.pk).update(created_at=created, updated_at=created)
    return chamada


# --- KPIs (7.1) ---

@pytest.mark.django_db
def test_kpis_base_cpc_retornos(tenant_aurora, admin_company, usuario_operacional):
    """Base conta só contatos com telefone; CPC/retornos no período."""
    _contato(tenant_aurora, nome='Sem tel', tel='—')            # sem telefone -> não conta
    _contato(tenant_aurora, nome='Com tel', tel='(11) 91111-1111')
    _chamada(tenant_aurora, usuario_operacional, status='realizada', dias_atras=1)
    _chamada(tenant_aurora, usuario_operacional, status='nao_atendeu', dias_atras=1)
    retorno_em = timezone.now() + timedelta(days=2)
    _chamada(tenant_aurora, usuario_operacional, status='retornar', dias_atras=0, retorno_em=retorno_em)

    c = _cliente_web(admin_company)
    r = c.get('/relatorios/?periodo=30')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Base em cobrança' in html
    assert 'Contatos úteis (CPC)' in html
    assert 'Retornos agendados' in html
    assert 'Acordos' not in html  # módulo de acordos removido
    assert 'Valor recuperado' not in html


@pytest.mark.django_db
def test_produtividade_por_operador(tenant_aurora, admin_company, usuario_operacional,
                                    usuario_operacional_beta):
    """A tabela agrupa por operador e o operador de outro tenant não aparece."""
    _chamada(tenant_aurora, usuario_operacional, status='realizada', dias_atras=1)
    _chamada(tenant_aurora, usuario_operacional, status='realizada', dias_atras=1)
    _chamada(tenant_aurora, usuario_operacional, status='retornar', dias_atras=0,
             retorno_em=timezone.now() + timedelta(days=1))
    _chamada(tenant_beta(), usuario_operacional_beta, status='realizada', dias_atras=1)

    c = _cliente_web(admin_company)
    html = c.get('/relatorios/?periodo=30').content.decode()
    assert 'Oper Aurora' in html
    assert 'Oper Beta' not in html
    assert '2' in html  # chamadas do Oper Aurora
    assert 'Produtividade por operador' in html


def tenant_beta():

    return Tenant.objects.get_or_create(nome='Clínica Beta', slug='clinica-beta')[0]


# --- Filtros de período (7.2) ---

@pytest.mark.django_db
def test_filtro_hoje_ignora_chamadas_antigas(tenant_aurora, admin_company, usuario_operacional):
    _chamada(tenant_aurora, usuario_operacional, status='realizada', dias_atras=0)
    _chamada(tenant_aurora, usuario_operacional, status='realizada', dias_atras=10)

    c = _cliente_web(admin_company)
    html = c.get('/relatorios/?periodo=hoje').content.decode()
    assert 'CPC' in html
    # 1 chamada hoje: cpc=1; a antiga (10 dias) fica fora
    assert '1' in html


@pytest.mark.django_db
def test_filtro_mes_usa_inicio_do_mes(tenant_aurora, admin_company, usuario_operacional):
    _chamada(tenant_aurora, usuario_operacional, status='realizada', dias_atras=0)
    _chamada(tenant_aurora, usuario_operacional, status='realizada', dias_atras=45)

    c = _cliente_web(admin_company)
    html = c.get('/relatorios/?periodo=mes').content.decode()
    assert 'Mês corrente' in html
    assert 'Produtividade por operador' in html


# --- Isolamento entre tenants ---

@pytest.mark.django_db
def test_isolamento_entre_tenants(tenant_aurora, tenant_beta, admin_company, usuario_operacional_beta):
    _chamada(tenant_beta, usuario_operacional_beta, status='realizada', dias_atras=0)

    c = _cliente_web(admin_company)
    html = c.get('/relatorios/?periodo=30').content.decode()
    # A clínica Aurora não vê nada da Beta
    assert 'Oper Beta' not in html


# --- Exportação CSV (7.3.1) ---

@pytest.mark.django_db
def test_exportar_csv(tenant_aurora, admin_company, usuario_operacional):
    _chamada(tenant_aurora, usuario_operacional, status='realizada', dias_atras=1)

    c = _cliente_web(admin_company)
    r = c.get('/relatorios/exportar/csv/?periodo=7')
    assert r.status_code == 200
    assert r['Content-Type'].startswith('text/csv')
    conteudo = r.content.decode('utf-8-sig')
    assert 'Relatório gerencial' in conteudo
    assert 'Contatos úteis realizados (CPC)' in conteudo
    assert 'Oper Aurora' in conteudo
    assert 'Valor recuperado' not in conteudo
    assert 'Acordos' not in conteudo


# --- Exportação PDF (7.3.2) ---

@pytest.mark.django_db
def test_exportar_pdf(tenant_aurora, admin_company, usuario_operacional):
    _chamada(tenant_aurora, usuario_operacional, status='realizada', dias_atras=1)

    c = _cliente_web(admin_company)
    r = c.get('/relatorios/exportar/pdf/?periodo=30')
    assert r.status_code == 200
    assert r['Content-Type'] == 'application/pdf'
    assert r.content[:4] == b'%PDF'
    assert 'attachment' in r['Content-Disposition']


@pytest.mark.django_db
def test_exportar_pdf_sem_dados(tenant_aurora, admin_company):
    """PDF funciona mesmo sem nenhum dado no período (empresa nova)."""
    c = _cliente_web(admin_company)
    r = c.get('/relatorios/exportar/pdf/?periodo=hoje')
    assert r.status_code == 200
    assert r.content[:4] == b'%PDF'


# --- Permissões ---

@pytest.mark.django_db
def test_nao_logado_redireciona_para_login():
    r = Client().get('/relatorios/')
    assert r.status_code == 302
    assert '/login/' in r['Location']


@pytest.mark.django_db
def test_viewer_pode_ver_relatorios(tenant_aurora, usuario_viewer):
    """viewer (somente leitura) pode consultar relatórios e exportar."""
    c = _cliente_web(usuario_viewer)
    assert c.get('/relatorios/').status_code == 200
    assert c.get('/relatorios/exportar/csv/').status_code == 200
    assert c.get('/relatorios/exportar/pdf/').status_code == 200


# --- Gráficos da série diária (S7+) ---

@pytest.mark.django_db
def test_graficos_serie_diaria_na_pagina(tenant_aurora, admin_company, usuario_operacional):
    """A página traz o gráfico SVG da série diária (CPC)."""
    _chamada(tenant_aurora, usuario_operacional, status='realizada', dias_atras=1)

    c = _cliente_web(admin_company)
    html = c.get('/relatorios/?periodo=30').content.decode()
    assert 'Atividade diária' in html
    assert '<svg' in html
    assert 'rlArea0' in html  # gradiente do gráfico
    assert 'Valor recuperado' not in html


# --- Filtro por operador (S7+) ---

@pytest.mark.django_db
def _corpo_tabela_produtividade(html):
    """Trecho <tbody> da tabela de produtividade (o <select> de operadores também lista nomes)."""
    inicio = html.index('<tbody>')
    fim = html.index('</tbody>', inicio)
    return html[inicio:fim]


@pytest.mark.django_db
def test_filtro_por_operador(tenant_aurora, admin_company, usuario_operacional,
                             usuario_operacional_beta):
    """`?operador=` restringe a tabela; id de outro tenant é ignorado (volta a todos)."""

    op2 = Usuario.objects.create(
        nome='Oper Dois', email='op2@aurora.com', role='operacional',
        tenant=tenant_aurora, senha='x',
    )
    _chamada(tenant_aurora, usuario_operacional, status='realizada', dias_atras=0)
    _chamada(tenant_aurora, op2, status='realizada', dias_atras=0)

    c = _cliente_web(admin_company)
    todos = _corpo_tabela_produtividade(c.get('/relatorios/?periodo=30').content.decode())
    assert 'Oper Aurora' in todos and 'Oper Dois' in todos

    filtrado = _corpo_tabela_produtividade(
        c.get(f'/relatorios/?periodo=30&operador={usuario_operacional.id}').content.decode())
    assert 'Oper Aurora' in filtrado
    assert 'Oper Dois' not in filtrado

    # id de outro tenant não vaza para a seleção
    invalido = _corpo_tabela_produtividade(
        c.get(f'/relatorios/?periodo=30&operador={usuario_operacional_beta.id}').content.decode())
    assert 'Oper Aurora' in invalido and 'Oper Dois' in invalido


# --- Comando enviar_relatorio (S7+) ---

@pytest.mark.django_db
def test_comando_enviar_relatorio_simulacao(tenant_aurora, admin_company):
    """Sem SMTP o comando roda em simulação e informa o que enviaria."""
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command('enviar_relatorio', '--tenant', str(tenant_aurora.pk), stdout=out)
    saida = out.getvalue()
    assert 'SIMULAÇÃO' in saida
    assert 'dona@aurora.com' in saida
    assert 'relatorio-gerencial' in saida


@pytest.mark.django_db
def test_comando_enviar_relatorio_smtp(tenant_aurora, admin_company):
    """Com SMTP configurado o comando envia o PDF anexado aos admins."""
    from io import StringIO

    from django.core.mail import outbox
    from django.core.management import call_command
    from django.test import override_settings

    with override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        EMAIL_HOST='smtp.exemplo.com.br',
        EMAIL_CONFIGURADO=True,
    ):
        call_command('enviar_relatorio', '--tenant', str(tenant_aurora.pk), stdout=StringIO())

    assert len(outbox) == 1
    assert 'dona@aurora.com' in outbox[0].to
    assert 'Relatório gerencial' in outbox[0].subject
    assert outbox[0].attachments  # PDF anexado
    conteudo_anexo = str(outbox[0].attachments[0][1])
    assert '%PDF' in conteudo_anexo
