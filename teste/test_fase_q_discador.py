"""Testes da Fase Q — S5 do PRD HAZON (Nation Dialer).

Fila (5.1): estrutura, contatos da carteira, ordenação e tela do operador.
Softphone (5.2): URI sip:/tel: a partir da configuração do tenant, ação de
chamada com registro de Chamada e resultado. Script (5.3): CRUD e exibição
na tela do operador. Tudo escopado por tenant; API incluída.
"""

import pytest
from django.test import Client

from acesso.models import Tenant
from contatos.models import Carteira, Contato
from discador.models import Chamada, Fila, Script
from discador.softphone import config_softphone, uri_chamada

SENHA = 'senha123'


@pytest.fixture(autouse=True)
def _softphone_aurora(tenant_aurora):
    """Configura o domínio SIP do tenant Aurora (padrão esperado nas URIs)."""
    tenant_aurora.softphone_dominio = 'sip.empresa.com.br'
    tenant_aurora.save(update_fields=['softphone_dominio'])


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


def _carteira(tenant, nome='Cobrança'):
    return Carteira.objects.create(nome=nome, tenant=tenant)


def _contato(tenant, nome='Ana', tel='(11) 98888-7777', carteira=None, score=0):
    c = Contato.objects.create(
        nome=nome, empresa='Empresa X', tel=tel, email=f'{nome}@x.com',
        seg='geral', tenant=tenant, cargo='Gerente', lead_score=score,
    )
    if carteira:
        c.carteira = carteira
        c.save(update_fields=['carteira'])
    return c


def _script(tenant, nome='Cobrança amigável'):
    return Script.objects.create(
        tenant=tenant, nome=nome, conteudo='- Situação: entender\n- Problema: dor\n- Necessidade: solução',
    )


def _fila(tenant, carteira=None, script=None, ordem='score'):
    return Fila.objects.create(nome='Fila 1', tenant=tenant, carteira=carteira, script=script, ordem=ordem)


# --- Modelo e softphone ---

@pytest.mark.django_db
def test_fila_escopada_por_tenant(tenant_aurora, tenant_beta):
    f1 = _fila(tenant_aurora)
    f2 = Fila.objects.create(nome='Fila 1', tenant=tenant_beta)
    assert f1.tenant_id == tenant_aurora.id
    assert f2.tenant_id == tenant_beta.id
    assert Fila.objects.filter(tenant_id=tenant_aurora.id).count() == 1


@pytest.mark.django_db
def test_contatos_da_fila_vem_da_carteira(tenant_aurora):
    carteira = _carteira(tenant_aurora)
    fora = _contato(tenant_aurora, nome='Fora')
    dentro = _contato(tenant_aurora, nome='Dentro', carteira=carteira)
    fila = _fila(tenant_aurora, carteira=carteira)
    ids = list(fila.contatos().values_list('id', flat=True))
    assert dentro.id in ids
    assert fora.id not in ids


@pytest.mark.django_db
def test_fila_sem_carteira_usa_todos_com_telefone(tenant_aurora):
    _contato(tenant_aurora, nome='Com tel')
    sem_tel = _contato(tenant_aurora, nome='Sem tel', tel='—')
    fila = _fila(tenant_aurora)
    ids = list(fila.contatos().values_list('id', flat=True))
    assert len(ids) == 1
    assert sem_tel.id not in ids


@pytest.mark.django_db
def test_fila_ordena_por_score(tenant_aurora):
    _contato(tenant_aurora, nome='Frio', score=5)
    _contato(tenant_aurora, nome='Quente', score=60)
    fila = _fila(tenant_aurora)
    nomes = list(fila.contatos().values_list('nome', flat=True))
    assert nomes == ['Quente', 'Frio']


@pytest.mark.django_db
def test_uri_sip_com_dominio_do_tenant(tenant_aurora):
    contato = _contato(tenant_aurora)
    assert uri_chamada(contato, tenant_aurora) == 'sip:+11988887777@sip.empresa.com.br'


@pytest.mark.django_db
def test_uri_sem_dominio_cai_em_tel(tenant_aurora):
    tenant = Tenant.objects.create(nome='Sem sip', slug='sem-sip-1', softphone_dominio='')
    contato = _contato(tenant)
    assert uri_chamada(contato, tenant) == 'tel:+11988887777'


@pytest.mark.django_db
def test_uri_sem_telefone_vazia(tenant_aurora):
    contato = _contato(tenant_aurora, tel='—')
    assert uri_chamada(contato, tenant_aurora) == ''


@pytest.mark.django_db
def test_config_softphone_usado_pela_uri(tenant_aurora):
    schema, dominio = config_softphone(tenant_aurora)
    assert schema == 'sip'
    assert dominio == 'sip.empresa.com.br'


# --- Web: tela do operador ---

@pytest.mark.django_db
def test_operador_renderiza_contatos_da_fila(tenant_aurora, admin_company, usuario_operacional):
    carteira = _carteira(tenant_aurora)
    c = _contato(tenant_aurora, nome='Ana Ligada', carteira=carteira)
    fila = _fila(tenant_aurora, carteira=carteira)
    html = _cliente_web(usuario_operacional).get(f'/discador/?fila={fila.id}').content.decode()
    assert 'Ana Ligada' in html
    assert 'Empresa X' in html
    assert 'Gerente' in html  # cargo exibido (5.1.4)
    assert str(c.lead_score) in html


@pytest.mark.django_db
def test_operador_preserva_ordem_da_fila(tenant_aurora, usuario_operacional):
    _contato(tenant_aurora, nome='Frio', score=5)
    _contato(tenant_aurora, nome='Quente', score=60)
    fila = _fila(tenant_aurora)
    html = _cliente_web(usuario_operacional).get(f'/discador/?fila={fila.id}').content.decode()
    assert html.index('Quente') < html.index('Frio')  # ordem configurada preservada


@pytest.mark.django_db
def test_chamar_contato_id_invalido_da_400(tenant_aurora, usuario_operacional):
    fila = _fila(tenant_aurora)
    r = _cliente_web(usuario_operacional).post(
        f'/discador/fila/{fila.id}/chamar/', data='{"contato_id": "abc"}',
        content_type='application/json')
    assert r.status_code == 400
    assert Chamada.objects.count() == 0


@pytest.mark.django_db
def test_operador_mostra_script_da_fila(tenant_aurora, usuario_operacional):
    script = _script(tenant_aurora)
    fila = _fila(tenant_aurora, script=script)
    html = _cliente_web(usuario_operacional).get(f'/discador/?fila={fila.id}').content.decode()
    assert 'Cobrança amigável' in html
    assert 'Situação: entender' in html
    assert 'Necessidade: solução' in html


@pytest.mark.django_db
def test_operador_sem_filas_mostra_vazio(tenant_aurora, usuario_operacional):
    html = _cliente_web(usuario_operacional).get('/discador/').content.decode()
    assert 'Nenhuma fila ainda' in html


@pytest.mark.django_db
def test_operador_nao_vaza_fila_de_outro_tenant(tenant_aurora, tenant_beta, usuario_operacional):
    fila_beta = _fila(tenant_beta)
    html = _cliente_web(usuario_operacional).get('/discador/').content.decode()
    assert fila_beta.nome not in html


# --- Web: chamada (5.2) ---

@pytest.mark.django_db
def test_chamar_registra_chamada_e_devolve_uri(tenant_aurora, usuario_operacional):
    contato = _contato(tenant_aurora)
    fila = _fila(tenant_aurora)
    c = _cliente_web(usuario_operacional)
    r = c.post(f'/discador/fila/{fila.id}/chamar/', data='{"contato_id": %d}' % contato.id,
               content_type='application/json')
    assert r.status_code == 200
    dados = r.json()
    assert dados['ok'] is True
    assert dados['uri'] == 'sip:+11988887777@sip.empresa.com.br'
    chamada = Chamada.objects.get()
    assert chamada.status == 'discada'
    assert chamada.fila_id == fila.id
    assert chamada.contato_id == contato.id
    assert chamada.operador_id == usuario_operacional.id


@pytest.mark.django_db
def test_chamar_contato_sem_telefone_bloqueia(tenant_aurora, usuario_operacional):
    contato = _contato(tenant_aurora, tel='—')
    fila = _fila(tenant_aurora)
    r = _cliente_web(usuario_operacional).post(
        f'/discador/fila/{fila.id}/chamar/', data='{"contato_id": %d}' % contato.id,
        content_type='application/json')
    assert r.status_code == 400
    assert Chamada.objects.count() == 0


@pytest.mark.django_db
def test_chamar_fila_de_outro_tenant_da_404(tenant_aurora, tenant_beta, usuario_operacional):
    fila_beta = _fila(tenant_beta)
    contato = _contato(tenant_aurora)
    r = _cliente_web(usuario_operacional).post(
        f'/discador/fila/{fila_beta.id}/chamar/', data='{"contato_id": %d}' % contato.id,
        content_type='application/json')
    assert r.status_code == 404
    assert Chamada.objects.count() == 0


@pytest.mark.django_db
def test_viewer_nao_inicia_chamada(tenant_aurora, usuario_viewer):
    contato = _contato(tenant_aurora)
    fila = _fila(tenant_aurora)
    r = _cliente_web(usuario_viewer).post(
        f'/discador/fila/{fila.id}/chamar/', data='{"contato_id": %d}' % contato.id,
        content_type='application/json')
    assert r.status_code == 302  # redireciona (sem permissão de edição)
    assert Chamada.objects.count() == 0


@pytest.mark.django_db
def test_registrar_resultado(tenant_aurora, usuario_operacional):
    contato = _contato(tenant_aurora)
    fila = _fila(tenant_aurora)
    chamada = Chamada.objects.create(fila=fila, contato=contato, operador_id=usuario_operacional.id,
                                     tenant=tenant_aurora)
    r = _cliente_web(usuario_operacional).post(
        f'/discador/chamadas/{chamada.id}/resultado/',
        data='{"status": "acordo", "observacao": "Fechou por 3x"}',
        content_type='application/json')
    assert r.status_code == 200
    assert r.json()['ok'] is True
    chamada.refresh_from_db()
    assert chamada.status == 'acordo'
    assert chamada.observacao == 'Fechou por 3x'


@pytest.mark.django_db
def test_registrar_resultado_status_invalido(tenant_aurora, usuario_operacional):
    contato = _contato(tenant_aurora)
    fila = _fila(tenant_aurora)
    chamada = Chamada.objects.create(fila=fila, contato=contato, operador_id=usuario_operacional.id,
                                     tenant=tenant_aurora)
    r = _cliente_web(usuario_operacional).post(
        f'/discador/chamadas/{chamada.id}/resultado/',
        data='{"status": "hackeado"}', content_type='application/json')
    assert r.status_code == 400
    chamada.refresh_from_db()
    assert chamada.status == 'discada'


@pytest.mark.django_db
def test_registrar_resultado_chamada_de_outro_tenant_404(tenant_aurora, tenant_beta, usuario_operacional):
    fila_beta = _fila(tenant_beta)
    contato_beta = _contato(tenant_beta)
    chamada_beta = Chamada.objects.create(fila=fila_beta, contato=contato_beta, tenant=tenant_beta)
    r = _cliente_web(usuario_operacional).post(
        f'/discador/chamadas/{chamada_beta.id}/resultado/',
        data='{"status": "acordo"}', content_type='application/json')
    assert r.status_code == 404


# --- Web: CRUD de filas (admin) ---

@pytest.mark.django_db
def test_filas_lista_renderiza(tenant_aurora, admin_company):
    carteira = _carteira(tenant_aurora)
    _fila(tenant_aurora, carteira=carteira)
    html = _cliente_web(admin_company).get('/discador/filas/').content.decode()
    assert 'Fila 1' in html
    assert 'Cobrança' in html


@pytest.mark.django_db
def test_fila_nova(tenant_aurora, admin_company):
    carteira = _carteira(tenant_aurora)
    script = _script(tenant_aurora)
    r = _cliente_web(admin_company).post('/discador/filas/nova/', {
        'nome': 'Fila nova', 'descricao': 'Base', 'carteira_id': str(carteira.id),
        'ordem': 'score', 'script_id': str(script.id), 'ativa': 'on',
    })
    assert r.status_code == 302
    fila = Fila.objects.get(nome='Fila nova')
    assert fila.carteira_id == carteira.id
    assert fila.script_id == script.id
    assert fila.ordem == 'score'


@pytest.mark.django_db
def test_fila_nova_sem_nome_da_erro(tenant_aurora, admin_company):
    r = _cliente_web(admin_company).post('/discador/filas/nova/', {'nome': '  '})
    assert r.status_code == 200
    assert 'Informe o nome da fila'.encode() in r.content
    assert Fila.objects.count() == 0


@pytest.mark.django_db
def test_operacional_nao_gerencia_filas(tenant_aurora, usuario_operacional):
    r = _cliente_web(usuario_operacional).post('/discador/filas/nova/', {'nome': 'X'})
    assert r.status_code == 302
    assert Fila.objects.count() == 0


@pytest.mark.django_db
def test_fila_editar_e_excluir(tenant_aurora, admin_company):
    fila = _fila(tenant_aurora)
    c = _cliente_web(admin_company)
    r = c.post(f'/discador/filas/{fila.id}/editar/', {'nome': 'Renomeada', 'ordem': 'criacao_desc', 'ativa': 'on'})
    assert r.status_code == 302
    fila.refresh_from_db()
    assert fila.nome == 'Renomeada'
    assert fila.ordem == 'criacao_desc'
    r = c.post(f'/discador/filas/{fila.id}/excluir/')
    assert r.status_code == 302
    assert Fila.objects.count() == 0


@pytest.mark.django_db
def test_fila_de_outro_tenant_da_404(tenant_aurora, tenant_beta, admin_company):
    fila_beta = _fila(tenant_beta)
    r = _cliente_web(admin_company).get(f'/discador/filas/{fila_beta.id}/editar/')
    assert r.status_code == 404


# --- Web: scripts (5.3) ---

@pytest.mark.django_db
def test_scripts_crud(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/discador/scripts/nova/', {'nome': 'SPIN', 'descricao': 'Vendas', 'conteudo': '- Passo 1\n- Passo 2', 'ativa': 'on'})
    assert r.status_code == 302
    script = Script.objects.get(nome='SPIN')
    assert script.conteudo == '- Passo 1\n- Passo 2'
    r = c.post(f'/discador/scripts/{script.id}/editar/', {'nome': 'SPIN v2', 'conteudo': '- Passo X', 'ativa': 'on'})
    assert r.status_code == 302
    script.refresh_from_db()
    assert script.nome == 'SPIN v2'
    html = c.get('/discador/scripts/').content.decode()
    assert 'SPIN v2' in html
    r = c.post(f'/discador/scripts/{script.id}/excluir/')
    assert r.status_code == 302
    assert Script.objects.count() == 0


@pytest.mark.django_db
def test_script_sem_conteudo_da_erro(tenant_aurora, admin_company):
    r = _cliente_web(admin_company).post('/discador/scripts/nova/', {'nome': 'X', 'conteudo': '  '})
    assert r.status_code == 200
    assert 'Escreva o roteiro'.encode() in r.content
    assert Script.objects.count() == 0


# --- API ---

def _login(client, usuario):
    from teste.conftest import fazer_login

    return fazer_login(client, usuario.email)


@pytest.mark.django_db(transaction=True)
def test_api_lista_filas(client, tenant_aurora, usuario_operacional):
    carteira = _carteira(tenant_aurora)
    _contato(tenant_aurora, carteira=carteira)
    _fila(tenant_aurora, carteira=carteira)
    headers = _login(client, usuario_operacional)
    r = client.get('/api/v1/discador/filas', headers=headers)
    assert r.status_code == 200
    dados = r.json()
    assert len(dados) == 1
    assert dados[0]['nome'] == 'Fila 1'
    assert dados[0]['total_contatos'] == 1


@pytest.mark.django_db(transaction=True)
def test_api_isolamento_filas(client, tenant_aurora, tenant_beta, usuario_operacional):
    _fila(tenant_beta)
    headers = _login(client, usuario_operacional)
    r = client.get('/api/v1/discador/filas', headers=headers)
    assert r.json() == []


@pytest.mark.django_db(transaction=True)
def test_api_cria_fila(client, tenant_aurora, usuario_operacional):
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/discador/filas', json={'nome': 'Fila API'}, headers=headers)
    assert r.status_code == 201
    assert Fila.objects.filter(tenant_id=tenant_aurora.id, nome='Fila API').exists()


@pytest.mark.django_db(transaction=True)
def test_api_viewer_nao_cria_fila(client, tenant_aurora, usuario_viewer):
    headers = _login(client, usuario_viewer)
    r = client.post('/api/v1/discador/filas', json={'nome': 'X'}, headers=headers)
    assert r.status_code == 403
    assert Fila.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_api_contatos_da_fila(client, tenant_aurora, usuario_operacional):
    carteira = _carteira(tenant_aurora)
    contato = _contato(tenant_aurora, carteira=carteira)
    fila = _fila(tenant_aurora, carteira=carteira)
    headers = _login(client, usuario_operacional)
    r = client.get(f'/api/v1/discador/filas/{fila.id}/contatos', headers=headers)
    assert r.status_code == 200
    dados = r.json()
    assert len(dados) == 1
    assert dados[0]['nome'] == contato.nome
    assert dados[0]['cargo'] == 'Gerente'
    assert dados[0]['uri'] == 'sip:+11988887777@sip.empresa.com.br'


@pytest.mark.django_db(transaction=True)
def test_api_iniciar_chamada(client, tenant_aurora, usuario_operacional):
    contato = _contato(tenant_aurora)
    fila = _fila(tenant_aurora)
    headers = _login(client, usuario_operacional)
    r = client.post(f'/api/v1/discador/filas/{fila.id}/chamar',
                    json={'contato_id': contato.id}, headers=headers)
    assert r.status_code == 201
    dados = r.json()
    assert dados['uri'] == 'sip:+11988887777@sip.empresa.com.br'
    chamada = Chamada.objects.get(pk=dados['chamada_id'])
    assert chamada.status == 'discada'
    assert chamada.operador_id == usuario_operacional.id


@pytest.mark.django_db(transaction=True)
def test_api_registrar_resultado(client, tenant_aurora, usuario_operacional):
    contato = _contato(tenant_aurora)
    fila = _fila(tenant_aurora)
    chamada = Chamada.objects.create(fila=fila, contato=contato, operador_id=usuario_operacional.id,
                                     tenant=tenant_aurora)
    headers = _login(client, usuario_operacional)
    r = client.post(f'/api/v1/discador/chamadas/{chamada.id}/resultado',
                    json={'status': 'realizada', 'observacao': 'Falou com o devedor'}, headers=headers)
    assert r.status_code == 200
    assert r.json()['status_label'] == 'Realizada'
    chamada.refresh_from_db()
    assert chamada.status == 'realizada'


@pytest.mark.django_db(transaction=True)
def test_api_resultado_chamada_de_outro_tenant_404(client, tenant_aurora, tenant_beta,
                                                   usuario_operacional):
    fila_beta = _fila(tenant_beta)
    contato_beta = _contato(tenant_beta)
    chamada_beta = Chamada.objects.create(fila=fila_beta, contato=contato_beta, tenant=tenant_beta)
    headers = _login(client, usuario_operacional)
    r = client.post(f'/api/v1/discador/chamadas/{chamada_beta.id}/resultado',
                    json={'status': 'acordo'}, headers=headers)
    assert r.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_api_scripts(client, tenant_aurora, usuario_operacional):
    _script(tenant_aurora)
    headers = _login(client, usuario_operacional)
    r = client.get('/api/v1/discador/scripts', headers=headers)
    assert r.status_code == 200
    dados = r.json()
    assert len(dados) == 1
    assert dados[0]['nome'] == 'Cobrança amigável'
    assert 'Situação: entender' in dados[0]['conteudo']
