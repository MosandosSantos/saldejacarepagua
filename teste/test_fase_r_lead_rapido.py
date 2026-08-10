"""Testes do cadastro rápido de lead no funil + completude de perfil (contato rico x pobre)."""

import re

import pytest
from django.test import Client

from contatos.models import Contato, Negocio, Tag, criar_negocio
from contatos.scoring import completude_do_contato


def _token_do_dom(html):
    """Extrai o token CSRF do HTML renderizado (como o JS do kanban faz)."""
    achados = re.findall(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    return achados[0] if achados else ''


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


# --- Completude do perfil (rico x pobre) ---

@pytest.mark.django_db
def test_contato_minimo_e_pobre(tenant_aurora):
    c = Contato.objects.create(nome='Só Nome', tenant=tenant_aurora)
    criar_negocio(c, tenant_id=tenant_aurora.id)
    comp = completude_do_contato(c)
    assert comp['nivel'] == 'pobre'
    assert comp['total'] < 35
    assert 'Telefone' in comp['faltam']
    assert 'E-mail' in comp['faltam']


@pytest.mark.django_db
def test_contato_completo_e_rico(tenant_aurora):
    c = Contato.objects.create(
        nome='Rica', tel='(11) 99999-0000', email='rica@x.com', seg='odonto',
        empresa='Empresa X', procedimento='Laser', origem='Indicação', cidade='SP',
        nascimento='1990-01-01', observacoes='Cliente antiga', tenant=tenant_aurora,
    )
    criar_negocio(c, valor=3000, tenant_id=tenant_aurora.id)
    tag = Tag.objects.create(nome='VIP', tenant=tenant_aurora)
    c.tags.add(tag)
    comp = completude_do_contato(c)
    assert comp['nivel'] == 'rico'
    assert comp['total'] >= 70
    assert comp['faltam'] == []


# --- Cadastro rápido de lead ---

@pytest.mark.django_db
def test_cadastro_rapido_cria_contato_pobre_e_negocio(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    # payload mínimo (só o essencial) → o lead nasce com perfil básico (contato pobre)
    r = c.post('/funil/novo-lead/', {
        'nome': 'Maria Lead', 'tel': '(11) 98888-7777',
        'stage': 'interessado', 'valor': '', 'origem': '',
    })
    assert r.status_code == 200
    dados = r.json()
    assert dados['ok'] is True
    assert dados['coluna'] == 'interessado'

    contato = Contato.objects.get(nome='Maria Lead')
    assert contato.tenant_id == tenant_aurora.id
    assert contato.tel == '(11) 98888-7777'
    assert contato.origem == '—'

    negocio = Negocio.objects.get(contato=contato)
    assert negocio.stage == 'interessado'
    assert float(negocio.valor) == 0
    assert negocio.principal is True  # primeiro negócio vira o principal
    assert negocio.responsavel_id == usuario_operacional.id  # dono do cadastro

    # o lead nasce com perfil básico (poucos dados — contato pobre)
    assert completude_do_contato(contato)['nivel'] == 'pobre'

    # o cartão renderizado volta pronto para o kanban inserir
    assert 'Maria Lead' in dados['html']
    assert 'kanban-card' in dados['html']


@pytest.mark.django_db
def test_cadastro_rapido_grava_campos_opcionais(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.post('/funil/novo-lead/', {
        'nome': 'Joana', 'tel': '(11) 97777-1234', 'email': 'joana@x.com',
        'stage': 'orcamento', 'valor': '1.500,00', 'origem': 'Instagram',
    })
    assert r.status_code == 200
    assert r.json()['ok'] is True
    contato = Contato.objects.get(nome='Joana')
    assert contato.email == 'joana@x.com'
    assert contato.origem == 'Instagram'
    negocio = Negocio.objects.get(contato=contato)
    assert negocio.stage == 'orcamento'
    assert float(negocio.valor) == 1500.00
    # com telefone + e-mail + origem + valor, o perfil evolui de básico para médio
    assert completude_do_contato(contato)['nivel'] == 'medio'


@pytest.mark.django_db
def test_cadastro_rapido_aparece_no_kanban(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    c.post('/funil/novo-lead/', {'nome': 'João Rápido', 'stage': 'interessado'})
    r = c.get('/funil/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'João Rápido' in html
    # o botão de novo lead aparece para quem pode editar
    assert 'btn-novo-lead' in html
    assert 'modal-novo-lead' in html


@pytest.mark.django_db
def test_kanban_viewer_nao_ve_botao_nem_modal(tenant_aurora, usuario_viewer):
    c = _cliente_web(usuario_viewer)
    r = c.get('/funil/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'btn-novo-lead' not in html
    assert 'modal-novo-lead' not in html


@pytest.mark.django_db
def test_kanban_renderiza_token_csrf_e_modal_para_quem_edita(tenant_aurora, usuario_operacional):
    """O kanban precisa expor um token CSRF no DOM para os POSTs AJAX (mover/novo lead).

    Regressão: quando o modal ficava fora do bloco, o token era perdido e o
    drag & drop falhava com 'CSRF token missing' (403).
    """
    c = _cliente_web(usuario_operacional)
    html = c.get('/funil/').content.decode()
    assert _token_do_dom(html) != ''
    assert 'id="modal-novo-lead"' in html
    assert 'id="form-novo-lead"' in html


@pytest.mark.django_db
def test_kanban_mover_lead_passa_verificacao_csrf(tenant_aurora, usuario_operacional):
    """Move um lead com verificação CSRF real (como o navegador): token do DOM + cookie."""
    contato = Contato.objects.create(nome='Lead', tel='(11) 98888-0000', tenant=tenant_aurora)
    negocio = criar_negocio(contato, stage='interessado', valor=100, tenant_id=tenant_aurora.id)

    c = Client(enforce_csrf_checks=True)
    s = c.session
    s['usuario_id'] = usuario_operacional.id
    s['usuario'] = {'nome': usuario_operacional.nome, 'email': usuario_operacional.email,
                    'role': usuario_operacional.role, 'tenant_id': usuario_operacional.tenant_id}
    s.save()

    html = c.get('/funil/').content.decode()
    token = _token_do_dom(html)
    assert token != ''
    r = c.post(f'/funil/{negocio.id}/mover/', {'stage': 'orcamento'},
               HTTP_X_CSRFTOKEN=token, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert r.status_code == 200
    negocio.refresh_from_db()
    assert negocio.stage == 'orcamento'


@pytest.mark.django_db
def test_cadastro_rapido_sem_nome_rejeita(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.post('/funil/novo-lead/', {'stage': 'interessado'})
    assert r.status_code == 400
    dados = r.json()
    assert dados['ok'] is False
    assert any('nome' in e.lower() for e in dados['erros'])
    assert not Contato.objects.exists()


@pytest.mark.django_db
def test_cadastro_rapido_etapa_invalida_rejeita(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.post('/funil/novo-lead/', {'nome': 'X', 'stage': 'etapa-inexistente'})
    assert r.status_code == 400
    assert not Contato.objects.exists()


@pytest.mark.django_db
def test_cadastro_rapido_valor_invalido_rejeita(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.post('/funil/novo-lead/', {'nome': 'X', 'stage': 'interessado', 'valor': 'abc'})
    assert r.status_code == 400
    assert any('valor' in e.lower() for e in r.json()['erros'])
    assert not Contato.objects.exists()


@pytest.mark.django_db
def test_cadastro_rapido_telefone_duplicado_rejeita(tenant_aurora, usuario_operacional):
    Contato.objects.create(nome='Existe', tel='(11) 99999-0000', tenant=tenant_aurora)
    c = _cliente_web(usuario_operacional)
    r = c.post('/funil/novo-lead/', {'nome': 'Duplicado', 'tel': '11999990000', 'stage': 'interessado'})
    assert r.status_code == 400
    assert 'telefone' in r.json()['erros'][0].lower()
    assert not Contato.objects.filter(nome='Duplicado').exists()


@pytest.mark.django_db
def test_cadastro_rapido_viewer_bloqueado(tenant_aurora, usuario_viewer):
    c = _cliente_web(usuario_viewer)
    r = c.post('/funil/novo-lead/', {'nome': 'X', 'stage': 'interessado'})
    assert r.status_code == 302  # sem permissão de edição → redirecionado
    assert not Contato.objects.exists()


@pytest.mark.django_db
def test_cadastro_rapido_nao_logado_redireciona_para_login():
    r = Client().post('/funil/novo-lead/', {'nome': 'X', 'stage': 'interessado'})
    assert r.status_code == 302
    assert '/login/' in r.url


# --- Relatório de leads pobres + coluna Perfil na lista ---

@pytest.mark.django_db
def test_relatorio_leads_pobres_lista_so_pobres(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    c.post('/funil/novo-lead/', {'nome': 'Pobre Ana', 'stage': 'interessado'})
    Contato.objects.create(
        nome='Rica Bia', tel='(11) 91111-0000', email='bia@x.com', seg='odonto',
        empresa='Empresa', cidade='SP', tenant=tenant_aurora,
    )
    r = c.get('/contatos/leads-pobres/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Pobre Ana' in html       # perfil básico aparece
    assert 'Rica Bia' not in html    # perfil médio/rico não aparece
    assert 'Completar perfil' in html


@pytest.mark.django_db
def test_relatorio_leads_pobres_vazio(tenant_aurora, usuario_operacional):
    Contato.objects.create(
        nome='Rica', tel='(11) 91111-0000', email='rica@x.com', seg='odonto',
        empresa='Empresa', cidade='SP', tenant=tenant_aurora,
    )
    c = _cliente_web(usuario_operacional)
    r = c.get('/contatos/leads-pobres/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Nenhum lead pobre' in html


@pytest.mark.django_db
def test_lista_contatos_mostra_coluna_perfil_e_link(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    c.post('/funil/novo-lead/', {'nome': 'Pobre Caio', 'stage': 'interessado'})
    r = c.get('/contatos/')
    assert r.status_code == 200
    html = r.content.decode()
    assert '>Perfil<' in html                                  # cabeçalho da coluna
    assert 'leads-pobres' in html                              # link para o relatório
    assert 'Leads pobres (1)' in html
    assert 'Pobre Caio' in html


@pytest.mark.django_db
def test_kanban_coluna_tem_botao_plus(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.get('/funil/')
    html = r.content.decode()
    assert 'btn-lead-coluna' in html
    assert 'data-etapa="interessado"' in html


@pytest.mark.django_db
def test_kanban_viewer_nao_ve_botao_plus_por_coluna(tenant_aurora, usuario_viewer):
    c = _cliente_web(usuario_viewer)
    html = c.get('/funil/').content.decode()
    assert 'btn-lead-coluna' not in html


# --- Abas por nível no relatório + foco nos campos faltantes ---

@pytest.mark.django_db
def test_relatorio_abas_filtram_por_nivel(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    c.post('/funil/novo-lead/', {'nome': 'Pobre Ana', 'stage': 'interessado'})
    Contato.objects.create(
        nome='Media Bia', tel='(11) 92222-0000', email='bia@x.com', seg='odonto',
        empresa='Empresa', cidade='SP', tenant=tenant_aurora,
    )  # 15+15+10+10+10 = 60 → médio

    # aba padrão (pobre): só a pobre
    html = c.get('/contatos/leads-pobres/').content.decode()
    assert 'Pobre Ana' in html and 'Media Bia' not in html

    # aba média: só a média
    html2 = c.get('/contatos/leads-pobres/?nivel=medio').content.decode()
    assert 'Media Bia' in html2 and 'Pobre Ana' not in html2

    # abas renderizam com contagens
    assert 'Pobre' in html and 'Médio' in html and 'Completo' in html


@pytest.mark.django_db
def test_relatorio_completar_leva_foco_aos_campos_faltantes(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    c.post('/funil/novo-lead/', {'nome': 'Pobre Ana', 'stage': 'interessado'})
    html = c.get('/contatos/leads-pobres/').content.decode()
    assert '?focar=' in html
    assert 'Completar perfil' in html


@pytest.mark.django_db
def test_form_edicao_renderiza_script_de_foco(tenant_aurora, usuario_operacional):
    contato = Contato.objects.create(nome='Pobre', tenant=tenant_aurora)
    c = _cliente_web(usuario_operacional)
    r = c.get(f'/contatos/{contato.id}/editar/?focar=Telefone,E-mail')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'MAPA_FOCAR' in html           # script de foco presente na edição
    assert 'focar-destaque' in html       # destaque visual
    # sem o parâmetro, o script continua presente mas o link da ficha usa ?focar=
    html2 = c.get(f'/contatos/{contato.id}/').content.decode()
    assert 'Completar perfil' in html2 and 'focar=' in html2
