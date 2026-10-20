"""Testes da Fase H — formulário público de captura de lead.

O link público (token por tenant) vira contato + negócio na primeira etapa do
pipeline, com origem configurável. Proteções: honeypot e limite de envios por IP.
"""

import pytest
from django.core.cache import cache
from django.test import Client

from acesso.models import token_captura_do_tenant
from contatos.models import Contato
from recepcao.models import etapas_do_tenant, garantir_etapas


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


def _link(tenant):
    return f"/captura/{token_captura_do_tenant(tenant)}/"


def _dados(nome='Maria Lead', tel='(11) 99999-0000', **extra):
    dados = {'nome': nome, 'tel': tel, 'email': 'maria@lead.com', 'seg': 'beleza',
             'procedimento': 'Laser CO2'}
    dados.update(extra)
    return dados


# --- Formulário público ---

@pytest.mark.django_db
def test_formulario_abre_sem_login(tenant_aurora):
    r = Client().get(_link(tenant_aurora))
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Quero ser atendido(a)' in html
    assert 'name="nome"' in html
    assert 'name="tel"' in html


@pytest.mark.django_db
def test_post_cria_contato_e_negocio_na_primeira_etapa(tenant_aurora):
    garantir_etapas(tenant_aurora.id, 'saude')
    r = Client().post(_link(tenant_aurora), _dados(), REMOTE_ADDR='10.0.0.1')
    assert r.status_code == 200
    assert b'Obrigado(a)' in r.content

    contato = Contato.objects.get(nome='Maria Lead')
    assert contato.tenant_id == tenant_aurora.id
    assert contato.tel == '(11) 99999-0000'
    assert contato.email == 'maria@lead.com'
    assert contato.seg == 'beleza'
    assert contato.procedimento == 'Laser CO2'
    assert contato.origem == 'Site'  # origem padrão do tenant

    negocio = contato.negocios.first()
    assert negocio is not None
    assert negocio.stage == etapas_do_tenant(tenant_aurora.id)[0]['key']
    assert float(negocio.valor) == 0


@pytest.mark.django_db
def test_origem_configurada_e_aplicada(tenant_aurora):
    tenant_aurora.origem_captura = 'Instagram'
    tenant_aurora.save(update_fields=['origem_captura'])
    Client().post(_link(tenant_aurora), _dados(nome='Via Insta'), REMOTE_ADDR='10.0.0.2')
    assert Contato.objects.get(nome='Via Insta').origem == 'Instagram'


@pytest.mark.django_db
def test_post_sem_nome_rejeitado(tenant_aurora):
    r = Client().post(_link(tenant_aurora), _dados(nome=''), REMOTE_ADDR='10.0.0.3')
    assert b'Informe seu nome' in r.content
    assert Contato.objects.count() == 0


@pytest.mark.django_db
def test_post_sem_telefone_e_email_rejeitado(tenant_aurora):
    r = Client().post(_link(tenant_aurora), _dados(tel='', email=''), REMOTE_ADDR='10.0.0.4')
    assert b'telefone ou e-mail' in r.content
    assert Contato.objects.count() == 0


# --- Proteções ---

@pytest.mark.django_db
def test_honeypot_preenchido_nao_cria(tenant_aurora):
    r = Client().post(_link(tenant_aurora), _dados(website='http://spam.com'), REMOTE_ADDR='10.0.0.5')
    assert r.status_code == 200
    assert b'Obrigado(a)' in r.content  # responde sucesso pro robô
    assert Contato.objects.count() == 0


@pytest.mark.django_db
def test_token_desconhecido_404():
    assert Client().get('/captura/token-inexistente/').status_code == 404


@pytest.mark.django_db
def test_formulario_desativado_nao_aceita(tenant_aurora):
    tenant_aurora.captura_ativa = False
    tenant_aurora.save(update_fields=['captura_ativa'])
    assert b'desativado' in Client().get(_link(tenant_aurora)).content

    Client().post(_link(tenant_aurora), _dados(), REMOTE_ADDR='10.0.0.6')
    assert Contato.objects.count() == 0


@pytest.mark.django_db
def test_rate_limit_por_ip(tenant_aurora):
    cache.clear()
    link = _link(tenant_aurora)
    # telefones distintos: a dedup por telefone não interfere no rate limit
    for i in range(5):
        r = Client().post(link, _dados(nome=f'Lead {i}', tel=f'(11) 90000-000{i}'), REMOTE_ADDR='10.9.9.9')
        assert b'Obrigado(a)' in r.content
    assert Contato.objects.count() == 5

    r6 = Client().post(link, _dados(nome='Lead 6', tel='(11) 90000-0006'), REMOTE_ADDR='10.9.9.9')
    assert b'Muitos envios' in r6.content
    assert Contato.objects.count() == 5  # o 6º não foi gravado


@pytest.mark.django_db
def test_mesmo_telefone_atualiza_contato_e_cria_novo_negocio(tenant_aurora):
    link = _link(tenant_aurora)
    Client().post(link, _dados(nome='Maria Lead', tel='(11) 98888-7777'), REMOTE_ADDR='10.0.0.7')
    Client().post(link, _dados(nome='Maria Atualizada', tel='11 988887777', email=''), REMOTE_ADDR='10.0.0.7')

    # mesmo telefone normalizado → 1 contato só, com o nome novo
    assert Contato.objects.count() == 1
    contato = Contato.objects.get()
    assert contato.nome == 'Maria Atualizada'
    assert contato.tel_normalizado == '11988887777'
    # e-mail vazio no 2º envio NÃO apaga o e-mail já cadastrado
    assert contato.email == 'maria@lead.com'
    assert contato.negocios.count() == 2  # cada envio vira um negócio


@pytest.mark.django_db
def test_erros_de_digitacao_nao_consomem_rate_limit(tenant_aurora):
    cache.clear()
    link = _link(tenant_aurora)
    # 6 envios inválidos (sem nome) do mesmo IP
    for i in range(6):
        r = Client().post(link, _dados(nome=''), REMOTE_ADDR='10.8.8.8')
        assert b'Informe seu nome' in r.content
    # nenhum contato criado e o 7º envio VÁLIDO ainda passa
    assert Contato.objects.count() == 0
    r_ok = Client().post(link, _dados(nome='Lead Válido'), REMOTE_ADDR='10.8.8.8')
    assert b'Obrigado(a)' in r_ok.content
    assert Contato.objects.count() == 1


# --- Configuração ---

@pytest.mark.django_db
def test_config_admin_ve_link_e_operacional_nao(tenant_aurora, admin_company, usuario_operacional):
    c = _cliente_web(admin_company)
    html = c.get('/config/').content.decode()
    # O config gera e persiste o token ao renderizar — recarrega para comparar
    # com o token que realmente está no banco (não gerar outro por cima).
    tenant_aurora.refresh_from_db()
    assert 'Captura de lead' in html
    assert tenant_aurora.token_captura in html  # link com o token persistido

    # O chip de navegação e o JS do template citam "captura" para todos;
    # o que deve sumir para o operacional é a SEÇÃO (id="captura").
    html2 = _cliente_web(usuario_operacional).get('/config/').content.decode()
    assert 'id="captura"' not in html2


@pytest.mark.django_db
def test_config_salva_origem_e_ativo(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    # manter ativo + trocar origem
    r = c.post('/config/', {'acao': 'captura_salvar', 'origem_captura': 'WhatsApp',
                            'captura_ativa': 'on'})
    assert r.status_code == 200
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.origem_captura == 'WhatsApp'
    assert tenant_aurora.captura_ativa is True

    # desativar (checkbox ausente no POST = off)
    c.post('/config/', {'acao': 'captura_salvar', 'origem_captura': 'WhatsApp'})
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.captura_ativa is False


@pytest.mark.django_db
def test_config_gera_novo_token(tenant_aurora, admin_company):
    antigo = token_captura_do_tenant(tenant_aurora)
    c = _cliente_web(admin_company)
    c.post('/config/', {'acao': 'captura_gerar'})
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.token_captura != antigo
    assert tenant_aurora.token_captura is not None
