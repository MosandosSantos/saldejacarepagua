"""Testes do PDF de valores por loja (upload, substituição, remoção e RBAC).

Cobre: envio do PDF no card "Observações — Tabela de Valores", exibição no
detalhe, substituição (1 arquivo por loja), rejeição de arquivo não-PDF e de
arquivo grande, bloqueio de viewer e remoção.
"""
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from contatos.models import LojaPdf
from core.gprb import connection as gconn
from repositories import gprb_repository as repo

SENHA = 'senha123'

pytestmark = pytest.mark.django_db(transaction=True)

_CRIADOS = {'lojas': [], 'prefeituras': []}

_PDF = b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n'


@pytest.fixture
def banco_loja_pdf(banco_gprb_teste):
    """Tenant + esquema mínimo da loja no banco de teste; limpa PDFs e lojas no fim."""
    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute('ALTER TABLE loja ADD COLUMN IF NOT EXISTS "mensalidade_regular" numeric(12,2)')
    cur.execute('SELECT id FROM tenant WHERE code = %s ORDER BY "createdAt" LIMIT 1', ('GPRB',))
    row = cur.fetchone()
    criei_tenant = row is None
    if criei_tenant:
        cur.execute(
            'INSERT INTO tenant (id, code, name, "createdAt", "updatedAt") '
            'VALUES (%s, %s, %s, NOW(), NOW())',
            ('test-tenant-loja-pdf', 'GPRB', 'Sal da Britânea (teste pdf)'),
        )
    _CRIADOS['lojas'].clear()
    _CRIADOS['prefeituras'].clear()
    yield {}
    for registro in LojaPdf.objects.all():
        if registro.arquivo:
            registro.arquivo.delete(save=False)
        registro.delete()
    for lid in _CRIADOS['lojas']:
        cur.execute('DELETE FROM loja WHERE id = %s', (lid,))
    for pid in _CRIADOS['prefeituras']:
        cur.execute('DELETE FROM prefeitura WHERE id = %s', (pid,))
    if criei_tenant:
        cur.execute('DELETE FROM tenant WHERE id = %s', ('test-tenant-loja-pdf',))


def _login(email):
    c = Client()
    resp = c.post('/login/', {'email': email, 'senha': SENHA})
    assert resp.status_code == 302, f'login falhou para {email}'
    return c


def _criar_loja(base):
    """Cria prefeitura + loja no banco GPRB de teste e devolve o id da loja."""
    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute('SELECT id FROM tenant WHERE code = %s ORDER BY "createdAt" LIMIT 1', ('GPRB',))
    tid = cur.fetchone()[0]
    pid = 'test-pf-pdf-' + uuid.uuid4().hex[:8]
    cur.execute(
        'INSERT INTO prefeitura (id, "tenantId", nome, sigla, prefeito, telefone, email, pix, '
        '"valorAnuidade", "dataVencimentoAnuidade", status, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())',
        (pid, tid, base, 'PDF', 'GM ' + base, '(41) 90000-0000', 'gm@teste.com',
         None, None, None, 'ATIVA'),
    )
    _CRIADOS['prefeituras'].append(pid)
    nome = f'{base} {uuid.uuid4().hex[:6]}'
    repo.criar_loja({
        'nome': nome, 'numero': '1', 'telefone': '', 'email': '',
        'prefeitura_id': pid, 'cidade': '', 'uf': '',
        'endereco': '', 'secretario_nome': '', 'secretario_telefone': '',
        'tesoureiro_nome': '', 'tesoureiro_telefone': '', 'mensalidade': None,
    })
    cur.execute(
        'SELECT id FROM loja WHERE "nomeFantasia" = %s ORDER BY "createdAt" DESC LIMIT 1',
        (nome,),
    )
    lid = cur.fetchone()[0]
    _CRIADOS['lojas'].append(lid)
    return lid


def _pdf(nome='valores.pdf', conteudo=_PDF):
    return SimpleUploadedFile(nome, conteudo, content_type='application/pdf')


def test_upload_pdf_guarda_e_exibe_no_detalhe(banco_loja_pdf, usuario_operacional):
    lid = _criar_loja('Loja Pdf Upload')
    c = _login('oper@aurora.com')

    r = c.post(f'/contatos/loja/{lid}/pdf/', {'pdf': _pdf()})
    assert r.status_code == 302
    assert 'ok=atualizado' in r.url

    registro = LojaPdf.objects.get(loja_id=lid)
    assert registro.arquivo.name.endswith('.pdf')

    html = c.get(f'/contatos/loja/{lid}/').content.decode()
    assert 'Observações — Tabela de Valores' in html
    assert registro.arquivo.url in html
    assert 'ok=erro' not in html


def test_upload_substitui_o_anterior(banco_loja_pdf, usuario_operacional):
    lid = _criar_loja('Loja Pdf Substitui')
    c = _login('oper@aurora.com')

    c.post(f'/contatos/loja/{lid}/pdf/', {'pdf': _pdf('tabela-2026.pdf')})
    primeiro = LojaPdf.objects.get(loja_id=lid)
    caminho_antigo = primeiro.arquivo.name

    r = c.post(f'/contatos/loja/{lid}/pdf/', {'pdf': _pdf('tabela-2027.pdf')})
    assert r.status_code == 302

    assert LojaPdf.objects.filter(loja_id=lid).count() == 1
    registro = LojaPdf.objects.get(loja_id=lid)
    assert registro.arquivo.name != caminho_antigo
    assert not registro.arquivo.storage.exists(caminho_antigo)


def test_upload_rejeita_arquivo_que_nao_e_pdf(banco_loja_pdf, usuario_operacional):
    lid = _criar_loja('Loja Pdf Invalido')
    c = _login('oper@aurora.com')

    arquivo = SimpleUploadedFile('valores.txt', b'nao sou pdf', content_type='text/plain')
    r = c.post(f'/contatos/loja/{lid}/pdf/', {'pdf': arquivo})
    assert r.status_code == 302
    assert 'erro=invalido' in r.url
    assert not LojaPdf.objects.filter(loja_id=lid).exists()

    r = c.post(f'/contatos/loja/{lid}/pdf/', {'pdf': _pdf('valores.pdf', b'conteudo invalido')})
    assert 'erro=invalido' in r.url
    assert not LojaPdf.objects.filter(loja_id=lid).exists()


def test_upload_rejeita_pdf_grande(banco_loja_pdf, usuario_operacional):
    lid = _criar_loja('Loja Pdf Grande')
    c = _login('oper@aurora.com')

    grande = SimpleUploadedFile('valores.pdf', b'x' * (10 * 1024 * 1024 + 1))
    r = c.post(f'/contatos/loja/{lid}/pdf/', {'pdf': grande})
    assert r.status_code == 302
    assert 'erro=tamanho' in r.url
    assert not LojaPdf.objects.filter(loja_id=lid).exists()


def test_sem_arquivo_retorna_erro(banco_loja_pdf, usuario_operacional):
    lid = _criar_loja('Loja Pdf Vazio')
    c = _login('oper@aurora.com')

    r = c.post(f'/contatos/loja/{lid}/pdf/', {})
    assert r.status_code == 302
    assert 'erro=arquivo' in r.url
    assert not LojaPdf.objects.filter(loja_id=lid).exists()


def test_viewer_nao_envia_nem_remove_pdf(banco_loja_pdf, usuario_operacional, usuario_viewer):
    lid = _criar_loja('Loja Pdf Viewer')
    oper = _login('oper@aurora.com')
    oper.post(f'/contatos/loja/{lid}/pdf/', {'pdf': _pdf()})
    assert LojaPdf.objects.filter(loja_id=lid).exists()

    viewer = _login('viewer@aurora.com')
    r = viewer.post(f'/contatos/loja/{lid}/pdf/', {'pdf': _pdf('outro.pdf')})
    assert r.status_code == 302
    assert r.url == '/dashboard/'

    r = viewer.post(f'/contatos/loja/{lid}/pdf/remover/')
    assert r.status_code == 302
    assert LojaPdf.objects.filter(loja_id=lid).exists()


def test_visualizacao_liberada_mas_form_oculto_para_viewer(
    banco_loja_pdf, usuario_operacional, usuario_viewer,
):
    lid = _criar_loja('Loja Pdf Leitura')
    oper = _login('oper@aurora.com')
    oper.post(f'/contatos/loja/{lid}/pdf/', {'pdf': _pdf()})
    registro = LojaPdf.objects.get(loja_id=lid)

    viewer = _login('viewer@aurora.com')
    html = viewer.get(f'/contatos/loja/{lid}/').content.decode()
    assert registro.arquivo.url in html
    assert 'name="pdf"' not in html
    assert 'Enviar PDF dos valores' not in html


def test_remover_pdf_apaga_registro_e_arquivo(banco_loja_pdf, usuario_operacional):
    lid = _criar_loja('Loja Pdf Remove')
    c = _login('oper@aurora.com')
    c.post(f'/contatos/loja/{lid}/pdf/', {'pdf': _pdf()})
    registro = LojaPdf.objects.get(loja_id=lid)
    caminho = registro.arquivo.name

    r = c.post(f'/contatos/loja/{lid}/pdf/remover/')
    assert r.status_code == 302
    assert 'ok=removido' in r.url
    assert not LojaPdf.objects.filter(loja_id=lid).exists()
    assert not registro.arquivo.storage.exists(caminho)

    html = c.get(f'/contatos/loja/{lid}/').content.decode()
    assert 'Nenhum PDF de valores enviado' not in html
    assert 'name="pdf"' in html


def test_detalhe_da_loja_sem_pdf_mostra_form(banco_loja_pdf, usuario_operacional):
    lid = _criar_loja('Loja Pdf Sem Arquivo')
    c = _login('oper@aurora.com')

    html = c.get(f'/contatos/loja/{lid}/').content.decode()
    assert 'Observações — Tabela de Valores' in html
    assert 'Enviar PDF dos valores' in html
