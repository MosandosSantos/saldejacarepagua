"""Testes da Fase A (funil de vendas) — telefone normalizado, dedup, histórico e negócios."""

import pytest

from contatos.forms import ContatoForm
from contatos.models import Contato, Movimentacao, Negocio, criar_negocio, registrar_movimentacao


def _contato_com_negocio(nome, tenant, stage='interessado', valor=0, **kwargs):
    """Cria contato + negócio via factory (igual ao app): o primeiro vira o principal."""
    seg = kwargs.pop('seg', '')
    contato = Contato.objects.create(nome=nome, seg=seg, tenant=tenant, **kwargs)
    criar_negocio(contato, stage=stage, valor=valor, tenant_id=tenant.id)
    return contato


@pytest.mark.django_db
def test_save_normaliza_telefone(tenant_aurora):
    contato = Contato.objects.create(nome='Ana', tel='(11) 99999-8888', seg='', tenant=tenant_aurora)
    assert contato.tel_normalizado == '11999998888'


@pytest.mark.django_db
def test_importacao_grava_tel_normalizado(tenant_aurora):
    from contatos.importador import importar_linhas

    cab = ['Nome', 'Telefone']
    importar_linhas(cab, [['Ana', '(11) 99999-7777']], {'nome': 0, 'tel': 1}, tenant_aurora.id)
    contato = Contato.objects.get(nome='Ana')
    assert contato.tel_normalizado == '11999997777'
    assert contato.negocio.stage == 'interessado'


def _dados_form(tel):
    return {
        'nome': 'Novo', 'empresa': 'Empresa X', 'tel': tel, 'email': 'novo@x.com',
        'seg': 'estetica', 'stage': 'interessado', 'valor': '0',
        'origem': 'Instagram', 'pagamento': 'Particular',
        'procedimento': 'Laser', 'ultima_consulta': '2026-01-01',
    }


@pytest.mark.django_db
def test_form_bloqueia_telefone_duplicado(tenant_aurora):
    _contato_com_negocio('Existente', tenant_aurora, tel='(11) 99999-1111')
    form = ContatoForm(data=_dados_form('(11) 99999-1111'), nicho='saude', tenant_id=tenant_aurora.id)
    assert not form.is_valid()
    assert 'tel' in form.errors


@pytest.mark.django_db
def test_form_aceita_telefone_de_outro_tenant(tenant_aurora, tenant_beta):
    _contato_com_negocio('Existente', tenant_beta, tel='(11) 99999-1111')
    form = ContatoForm(data=_dados_form('(11) 99999-1111'), nicho='saude', tenant_id=tenant_aurora.id)
    assert form.is_valid()


@pytest.mark.django_db
def test_registrar_movimentacao(tenant_aurora, usuario_operacional):
    negocio = _contato_com_negocio('Ana', tenant_aurora).negocio
    mv = registrar_movimentacao(negocio, 'interessado', 'fechado', usuario_operacional.id)
    assert mv.de_stage == 'interessado'
    assert mv.para_stage == 'fechado'
    assert mv.autor_id == usuario_operacional.id
    assert negocio.movimentacoes.count() == 1


@pytest.mark.django_db
def test_registrar_movimentacao_ignora_sem_mudanca(tenant_aurora):
    negocio = _contato_com_negocio('Ana', tenant_aurora).negocio
    assert registrar_movimentacao(negocio, 'interessado', 'interessado', None) is None
    assert Movimentacao.objects.count() == 0


def _sessao_web(client, usuario):
    """Simula o login por sessão usado nas views web."""
    s = client.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {
        'nome': usuario.nome, 'email': usuario.email,
        'role': usuario.role, 'tenant_id': usuario.tenant_id,
    }
    s['nicho'] = 'saude'
    s.save()


@pytest.mark.django_db
def test_mover_ajax_atualiza_board(tenant_aurora, usuario_operacional):
    from django.test import Client

    contato = _contato_com_negocio('Ana', tenant_aurora, stage='interessado', valor=100)
    c = Client()
    _sessao_web(c, usuario_operacional)
    # a URL do funil move o NEGÓCIO (pk = id do negocio, não do contato)
    resp = c.post(
        f'/funil/{contato.negocio.id}/mover/', {'stage': 'fechado'},
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
    )
    assert resp.status_code == 200
    dados = resp.json()
    assert dados['ok'] is True
    colunas = {col['key']: col for col in dados['colunas']}
    assert colunas['interessado']['count'] == 0
    assert colunas['fechado']['count'] == 1
    assert colunas['fechado']['soma'] == 'R$ 100'
    contato.refresh_from_db()
    assert contato.negocio.stage == 'fechado'
    assert contato.negocio.movimentacoes.count() == 1
    assert contato.negocio.movimentacoes.first().para_stage == 'fechado'


@pytest.mark.django_db
def test_dashboard_renderiza_analise(tenant_aurora, usuario_operacional):
    from django.test import Client

    _contato_com_negocio('Ana', tenant_aurora, stage='interessado', valor=1000,
                         origem='Instagram', seg='estetica')
    _contato_com_negocio('Bia', tenant_aurora, stage='fechado', valor=2000,
                         origem='Google', seg='estetica')
    c = Client()
    _sessao_web(c, usuario_operacional)
    resp = c.get('/dashboard/')
    assert resp.status_code == 200
    html = resp.content.decode('utf-8')
    assert 'Análise do funil' in html
    assert 'Ticket médio' in html
    assert 'Instagram' in html


@pytest.mark.django_db(transaction=True)
def test_api_cria_negocio_para_contato(client, headers_operacional):
    resp = client.post('/api/v1/contatos', headers=headers_operacional, json={
        'nome': 'Ana Souza', 'seg': 'estetica', 'stage': 'orcamento', 'valor': 2500,
    })
    assert resp.status_code == 201
    contato = Contato.objects.get(pk=resp.json()['id'])
    assert contato.negocio.stage == 'orcamento'
    assert contato.negocio.valor == 2500
    assert contato.negocio.updated_at is not None


@pytest.mark.django_db
def test_form_web_cria_e_atualiza_negocio(tenant_aurora, usuario_operacional):
    from django.test import Client

    c = Client()
    _sessao_web(c, usuario_operacional)

    # criação via formulário web
    resp = c.post('/contatos/novo/', _dados_form('(11) 97777-6666'))
    assert resp.status_code == 302
    contato = Contato.objects.get(nome='Novo')
    assert contato.negocio.stage == 'interessado'

    # edição muda etapa e valor do negócio + grava histórico
    dados = _dados_form('(11) 97777-6666')
    dados['stage'] = 'fechado'
    dados['valor'] = '500'
    resp = c.post(f'/contatos/{contato.id}/editar/', dados)
    assert resp.status_code == 302
    contato.refresh_from_db()
    assert contato.negocio.stage == 'fechado'
    assert float(contato.negocio.valor) == 500
    assert contato.negocio.movimentacoes.count() == 2  # criação + mudança


# --- Múltiplos negócios por contato (multi-deal) ---


@pytest.mark.django_db
def test_primeiro_negocio_e_principal(tenant_aurora):
    contato = _contato_com_negocio('Ana', tenant_aurora, stage='interessado', valor=100)
    assert contato.negocio is not None
    assert contato.negocio.principal is True
    assert contato.stage == 'interessado'
    assert float(contato.valor) == 100


@pytest.mark.django_db
def test_segundo_negocio_nao_vira_principal(tenant_aurora):
    contato = _contato_com_negocio('Ana', tenant_aurora, stage='interessado', valor=100)
    principal_antes = contato.negocio
    segundo = criar_negocio(contato, stage='orcamento', valor=500, tenant_id=tenant_aurora.id)
    assert segundo.principal is False
    # o principal continua sendo o primeiro
    contato.refresh_from_db()
    assert contato.negocio.id == principal_antes.id
    assert contato.negocios.count() == 2


@pytest.mark.django_db
def test_tornar_principal_remarca_os_demais(tenant_aurora):
    from contatos.models import tornar_principal

    contato = _contato_com_negocio('Ana', tenant_aurora, stage='interessado', valor=100)
    segundo = criar_negocio(contato, stage='orcamento', valor=500, tenant_id=tenant_aurora.id)
    tornar_principal(segundo)
    contato.refresh_from_db()
    assert contato.negocio.id == segundo.id
    assert contato.negocios.filter(principal=True).count() == 1
    assert contato.negocio.principal is True


@pytest.mark.django_db
def test_primeiro_negocio_pela_view_e_principal(tenant_aurora, usuario_operacional):
    from django.test import Client

    contato = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    c = Client()
    _sessao_web(c, usuario_operacional)
    r = c.post(f'/contatos/{contato.id}/negocios/novo/', {
        'titulo': 'Deal 1', 'stage': 'interessado', 'valor': '100',
    })
    assert r.status_code == 302
    assert contato.negocios.count() == 1
    assert contato.negocios.get().principal is True


@pytest.mark.django_db
def test_funil_move_negocio_nao_principal(tenant_aurora, usuario_operacional):
    from django.test import Client

    contato = _contato_com_negocio('Ana', tenant_aurora, stage='interessado', valor=100)
    segundo = criar_negocio(contato, stage='interessado', valor=500, tenant_id=tenant_aurora.id)
    c = Client()
    _sessao_web(c, usuario_operacional)
    resp = c.post(
        f'/funil/{segundo.id}/mover/', {'stage': 'fechado'},
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
    )
    assert resp.status_code == 200
    segundo.refresh_from_db()
    assert segundo.stage == 'fechado'
    # o negócio principal não foi afetado
    contato.refresh_from_db()
    assert contato.negocio.stage == 'interessado'


@pytest.mark.django_db
def test_dashboard_movimentacoes_isoladas_por_tenant(tenant_aurora, tenant_beta, usuario_operacional):
    from django.test import Client

    c_beta = _contato_com_negocio('Beta Cliente', tenant_beta)
    registrar_movimentacao(c_beta.negocio, 'interessado', 'fechado', None)
    c_aurora = _contato_com_negocio('Aurora Cliente', tenant_aurora)
    registrar_movimentacao(c_aurora.negocio, 'interessado', 'fechado', None)

    c = Client()
    _sessao_web(c, usuario_operacional)
    resp = c.get('/dashboard/')
    assert resp.status_code == 200
    html = resp.content.decode('utf-8')
    assert 'Aurora Cliente' in html
    assert 'Beta Cliente' not in html
