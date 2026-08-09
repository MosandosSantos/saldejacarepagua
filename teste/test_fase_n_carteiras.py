"""Testes da Fase N — S3 do PRD HAZON (Gestão de bases).

Carteiras (3.1): estrutura, listagem, detalhe, criar/editar/excluir — tudo escopado
por tenant. Cargo no cliente (3.2.7) e associação cliente -> carteira (3.2.2).
CSV associado à carteira (3.3.5) e endpoints da API.
"""

import pytest
from django.test import Client

from acesso.models import Tenant
from contatos.models import Carteira, Contato, Negocio

SENHA = 'senha123'


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


def _criar_usuario(nome, email, role, tenant):
    from acesso.models import Usuario
    from django.contrib.auth.hashers import make_password

    return Usuario.objects.create(
        nome=nome, email=email, role=role, tenant=tenant, senha=make_password(SENHA)
    )


# --- Modelo ---

@pytest.mark.django_db
def test_carteira_escopada_por_tenant(tenant_aurora, tenant_beta):
    c1 = Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    c2 = Carteira.objects.create(nome='Cobrança', tenant=tenant_beta)  # mesmo nome, tenants diferentes
    assert c1.nome == 'Cobrança'
    assert c1.tenant_id == tenant_aurora.id
    assert c2.tenant_id == tenant_beta.id
    assert Carteira.objects.filter(tenant_id=tenant_aurora.id).count() == 1


@pytest.mark.django_db
def test_contato_tem_cargo_e_carteira(tenant_aurora):
    carteira = Carteira.objects.create(nome='Prospecção', tenant=tenant_aurora)
    contato = Contato.objects.create(
        nome='João', empresa='Tech Ltda', tel='(11) 98888-1111', email='joao@tech.com',
        seg='geral', tenant=tenant_aurora, cargo='Diretor', carteira=carteira,
    )
    assert contato.cargo == 'Diretor'
    assert contato.carteira_id == carteira.id
    assert contato.carteira.nome == 'Prospecção'
    assert carteira.contatos.count() == 1


@pytest.mark.django_db
def test_excluir_carteira_mantem_contato(tenant_aurora):
    carteira = Carteira.objects.create(nome='Campanha junho', tenant=tenant_aurora)
    contato = Contato.objects.create(
        nome='Maria', seg='geral', tenant=tenant_aurora, carteira=carteira,
    )
    carteira.delete()
    contato.refresh_from_db()
    assert contato.carteira_id is None  # SET_NULL — contato continua existindo
    assert Contato.objects.count() == 1


# --- Web: listagem e criação ---

@pytest.mark.django_db
def test_lista_carteiras_renderiza(tenant_aurora, admin_company):
    Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    Carteira.objects.create(nome='Prospecção', tenant=tenant_aurora)
    r = _cliente_web(admin_company).get('/contatos/carteiras/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Cobrança' in html
    assert 'Prospecção' in html
    assert 'Nova carteira' in html


@pytest.mark.django_db
def test_criar_carteira_admin(tenant_aurora, admin_company):
    r = _cliente_web(admin_company).post(
        '/contatos/carteiras/', {'nome': 'Cobrança junho', 'descricao': 'Base de junho'}
    )
    assert r.status_code == 200
    carteira = Carteira.objects.get(tenant_id=tenant_aurora.id, nome='Cobrança junho')
    assert carteira.descricao == 'Base de junho'


@pytest.mark.django_db
def test_criar_carteira_sem_nome_da_erro(tenant_aurora, admin_company):
    r = _cliente_web(admin_company).post('/contatos/carteiras/', {'nome': '  '})
    assert r.status_code == 200
    assert 'Informe o nome da carteira'.encode() in r.content
    assert Carteira.objects.count() == 0


@pytest.mark.django_db
def test_criar_carteira_duplicada_no_tenant(tenant_aurora, admin_company):
    Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    r = _cliente_web(admin_company).post('/contatos/carteiras/', {'nome': 'Cobrança'})
    assert 'Já existe uma carteira'.encode() in r.content
    assert Carteira.objects.count() == 1


@pytest.mark.django_db
def test_operacional_nao_cria_carteira(tenant_aurora, usuario_operacional):
    r = _cliente_web(usuario_operacional).post('/contatos/carteiras/', {'nome': 'X'})
    assert r.status_code == 200
    assert Carteira.objects.count() == 0  # POST ignorado (só admin cria)


@pytest.mark.django_db
def test_viewer_ve_carteiras(tenant_aurora, usuario_viewer):
    Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    r = _cliente_web(usuario_viewer).get('/contatos/carteiras/')
    assert r.status_code == 200
    assert 'Nova carteira' not in r.content.decode()  # sem form de criação


@pytest.mark.django_db
def test_isolamento_entre_tenants(tenant_aurora, tenant_beta, admin_company):
    Carteira.objects.create(nome='Só da Aurora', tenant=tenant_aurora)
    Carteira.objects.create(nome='Só da Beta', tenant=tenant_beta)
    html = _cliente_web(admin_company).get('/contatos/carteiras/').content.decode()
    assert 'Só da Aurora' in html
    assert 'Só da Beta' not in html


# --- Web: detalhe, editar e excluir ---

@pytest.mark.django_db
def test_detalhe_lista_contatos_da_carteira(tenant_aurora, admin_company):
    carteira = Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    Contato.objects.create(nome='Ana', seg='geral', tenant=tenant_aurora, carteira=carteira)
    Contato.objects.create(nome='Bia', seg='geral', tenant=tenant_aurora, carteira=carteira)
    # contato de outra carteira não aparece
    outra = Carteira.objects.create(nome='Outra', tenant=tenant_aurora)
    Contato.objects.create(nome='Carla', seg='geral', tenant=tenant_aurora, carteira=outra)
    r = _cliente_web(admin_company).get(f'/contatos/carteiras/{carteira.id}/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Ana' in html and 'Bia' in html
    assert 'Carla' not in html


@pytest.mark.django_db
def test_detalhe_filtra_por_etapa(tenant_aurora, admin_company):
    from funil.models import garantir_etapas

    garantir_etapas(tenant_aurora.id, 'saude')
    carteira = Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    c1 = Contato.objects.create(nome='Ana', seg='geral', tenant=tenant_aurora, carteira=carteira)
    c2 = Contato.objects.create(nome='Bia', seg='geral', tenant=tenant_aurora, carteira=carteira)
    Negocio.objects.create(contato=c1, stage='fechado', valor=100, tenant=tenant_aurora)
    Negocio.objects.create(contato=c2, stage='interessado', valor=0, tenant=tenant_aurora)
    r = _cliente_web(admin_company).get(f'/contatos/carteiras/{carteira.id}/?etapa=fechado')
    html = r.content.decode()
    assert 'Ana' in html
    assert 'Bia' not in html


@pytest.mark.django_db
def test_editar_carteira_admin(tenant_aurora, admin_company):
    carteira = Carteira.objects.create(nome='Antiga', tenant=tenant_aurora)
    r = _cliente_web(admin_company).post(
        f'/contatos/carteiras/{carteira.id}/',
        {'acao': 'editar', 'nome': 'Nova', 'descricao': 'ok'},
    )
    assert r.status_code == 200
    carteira.refresh_from_db()
    assert carteira.nome == 'Nova'
    assert carteira.descricao == 'ok'


@pytest.mark.django_db
def test_excluir_carteira_admin(tenant_aurora, admin_company):
    carteira = Carteira.objects.create(nome='Temporária', tenant=tenant_aurora)
    r = _cliente_web(admin_company).post(
        f'/contatos/carteiras/{carteira.id}/', {'acao': 'excluir'}
    )
    assert r.status_code == 302  # redireciona para a lista
    assert Carteira.objects.count() == 0


@pytest.mark.django_db
def test_carteira_de_outro_tenant_da_404(tenant_aurora, tenant_beta, admin_company):
    carteira_beta = Carteira.objects.create(nome='Da Beta', tenant=tenant_beta)
    r = _cliente_web(admin_company).get(f'/contatos/carteiras/{carteira_beta.id}/')
    assert r.status_code == 404


# --- Formulário do contato ---

@pytest.mark.django_db
def test_formulario_mostra_cargo_e_carteira(tenant_aurora, admin_company):
    Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    html = _cliente_web(admin_company).get('/contatos/novo/').content.decode()
    assert 'Cargo' in html
    assert 'Carteira' in html
    assert 'Cobrança' in html


@pytest.mark.django_db
def test_formulario_salva_cargo_e_carteira(tenant_aurora, admin_company):
    from funil.models import garantir_etapas

    garantir_etapas(tenant_aurora.id, 'saude')
    carteira = Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    r = _cliente_web(admin_company).post('/contatos/novo/', {
        'nome': 'João', 'empresa': 'Tech', 'tel': '(11) 97777-2222', 'email': 'joao@x.com',
        'seg': 'geral', 'stage': 'interessado', 'cargo': 'Diretor', 'carteira': str(carteira.id),
        'ultima_consulta': '2026-01-15', 'procedimento': 'Laser',
    })
    assert r.status_code == 302
    contato = Contato.objects.get(nome='João')
    assert contato.cargo == 'Diretor'
    assert contato.carteira_id == carteira.id


@pytest.mark.django_db
def test_formulario_ficha_mostra_cargo_e_carteira(tenant_aurora, admin_company):
    carteira = Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    contato = Contato.objects.create(
        nome='Ana', seg='geral', tenant=tenant_aurora, cargo='Gerente', carteira=carteira,
    )
    html = _cliente_web(admin_company).get(f'/contatos/{contato.id}/').content.decode()
    assert 'Gerente' in html
    assert 'Cobrança' in html


# --- Lista com filtro por carteira ---

@pytest.mark.django_db
def test_lista_filtra_por_carteira(tenant_aurora, admin_company):
    c1 = Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    Contato.objects.create(nome='Ana', seg='geral', tenant=tenant_aurora, carteira=c1)
    Contato.objects.create(nome='Bia', seg='geral', tenant=tenant_aurora)
    r = _cliente_web(admin_company).get(f'/contatos/?carteira={c1.id}')
    html = r.content.decode()
    assert 'Ana' in html
    assert 'Bia' not in html


# --- Importador CSV com carteira ---

@pytest.mark.django_db
def test_importador_associa_carteira(tenant_aurora, admin_company):
    from contatos.importador import importar_linhas

    carteira = Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    cab = ['Nome', 'Telefone', 'Cargo']
    linhas = [['Ana', '(11) 90000-0001', 'Diretora'], ['Bia', '(11) 90000-0002', '']]
    mapeamento = {'nome': 0, 'tel': 1, 'cargo': 2}
    rel = importar_linhas(cab, linhas, mapeamento, tenant_aurora.id, carteira_id=carteira.id)
    assert rel['importados'] == 2
    ana = Contato.objects.get(nome='Ana')
    bia = Contato.objects.get(nome='Bia')
    assert ana.cargo == 'Diretora'
    assert ana.carteira_id == carteira.id
    assert bia.carteira_id == carteira.id


@pytest.mark.django_db
def test_importador_carteira_de_outro_tenant_descartada(tenant_aurora, tenant_beta, admin_company):
    from contatos.importador import importar_linhas

    carteira_beta = Carteira.objects.create(nome='Da Beta', tenant=tenant_beta)
    cab = ['Nome', 'Telefone']
    linhas = [['Ana', '(11) 90000-0003']]
    rel = importar_linhas(
        cab, linhas, {'nome': 0, 'tel': 1}, tenant_aurora.id,
        carteira_id=carteira_beta.id,
    )
    assert rel['importados'] == 1
    assert Contato.objects.get(nome='Ana').carteira_id is None  # id fora do tenant cai fora


@pytest.mark.django_db
def test_importar_pagina_oferece_seletor_de_carteira(tenant_aurora, admin_company):
    Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    html = _cliente_web(admin_company).get('/contatos/importar/').content.decode()
    assert 'Carteira de destino' in html
    assert 'Cobrança' in html


# --- API ---

def _login(client, usuario):
    from teste.conftest import fazer_login

    return fazer_login(client, usuario.email)


@pytest.mark.django_db(transaction=True)
def test_api_lista_carteiras(client, tenant_aurora, usuario_operacional):
    Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    headers = _login(client, usuario_operacional)
    r = client.get('/api/v1/carteiras', headers=headers)
    assert r.status_code == 200
    dados = r.json()
    assert len(dados) == 1
    assert dados[0]['nome'] == 'Cobrança'


@pytest.mark.django_db(transaction=True)
def test_api_isolamento_carteiras(client, tenant_aurora, tenant_beta, usuario_operacional):
    Carteira.objects.create(nome='Da Beta', tenant=tenant_beta)
    headers = _login(client, usuario_operacional)  # operacional da Aurora
    r = client.get('/api/v1/carteiras', headers=headers)
    assert r.json() == []


@pytest.mark.django_db(transaction=True)
def test_api_cria_carteira(client, tenant_aurora, usuario_operacional):
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/carteiras', json={'nome': 'Prospecção', 'descricao': 'Base'}, headers=headers)
    assert r.status_code == 201
    assert r.json()['nome'] == 'Prospecção'
    assert Carteira.objects.filter(tenant_id=tenant_aurora.id, nome='Prospecção').exists()


@pytest.mark.django_db(transaction=True)
def test_api_carteira_nome_so_espacos_rejeitado(client, tenant_aurora, usuario_operacional):
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/carteiras', json={'nome': '   '}, headers=headers)
    assert r.status_code == 422
    assert Carteira.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_api_viewer_nao_cria_carteira(client, tenant_aurora, usuario_viewer):
    headers = _login(client, usuario_viewer)
    r = client.post('/api/v1/carteiras', json={'nome': 'X'}, headers=headers)
    assert r.status_code == 403
    assert Carteira.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_api_contato_aceita_cargo_e_carteira(client, tenant_aurora, usuario_operacional):
    carteira = Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/contatos', json={
        'nome': 'Ana', 'seg': 'geral', 'stage': 'interessado',
        'cargo': 'Diretora', 'carteira_id': carteira.id,
    }, headers=headers)
    assert r.status_code == 201
    dados = r.json()
    assert dados['cargo'] == 'Diretora'
    assert dados['carteira_id'] == carteira.id


@pytest.mark.django_db(transaction=True)
def test_api_contato_carteira_de_outro_tenant_rejeitada(client, tenant_aurora, tenant_beta, usuario_operacional):
    carteira_beta = Carteira.objects.create(nome='Da Beta', tenant=tenant_beta)
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/contatos', json={
        'nome': 'Ana', 'seg': 'geral', 'stage': 'interessado', 'carteira_id': carteira_beta.id,
    }, headers=headers)
    assert r.status_code == 400  # carteira fora do tenant


@pytest.mark.django_db(transaction=True)
def test_api_exclui_carteira(client, tenant_aurora, usuario_operacional):
    carteira = Carteira.objects.create(nome='Temporária', tenant=tenant_aurora)
    headers = _login(client, usuario_operacional)
    r = client.delete(f'/api/v1/carteiras/{carteira.id}', headers=headers)
    assert r.status_code == 204
    assert Carteira.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_api_exclui_carteira_de_outro_tenant_404(client, tenant_aurora, tenant_beta, usuario_operacional):
    carteira_beta = Carteira.objects.create(nome='Da Beta', tenant=tenant_beta)
    headers = _login(client, usuario_operacional)
    r = client.delete(f'/api/v1/carteiras/{carteira_beta.id}', headers=headers)
    assert r.status_code == 404
    assert Carteira.objects.filter(pk=carteira_beta.id).exists()
