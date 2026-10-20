"""Testes da Fase J — lead scoring, orçamento em PDF e metas por vendedor."""

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from acesso.models import MetaVendedor, token_captura_do_tenant
from contatos.models import Contato, Negocio, criar_negocio
from contatos.scoring import atualizar_score, calcular_score


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


def _dados_form(tel, **kw):
    dados = {
        'nome': 'Novo', 'empresa': 'Empresa X', 'tel': tel, 'email': 'novo@x.com',
        'seg': 'beleza', 'stage': 'suplica', 'valor': '0',
        'origem': 'Instagram', 'pagamento': 'Particular',
        'procedimento': 'Laser', 'ultima_consulta': '2026-01-01',
    }
    dados.update(kw)
    return dados


def _contato(tenant, **kw):
    seg = kw.pop('seg', '')
    nome = kw.pop('nome', 'Ana')
    stage = kw.pop('stage', 'suplica')
    valor = kw.pop('valor', 0)
    c = Contato.objects.create(nome=nome, seg=seg, tenant=tenant, **kw)
    criar_negocio(c, stage=stage, valor=valor, tenant_id=tenant.id)
    return c


# ---------------------------------------------------------------------------
# Lead scoring — cálculo
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_score_calcula_por_origem_segmento_e_contato(tenant_aurora):
    c = _contato(tenant_aurora, origem='Indicação', seg='odonto',
                 email='ana@x.com', tel='(11) 99999-0000')
    r = calcular_score(c)
    # Indicação (10) + odonto (8) + e-mail (5) + telefone (3) + interessado (3)
    assert r['total'] == 29
    assert r['nivel'] == 'morno'
    assert len(r['detalhes']) >= 4


@pytest.mark.django_db
def test_score_sem_dados_e_frio(tenant_aurora):
    c = Contato.objects.create(nome='Frio', seg='', tenant=tenant_aurora)
    r = calcular_score(c)
    assert r['total'] == 0
    assert r['nivel'] == 'frio'


@pytest.mark.django_db
def test_score_negocio_fechado_e_quente(tenant_aurora):
    c = _contato(tenant_aurora, origem='Indicação', seg='odonto',
                 email='ana@x.com', tel='(11) 99999-0000', stage='diploma')
    r = calcular_score(c)
    assert r['total'] >= 40
    assert r['nivel'] == 'quente'


# ---------------------------------------------------------------------------
# Lead scoring — hooks nos pontos de evento
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_contato_novo_web_recebe_score(tenant_aurora, usuario_operacional):
    c = Client()
    _sessao_web(c, usuario_operacional)
    r = c.post('/contatos/novo/', _dados_form('(11) 97777-6666', origem='Indicação', seg='odonto'))
    assert r.status_code == 302
    contato = Contato.objects.get(nome='Novo')
    assert contato.lead_score > 0
    # badge de score aparece na ficha
    html = c.get(f'/contatos/{contato.id}/').content.decode()
    assert '🔥' in html
    assert str(contato.lead_score) in html


@pytest.mark.django_db
def test_nota_aumenta_score(tenant_aurora, usuario_operacional):
    c = _contato(tenant_aurora, origem='Instagram', seg='beleza', email='a@x.com')
    antes = c.lead_score
    cliente = Client()
    _sessao_web(cliente, usuario_operacional)
    cliente.post(f'/contatos/{c.id}/notas/', {'texto': 'Retornou ligação, muito interessada'})
    c.refresh_from_db()
    assert c.lead_score > antes


@pytest.mark.django_db
def test_mover_etapa_atualiza_score_e_kanban(tenant_aurora, usuario_operacional):
    c = _contato(tenant_aurora, origem='Indicação', seg='odonto', email='a@x.com', tel='(11) 90000-1111')
    cliente = Client()
    _sessao_web(cliente, usuario_operacional)
    r = cliente.post(
        f'/recepcao/{c.negocio.id}/mover/', {'stage': 'comunicacao'},
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
    )
    assert r.status_code == 200
    c.refresh_from_db()
    assert c.lead_score > 0
    # card do kanban mostra o nível do score (caixa baixa no template)
    html = cliente.get('/recepcao/').content.decode()
    assert 'quente' in html or 'morno' in html


@pytest.mark.django_db
def test_lista_ordena_por_score(tenant_aurora, usuario_operacional):
    frio = _contato(tenant_aurora, nome='Frio', seg='', origem='Outro')
    quente = _contato(tenant_aurora, nome='Quente', origem='Indicação', seg='odonto',
                      email='q@x.com', tel='(11) 90000-2222', stage='diploma')
    atualizar_score(frio)
    atualizar_score(quente)
    assert quente.lead_score > frio.lead_score
    c = Client()
    _sessao_web(c, usuario_operacional)
    html = c.get('/contatos/?ord=score').content.decode()
    assert html.find('Quente') < html.find('Frio')


@pytest.mark.django_db(transaction=True)
def test_api_cria_contato_atualiza_score(client, headers_operacional):
    resp = client.post('/api/v1/contatos', headers=headers_operacional, json={
        'nome': 'Ana API', 'seg': 'odonto', 'stage': 'comunicacao',
        'valor': 2500, 'origem': 'Indicação',
    })
    assert resp.status_code == 201
    contato = Contato.objects.get(pk=resp.json()['id'])
    assert contato.lead_score > 0


@pytest.mark.django_db
def test_importador_grava_score(tenant_aurora):
    from contatos.importador import importar_linhas

    cab = ['Nome', 'Origem', 'Segmento']
    importar_linhas(cab, [['Bia', 'Indicação', 'Odontologia']],
                    {'nome': 0, 'origem': 1, 'seg': 2}, tenant_aurora.id)
    contato = Contato.objects.get(nome='Bia')
    assert contato.lead_score > 0


@pytest.mark.django_db
def test_captura_lead_grava_score(tenant_aurora):

    token = token_captura_do_tenant(tenant_aurora)
    r = Client().post(f'/captura/{token}/', {'nome': 'Lead Site', 'tel': '(11) 98888-1234'})
    assert r.status_code == 200
    contato = Contato.objects.get(nome='Lead Site')
    assert contato.lead_score > 0  # origem do tenant (Site) pontua


# ---------------------------------------------------------------------------
# Orçamento em PDF
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_orcamento_pdf_gera_documento(tenant_aurora, usuario_operacional):
    c = _contato(tenant_aurora, nome='Ana Orça', origem='Site', valor=1500)
    cliente = Client()
    _sessao_web(cliente, usuario_operacional)
    r = cliente.get(f'/contatos/{c.id}/negocios/{c.negocio.id}/orcamento/')
    assert r.status_code == 200
    assert r['Content-Type'] == 'application/pdf'
    assert r.content[:5] == b'%PDF-'
    assert f'orcamento-{c.id}' in r['Content-Disposition']


@pytest.mark.django_db
def test_orcamento_pdf_viewer_tambem_baixa(tenant_aurora, usuario_viewer):
    c = _contato(tenant_aurora, nome='Ana Viewer', origem='Site', valor=500)
    cliente = Client()
    _sessao_web(cliente, usuario_viewer)
    r = cliente.get(f'/contatos/{c.id}/negocios/{c.negocio.id}/orcamento/')
    assert r.status_code == 200
    assert r.content[:5] == b'%PDF-'


@pytest.mark.django_db
def test_orcamento_pdf_isolado_por_tenant(tenant_aurora, usuario_operacional_beta):
    c = _contato(tenant_aurora, nome='Ana Sigilosa', origem='Site', valor=900)
    cliente = Client()
    _sessao_web(cliente, usuario_operacional_beta)
    r = cliente.get(f'/contatos/{c.id}/negocios/{c.negocio.id}/orcamento/')
    assert r.status_code == 404  # não vaza o orçamento de outro tenant


def test_parcelas_fecham_o_total():
    from contatos.orcamento import _parcelas

    opcoes = _parcelas(1000)
    assert len(opcoes) == 3
    for n, base, ultima in opcoes:
        assert base * (n - 1) + ultima == 1000
    # valor quebrado não perde centavos
    for n, base, ultima in _parcelas(1234.56):
        assert base * (n - 1) + ultima == Decimal('1234.56')


# ---------------------------------------------------------------------------
# Metas por vendedor
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_define_meta_do_vendedor(tenant_aurora, admin_company, usuario_operacional):
    c = Client()
    _sessao_web(c, admin_company)
    mes = date.today().replace(day=1)
    r = c.post('/config/', {
        'acao': 'metas_vendedores',
        'mes': mes.isoformat(),
        f'meta_{usuario_operacional.id}': '30.000,00',
    })
    assert r.status_code == 200
    meta = MetaVendedor.objects.get(usuario=usuario_operacional, mes=mes)
    assert float(meta.valor) == 30000.0
    assert 'atualizadas' in r.content.decode()


@pytest.mark.django_db
def test_esvaziar_meta_remove(tenant_aurora, admin_company, usuario_operacional):
    mes = date.today().replace(day=1)
    MetaVendedor.objects.create(usuario=usuario_operacional, mes=mes, valor=1000)
    c = Client()
    _sessao_web(c, admin_company)
    c.post('/config/', {
        'acao': 'metas_vendedores', 'mes': mes.isoformat(),
        f'meta_{usuario_operacional.id}': '',
    })
    assert not MetaVendedor.objects.filter(usuario=usuario_operacional, mes=mes).exists()


@pytest.mark.django_db
def test_operacional_nao_define_metas(tenant_aurora, usuario_operacional):
    c = Client()
    _sessao_web(c, usuario_operacional)
    mes = date.today().replace(day=1)
    c.post('/config/', {
        'acao': 'metas_vendedores', 'mes': mes.isoformat(),
        f'meta_{usuario_operacional.id}': '1000',
    })
    assert not MetaVendedor.objects.exists()


@pytest.mark.django_db
def test_negocio_form_grava_responsavel(tenant_aurora, usuario_operacional, admin_company):
    c = Client()
    _sessao_web(c, admin_company)
    contato = Contato.objects.create(nome='Ana Deal', seg='', tenant=tenant_aurora)
    r = c.post(f'/contatos/{contato.id}/negocios/novo/', {
        'titulo': 'Deal com vendedor', 'stage': 'suplica', 'valor': '800',
        'responsavel': str(usuario_operacional.id),
    })
    assert r.status_code == 302
    negocio = Negocio.objects.get(contato=contato)
    assert negocio.responsavel_id == usuario_operacional.id


@pytest.mark.django_db
def test_dashboard_mostra_atingimento_da_meta(tenant_aurora, usuario_operacional, admin_company):
    mes = date.today().replace(day=1)
    MetaVendedor.objects.create(usuario=usuario_operacional, mes=mes, valor=500)
    c = _contato(tenant_aurora, nome='Cliente Fechou', origem='Site', valor=600)
    negocio = c.negocio  # uma única instância (a property refaz a query a cada acesso)
    negocio.stage = 'diploma'
    negocio.responsavel = usuario_operacional
    negocio.save()

    cliente = Client()
    _sessao_web(cliente, admin_company)
    html = cliente.get('/dashboard/').content.decode()
    assert 'Metas dos vendedores' in html
    assert usuario_operacional.nome in html
    assert 'meta batida' in html  # 600 vendido > 500 meta


@pytest.mark.django_db
def test_metas_isoladas_por_tenant(tenant_aurora, tenant_beta, usuario_operacional_beta):
    from teste.conftest import criar_usuario

    mes = date.today().replace(day=1)
    # membro + meta do tenant beta
    MetaVendedor.objects.create(usuario=usuario_operacional_beta, mes=mes, valor=500)
    # membro + meta do tenant aurora — não pode vazar para o beta
    oper_aurora = criar_usuario('Oper Aurora', 'oper2@x.com', 'operacional', tenant_aurora)
    MetaVendedor.objects.create(usuario=oper_aurora, mes=mes, valor=900)
    dona_beta = criar_usuario('Dona Beta', 'beta2@x.com', 'admin_company', tenant_beta)

    cliente = Client()
    _sessao_web(cliente, dona_beta)
    html = cliente.get('/dashboard/').content.decode()
    assert 'Metas dos vendedores' in html
    assert usuario_operacional_beta.nome in html
    assert 'Oper Aurora' not in html  # vendedor de outro tenant não aparece


@pytest.mark.django_db
def test_orcamento_pdf_suporta_nome_com_e_comercial(tenant_aurora, usuario_operacional):
    # o Paragraph do reportlab interpreta XML — `&` e `<` não podem quebrar o PDF
    c = _contato(tenant_aurora, nome='Dentária & Cia <Teste>', empresa='M & M',
                 origem='Site', valor=1500)
    c.observacoes = 'Desconto de 5% & condições especiais'
    c.save()
    cliente = Client()
    _sessao_web(cliente, usuario_operacional)
    r = cliente.get(f'/contatos/{c.id}/negocios/{c.negocio.id}/orcamento/')
    assert r.status_code == 200
    assert r.content[:5] == b'%PDF-'
