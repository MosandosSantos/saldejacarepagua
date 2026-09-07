"""Testes da Fase P — S4 do PRD HAZON (estrutura de campanhas, 4.1).

Campanha (nome, descrição, canal, ativa) escopada por tenant; listagem e detalhe;
o canal de e-mail dispara usando o app `emails` e vincula os envios à campanha
(KPIs no detalhe); endpoints da API.
"""

import pytest
from django.test import Client

from campanhas.models import Campanha
from contatos.models import Contato
from emails.models import EmailEnviado, ModeloEmail

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


def _modelo(tenant_aurora):
    return ModeloEmail.objects.create(
        tenant=tenant_aurora, nome='Proposta', assunto='Oi {{nome}}',
        corpo='Olá {{nome}}: <a href="https://exemplo.com/x">link</a>',
    )


def _contato(tenant_aurora, nome='Ana', email='ana@x.com'):
    return Contato.objects.create(
        nome=nome, empresa='X', tel='(11) 98888-7777', email=email,
        seg='geral', tenant=tenant_aurora,
    )


# --- Modelo ---

@pytest.mark.django_db
def test_campanha_escopada_por_tenant(tenant_aurora, tenant_beta):
    c1 = Campanha.objects.create(nome='Lembrete', canal='email', tenant=tenant_aurora)
    c2 = Campanha.objects.create(nome='Lembrete', canal='email', tenant=tenant_beta)
    assert c1.tenant_id == tenant_aurora.id
    assert c2.tenant_id == tenant_beta.id
    assert c1.get_canal_display() == 'E-mail'
    assert Campanha.objects.filter(tenant_id=tenant_aurora.id).count() == 1


@pytest.mark.django_db
def test_canal_padrao_email(tenant_aurora):
    c = Campanha.objects.create(nome='X', tenant=tenant_aurora)
    assert c.canal == 'email'


# --- Web: listagem e criação ---

@pytest.mark.django_db
def test_lista_campanhas_renderiza(tenant_aurora, admin_company):
    Campanha.objects.create(nome='Lembrete', canal='email', tenant=tenant_aurora)
    Campanha.objects.create(nome='Promo', canal='whatsapp', tenant=tenant_aurora)
    html = _cliente_web(admin_company).get('/campanhas/').content.decode()
    assert 'Lembrete' in html
    assert 'Promo' in html
    assert 'Nova campanha' in html
    assert 'E-mail' in html  # rótulo do canal


@pytest.mark.django_db
def test_criar_campanha(tenant_aurora, admin_company):
    r = _cliente_web(admin_company).post('/campanhas/novo/', {
        'nome': 'Lembrete junho', 'descricao': 'Base', 'canal': 'email', 'ativa': 'on',
    })
    assert r.status_code == 302
    campanha = Campanha.objects.get(tenant_id=tenant_aurora.id, nome='Lembrete junho')
    assert campanha.canal == 'email'
    assert campanha.ativa is True
    assert campanha.descricao == 'Base'


@pytest.mark.django_db
def test_criar_campanha_sem_nome_da_erro(tenant_aurora, admin_company):
    r = _cliente_web(admin_company).post('/campanhas/novo/', {'nome': '  '})
    assert r.status_code == 200
    assert b'Informe o nome da campanha' in r.content
    assert Campanha.objects.count() == 0


@pytest.mark.django_db
def test_criar_campanha_duplicada_no_tenant(tenant_aurora, admin_company):
    Campanha.objects.create(nome='X', tenant=tenant_aurora)
    r = _cliente_web(admin_company).post('/campanhas/novo/', {'nome': 'X'})
    assert 'Já existe uma campanha'.encode() in r.content
    assert Campanha.objects.count() == 1


@pytest.mark.django_db
def test_operacional_pode_criar_campanha(tenant_aurora, usuario_operacional):
    r = _cliente_web(usuario_operacional).post('/campanhas/novo/', {'nome': 'Op'})
    assert r.status_code == 302
    assert Campanha.objects.count() == 1


@pytest.mark.django_db
def test_viewer_nao_cria_campanha(tenant_aurora, usuario_viewer):
    r = _cliente_web(usuario_viewer).post('/campanhas/novo/', {'nome': 'X'})
    assert r.status_code == 302
    assert Campanha.objects.count() == 0


@pytest.mark.django_db
def test_isolamento_entre_tenants(tenant_aurora, tenant_beta, admin_company):
    Campanha.objects.create(nome='Só da Aurora', tenant=tenant_aurora)
    Campanha.objects.create(nome='Só da Beta', tenant=tenant_beta)
    html = _cliente_web(admin_company).get('/campanhas/').content.decode()
    assert 'Só da Aurora' in html
    assert 'Só da Beta' not in html


# --- Web: editar/excluir ---

@pytest.mark.django_db
def test_editar_campanha(tenant_aurora, admin_company):
    campanha = Campanha.objects.create(nome='Antiga', tenant=tenant_aurora)
    r = _cliente_web(admin_company).post(f'/campanhas/{campanha.id}/editar/', {
        'nome': 'Nova', 'descricao': 'ok', 'canal': 'email', 'ativa': 'on',
    })
    assert r.status_code == 302
    campanha.refresh_from_db()
    assert campanha.nome == 'Nova'


@pytest.mark.django_db
def test_excluir_campanha(tenant_aurora, admin_company):
    campanha = Campanha.objects.create(nome='Temp', tenant=tenant_aurora)
    r = _cliente_web(admin_company).post(f'/campanhas/{campanha.id}/excluir/')
    assert r.status_code == 302
    assert Campanha.objects.count() == 0


@pytest.mark.django_db
def test_campanha_de_outro_tenant_da_404(tenant_aurora, tenant_beta, admin_company):
    campanha_beta = Campanha.objects.create(nome='Da Beta', tenant=tenant_beta)
    r = _cliente_web(admin_company).get(f'/campanhas/{campanha_beta.id}/')
    assert r.status_code == 404


# --- Detalhe e disparo integrado ---

@pytest.mark.django_db
def test_detalhe_mostra_kpis_e_disparo(tenant_aurora, admin_company):
    campanha = Campanha.objects.create(nome='Lembrete', canal='email', tenant=tenant_aurora)
    html = _cliente_web(admin_company).get(f'/campanhas/{campanha.id}/').content.decode()
    assert 'Enviados' in html and 'Abertos' in html and 'Cliques' in html and 'Convertidos' in html
    assert 'Disparar' in html


@pytest.mark.django_db
def test_detalhe_canal_sem_integracao_mostra_pendencia(tenant_aurora, admin_company):
    campanha = Campanha.objects.create(nome='Whats', canal='whatsapp', tenant=tenant_aurora)
    html = _cliente_web(admin_company).get(f'/campanhas/{campanha.id}/').content.decode()
    assert 'Integração pendente' in html
    assert 'Disparar' not in html


@pytest.mark.django_db
def test_disparo_vincula_envios_a_campanha(tenant_aurora, admin_company):
    campanha = Campanha.objects.create(nome='Lembrete', canal='email', tenant=tenant_aurora)
    modelo = _modelo(tenant_aurora)
    _contato(tenant_aurora, nome='Ana', email='ana@x.com')
    _contato(tenant_aurora, nome='Bia', email='bia@x.com')
    c = _cliente_web(admin_company)
    r = c.post(f'/campanhas/{campanha.id}/', {
        'modelo_id': str(modelo.id), 'seg': '', 'carteira_id': '',
    })
    assert r.status_code == 200
    assert EmailEnviado.objects.filter(campanha=campanha).count() == 2
    assert b'2 envio(s) registrado(s)' in r.content


@pytest.mark.django_db
def test_disparo_campanha_inativa_bloqueado(tenant_aurora, admin_company):
    campanha = Campanha.objects.create(nome='Inativa', canal='email', tenant=tenant_aurora, ativa=False)
    modelo = _modelo(tenant_aurora)
    _contato(tenant_aurora, email='ana@x.com')
    r = _cliente_web(admin_company).post(f'/campanhas/{campanha.id}/', {
        'modelo_id': str(modelo.id), 'seg': '', 'carteira_id': '',
    })
    assert r.status_code == 200
    assert b'Campanha inativa' in r.content
    assert EmailEnviado.objects.count() == 0


@pytest.mark.django_db
def test_disparo_filtra_por_segmento_e_carteira(tenant_aurora, admin_company):
    from contatos.models import Carteira

    campanha = Campanha.objects.create(nome='Lembrete', canal='email', tenant=tenant_aurora)
    modelo = _modelo(tenant_aurora)
    carteira = Carteira.objects.create(nome='Cobrança', tenant=tenant_aurora)
    _contato(tenant_aurora, nome='Ana', email='ana@x.com')
    c1 = _contato(tenant_aurora, nome='Bia', email='bia@x.com', )
    c1.seg = 'estetica'
    c1.carteira = carteira
    c1.save()
    c = _cliente_web(admin_company)
    r = c.post(f'/campanhas/{campanha.id}/', {
        'modelo_id': str(modelo.id), 'seg': 'estetica', 'carteira_id': str(carteira.id),
    })
    assert r.status_code == 200
    assert EmailEnviado.objects.filter(campanha=campanha).count() == 1
    assert EmailEnviado.objects.get().contato.nome == 'Bia'


@pytest.mark.django_db
def test_detalhe_mostra_envios_e_conversao(tenant_aurora, admin_company):
    from django.utils import timezone

    campanha = Campanha.objects.create(nome='Lembrete', canal='email', tenant=tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = EmailEnviado.objects.create(
        tenant=tenant_aurora, contato=contato, destinatario='ana@x.com',
        assunto='a', corpo='c', status='simulado', campanha=campanha,
    )
    envio.convertido_em = timezone.now()
    envio.save(update_fields=['convertido_em'])
    html = _cliente_web(admin_company).get(f'/campanhas/{campanha.id}/').content.decode()
    assert 'ana@x.com' in html
    assert '✓' in html


# --- API ---

def _login(client, usuario):
    from teste.conftest import fazer_login

    return fazer_login(client, usuario.email)


@pytest.mark.django_db(transaction=True)
def test_api_lista_campanhas(client, tenant_aurora, usuario_operacional):
    Campanha.objects.create(nome='Lembrete', canal='email', tenant=tenant_aurora)
    headers = _login(client, usuario_operacional)
    r = client.get('/api/v1/campanhas', headers=headers)
    assert r.status_code == 200
    dados = r.json()
    assert len(dados) == 1
    assert dados[0]['nome'] == 'Lembrete'
    assert dados[0]['canal'] == 'email'


@pytest.mark.django_db(transaction=True)
def test_api_isolamento_campanhas(client, tenant_aurora, tenant_beta, usuario_operacional):
    Campanha.objects.create(nome='Da Beta', tenant=tenant_beta)
    headers = _login(client, usuario_operacional)
    r = client.get('/api/v1/campanhas', headers=headers)
    assert r.json() == []


@pytest.mark.django_db(transaction=True)
def test_api_cria_campanha(client, tenant_aurora, usuario_operacional):
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/campanhas', json={'nome': 'Lembrete', 'canal': 'email'}, headers=headers)
    assert r.status_code == 201
    assert r.json()['nome'] == 'Lembrete'
    assert Campanha.objects.filter(tenant_id=tenant_aurora.id).exists()


@pytest.mark.django_db(transaction=True)
def test_api_campanha_duplicada_409(client, tenant_aurora, usuario_operacional):
    Campanha.objects.create(nome='X', tenant=tenant_aurora)
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/campanhas', json={'nome': 'X'}, headers=headers)
    assert r.status_code == 409


@pytest.mark.django_db(transaction=True)
def test_api_canal_invalido_422(client, tenant_aurora, usuario_operacional):
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/campanhas', json={'nome': 'X', 'canal': 'fax'}, headers=headers)
    assert r.status_code == 422


@pytest.mark.django_db(transaction=True)
def test_api_viewer_nao_cria_campanha(client, tenant_aurora, usuario_viewer):
    headers = _login(client, usuario_viewer)
    r = client.post('/api/v1/campanhas', json={'nome': 'X'}, headers=headers)
    assert r.status_code == 403
    assert Campanha.objects.count() == 0
