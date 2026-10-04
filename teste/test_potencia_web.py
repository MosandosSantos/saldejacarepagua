"""Testes web do CRUD de Potências com os novos campos.

Cobre: inclusão/edição com contatos de cargo (secretário/tesoureiro), PIX,
valor e vencimento da anuidade, e a listagem com sigla/anuidade/vencimento.
Regressão: e-mail coletado no form agora é persistido (coluna nova).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from core.gprb import connection as gconn
from repositories import gprb_repository as repo

SENHA = 'senha123'

pytestmark = pytest.mark.django_db(transaction=True)


def _login(email):
    c = Client()
    resp = c.post('/login/', {'email': email, 'senha': SENHA})
    assert resp.status_code == 302, f'login falhou para {email}'
    return c


@pytest.fixture
def seed_potencia(banco_gprb_teste):
    """Tenant GPRB (reusa o existente ou cria) no banco de teste."""
    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute('SELECT id FROM tenant WHERE code = %s ORDER BY "createdAt" LIMIT 1', ('GPRB',))
    row = cur.fetchone()
    criei_tenant = False
    if row is None:
        tid = 'test-tenant-potencia'
        cur.execute(
            'INSERT INTO tenant (id, code, name, "createdAt", "updatedAt") '
            'VALUES (%s, %s, %s, NOW(), NOW())',
            (tid, 'GPRB', 'Sal da Britânea (teste)'),
        )
        criei_tenant = True
    else:
        tid = row[0]
    yield {'tenant': tid}
    if criei_tenant:
        cur.execute('DELETE FROM prefeitura WHERE "tenantId" = %s', (tid,))
        cur.execute('DELETE FROM tenant WHERE id = %s', (tid,))


def _criar_potencia(nome, sigla='', pix='', valor=None, vencimento=None):
    """Insere prefeitura direto no banco e devolve o id gerado."""
    tid = None
    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute('SELECT id FROM tenant WHERE code = %s ORDER BY "createdAt" LIMIT 1', ('GPRB',))
    row = cur.fetchone()
    assert row is not None, 'tenant GPRB precisa existir (use o fixture seed_potencia)'
    tid = row[0]
    cur.execute(
        'INSERT INTO prefeitura (id, "tenantId", nome, sigla, prefeito, telefone, email, pix, '
        '"valorAnuidade", "dataVencimentoAnuidade", status, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()) RETURNING id',
        ('test-pf-' + nome[:8].lower(), tid, nome, sigla or None, 'GM ' + nome,
         '(21) 90000-0000', 'gm@' + nome.split()[0].lower() + '.com', pix or None,
         valor, vencimento, 'ATIVA'),
    )
    return cur.fetchone()[0]


def test_incluir_potencia_salva_todos_os_campos(seed_potencia, usuario_operacional):
    c = _login('oper@aurora.com')
    r = c.post('/contatos/prefeitura/nova/', {
        'nome': 'Potência Inclusao Teste', 'sigla': 'PIT', 'prefeito': 'GM Teste',
        'telefone': '(21) 99999-0001', 'email': 'gm@pit.com',
        'secretario_email': 'sec@pit.com', 'secretario_telefone': '(21) 99999-0002',
        'tesoureiro_email': 'tes@pit.com', 'tesoureiro_telefone': '(21) 99999-0003',
        'valor_anuidade': '1.500,00', 'vencimento_anuidade': '2027-01-31',
        'pix': '12345678900',
    })
    assert r.status_code == 302

    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute('SELECT id FROM prefeitura WHERE nome = %s', ('Potência Inclusao Teste',))
    pid = cur.fetchone()[0]

    pf = repo.buscar_prefeitura(pid)
    assert pf['sigla'] == 'PIT'
    assert pf['prefeito'] == 'GM Teste'
    assert pf['email'] == 'gm@pit.com'  # regressão: antes o e-mail era descartado
    assert pf['secretario_email'] == 'sec@pit.com'
    assert pf['secretario_telefone'] == '(21) 99999-0002'
    assert pf['tesoureiro_email'] == 'tes@pit.com'
    assert pf['tesoureiro_telefone'] == '(21) 99999-0003'
    assert pf['pix'] == '12345678900'
    assert pf['valor_anuidade'] == Decimal('1500.00')
    assert pf['vencimento_anuidade'] == date(2027, 1, 31)

    # limpeza
    cur.execute('DELETE FROM prefeitura WHERE id = %s', (pid,))


def test_editar_potencia_atualiza_campos(seed_potencia, usuario_operacional):
    pid = _criar_potencia('Pot Edicao', sigla='PED', valor=Decimal('1000.00'))
    c = _login('oper@aurora.com')

    r = c.post(f'/contatos/prefeitura/{pid}/editar/', {
        'nome': 'Pot Edicao', 'sigla': 'PED', 'prefeito': 'GM Editado',
        'telefone': '(21) 98888-0000', 'email': 'gm@ped.com',
        'secretario_email': 'sec@ped.com', 'secretario_telefone': '(21) 98888-0001',
        'tesoureiro_email': 'tes@ped.com', 'tesoureiro_telefone': '(21) 98888-0002',
        'valor_anuidade': '2.000,00', 'vencimento_anuidade': '2027-12-31',
        'pix': 'chave@pix.com',
    })
    assert r.status_code == 302

    pf = repo.buscar_prefeitura(pid)
    assert pf['prefeito'] == 'GM Editado'
    assert pf['pix'] == 'chave@pix.com'
    assert pf['valor_anuidade'] == Decimal('2000.00')
    assert pf['vencimento_iso'] == '2027-12-31'

    # página de edição traz os valores salvos
    html = c.get(f'/contatos/prefeitura/{pid}/editar/').content.decode()
    assert 'chave@pix.com' in html
    assert 'sec@ped.com' in html

    gconn.connect().cursor().execute('DELETE FROM prefeitura WHERE id = %s', (pid,))


def test_lista_mostra_sigla_anuidade_e_vencimento(seed_potencia, usuario_operacional):
    pid = _criar_potencia(
        'Pot Lista Teste', sigla='PLT',
        valor=Decimal('1500.00'), vencimento=date(2027, 1, 31),
    )
    c = _login('oper@aurora.com')
    html = c.get('/contatos/prefeituras/').content.decode()
    assert 'Pot Lista Teste' in html
    assert 'PLT' in html
    assert 'R$ 1.500,00' in html
    assert '31/01/2027' in html

    gconn.connect().cursor().execute('DELETE FROM prefeitura WHERE id = %s', (pid,))


def test_campos_opcionais_ficam_vazios(seed_potencia, usuario_operacional):
    c = _login('oper@aurora.com')
    r = c.post('/contatos/prefeitura/nova/', {'nome': 'Pot Minima'})
    assert r.status_code == 302

    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute('SELECT id FROM prefeitura WHERE nome = %s', ('Pot Minima',))
    pid = cur.fetchone()[0]
    pf = repo.buscar_prefeitura(pid)
    assert pf['pix'] == ''
    assert pf['valor_anuidade'] is None
    assert pf['vencimento_iso'] == ''
    cur.execute('DELETE FROM prefeitura WHERE id = %s', (pid,))


def test_excluir_potencia_sem_lojas_remove_registro(seed_potencia, usuario_operacional):
    pid = _criar_potencia('Pot Excluir Sem Lojas')
    c = _login('oper@aurora.com')

    html = c.get(f'/contatos/prefeitura/{pid}/excluir/')
    assert html.status_code == 200
    assert 'Pot Excluir Sem Lojas' in html.content.decode()

    r = c.post(f'/contatos/prefeitura/{pid}/excluir/')
    assert r.status_code == 302

    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM prefeitura WHERE id = %s', (pid,))
    assert cur.fetchone()[0] == 0


def test_excluir_potencia_com_lojas_e_bloqueada(seed_potencia, usuario_operacional):
    pid = _criar_potencia('Pot Excluir Com Lojas')
    try:
        repo.criar_loja({
            'nome': 'Loja da Pot Bloqueada', 'numero': '1',
            'prefeitura_id': pid,
        })
        c = _login('oper@aurora.com')

        r = c.post(f'/contatos/prefeitura/{pid}/excluir/')
        assert r.status_code == 200
        assert 'loja(s) vinculada(s)' in r.content.decode()

        conn = gconn.connect()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM prefeitura WHERE id = %s', (pid,))
        assert cur.fetchone()[0] == 1
    finally:
        conn = gconn.connect()
        cur = conn.cursor()
        cur.execute('DELETE FROM loja WHERE "prefeituraId" = %s', (pid,))
        cur.execute('DELETE FROM prefeitura WHERE id = %s', (pid,))
