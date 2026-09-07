"""Testes do importador de contatos — parse de CSV, normalização e deduplicação."""
from decimal import Decimal

import pytest

from contatos.importador import (
    importar_linhas,
    normalizar_data,
    normalizar_seg,
    normalizar_stage,
    normalizar_valor,
    parse_csv,
    sugerir_mapeamento,
)
from contatos.models import Contato


@pytest.mark.django_db
def test_parse_csv_ponto_e_virgula():
    cab, linhas = parse_csv(b'Nome;Telefone\nAna;11999999999\n')
    assert cab == ['Nome', 'Telefone']
    assert linhas == [['Ana', '11999999999']]


@pytest.mark.django_db
def test_parse_csv_virgula_com_aspas():
    cab, linhas = parse_csv(b'nome,email\n"Silva, Ana",ana@x.com\n')
    assert cab == ['nome', 'email']
    assert linhas == [['Silva, Ana', 'ana@x.com']]


@pytest.mark.django_db
def test_parse_csv_sem_cabecalho():
    cab, linhas = parse_csv(b'Ana;11999999999\n', tem_cabecalho=False)
    assert cab == ['Coluna 1', 'Coluna 2']
    assert len(linhas) == 1


@pytest.mark.django_db
def test_parse_csv_vazio_erro():
    with pytest.raises(ValueError):
        parse_csv(b'')


@pytest.mark.django_db
def test_parse_csv_so_cabecalho_erro():
    with pytest.raises(ValueError):
        parse_csv(b'Nome;Telefone\n')


def test_normalizar_valor():
    assert normalizar_valor('1.234,56') == Decimal('1234.56')
    assert normalizar_valor('1234,56') == Decimal('1234.56')
    assert normalizar_valor('R$ 1.500,00') == Decimal('1500.00')
    assert normalizar_valor('1234.56') == Decimal('1234.56')
    assert normalizar_valor('abc') is None
    assert normalizar_valor('-5') is None
    assert normalizar_valor('') is None


def test_normalizar_stage():
    assert normalizar_stage('Suplica') == 'suplica'
    assert normalizar_stage('suplica') == 'suplica'
    assert normalizar_stage('Prefeito') == 'prefeito'
    assert normalizar_stage('Desconhecido') == 'suplica'
    assert normalizar_stage('') == 'suplica'


def test_normalizar_seg():
    assert normalizar_seg('Eletrônicos') == 'eletronicos'
    assert normalizar_seg('eletronicos') == 'eletronicos'
    assert normalizar_seg('Moda') == 'moda'
    assert normalizar_seg('') == ''


def test_normalizar_data():
    assert normalizar_data('15/03/1990') == '1990-03-15'
    assert normalizar_data('1990-03-15') == '1990-03-15'
    assert normalizar_data('') is None


def test_sugerir_mapeamento():
    sugestoes = sugerir_mapeamento(['Nome', 'Telefone', 'E-mail', 'Valor', 'Etapa'])
    assert sugestoes == {'nome': 0, 'tel': 1, 'email': 2, 'valor': 3, 'stage': 4}


@pytest.mark.django_db
def test_importa_e_deduplica(tenant_aurora):
    Contato.objects.create(
        nome='Existente', tel='(11) 99999-8888', email='x@y.com',
        seg='', tenant=tenant_aurora,
    )
    cab = ['Nome', 'Telefone', 'E-mail', 'Etapa', 'Valor']
    linhas = [
        ['Novo1', '11999998888', 'outro@y.com', 'Fechado', '1.234,56'],  # dup. por telefone
        ['Novo2', '11988887777', 'x@y.com', 'Interessado', '100'],       # dup. por e-mail
        ['Novo3', '11977776666', 'n3@y.com', 'Perdido', ''],             # novo
    ]
    rel = importar_linhas(
        cab, linhas, {'nome': 0, 'tel': 1, 'email': 2, 'stage': 3, 'valor': 4},
        tenant_aurora.id, nicho='saude',
    )
    assert rel['importados'] == 1
    assert rel['duplicados'] == 2
    assert rel['erros'] == 0
    assert Contato.objects.filter(tenant=tenant_aurora).count() == 2
    novo = Contato.objects.get(nome='Novo3')
    assert novo.stage == 'perdido'
    assert novo.valor == Decimal(0)


@pytest.mark.django_db
def test_duplicado_dentro_do_arquivo(tenant_aurora):
    cab = ['Nome', 'Telefone']
    linhas = [
        ['A', '11999990000'],
        ['B', '11999990000'],
    ]
    rel = importar_linhas(cab, linhas, {'nome': 0, 'tel': 1}, tenant_aurora.id)
    assert rel['importados'] == 1
    assert rel['duplicados'] == 1


@pytest.mark.django_db
def test_linha_sem_nome_vira_erro(tenant_aurora):
    cab = ['Nome']
    rel = importar_linhas(cab, [['']], {'nome': 0}, tenant_aurora.id)
    assert rel['importados'] == 0
    assert rel['erros'] == 1
    assert rel['detalhes_erros'][0][1] == 'sem nome'
    assert rel['detalhes_erros'][0][0] == 2  # linha 2 do arquivo (apos cabecalho)


@pytest.mark.django_db
def test_nao_pula_duplicado_quando_desligado(tenant_aurora):
    Contato.objects.create(
        nome='Existente', tel='(11) 99999-8888', email='', seg='',
        tenant=tenant_aurora,
    )
    cab = ['Nome', 'Telefone']
    rel = importar_linhas(
        cab, [['Novo', '11999998888']], {'nome': 0, 'tel': 1},
        tenant_aurora.id, pular_duplicadas=False,
    )
    assert rel['importados'] == 1
    assert Contato.objects.filter(tenant=tenant_aurora).count() == 2


@pytest.mark.django_db
def test_importa_com_tags_e_segmento(tenant_aurora):
    cab = ['Nome', 'Segmento', 'Tags']
    linhas = [['Ana', 'Eletrônicos', 'VIP, Retorno']]
    rel = importar_linhas(
        cab, linhas, {'nome': 0, 'seg': 1, 'tags': 2}, tenant_aurora.id,
    )
    assert rel['importados'] == 1
    contato = Contato.objects.get(nome='Ana')
    assert contato.seg == 'eletronicos'
    assert sorted(contato.tags.values_list('nome', flat=True)) == ['Retorno', 'VIP']


@pytest.mark.django_db
def test_data_invalida_vira_erro(tenant_aurora):
    cab = ['Nome', 'Nascimento']
    linhas = [['Ana', '31/02/2020']]
    rel = importar_linhas(cab, linhas, {'nome': 0, 'nascimento': 1}, tenant_aurora.id)
    assert rel['importados'] == 0
    assert rel['erros'] == 1
    assert rel['detalhes_erros'][0][1] == 'data de nascimento inválida'
    assert not Contato.objects.filter(nome='Ana').exists()


@pytest.mark.django_db
def test_tenant_nao_importa_dados_de_outro_tenant(tenant_aurora, tenant_beta):
    Contato.objects.create(
        nome='Da Aurora', tel='11999998888', email='', seg='',
        tenant=tenant_aurora,
    )
    cab = ['Nome', 'Telefone']
    rel = importar_linhas(
        cab, [['Da Beta', '11999998888']], {'nome': 0, 'tel': 1}, tenant_beta.id,
    )
    assert rel['importados'] == 1  # dedupe é por tenant
    assert Contato.objects.filter(tenant=tenant_beta, nome='Da Beta').exists()
