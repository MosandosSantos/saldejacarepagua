"""Testes web do CRUD de Membros GPRB (views/gprb_membros.py).

Cobre: detalhe (feliz + 404), edicao (GET preenchido, POST gravando campos e
lojas N:N, nome obrigatorio, data invalida) e exclusao/inativacao.
Reaproveita o mesmo seed idempotente de test_gprb_writes (tenant + potencia +
2 lojas + 1 membro no banco `saldabritanea_test`).
"""
import pytest
from django.test import Client

from core.gprb import connection as gconn
from repositories import gprb_repository as repo

SENHA = 'senha123'

pytestmark = pytest.mark.django_db(transaction=True)

TID, PID, MID = 'test-tenant-0001', 'test-pf-0001', 'test-mem-0001'
LOJAS = ['test-loja-0001', 'test-loja-0002']


@pytest.fixture
def seed_membro(banco_gprb_teste):
    """Tenant GPRB + potencia + 2 lojas + 1 membro no banco de teste."""
    conn = gconn.connect()
    cur = conn.cursor()
    # idempotencia: limpa restos de execucoes anteriores
    cur.execute('DELETE FROM member_loja WHERE "memberId" = %s OR "lojaId" = ANY(%s)', (MID, LOJAS))
    cur.execute('DELETE FROM member WHERE id = %s', (MID,))
    cur.execute('DELETE FROM loja WHERE id = ANY(%s)', (LOJAS,))
    cur.execute('DELETE FROM prefeitura WHERE id = %s', (PID,))
    cur.execute('DELETE FROM tenant WHERE id = %s', (TID,))
    cur.execute(
        'INSERT INTO tenant (id, code, name, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, NOW(), NOW()) ON CONFLICT (id) DO NOTHING',
        (TID, 'GPRB', 'Sal da Britânea (teste)'),
    )
    cur.execute(
        'INSERT INTO prefeitura (id, "tenantId", nome, status, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, %s, NOW(), NOW()) ON CONFLICT (id) DO NOTHING',
        (PID, TID, 'Potência Teste', 'ATIVA'),
    )
    for i, lid in enumerate(LOJAS, 1):
        cur.execute(
            'INSERT INTO loja (id, "tenantId", "lojaMX", "prefeituraId", "nomeFantasia", '
            '"createdAt", "updatedAt") VALUES (%s, %s, %s, %s, %s, NOW(), NOW())',
            (lid, TID, f'LT{i}', PID, f'Loja Teste {i}'),
        )
    cur.execute(
        'INSERT INTO member (id, "tenantId", "nomeCompleto", cpf, email, celular, '
        '"enderecoLogradouro", "enderecoCep", "enderecoCidade", "enderecoUf", '
        'situacao, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())',
        (MID, TID, 'Membro Teste', '000.000.000-00', 'membro@teste.com',
         '(21) 90000-0000', 'Rua Teste', '00000-000', 'Rio de Janeiro', 'RJ', 'ATIVO'),
    )
    yield {'tenant': TID, 'prefeitura': PID, 'lojas': LOJAS, 'member': MID}
    # limpeza (ordem segura)
    cur.execute('DELETE FROM member_loja WHERE "memberId" = %s', (MID,))
    cur.execute('DELETE FROM member WHERE id = %s', (MID,))
    for lid in LOJAS:
        cur.execute('DELETE FROM loja WHERE id = %s', (lid,))
    cur.execute('DELETE FROM prefeitura WHERE id = %s', (PID,))


def _login(email):
    c = Client()
    resp = c.post('/login/', {'email': email, 'senha': SENHA})
    assert resp.status_code == 302, f'login falhou para {email}'
    return c


def _post_edicao(loja_ids, **extras):
    """POST completo do form de edicao (mesmo shape do template real)."""
    dados = {
        'nome': 'Membro Editado',
        'email': 'editado@teste.com',
        'celular': '(41) 98000-0001',
        'cpf': '000.000.000-00',
        'telefone_urgencia': '(41) 98000-0002',
        'situacao': 'ATIVO',
        'rito': 'REAA',
        'cadastro_maconico': '12345',
        'tipo_admissao': 'Iniciacao',
        'escolaridade': 'Superior',
        'nacionalidade': 'Brasileiro',
        'naturalidade': 'Curitiba',
        'estado_civil': 'Casado',
        'pai': 'Joao', 'mae': 'Maria',
        'identidade': '1234567', 'orgao_emissor': 'SSP-PR',
        'endereco': 'Rua Nova', 'numero': '100', 'complemento': 'Ap 5',
        'bairro': 'Centro', 'cidade': 'Curitiba', 'uf': 'PR', 'cep': '80000-000',
        'potencia': 'CSMB', 'cargo': 'Veneravel',
        'condicao': 'Regular',
        'data_admissao': '1990-05-10',
        'data_nascimento': '',
        'apresentacao_mx': '', 'apresentacao_ec': '', 'armadura_cbcs': '',
        'data_emissao': '', 'data_passagem': '', 'data_elevacao': '',
        'data_instalacao': '', 'data_iniciacao': '',
        **{'lojas': loja_ids},
        **extras,
    }
    return dados


def test_membro_detalhe_renderiza_ficha(seed_membro, usuario_operacional):
    c = _login('oper@aurora.com')
    r = c.get(f'/contatos/membro/{MID}/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Membro Teste' in html
    assert 'membro@teste.com' in html


def test_membro_detalhe_404_para_id_desconhecido(seed_membro, usuario_operacional):
    c = _login('oper@aurora.com')
    r = c.get('/contatos/membro/id-inexistente-xyz/')
    assert r.status_code == 404


def test_membro_editar_get_mostra_form_preenchido(seed_membro, usuario_operacional):
    c = _login('oper@aurora.com')
    r = c.get(f'/contatos/membro/{MID}/editar/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Membro Teste' in html
    # select de lojas traz as duas lojas do seed
    assert 'Loja Teste 1' in html and 'Loja Teste 2' in html


def test_membro_editar_post_grava_campos_e_lojas(seed_membro, usuario_operacional):
    c = _login('oper@aurora.com')
    r = c.post(f'/contatos/membro/{MID}/editar/', _post_edicao(LOJAS))
    assert r.status_code == 302
    assert 'sucesso=1' in r.url

    m = repo.buscar_membro(MID)
    assert m['nome'] == 'Membro Editado'
    assert m['email'] == 'editado@teste.com'
    assert m['cidade'] == 'Curitiba'
    assert str(m['data_admissao'])[:10] == '1990-05-10'
    assert sorted(m['lojas_ids']) == sorted(LOJAS)


def test_membro_editar_post_sem_nome_mostra_erro(seed_membro, usuario_operacional):
    c = _login('oper@aurora.com')
    r = c.post(f'/contatos/membro/{MID}/editar/', _post_edicao(LOJAS, nome=''))
    assert r.status_code == 200
    assert 'Informe o nome' in r.content.decode()
    # nada mudou
    assert repo.buscar_membro(MID)['nome'] == 'Membro Teste'


def test_membro_editar_post_data_invalida_mostra_erro(seed_membro, usuario_operacional):
    c = _login('oper@aurora.com')
    r = c.post(
        f'/contatos/membro/{MID}/editar/',
        _post_edicao(LOJAS, data_admissao='31/02/2020'),
    )
    assert r.status_code == 200
    assert 'Data invalida' in r.content.decode()


def test_membro_editar_sem_loja_deixa_membro_sem_lojas(seed_membro, usuario_operacional):
    c = _login('oper@aurora.com')
    r = c.post(f'/contatos/membro/{MID}/editar/', _post_edicao([]))
    assert r.status_code == 302
    assert repo.buscar_membro(MID)['lojas_ids'] == []


def test_membro_excluir_remove_registro(seed_membro, usuario_operacional):
    c = _login('oper@aurora.com')
    html = c.get(f'/contatos/membro/{MID}/excluir/')
    assert html.status_code == 200
    assert 'Membro Teste' in html.content.decode()

    r = c.post(f'/contatos/membro/{MID}/excluir/', {'acao': 'excluir'})
    assert r.status_code == 302
    assert repo.buscar_membro(MID) is None


def test_membro_inativar_marca_situacao_inativa(seed_membro, usuario_operacional):
    c = _login('oper@aurora.com')
    r = c.post(f'/contatos/membro/{MID}/excluir/', {'acao': 'inativar'})
    assert r.status_code == 302
    assert repo.buscar_membro(MID)['situacao'] == 'INATIVO'
