"""Testes da Fase R — S6 do PRD HAZON (CRM, follow-up e acordos).

Simulador financeiro com regras de desconto configuráveis (6.3), registro de
acordo e PIX com BR Code estático (6.4), follow-up automático quando a chamada
do discador é 'Retornar depois' (6.2), configuração por empresa e API.
"""

from decimal import Decimal

import pytest
from django.test import Client

from acesso.models import Tenant
from acordos.models import Acordo, RegraDesconto
from acordos.pix import _crc16, montar_payload_pix, qrcode_svg
from acordos.servico import registrar_acordo, simular
from contatos.models import Contato
from discador.models import Chamada, Fila
from tarefas.models import Tarefa

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


def _contato(tenant, nome='Ana'):
    return Contato.objects.create(
        nome=nome, empresa='X', tel='(11) 98888-7777', email='ana@x.com',
        seg='geral', tenant=tenant,
    )


def _tenant_com_pix(tenant_aurora):
    tenant_aurora.pix_chave = '12345678000195'
    tenant_aurora.pix_recebedor = 'Empresa Aurora LTDA'
    tenant_aurora.pix_cidade = 'Sao Paulo'
    tenant_aurora.save(update_fields=['pix_chave', 'pix_recebedor', 'pix_cidade'])
    return tenant_aurora


# --- Simulador (6.3) ---

@pytest.mark.django_db
def test_simular_aplica_regras_padrao(tenant_aurora):
    opcoes = simular(1000, tenant_aurora.id)
    vista = [o for o in opcoes if o['modalidade'] == 'vista'][0]
    assert vista['percentual'] == 30
    assert vista['valor_final'] == 700
    assert vista['desconto'] == 300
    parcelado = [o for o in opcoes if o['modalidade'] == 'parcelado']
    assert {o['parcelas'] for o in parcelado} == {2, 3, 6}


@pytest.mark.django_db
def test_simular_usar_regras_do_tenant(tenant_aurora):
    RegraDesconto.objects.create(modalidade='vista', parcelas=1, percentual=25, tenant=tenant_aurora)
    RegraDesconto.objects.create(modalidade='parcelado', parcelas=4, percentual=10, tenant=tenant_aurora)
    opcoes = simular(1000, tenant_aurora.id)
    modalidades = [(o['modalidade'], o['parcelas']) for o in opcoes]
    assert ('vista', 1) in modalidades
    assert ('parcelado', 4) in modalidades
    assert all(o['percentual'] != 30 for o in opcoes)  # padrão substituído
    parcela4 = [o for o in opcoes if o['parcelas'] == 4][0]
    assert parcela4['valor_final'] == 900


@pytest.mark.django_db
def test_simular_valor_parcelado_redondo(tenant_aurora):
    opcoes = simular(1000, tenant_aurora.id)
    p3 = [o for o in opcoes if o['parcelas'] == 3][0]
    assert p3['valor_final'] == 850
    assert p3['parcela'] == Decimal('283.34')  # resto na última parcela


# --- Registro do acordo ---

@pytest.mark.django_db
def test_registrar_acordo_aceito(tenant_aurora):
    contato = _contato(tenant_aurora)
    acordo = registrar_acordo(contato, 1000, 'vista', 1, tenant_aurora.id)
    assert acordo.status == 'aceito'
    assert acordo.valor_final == 700
    assert acordo.percentual_desconto == 30
    assert acordo.contato_id == contato.id


@pytest.mark.django_db
def test_registrar_acordo_parcelado(tenant_aurora):
    contato = _contato(tenant_aurora)
    acordo = registrar_acordo(contato, 1000, 'parcelado', 3, tenant_aurora.id)
    assert acordo.valor_final == 850
    assert acordo.parcelas == 3
    assert acordo.valor_parcela == Decimal('283.34')


# --- PIX / BR Code (6.4) ---

@pytest.mark.django_db
def test_payload_pix_emv_valido(tenant_aurora):
    _tenant_com_pix(tenant_aurora)
    payload = montar_payload_pix(
        tenant_aurora.pix_chave, tenant_aurora.pix_recebedor, tenant_aurora.pix_cidade, '123.45',
    )
    assert payload.startswith('000201')
    assert 'BR.GOV.BCB.PIX' in payload
    assert '5303986' in payload  # moeda BRL
    assert payload[-4:] == _crc16(payload[:-4])  # CRC confere
    assert '5406123.45' in payload  # valor 123.45 (tag 54 + tamanho 06 + valor)


@pytest.mark.django_db
def test_payload_sem_chave_nao_quebra(tenant_aurora):
    payload = montar_payload_pix('', 'Empresa', 'Cidade', '10.00')
    assert payload.startswith('000201')
    assert payload[-4:] == _crc16(payload[:-4])


@pytest.mark.django_db
def test_qrcode_svg_renderiza(tenant_aurora):
    payload = montar_payload_pix('chave@x.com', 'Empresa', 'Cidade', '10.00')
    svg = qrcode_svg(payload)
    assert '<svg' in svg
    assert 'path' in svg or 'rect' in svg


# --- Web: lista / simular / registrar ---

@pytest.mark.django_db
def test_lista_acordos_renderiza(tenant_aurora, admin_company):
    contato = _contato(tenant_aurora)
    registrar_acordo(contato, 1000, 'vista', 1, tenant_aurora.id)
    html = _cliente_web(admin_company).get('/acordos/').content.decode()
    assert 'Ana' in html
    assert 'Aceito' in html


@pytest.mark.django_db
def test_simular_web_mostra_opcoes(tenant_aurora, admin_company):
    contato = _contato(tenant_aurora)
    c = _cliente_web(admin_company)
    r = c.get(f'/acordos/contato/{contato.id}/simular/')
    assert r.status_code == 200
    assert 'Simular acordo' in r.content.decode()
    r = c.post(f'/acordos/contato/{contato.id}/simular/', {'valor_original': '1000,00'})
    html = r.content.decode()
    assert 'À vista' in html and '30%' in html
    assert '3x' in html


@pytest.mark.django_db
def test_registrar_acordo_web(tenant_aurora, admin_company):
    contato = _contato(tenant_aurora)
    c = _cliente_web(admin_company)
    r = c.post(f'/acordos/contato/{contato.id}/registrar/', {
        'modalidade': 'parcelado', 'parcelas': '3', 'valor_original': '1000.00',
    })
    assert r.status_code == 302
    acordo = Acordo.objects.get(contato=contato)
    assert acordo.valor_final == 850
    assert acordo.status == 'aceito'


@pytest.mark.django_db
def test_detalhe_acordo_gera_pix(tenant_aurora, admin_company):
    _tenant_com_pix(tenant_aurora)
    contato = _contato(tenant_aurora)
    acordo = registrar_acordo(contato, 1000, 'vista', 1, tenant_aurora.id)
    c = _cliente_web(admin_company)
    r = c.get(f'/acordos/{acordo.id}/?gerar_pix=1')
    html = r.content.decode()
    assert '000201' in html  # payload copia-e-cola
    assert '<svg' in html    # QR Code
    acordo.refresh_from_db()
    assert acordo.status == 'pix_gerado'
    assert acordo.pix_payload.startswith('000201')


@pytest.mark.django_db
def test_marcar_pago(tenant_aurora, admin_company):
    contato = _contato(tenant_aurora)
    acordo = registrar_acordo(contato, 1000, 'vista', 1, tenant_aurora.id)
    r = _cliente_web(admin_company).post(f'/acordos/{acordo.id}/pago/')
    assert r.status_code == 302
    acordo.refresh_from_db()
    assert acordo.status == 'pago'
    assert acordo.pago_em is not None


@pytest.mark.django_db
def test_recusar_acordo(tenant_aurora, admin_company):
    contato = _contato(tenant_aurora)
    acordo = registrar_acordo(contato, 1000, 'vista', 1, tenant_aurora.id)
    r = _cliente_web(admin_company).post(f'/acordos/{acordo.id}/recusar/')
    assert r.status_code == 302
    acordo.refresh_from_db()
    assert acordo.status == 'recusado'


@pytest.mark.django_db
def test_isolamento_acordos_entre_tenants(tenant_aurora, tenant_beta, admin_company):
    contato_beta = _contato(tenant_beta)
    acordo_beta = registrar_acordo(contato_beta, 1000, 'vista', 1, tenant_beta.id)
    r = _cliente_web(admin_company).get(f'/acordos/{acordo_beta.id}/')
    assert r.status_code == 404


@pytest.mark.django_db
def test_viewer_nao_simula_acordo(tenant_aurora, usuario_viewer):
    contato = _contato(tenant_aurora)
    r = _cliente_web(usuario_viewer).post(f'/acordos/contato/{contato.id}/simular/', {'valor_original': '100'})
    assert r.status_code == 302  # sem permissão de edição
    assert Acordo.objects.count() == 0


# --- Follow-up automático (6.2) ---

@pytest.mark.django_db
def test_retornar_cria_tarefa_de_followup(tenant_aurora, usuario_operacional):
    contato = _contato(tenant_aurora)
    fila = Fila.objects.create(nome='F', tenant=tenant_aurora)
    chamada = Chamada.objects.create(fila=fila, contato=contato, operador_id=usuario_operacional.id,
                                     tenant=tenant_aurora)
    r = _cliente_web(usuario_operacional).post(
        f'/discador/chamadas/{chamada.id}/resultado/',
        data='{"status": "retornar", "retorno_em": "2026-09-01T10:00:00-03:00", "observacao": "Cliente ocupado"}',
        content_type='application/json')
    assert r.status_code == 200
    assert r.json()['followup'] is True
    tarefa = Tarefa.objects.get()
    assert tarefa.titulo.startswith('Retornar ligação')
    assert tarefa.contato_id == contato.id
    assert tarefa.responsavel_id == usuario_operacional.id
    assert str(tarefa.vencimento) == '2026-09-01'
    assert tarefa.prioridade == 'alta'


@pytest.mark.django_db
def test_resultado_sem_retorno_nao_cria_tarefa(tenant_aurora, usuario_operacional):
    contato = _contato(tenant_aurora)
    fila = Fila.objects.create(nome='F', tenant=tenant_aurora)
    chamada = Chamada.objects.create(fila=fila, contato=contato, operador_id=usuario_operacional.id,
                                     tenant=tenant_aurora)
    r = _cliente_web(usuario_operacional).post(
        f'/discador/chamadas/{chamada.id}/resultado/',
        data='{"status": "realizada"}', content_type='application/json')
    assert r.status_code == 200
    assert r.json()['followup'] is False
    assert Tarefa.objects.count() == 0


# --- Config (regras + PIX) ---

@pytest.mark.django_db
def test_config_salva_pix(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/config/', {
        'acao': 'pix_salvar', 'pix_chave': 'ana@empresa.com',
        'pix_recebedor': 'Empresa', 'pix_cidade': 'SP',
    })
    assert r.status_code == 200
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.pix_chave == 'ana@empresa.com'
    assert 'Dados do PIX atualizados'.encode() in r.content


@pytest.mark.django_db
def test_config_salva_regra_desconto(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/config/', {'acao': 'regra_desconto', 'modalidade': 'vista', 'parcelas': '1', 'percentual': '40'})
    assert r.status_code == 200
    assert RegraDesconto.objects.filter(tenant_id=tenant_aurora.id, modalidade='vista', parcelas=1, percentual=40).exists()
    assert 'Regra salva'.encode() in r.content


@pytest.mark.django_db
def test_config_operacional_nao_ve_acordos(tenant_aurora, usuario_operacional):
    html = _cliente_web(usuario_operacional).get('/config/').content.decode()
    assert 'Chave PIX' not in html
    assert 'regra_desconto' not in html


# --- API ---

def _login(client, usuario):
    from teste.conftest import fazer_login

    return fazer_login(client, usuario.email)


@pytest.mark.django_db(transaction=True)
def test_api_simular(client, tenant_aurora, usuario_operacional):
    contato = _contato(tenant_aurora)
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/acordos/simular', json={
        'contato_id': contato.id, 'valor_original': '1000',
    }, headers=headers)
    assert r.status_code == 200
    dados = r.json()
    assert dados[0]['modalidade'] == 'vista'
    assert float(dados[0]['valor_final']) == 700.0


@pytest.mark.django_db(transaction=True)
def test_api_cria_acordo(client, tenant_aurora, usuario_operacional):
    contato = _contato(tenant_aurora)
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/acordos', json={
        'contato_id': contato.id, 'valor_original': '1000',
        'modalidade': 'parcelado', 'parcelas': 3,
    }, headers=headers)
    assert r.status_code == 201
    assert r.json()['status'] == 'aceito'
    assert float(r.json()['valor_final']) == 850.0
    assert Acordo.objects.filter(tenant_id=tenant_aurora.id).exists()


@pytest.mark.django_db(transaction=True)
def test_api_acordo_contato_de_outro_tenant_404(client, tenant_aurora, tenant_beta, usuario_operacional):
    contato_beta = _contato(tenant_beta)
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/acordos', json={
        'contato_id': contato_beta.id, 'valor_original': '100', 'modalidade': 'vista', 'parcelas': 1,
    }, headers=headers)
    assert r.status_code == 404
    assert Acordo.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_api_viewer_nao_cria_acordo(client, tenant_aurora, usuario_viewer):
    contato = _contato(tenant_aurora)
    headers = _login(client, usuario_viewer)
    r = client.post('/api/v1/acordos', json={
        'contato_id': contato.id, 'valor_original': '100', 'modalidade': 'vista', 'parcelas': 1,
    }, headers=headers)
    assert r.status_code == 403
    assert Acordo.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_api_resultado_acordo(client, tenant_aurora, usuario_operacional):
    contato = _contato(tenant_aurora)
    acordo = registrar_acordo(contato, 1000, 'vista', 1, tenant_aurora.id)
    headers = _login(client, usuario_operacional)
    r = client.post(f'/api/v1/acordos/{acordo.id}/resultado',
                    json={'status': 'pago'}, headers=headers)
    assert r.status_code == 200
    assert r.json()['status'] == 'pago'
    acordo.refresh_from_db()
    assert acordo.status == 'pago'
