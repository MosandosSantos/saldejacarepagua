"""Testes da Fase I — Automações no-code (regras).

O admin cria uma regra (gatilho + ações). Quando o evento acontece — contato novo,
negócio criado, negócio movido de etapa ou negócio parado — o motor executa as
ações (tarefa, nota, tag, e-mail) e registra a execução. Tudo escopado por tenant;
gestão restrita ao admin; viewer só visualiza.

"""

import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from acesso.models import Tenant
from automacoes.models import Automacao, PassoAutomacao, RegistroExecucao
from contatos.models import Contato, Negocio, Nota, Tag, criar_negocio
from emails.models import EmailEnviado, ModeloEmail
from tarefas.models import Tarefa


def _dados_contato(nome, **overrides):
    """POST válido do formulário de contato (todas as colunas que o form exige)."""
    dados = {
        'nome': nome, 'empresa': 'Empresa X', 'tel': '(11) 90000-0000', 'email': 'novo@x.com',
        'seg': 'estetica', 'stage': 'interessado', 'valor': '0',
        'origem': 'Instagram', 'pagamento': 'Particular',
        'procedimento': 'Laser', 'ultima_consulta': '2026-01-01',
    }
    dados.update(overrides)
    return dados


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


def _contato(tenant, **kw):
    dados = {'nome': 'Ana', 'seg': 'estetica'}
    dados.update(kw)
    return Contato.objects.create(tenant=tenant, **dados)


def _auto(tenant, trigger='contato_criado', criado_por=None, nome='Regra de teste', **kw):
    return Automacao.objects.create(
        tenant=tenant, nome=nome, trigger=trigger,
        criado_por=criado_por, **kw
    )


def _passo(auto, acao='tarefa', ordem=0, **params):
    return PassoAutomacao.objects.create(automacao=auto, ordem=ordem, acao=acao, parametros=params)


def _payload_auto(trigger='contato_criado', passos=None, **extra):
    dados = {'nome': 'Nova regra', 'trigger': trigger, 'ativa': 'on'}
    dados.update(extra)
    if passos is None:
        passos = [{'acao': 'tarefa', 'titulo': 'Entrar em contato',
                   'prioridade': 'media', 'vencimento_dias': '', 'responsavel_id': '',
                   'texto': '', 'tag': '', 'modelo_id': ''}]
    dados['passos_json'] = json.dumps(passos)
    return dados


# --- CRUD web ---


@pytest.mark.django_db
def test_admin_cria_automacao_pela_web(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/automacoes/nova/', _payload_auto(
        passos=[{'acao': 'tarefa', 'titulo': 'Ligar para {{nome}}', 'prioridade': 'alta',
                 'vencimento_dias': '2', 'responsavel_id': '', 'texto': '', 'tag': '', 'modelo_id': ''}],
    ))
    assert r.status_code == 302
    auto = Automacao.objects.get(nome='Nova regra')
    assert auto.tenant_id == tenant_aurora.id
    assert auto.trigger == 'contato_criado'
    assert auto.ativa
    passo = auto.passos.get()
    assert passo.acao == 'tarefa'
    assert passo.parametros['titulo'] == 'Ligar para {{nome}}'
    assert passo.parametros['prioridade'] == 'alta'
    assert passo.parametros['vencimento_dias'] == 2


@pytest.mark.django_db
def test_form_sem_acoes_rejeitado(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/automacoes/nova/', _payload_auto(passos=[]))
    assert r.status_code == 200
    assert 'Adicione pelo menos uma aç' in r.content.decode('utf-8', 'ignore')
    assert Automacao.objects.count() == 0


@pytest.mark.django_db
def test_edita_automacao_e_atualiza_passos(tenant_aurora, admin_company):
    auto = _auto(tenant_aurora, criado_por=admin_company)
    _passo(auto, 'tarefa', titulo='Tarefa antiga')
    c = _cliente_web(admin_company)
    r = c.post(f'/automacoes/{auto.id}/editar/', _payload_auto(
        passos=[{'acao': 'nota', 'titulo': '', 'prioridade': 'media', 'vencimento_dias': '',
                 'responsavel_id': '', 'texto': 'Entrou em negociação', 'tag': '', 'modelo_id': ''}],
    ))
    assert r.status_code == 302
    auto.refresh_from_db()
    assert auto.passos.count() == 1
    assert auto.passos.get().acao == 'nota'


@pytest.mark.django_db
def test_duplicar_cria_copia_desativada(tenant_aurora, admin_company):
    auto = _auto(tenant_aurora, criado_por=admin_company)
    _passo(auto, 'tarefa', titulo='Ligar')
    c = _cliente_web(admin_company)
    r = c.post(f'/automacoes/{auto.id}/duplicar/', {})
    assert r.status_code == 302
    copia = Automacao.objects.exclude(pk=auto.pk).get()
    assert copia.ativa is False
    assert copia.passos.count() == 1
    assert 'cópia' in copia.nome


@pytest.mark.django_db
def test_ativar_desativar_toggle(tenant_aurora, admin_company):
    auto = _auto(tenant_aurora, ativa=True)
    c = _cliente_web(admin_company)
    c.post(f'/automacoes/{auto.id}/ativar/', {})
    auto.refresh_from_db()
    assert not auto.ativa
    c.post(f'/automacoes/{auto.id}/ativar/', {})
    auto.refresh_from_db()
    assert auto.ativa


# --- Motor: triggers e ações ---


@pytest.mark.django_db
def test_contato_novo_dispara_tarefa_com_placeholder(tenant_aurora, admin_company, usuario_operacional):
    auto = _auto(tenant_aurora, criado_por=admin_company)
    _passo(auto, 'tarefa', titulo='Ligar para {{nome}}', prioridade='alta', vencimento_dias=2,
           responsavel_id=usuario_operacional.id)
    c = _cliente_web(admin_company)
    r = c.post('/contatos/novo/', _dados_contato('Maria Nova'))
    assert r.status_code == 302
    t = Tarefa.objects.get()
    assert t.titulo == 'Ligar para Maria Nova'
    assert t.prioridade == 'alta'
    assert t.vencimento == timezone.localdate() + timedelta(days=2)
    assert t.responsavel_id == usuario_operacional.id
    assert t.contato.nome == 'Maria Nova'
    # log de execução + contador
    assert RegistroExecucao.objects.filter(automacao=auto).count() == 1
    auto.refresh_from_db()
    assert auto.total_execucoes == 1


@pytest.mark.django_db
def test_trigger_movido_filtra_por_etapa_destino(tenant_aurora, admin_company):
    auto = _auto(tenant_aurora, trigger='negocio_movido', parametros={'para_etapa': 'orcamento'},
                 criado_por=admin_company)
    _passo(auto, 'nota', texto='Chegou no orçamento!')
    contato = _contato(tenant_aurora)
    negocio = criar_negocio(contato, stage='interessado', tenant_id=tenant_aurora.id)
    c = _cliente_web(admin_company)

    # move para etapa errada → nada acontece
    c.post(f'/funil/{negocio.id}/mover/', {'stage': 'avaliacao_feita'})
    assert Nota.objects.count() == 0

    # move para o orçamento → dispara
    c.post(f'/funil/{negocio.id}/mover/', {'stage': 'orcamento'})
    nota = Nota.objects.get()
    assert nota.texto == 'Chegou no orçamento!'
    assert nota.contato_id == contato.id
    assert nota.autor_id == admin_company.id


@pytest.mark.django_db
def test_trigger_movido_sem_etapa_dispara_qualquer_mudanca(tenant_aurora, admin_company):
    auto = _auto(tenant_aurora, trigger='negocio_movido', parametros={}, criado_por=admin_company)
    _passo(auto, 'tag', tag='Movido')
    contato = _contato(tenant_aurora)
    negocio = criar_negocio(contato, stage='interessado', tenant_id=tenant_aurora.id)
    c = _cliente_web(admin_company)
    c.post(f'/funil/{negocio.id}/mover/', {'stage': 'avaliacao_feita'})
    assert contato.tags.filter(nome='Movido').exists()


@pytest.mark.django_db
def test_automacao_inativa_nao_executa(tenant_aurora, admin_company):
    auto = _auto(tenant_aurora, ativa=False, criado_por=admin_company)
    _passo(auto, 'tarefa', titulo='Não deve nascer')
    c = _cliente_web(admin_company)
    c.post('/contatos/novo/', _dados_contato('Ana Inativa'))
    assert Tarefa.objects.count() == 0
    assert RegistroExecucao.objects.count() == 0


@pytest.mark.django_db
def test_acao_email_simula_envio(tenant_aurora, admin_company):
    modelo = ModeloEmail.objects.create(
        tenant=tenant_aurora, nome='Boas-vindas', assunto='Olá {{nome}}',
        corpo='Tudo bem, {{nome}}?',
    )
    auto = _auto(tenant_aurora, criado_por=admin_company)
    _passo(auto, 'email', modelo_id=modelo.id)
    c = _cliente_web(admin_company)
    c.post('/contatos/novo/', _dados_contato('Cliente Email', email='cliente@x.com'))
    envio = EmailEnviado.objects.get()
    assert envio.destinatario == 'cliente@x.com'
    assert envio.status == 'simulado'  # sem SMTP nos testes
    assert 'Cliente Email' in envio.assunto


@pytest.mark.django_db
def test_acao_email_sem_endereco_nao_cria_envio(tenant_aurora, admin_company):
    from automacoes.engine import disparar
    modelo = ModeloEmail.objects.create(tenant=tenant_aurora, nome='M', assunto='A', corpo='C')
    auto = _auto(tenant_aurora, criado_por=admin_company)
    _passo(auto, 'email', modelo_id=modelo.id)
    contato = _contato(tenant_aurora, nome='Sem Email')  # e-mail default '—'
    disparar('contato_criado', tenant_id=tenant_aurora.id, contato=contato, negocio=contato.negocio)
    assert EmailEnviado.objects.count() == 0  # e-mail default '—' é tratado como vazio
    assert RegistroExecucao.objects.get().status == 'ok'


@pytest.mark.django_db
def test_acao_tarefa_descarta_responsavel_de_outro_tenant(tenant_aurora, tenant_beta, admin_company):
    from acesso.models import Usuario
    from django.contrib.auth.hashers import make_password
    beta = Usuario.objects.create(nome='Beta', email='beta@x.com', role='admin_company',
                                  tenant=tenant_beta, senha=make_password('senha123'))
    auto = _auto(tenant_aurora, criado_por=admin_company)
    _passo(auto, 'tarefa', titulo='Tarefa', responsavel_id=beta.id)
    c = _cliente_web(admin_company)
    c.post('/contatos/novo/', _dados_contato('Ana'))
    t = Tarefa.objects.get()
    assert t.responsavel_id is None  # responsável de outra clínica descartado


@pytest.mark.django_db
def test_placeholders_de_etapa_e_valor(tenant_aurora, admin_company):
    auto = _auto(tenant_aurora, trigger='negocio_movido', parametros={}, criado_por=admin_company)
    _passo(auto, 'nota', texto='{{nome}} agora em {{etapa}} ({{valor}})')
    contato = _contato(tenant_aurora, empresa='Clínica X')
    negocio = criar_negocio(contato, stage='interessado', valor=1500, tenant_id=tenant_aurora.id)
    c = _cliente_web(admin_company)
    c.post(f'/funil/{negocio.id}/mover/', {'stage': 'orcamento'})
    nota = Nota.objects.get()
    assert nota.texto == 'Ana agora em Orçamento enviado (R$ 1.500,00)'


# --- Isolamento por tenant ---


@pytest.mark.django_db
def test_automacao_de_outra_clinica_nao_dispara(tenant_aurora, tenant_beta, admin_company):
    from acesso.models import Usuario
    from django.contrib.auth.hashers import make_password
    beta_admin = Usuario.objects.create(nome='Beta', email='beta@beta.com', role='admin_company',
                                        tenant=tenant_beta, senha=make_password('senha123'))
    _auto(tenant_aurora, criado_por=admin_company)
    _passo(Automacao.objects.get(), 'tarefa', titulo='Só da Aurora')

    c = _cliente_web(beta_admin)
    c.post('/contatos/novo/', _dados_contato('Cliente Beta'))
    assert Tarefa.objects.count() == 0

    # contato na Aurora dispara a regra da Aurora
    c2 = _cliente_web(admin_company)
    c2.post('/contatos/novo/', _dados_contato('Cliente Aurora'))
    assert Tarefa.objects.count() == 1


# --- Estagnados ---


@pytest.mark.django_db
def test_comando_estagnados_dispara_para_negocio_parado(tenant_aurora, admin_company):
    auto = _auto(tenant_aurora, trigger='negocio_estagnado', parametros={'dias': 5},
                 criado_por=admin_company)
    _passo(auto, 'tarefa', titulo='Recuperar negócio de {{nome}}')
    contato = _contato(tenant_aurora)
    negocio = criar_negocio(contato, stage='interessado', tenant_id=tenant_aurora.id)
    # simula um negócio sem movimentação há 10 dias
    Negocio.objects.filter(pk=negocio.pk).update(updated_at=timezone.now() - timedelta(days=10))

    call_command('verificar_estagnados', '--tenant', str(tenant_aurora.id))
    t = Tarefa.objects.get()
    assert t.titulo == 'Recuperar negócio de Ana'
    assert RegistroExecucao.objects.filter(automacao=auto).count() == 1

    # negócio fechado/perdido não é varrido
    Negocio.objects.filter(pk=negocio.pk).update(stage='fechado')
    call_command('verificar_estagnados', '--tenant', str(tenant_aurora.id))
    assert Tarefa.objects.count() == 1


@pytest.mark.django_db
def test_botao_estagnadas_na_web(tenant_aurora, admin_company):
    _auto(tenant_aurora, trigger='negocio_estagnado', parametros={'dias': 1})
    _passo(Automacao.objects.get(), 'tarefa', titulo='Recuperar')
    contato = _contato(tenant_aurora)
    negocio = criar_negocio(contato, stage='interessado', tenant_id=tenant_aurora.id)
    Negocio.objects.filter(pk=negocio.pk).update(updated_at=timezone.now() - timedelta(days=3))
    c = _cliente_web(admin_company)
    r = c.post('/automacoes/estagnadas/', {})
    assert r.status_code == 302
    assert Tarefa.objects.count() == 1


# --- Permissões ---


@pytest.mark.django_db
def test_operacional_nao_gerencia(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.post('/automacoes/nova/', _payload_auto())
    assert r.status_code == 302  # redirecionado (web_requer_admin)
    assert Automacao.objects.count() == 0


@pytest.mark.django_db
def test_viewer_ve_lista_sem_acoes_de_gestao(tenant_aurora, usuario_viewer):
    _auto(tenant_aurora, nome='Regra visível')
    c = _cliente_web(usuario_viewer)
    html = c.get('/automacoes/').content.decode()
    assert 'Regra visível' in html
    assert 'Nova automação' not in html  # sem botão de criar


@pytest.mark.django_db
def test_admin_saas_abre_pagina(admin_saas):
    c = _cliente_web(admin_saas)
    assert c.get('/automacoes/').status_code == 200


# --- Outros pontos de evento ---


@pytest.mark.django_db
def test_captura_publica_dispara_automacao(tenant_aurora, admin_company):
    tenant_aurora.token_captura = 'token-secreto-123'
    tenant_aurora.save(update_fields=['token_captura'])
    auto = _auto(tenant_aurora, criado_por=admin_company)
    _passo(auto, 'tarefa', titulo='Lead novo: {{nome}}')
    c = Client()
    r = c.post('/captura/token-secreto-123/', {'nome': 'João Captura', 'tel': '(11) 98888-0000'})
    assert r.status_code == 200
    t = Tarefa.objects.get()
    assert t.titulo == 'Lead novo: João Captura'
    assert t.contato.tel == '(11) 98888-0000'


@pytest.mark.django_db
def test_importador_dispara_automacao(tenant_aurora, admin_company):
    from contatos.importador import importar_linhas
    auto = _auto(tenant_aurora, criado_por=admin_company)
    _passo(auto, 'tarefa', titulo='Importado: {{nome}}')
    cabecalhos = ['Nome', 'Telefone']
    linhas = [['Ana Importada', '(11) 90000-1111']]
    mapeamento = {'nome': 0, 'tel': 1}
    relatorio = importar_linhas(cabecalhos, linhas, mapeamento, tenant_aurora.id, nicho='saude')
    assert relatorio['importados'] == 1
    t = Tarefa.objects.get()
    assert t.titulo == 'Importado: Ana Importada'


@pytest.mark.django_db(transaction=True)
def test_api_cria_contato_dispara_automacao(client, tenant_aurora, headers_operacional, admin_company):
    auto = _auto(tenant_aurora, criado_por=admin_company)
    _passo(auto, 'tarefa', titulo='API: {{nome}}')
    r = client.post('/api/v1/contatos/', json={
        'nome': 'Contato API', 'seg': 'estetica', 'stage': 'interessado', 'valor': 500,
    }, headers=headers_operacional)
    assert r.status_code == 201
    t = Tarefa.objects.get()
    assert t.titulo == 'API: Contato API'
    assert t.tenant_id == tenant_aurora.id


@pytest.mark.django_db
def test_editar_contato_muda_etapa_dispara(client, tenant_aurora, admin_company):
    auto = _auto(tenant_aurora, trigger='negocio_movido', parametros={}, criado_por=admin_company)
    _passo(auto, 'nota', texto='Etapa alterada')
    contato = _contato(tenant_aurora)
    criar_negocio(contato, stage='interessado', tenant_id=tenant_aurora.id)
    c = _cliente_web(admin_company)
    r = c.post(f'/contatos/{contato.id}/editar/', _dados_contato(contato.nome, stage='avaliacao_agendada'))
    assert r.status_code == 302
    assert Nota.objects.filter(texto='Etapa alterada').count() == 1

    # mesmo stage → não dispara de novo
    r = c.post(f'/contatos/{contato.id}/editar/', _dados_contato(contato.nome, stage='avaliacao_agendada'))
    assert Nota.objects.filter(texto='Etapa alterada').count() == 1


@pytest.mark.django_db
def test_testar_executa_uma_vez(tenant_aurora, admin_company):
    auto = _auto(tenant_aurora, criado_por=admin_company)
    _passo(auto, 'tarefa', titulo='Teste')
    _contato(tenant_aurora, nome='Contato Teste')
    c = _cliente_web(admin_company)
    r = c.post(f'/automacoes/{auto.id}/testar/', {})
    assert r.status_code == 302
    assert Tarefa.objects.count() == 1
    assert RegistroExecucao.objects.filter(automacao=auto).count() == 1


@pytest.mark.django_db
def test_negocio_novo_na_ficha_dispara_negocio_criado(tenant_aurora, admin_company):
    auto = _auto(tenant_aurora, trigger='negocio_criado', criado_por=admin_company)
    _passo(auto, 'tarefa', titulo='Novo negócio de {{nome}}')
    contato = _contato(tenant_aurora)
    c = _cliente_web(admin_company)
    r = c.post(f'/contatos/{contato.id}/negocios/novo/', {
        'titulo': 'Tratamento completo', 'stage': 'orcamento', 'valor': '2500,00',
    })
    assert r.status_code == 302
    t = Tarefa.objects.get()
    assert t.titulo == 'Novo negócio de Ana'
    assert t.contato_id == contato.id
