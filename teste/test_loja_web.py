"""Testes web do CRUD de Lojas com os campos novos.

Cobre: criacao com diretoria (secretario/tesoureiro), mensalidade (formato BR),
endereco em campo unico, obrigatoriedade da Potencia, edicao gravando os campos
novos, exibicao na lista/detalhe e exclusao (com e sem membros vinculados).
"""
import uuid

import pytest
from django.test import Client

from contatos.importador import normalizar_valor
from core.gprb import connection as gconn
from repositories import gprb_repository as repo

SENHA = 'senha123'

pytestmark = pytest.mark.django_db(transaction=True)

# Colunas que a suite espera na tabela loja do banco de teste (idempotente).
_COLUNAS = (
    ('mensalidade_regular', 'numeric(12,2)'),
    ('enderecoLogradouro', 'varchar(255)'),
    ('secretarioNome', 'varchar(255)'),
    ('secretarioTelefone', 'varchar(255)'),
    ('tesoureiroNome', 'varchar(255)'),
    ('tesoureiroTelefone', 'varchar(255)'),
)

_CRIADOS = {'lojas': [], 'prefeituras': []}


@pytest.fixture
def banco_loja(banco_gprb_teste):
    """Garante schema da loja no banco de teste + tenant GPRB, e limpa no fim."""
    conn = gconn.connect()
    cur = conn.cursor()
    for col, tipo in _COLUNAS:
        cur.execute(
            f'ALTER TABLE loja ADD COLUMN IF NOT EXISTS "{col}" {tipo}'  # nosec B608
        )
    cur.execute('SELECT id FROM tenant WHERE code = %s ORDER BY "createdAt" LIMIT 1', ('GPRB',))
    row = cur.fetchone()
    criei_tenant = False
    if row is None:
        tid = 'test-tenant-loja'
        cur.execute(
            'INSERT INTO tenant (id, code, name, "createdAt", "updatedAt") '
            'VALUES (%s, %s, %s, NOW(), NOW())',
            (tid, 'GPRB', 'Sal da Britânea (teste lojas)'),
        )
        criei_tenant = True
    _CRIADOS['lojas'].clear()
    _CRIADOS['prefeituras'].clear()
    yield {}
    for lid in _CRIADOS['lojas']:
        cur.execute('DELETE FROM loja WHERE id = %s', (lid,))
    for pid in _CRIADOS['prefeituras']:
        cur.execute('DELETE FROM prefeitura WHERE id = %s', (pid,))
    if criei_tenant:
        tid = 'test-tenant-loja'
        cur.execute('DELETE FROM loja WHERE "tenantId" = %s', (tid,))
        cur.execute('DELETE FROM prefeitura WHERE "tenantId" = %s', (tid,))
        cur.execute('DELETE FROM tenant WHERE id = %s', (tid,))


def _login(email):
    c = Client()
    resp = c.post('/login/', {'email': email, 'senha': SENHA})
    assert resp.status_code == 302, f'login falhou para {email}'
    return c


def _nome_unico(base):
    return f'{base} {uuid.uuid4().hex[:6]}'


def _criar_prefeitura(nome):
    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute('SELECT id FROM tenant WHERE code = %s ORDER BY "createdAt" LIMIT 1', ('GPRB',))
    tid = cur.fetchone()[0]
    cur.execute(
        'INSERT INTO prefeitura (id, "tenantId", nome, sigla, prefeito, telefone, email, pix, '
        '"valorAnuidade", "dataVencimentoAnuidade", status, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()) RETURNING id',
        ('test-pf-loja-' + uuid.uuid4().hex[:8], tid, nome, 'PLT', 'GM ' + nome,
         '(41) 90000-0000', 'gm@teste.com', None, None, None, 'ATIVA'),
    )
    pid = cur.fetchone()[0]
    _CRIADOS['prefeituras'].append(pid)
    return pid


def _id_da_loja(nome):
    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute(
        'SELECT id FROM loja WHERE "nomeFantasia" = %s ORDER BY "createdAt" DESC LIMIT 1',
        (nome,),
    )
    lid = cur.fetchone()[0]
    _CRIADOS['lojas'].append(lid)
    return lid


def _criar_loja_simples(nome, pid, mensalidade=None, endereco=''):
    """Cria loja pelo repository e devolve o id (já registrado p/ limpeza)."""
    repo.criar_loja({
        'nome': nome, 'numero': '1', 'telefone': '', 'email': '',
        'prefeitura_id': pid, 'cidade': '', 'uf': '',
        'endereco': endereco, 'secretario_nome': '', 'secretario_telefone': '',
        'tesoureiro_nome': '', 'tesoureiro_telefone': '', 'mensalidade': mensalidade,
    })
    return _id_da_loja(nome)


def _criar_membro_na_loja(nome, loja_id):
    """Cria membro ATIVO vinculado à loja (mesmo shape do seed de test_gprb_writes)."""
    conn = gconn.connect()
    cur = conn.cursor()
    mid = 'test-mem-' + uuid.uuid4().hex[:8]
    cur.execute(
        'INSERT INTO member (id, "tenantId", "nomeCompleto", cpf, email, celular, '
        '"enderecoLogradouro", "enderecoCep", "enderecoCidade", "enderecoUf", '
        'situacao, "createdAt", "updatedAt") '
        'VALUES (%s, (SELECT "tenantId" FROM loja WHERE id = %s), %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())',
        (mid, loja_id, nome, '000.000.000-00', nome.split()[0].lower() + '@teste.com',
         '(41) 90000-0000', 'Rua Teste', '00000-000', 'Curitiba', 'PR', 'ATIVO'),
    )
    cur.execute('INSERT INTO member_loja ("memberId", "lojaId") VALUES (%s, %s)', (mid, loja_id))
    return mid


def _excluir_membro(mid):
    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute('DELETE FROM member_loja WHERE "memberId" = %s', (mid,))
    cur.execute('DELETE FROM member WHERE id = %s', (mid,))


def test_criar_loja_salva_diretoria_mensalidade_e_endereco(banco_loja, usuario_operacional):
    pid = _criar_prefeitura('Pref Loja Criacao')
    nome = _nome_unico('Loja Criacao Teste')
    c = _login('oper@aurora.com')

    r = c.post('/contatos/loja/nova/', {
        'nome': nome, 'numero': '77', 'prefeitura': pid,
        'telefone': '(41) 97000-0001', 'email': 'loja@teste.com',
        'secretario_nome': 'Sec Silva', 'secretario_telefone': '(41) 97000-0002',
        'tesoureiro_nome': 'Tes Souza', 'tesoureiro_telefone': '(41) 97000-0003',
        'mensalidade': '150,00',
        'endereco': 'Rua das Torres, 77, Centro',
        'cidade': 'Curitiba', 'uf': 'PR',
    })
    assert r.status_code == 302

    loja = repo.buscar_loja(_id_da_loja(nome))
    assert loja['secretario'] == 'Sec Silva'
    assert loja['secretario_telefone'] == '(41) 97000-0002'
    assert loja['tesoureiro'] == 'Tes Souza'
    assert loja['tesoureiro_telefone'] == '(41) 97000-0003'
    assert loja['mensalidade'] == '150,00'
    assert loja['endereco'] == 'Rua das Torres, 77, Centro'


def test_criar_loja_exige_potencia(banco_loja, usuario_operacional):
    c = _login('oper@aurora.com')
    r = c.post('/contatos/loja/nova/', {'nome': 'Loja Sem Potencia Teste'})
    assert r.status_code == 200
    assert 'Potência' in r.content.decode()

    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM loja WHERE "nomeFantasia" = %s', ('Loja Sem Potencia Teste',))
    assert cur.fetchone()[0] == 0


def test_editar_loja_atualiza_campos_novos(banco_loja, usuario_operacional):
    pid = _criar_prefeitura('Pref Loja Edicao')
    nome = _nome_unico('Loja Edicao Teste')
    repo.criar_loja({
        'nome': nome, 'numero': '10', 'telefone': '', 'email': '',
        'prefeitura_id': pid, 'cidade': 'Curitiba', 'uf': 'PR',
        'endereco': 'Rua Antiga, 1, Bairro Velho',
        'secretario_nome': 'Sec Orig', 'secretario_telefone': '',
        'tesoureiro_nome': 'Tes Orig', 'tesoureiro_telefone': '',
        'mensalidade': None,
    })
    lid = _id_da_loja(nome)
    c = _login('oper@aurora.com')

    r = c.post(f'/contatos/loja/{lid}/editar/', {
        'nome': nome, 'numero': '10', 'telefone': '(41) 98000-0000',
        'email': 'loja@editada.com', 'prefeitura': pid,
        'secretario_nome': 'Sec Editado', 'secretario_telefone': '(41) 98000-0001',
        'tesoureiro_nome': 'Tes Editado', 'tesoureiro_telefone': '(41) 98000-0002',
        'mensalidade': '200,00',
        'endereco': 'Rua Editada, 456, Bairro Novo',
        'cidade': 'Curitiba', 'uf': 'PR', 'deputado_mestre': '',
    })
    assert r.status_code == 302

    loja = repo.buscar_loja(lid)
    assert loja['secretario'] == 'Sec Editado'
    assert loja['tesoureiro'] == 'Tes Editado'
    assert loja['mensalidade'] == '200,00'
    assert loja['endereco'] == 'Rua Editada, 456, Bairro Novo'

    html = c.get(f'/contatos/loja/{lid}/editar/').content.decode()
    assert 'Sec Editado' in html
    assert '200,00' in html


def test_lista_exibe_diretoria_e_mensalidade(banco_loja, usuario_operacional):
    pid = _criar_prefeitura('Pref Loja Lista')
    nome = _nome_unico('Loja Lista Teste')
    repo.criar_loja({
        'nome': nome, 'numero': '20', 'telefone': '', 'email': '',
        'prefeitura_id': pid, 'cidade': '', 'uf': '',
        'endereco': '', 'secretario_nome': 'Sec Lista', 'secretario_telefone': '',
        'tesoureiro_nome': '', 'tesoureiro_telefone': '', 'mensalidade': 150,
    })
    lid = _id_da_loja(nome)
    c = _login('oper@aurora.com')

    html = c.get(f'/contatos/lojas/?q={nome}').content.decode()
    assert nome in html
    assert 'Sec Lista' in html
    assert 'R$ 150,00' in html


def test_detalhe_exibe_diretoria_e_mensalidade(banco_loja, usuario_operacional):
    pid = _criar_prefeitura('Pref Loja Detalhe')
    nome = _nome_unico('Loja Detalhe Teste')
    repo.criar_loja({
        'nome': nome, 'numero': '30', 'telefone': '', 'email': '',
        'prefeitura_id': pid, 'cidade': '', 'uf': '',
        'endereco': 'Rua Detalhe, 9, Centro',
        'secretario_nome': 'Sec Detalhe', 'secretario_telefone': '(41) 99000-0001',
        'tesoureiro_nome': 'Tes Detalhe', 'tesoureiro_telefone': '',
        'mensalidade': normalizar_valor('1.800,00'),
    })
    lid = _id_da_loja(nome)
    c = _login('oper@aurora.com')

    html = c.get(f'/contatos/loja/{lid}/').content.decode()
    assert 'Sec Detalhe' in html
    assert 'Tes Detalhe' in html
    assert 'R$ 1.800,00' in html
    assert 'Rua Detalhe, 9, Centro' in html


def test_excluir_loja_sem_membros_remove_registro(banco_loja, usuario_operacional):
    pid = _criar_prefeitura('Pref Loja Excluir')
    nome = _nome_unico('Loja Excluir Teste')
    lid = _criar_loja_simples(nome, pid)
    c = _login('oper@aurora.com')

    html = c.get(f'/contatos/loja/{lid}/excluir/')
    assert html.status_code == 200
    assert nome in html.content.decode()

    r = c.post(f'/contatos/loja/{lid}/excluir/')
    assert r.status_code == 302
    assert repo.buscar_loja(lid) is None


def test_excluir_loja_com_membros_e_bloqueada(banco_loja, usuario_operacional):
    pid = _criar_prefeitura('Pref Loja Excluir Bloq')
    nome = _nome_unico('Loja Bloqueada Teste')
    lid = _criar_loja_simples(nome, pid)
    mid = _criar_membro_na_loja('Membro Bloqueio', lid)
    try:
        c = _login('oper@aurora.com')
        r = c.post(f'/contatos/loja/{lid}/excluir/')
        assert r.status_code == 200
        assert 'vinculado(s)' in r.content.decode()
        assert repo.buscar_loja(lid) is not None
    finally:
        _excluir_membro(mid)


def test_membros_json_da_loja_retorna_membros(banco_loja, usuario_operacional):
    pid = _criar_prefeitura('Pref Loja Json')
    nome = _nome_unico('Loja Json Teste')
    lid = _criar_loja_simples(nome, pid)
    mid = _criar_membro_na_loja('Membro Json Teste', lid)
    try:
        c = _login('oper@aurora.com')
        r = c.get(f'/contatos/loja/{lid}/membros-json/')
        assert r.status_code == 200
        nomes = [m['nome'] for m in r.json()['membros']]
        assert 'Membro Json Teste' in nomes
    finally:
        _excluir_membro(mid)
