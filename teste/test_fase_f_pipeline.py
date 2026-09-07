"""Testes da Fase F — pipeline de vendas configurável por tenant.

Cada clínica tem as próprias etapas (nome, cor, ordem e probabilidade) em vez das
etapas fixas por nicho. Cobrimos: fallback do nicho, semeação, renomear, criar,
excluir (com guardas), isolamento entre tenants, mover para etapa customizada,
formulários, receita projetada ponderada e onboarding.
"""

import pytest
from django.test import Client

from contatos.forms import ContatoForm
from contatos.importador import normalizar_stage
from contatos.models import Contato, Movimentacao, criar_negocio
from recepcao.models import EtapaFunil, adotar_nicho, etapas_do_tenant, garantir_etapas


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


def _contato(tenant, nome='Ana'):
    return Contato.objects.create(nome=nome, seg='estetica', tenant=tenant, origem='Indicacao')


# --- Fallback do nicho e semeação ---

@pytest.mark.django_db
def test_kanban_sem_etapas_mostra_nicho(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.get('/recepcao/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Avaliação agendada' in html  # nome do nicho saude (fallback)
    assert html.count('class="kanban-col') == 6  # 6 colunas padrão
    assert 'data-stage="interessado"' in html
    assert 'data-stage="fechado"' in html


@pytest.mark.django_db
def test_garantir_etapas_semeia_do_nicho(tenant_aurora):
    garantir_etapas(tenant_aurora.id, 'imob')
    etapas = EtapaFunil.objects.filter(tenant_id=tenant_aurora.id).order_by('ordem')
    assert etapas.count() == 6
    nomes = {e.key: e.nome for e in etapas}
    assert nomes['interessado'] == 'Lead novo'       # nome do nicho imob
    assert nomes['avaliacao_agendada'] == 'Visita agendada'
    sistema = {e.key for e in etapas if e.sistema}
    assert sistema == {'fechado', 'perdido'}
    fechado = etapas.get(key='fechado')
    assert float(fechado.peso) == 1.0
    assert float(etapas.get(key='perdido').peso) == 0.0


@pytest.mark.django_db
def test_garantir_etapas_idempotente(tenant_aurora):
    garantir_etapas(tenant_aurora.id, 'saude')
    garantir_etapas(tenant_aurora.id, 'saude')
    assert EtapaFunil.objects.filter(tenant_id=tenant_aurora.id).count() == 6


@pytest.mark.django_db
def test_onboarding_semeia_etapas_do_nicho_escolhido(tenant_aurora, admin_company):
    assert tenant_aurora.nicho is None
    c = _cliente_web(admin_company)
    r = c.post('/login/onboarding/', {'nicho': 'odonto'})
    assert r.status_code == 302
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.nicho == 'odonto'
    etapas = {e.key: e.nome for e in EtapaFunil.objects.filter(tenant_id=tenant_aurora.id)}
    assert etapas['avaliacao_agendada'] == 'Consulta agendada'


# --- Configuração (admin) ---

@pytest.mark.django_db
def test_config_admin_ve_secao_etapas_e_operacional_nao(tenant_aurora, admin_company, usuario_operacional):
    c = _cliente_web(admin_company)
    r = c.get('/config/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Etapas do funil' in html
    assert 'Adicionar etapa' in html
    assert 'data-stage' not in html

    c2 = _cliente_web(usuario_operacional)
    html2 = c2.get('/config/').content.decode()
    assert 'Etapas do funil' not in html2


@pytest.mark.django_db
def test_config_admin_acessa_config_semeia_etapas(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    c.get('/config/')
    assert EtapaFunil.objects.filter(tenant_id=tenant_aurora.id).count() == 6


@pytest.mark.django_db
def test_renomear_etapa_reflete_no_funil(tenant_aurora, admin_company):
    garantir_etapas(tenant_aurora.id, 'saude')
    c = _cliente_web(admin_company)
    etapa = EtapaFunil.objects.get(tenant_id=tenant_aurora.id, key='interessado')
    r = c.post('/config/', {
        'acao': 'etapa_editar', 'etapa_id': etapa.id,
        'nome': 'Novo lead', 'cor': '#f472b6', 'ordem': '0', 'peso': '0.15',
    })
    assert r.status_code == 200
    etapa.refresh_from_db()
    assert etapa.nome == 'Novo lead'
    assert etapa.key == 'interessado'  # key preservada (negócios continuam apontando)
    assert float(etapa.peso) == 0.15

    html = c.get('/recepcao/').content.decode()
    assert 'Novo lead' in html
    assert 'Interessado' not in html


@pytest.mark.django_db
def test_etapa_sistema_pode_renomear_mas_nao_excluir(tenant_aurora, admin_company):
    garantir_etapas(tenant_aurora.id, 'saude')
    c = _cliente_web(admin_company)
    fechado = EtapaFunil.objects.get(tenant_id=tenant_aurora.id, key='fechado')

    # renomear é permitido (key continua 'fechado' — dashboard segue funcionando)
    c.post('/config/', {
        'acao': 'etapa_editar', 'etapa_id': fechado.id,
        'nome': 'Ganho', 'cor': fechado.cor, 'ordem': '4', 'peso': '1',
    })
    fechado.refresh_from_db()
    assert fechado.nome == 'Ganho'
    assert fechado.key == 'fechado'

    # excluir é bloqueado
    r = c.post('/config/', {'acao': 'etapa_excluir', 'etapa_id': fechado.id})
    assert 'não podem ser excluídas'.encode() in r.content
    assert EtapaFunil.objects.filter(pk=fechado.pk).exists()


@pytest.mark.django_db
def test_criar_etapa_customizada(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/config/', {
        'acao': 'etapa_nova', 'nome': 'Proposta enviada', 'cor': '#f472b6',
        'ordem': '10', 'peso': '0.7',
    })
    assert r.status_code == 200
    etapa = EtapaFunil.objects.get(tenant_id=tenant_aurora.id, key='proposta-enviada')
    assert etapa.nome == 'Proposta enviada'
    assert etapa.cor == '#f472b6'
    assert float(etapa.peso) == 0.7
    assert not etapa.sistema

    html = c.get('/recepcao/').content.decode()
    assert 'Proposta enviada' in html
    assert 'data-stage="proposta-enviada"' in html


@pytest.mark.django_db
def test_criar_etapa_nome_sistema_vira_chave_alternativa(tenant_aurora, admin_company):
    garantir_etapas(tenant_aurora.id, 'saude')
    c = _cliente_web(admin_company)
    c.post('/config/', {'acao': 'etapa_nova', 'nome': 'Fechado', 'cor': '#7fe3c4',
                        'ordem': '50', 'peso': '1'})
    # a key reservada 'fechado' não pode ser roubada — vira fechado_2
    assert EtapaFunil.objects.filter(tenant_id=tenant_aurora.id, key='fechado_2').exists()


@pytest.mark.django_db
def test_excluir_etapa_com_negocio_bloqueado_e_sem_negocio_ok(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    c.post('/config/', {'acao': 'etapa_nova', 'nome': 'Em uso', 'cor': '#f472b6',
                        'ordem': '10', 'peso': '0.5'})
    c.post('/config/', {'acao': 'etapa_nova', 'nome': 'Vazia', 'cor': '#60a5fa',
                        'ordem': '11', 'peso': '0.5'})
    em_uso = EtapaFunil.objects.get(tenant_id=tenant_aurora.id, key='em-uso')
    vazia = EtapaFunil.objects.get(tenant_id=tenant_aurora.id, key='vazia')

    contato = _contato(tenant_aurora)
    criar_negocio(contato, stage='em-uso', valor=100, tenant_id=tenant_aurora.id)

    r = c.post('/config/', {'acao': 'etapa_excluir', 'etapa_id': em_uso.id})
    assert 'ainda tem negócios'.encode() in r.content
    assert EtapaFunil.objects.filter(pk=em_uso.pk).exists()

    r2 = c.post('/config/', {'acao': 'etapa_excluir', 'etapa_id': vazia.id})
    assert not EtapaFunil.objects.filter(pk=vazia.pk).exists()
    assert 'excluída'.encode() in r2.content


# --- Isolamento entre tenants ---

@pytest.mark.django_db
def test_etapas_isoladas_por_tenant(tenant_aurora, tenant_beta, admin_company):
    garantir_etapas(tenant_aurora.id, 'saude')
    c = _cliente_web(admin_company)
    c.post('/config/', {'acao': 'etapa_nova', 'nome': 'Só da Aurora', 'cor': '#f472b6',
                        'ordem': '50', 'peso': '0.5'})

    etapas_aurora = [e['key'] for e in etapas_do_tenant(tenant_aurora.id)]
    etapas_beta = [e['key'] for e in etapas_do_tenant(tenant_beta.id)]
    assert 'so-da-aurora' in etapas_aurora
    assert 'so-da-aurora' not in etapas_beta
    assert EtapaFunil.objects.filter(tenant_id=tenant_beta.id).count() == 0  # beta segue nicho


# --- Funil: mover e formulários ---

@pytest.mark.django_db
def test_mover_para_etapa_customizada(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    c.post('/config/', {'acao': 'etapa_nova', 'nome': 'Quente', 'cor': '#f472b6',
                        'ordem': '10', 'peso': '0.8'})
    contato = _contato(tenant_aurora)
    negocio = criar_negocio(contato, stage='interessado', valor=500, tenant_id=tenant_aurora.id)

    r = c.post(f'/recepcao/{negocio.id}/mover/', {'stage': 'quente'})
    assert r.status_code in (200, 302)
    negocio.refresh_from_db()
    assert negocio.stage == 'quente'
    assert Movimentacao.objects.filter(negocio=negocio, para_stage='quente').exists()


@pytest.mark.django_db
def test_form_contato_usa_etapas_do_tenant(tenant_aurora):
    garantir_etapas(tenant_aurora.id, 'saude')
    etapa = EtapaFunil.objects.get(tenant_id=tenant_aurora.id, key='interessado')
    etapa.nome = 'Novo lead'
    etapa.save(update_fields=['nome'])

    form = ContatoForm(nicho='saude', tenant_id=tenant_aurora.id)
    choices = dict(form.fields['stage'].choices)
    assert choices['interessado'] == 'Novo lead'

    # sem tenant (admin_saas) continua usando o nicho
    form_saas = ContatoForm(nicho='saude', tenant_id=None)
    assert dict(form_saas.fields['stage'].choices)['interessado'] == 'Interessado'


# --- Dashboard ponderado ---

@pytest.mark.django_db
def test_receita_projetada_usa_peso_da_etapa(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    c.post('/config/', {'acao': 'etapa_nova', 'nome': 'Quente', 'cor': '#f472b6',
                        'ordem': '10', 'peso': '0.9'})
    contato = _contato(tenant_aurora)
    criar_negocio(contato, stage='quente', valor=1000, tenant_id=tenant_aurora.id)

    r = c.get('/dashboard/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'R$ 900' in html  # 1000 x 0.9


# --- Onboarding de tenant semeados com o nicho padrão (backfill antigo) ---

@pytest.mark.django_db
def test_adotar_nicho_renomeia_padrao_mas_nao_customizado(tenant_aurora):
    # simula o backfill antigo: tenant semeado com rótulos de saúde
    garantir_etapas(tenant_aurora.id, 'saude')
    # o admin já personalizou uma etapa
    etapa = EtapaFunil.objects.get(tenant_id=tenant_aurora.id, key='interessado')
    etapa.nome = 'Lead quente'
    etapa.save(update_fields=['nome'])

    # o dono faz o onboarding escolhendo odonto
    adotar_nicho(tenant_aurora.id, 'odonto')

    etapas = {e.key: e.nome for e in EtapaFunil.objects.filter(tenant_id=tenant_aurora.id)}
    assert etapas['avaliacao_agendada'] == 'Consulta agendada'  # padrão intocada → adotou odonto
    assert etapas['avaliacao_feita'] == 'Consulta realizada'
    assert etapas['interessado'] == 'Lead quente'               # customizada → preservada
    assert etapas['fechado'] == 'Fechado'


# --- API: etapa fora do pipeline é rejeitada ---

@pytest.mark.django_db(transaction=True)
def test_api_rejeita_etapa_fora_do_pipeline(client, tenant_aurora, headers_admin_company):
    garantir_etapas(tenant_aurora.id, 'saude')

    r = client.post('/api/v1/contatos', headers=headers_admin_company,
                    json={'nome': 'X', 'seg': 'estetica', 'stage': 'etapa-inexistente'})
    assert r.status_code == 400
    assert 'etapa invalida' in r.json()['detail']
    assert not Contato.objects.filter(nome='X').exists()

    # etapa válida do pipeline continua aceita
    r2 = client.post('/api/v1/contatos', headers=headers_admin_company,
                     json={'nome': 'Y', 'seg': 'estetica', 'stage': 'orcamento'})
    assert r2.status_code == 201
    assert Contato.objects.filter(nome='Y').exists()


# --- Importador ---

@pytest.mark.django_db
def test_importador_reconhece_etapas_do_tenant(tenant_aurora):
    garantir_etapas(tenant_aurora.id, 'saude')
    EtapaFunil.objects.create(
        tenant=tenant_aurora, key='proposta-avancada', nome='Proposta avançada',
        cor='#f472b6', ordem=10, peso='0.75',
    )
    etapas = etapas_do_tenant(tenant_aurora.id)
    # nome customizado da etapa vira a chave customizada
    assert normalizar_stage('Proposta avançada', 'saude', etapas) == 'proposta-avancada'
    assert normalizar_stage('proposta-avancada', 'saude', etapas) == 'proposta-avancada'
    # chaves padrão continuam mapeando
    assert normalizar_stage('Orçamento enviado', 'saude', etapas) == 'orcamento'
    # sem etapas (comportamento antigo) segue funcionando
    assert normalizar_stage('Avaliação agendada') == 'avaliacao_agendada'
