"""Testes do Modulo de Comunicacao (PRD_comunicacao) — envio e-mail/WhatsApp.

Cobre: placeholders, montagem de destinatarios por Prefeitura/Loja (GPRB mockado),
RBAC web (sessao), POST de campanha e os endpoints JSON de status do WhatsApp.
"""
import time

import pytest
from django.test import Client

import gestao.comunicacao as comunicacao_mod
from gestao.comunicacao import (
    _aplicar_placeholders,
    _normalizar_celular,
    montar_destinatarios,
)
from gestao.models import Campanha

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Req:
    """Request fake com apenas POST (o que montar_destinatarios usa)."""

    def __init__(self, post):
        self.POST = post


class _FakeCur:
    def __init__(self, fetchone_seq=(), fetchall_seq=()):
        self._one = list(fetchone_seq)
        self._all = list(fetchall_seq)
        self.executados = []

    def execute(self, sql, params=None):
        self.executados.append(sql)

    def fetchone(self):
        return self._one.pop(0) if self._one else None

    def fetchall(self):
        return self._all.pop(0) if self._all else []


class _FakeConn:
    def __init__(self, **kw):
        self._kw = kw
        self.ultima_cursor = None

    def cursor(self):
        self.ultima_cursor = _FakeCur(**self._kw)
        return self.ultima_cursor

    def close(self):
        pass

    def commit(self):
        pass


def _gprb_mock(monkeypatch, fetchone_seq=(), fetchall_seq=()):
    """Patcheia core.gprb.connect com uma conexao fake (filas de resultados)."""
    monkeypatch.setattr(
        'core.gprb.connect',
        lambda: _FakeConn(fetchone_seq=fetchone_seq, fetchall_seq=fetchall_seq),
    )


def _envio_sincrono(monkeypatch):
    """Executa o envio na propria thread (sqlite: evita lock de tabela na thread)."""
    monkeypatch.setattr(
        'gestao.views.disparar_async',
        lambda campanha_id: comunicacao_mod._rodar_envio(campanha_id),
    )


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = ''
    s.save()
    return c


def _aguardar_status(campanha_id, limite=3.0):
    """Espera a thread de envio concluir (dev: SMTP simulado, termina rapido)."""
    fim = time.time() + limite
    while time.time() < fim:
        c = Campanha.objects.get(pk=campanha_id)
        if c.status in ('enviada', 'falha'):
            return c
        time.sleep(0.05)
    return Campanha.objects.get(pk=campanha_id)


# --- Placeholders ---

@pytest.mark.django_db
def test_placeholders_substituem_dados_do_destinatario():
    dest = {'nome': 'Maria', 'email': 'maria@ex.com', 'zap': '5521999990000'}
    corpo = 'Olá {{NOME}}, seu e-mail é {{EMAIL}} e o celular {{CELULAR}}.'
    assert _aplicar_placeholders(corpo, dest) == \
        'Olá Maria, seu e-mail é maria@ex.com e o celular 5521999990000.'


@pytest.mark.django_db
def test_placeholders_aceitam_minusculas():
    dest = {'nome': 'João'}
    assert _aplicar_placeholders('{{nome}}', dest) == 'João'


@pytest.mark.django_db
def test_normalizar_celular_adiciona_ddi55():
    assert _normalizar_celular('(21) 99999-0000') == '5521999990000'
    assert _normalizar_celular('5521999990000') == '5521999990000'
    assert _normalizar_celular('') == ''


# --- Destinatarios: Prefeituras / Lojas (GPRB mockado) ---

@pytest.mark.django_db
def test_destinatarios_todas_prefeituras_email(monkeypatch):
    _gprb_mock(monkeypatch, fetchone_seq=[('tid',)], fetchall_seq=[[
        ('p1', 'Prefeitura Norte', 'João Prefeito', 'joao@pf.gov', '21999990000'),
        ('p2', 'Prefeitura Sul', '', 'sul@pf.gov', ''),
    ]])
    erros = []
    dest = montar_destinatarios('prefeituras', 'EMAIL', _Req({
        'filtro_prefeitura': '', 'filtro_loja': '',
    }), erros)
    assert dest == [
        {'nome': 'João Prefeito', 'email': 'joao@pf.gov'},
        {'nome': 'Prefeitura Sul', 'email': 'sul@pf.gov'},
    ]
    assert erros == []


@pytest.mark.django_db
def test_destinatarios_prefeitura_especifica_email(monkeypatch):
    _gprb_mock(monkeypatch, fetchone_seq=[('tid',)], fetchall_seq=[[
        ('p1', 'Prefeitura Norte', 'João Prefeito', 'joao@pf.gov', '21999990000'),
    ]])
    erros = []
    dest = montar_destinatarios('prefeituras', 'EMAIL', _Req({
        'filtro_prefeitura': 'p1', 'filtro_loja': '',
    }), erros)
    assert dest == [{'nome': 'João Prefeito', 'email': 'joao@pf.gov'}]


@pytest.mark.django_db
def test_destinatarios_loja_deputado_mestre_zap(monkeypatch):
    _gprb_mock(monkeypatch, fetchone_seq=[('tid',)], fetchall_seq=[[
        ('m1', 'José Deputado', 'jose@loja.com', '(11) 98888-7777'),
    ]])
    erros = []
    dest = montar_destinatarios('prefeituras', 'ZAP', _Req({
        'filtro_prefeitura': 'p1', 'filtro_loja': 'l1',
    }), erros)
    assert dest == [{'nome': 'José Deputado', 'zap': '5511988887777'}]


@pytest.mark.django_db
def test_destinatarios_ignora_prefeitura_sem_email(monkeypatch):
    _gprb_mock(monkeypatch, fetchone_seq=[('tid',)], fetchall_seq=[[
        ('p1', 'Prefeitura Norte', 'João Prefeito', '', '21999990000'),
    ]])
    erros = []
    dest = montar_destinatarios('prefeituras', 'EMAIL', _Req({
        'filtro_prefeitura': 'p1', 'filtro_loja': '',
    }), erros)
    assert dest == []
    assert any('sem e-mail' in e for e in erros)


@pytest.mark.django_db
def test_destinatarios_loja_sem_prefeitura_erro(monkeypatch):
    erros = []
    dest = montar_destinatarios('prefeituras', 'EMAIL', _Req({
        'filtro_prefeitura': '', 'filtro_loja': 'l1',
    }), erros)
    assert dest == []
    assert any('prefeitura' in e.lower() for e in erros)


@pytest.mark.django_db
def test_destinatarios_gprb_indisponivel_erro_amigavel(monkeypatch):
    def _boom():
        raise RuntimeError('conexao recusada')

    monkeypatch.setattr('core.gprb.connect', _boom)
    erros = []
    dest = montar_destinatarios('prefeituras', 'EMAIL', _Req({
        'filtro_prefeitura': '', 'filtro_loja': '',
    }), erros)
    assert dest == []
    assert any('GPRB' in e for e in erros)


@pytest.mark.django_db
def test_destinatarios_origem_invalida_erro():
    erros = []
    dest = montar_destinatarios('invalida', 'EMAIL', _Req({
        'filtro_prefeitura': '', 'filtro_loja': '',
    }), erros)
    assert dest == []
    assert any('destino' in e for e in erros)


# --- Destinatario individual ---

@pytest.mark.django_db
def test_destinatarios_individual_email():
    erros = []
    dest = montar_destinatarios('individual', 'EMAIL', _Req({
        'ind_nome': 'Maria', 'ind_contato': 'maria@ex.com',
    }), erros)
    assert dest == [{'nome': 'Maria', 'email': 'maria@ex.com'}]
    assert erros == []


@pytest.mark.django_db
def test_destinatarios_individual_zap_normaliza():
    erros = []
    dest = montar_destinatarios('individual', 'ZAP', _Req({
        'ind_nome': 'João', 'ind_contato': '(21) 99999-0000',
    }), erros)
    assert dest == [{'nome': 'João', 'zap': '5521999990000'}]
    assert erros == []


@pytest.mark.django_db
def test_destinatarios_individual_sem_contato_erro():
    erros = []
    dest = montar_destinatarios('individual', 'EMAIL', _Req({
        'ind_nome': '', 'ind_contato': '',
    }), erros)
    assert dest == []
    assert any('contato' in e for e in erros)


# --- Views: RBAC ---

@pytest.mark.django_db
def test_comunicacoes_requer_login():
    assert Client().get('/comunicacao/').status_code == 302


@pytest.mark.django_db
def test_comunicacoes_abre_para_logado_com_select_prefeitura(monkeypatch, admin_company):
    monkeypatch.setattr('core.gprb.connect', lambda: (_ for _ in ()).throw(RuntimeError('offline')))
    r = _cliente_web(admin_company).get('/comunicacao/')
    assert r.status_code == 200
    conteudo = r.content.decode()
    assert 'Comunicações' in conteudo
    assert 'Prefeitura' in conteudo
    assert 'GPRB indisponível' in conteudo


@pytest.mark.django_db
def test_viewer_nao_pode_enviar(usuario_viewer):
    r = _cliente_web(usuario_viewer).post('/comunicacao/', {
        'canal': 'EMAIL', 'origem': 'prefeituras', 'assunto': 'Oi',
        'corpo': 'Olá', 'filtro_prefeitura': '',
    })
    assert 'permissão' in r.content.decode()
    assert Campanha.objects.count() == 0


# --- POST: campanha por prefeituras (GPRB mockado, SMTP simulado) ---

@pytest.mark.django_db
def test_post_individual_email_cria_e_envia_campanha(monkeypatch, admin_company):
    _envio_sincrono(monkeypatch)
    _gprb_mock(monkeypatch, fetchone_seq=[('tid',)], fetchall_seq=[[('p1', 'Prefeitura Norte')]])
    r = _cliente_web(admin_company).post('/comunicacao/', {
        'canal': 'EMAIL', 'origem': 'individual', 'assunto': 'Bem-vindo',
        'corpo': 'Olá {{NOME}}!', 'ind_nome': 'Maria', 'ind_contato': 'maria@ex.com',
    })
    assert r.status_code == 200
    assert 'Campanha criada' in r.content.decode()

    campanha = Campanha.objects.get()
    assert campanha.origem == 'individual'
    assert campanha.filtros == {}
    assert campanha.destinatarios == [{'nome': 'Maria', 'email': 'maria@ex.com'}]

    concluida = _aguardar_status(campanha.id)
    assert concluida.status == 'enviada'          # simulado sem SMTP
    assert concluida.total_enviados == 1
    assert concluida.total_falhas == 0


@pytest.mark.django_db
def test_post_todas_prefeituras_email_cria_e_envia_campanha(monkeypatch, admin_company):
    _envio_sincrono(monkeypatch)
    # Sequencia de conexoes: montar_destinatarios (tid + prefeitos), listar_prefeituras (tid + opcoes)
    _gprb_mock(
        monkeypatch,
        fetchone_seq=[('tid',), ('tid',)],
        fetchall_seq=[
            [('p1', 'Prefeitura Norte', 'João Prefeito', 'joao@pf.gov', '21999990000')],
            [('p1', 'Prefeitura Norte')],
        ],
    )
    r = _cliente_web(admin_company).post('/comunicacao/', {
        'canal': 'EMAIL', 'origem': 'prefeituras', 'assunto': 'Bem-vindo',
        'corpo': 'Olá {{NOME}}!', 'filtro_prefeitura': '',
    })
    assert r.status_code == 200
    assert 'Campanha criada' in r.content.decode()

    campanha = Campanha.objects.get()
    assert campanha.canal == 'EMAIL'
    assert campanha.origem == 'prefeituras'
    assert campanha.filtros == {'prefeitura': '', 'loja': ''}
    assert campanha.destinatarios == [{'nome': 'João Prefeito', 'email': 'joao@pf.gov'}]
    assert campanha.criado_por_id == admin_company.id

    concluida = _aguardar_status(campanha.id)
    assert concluida.status == 'enviada'          # simulado sem SMTP
    assert concluida.total_enviados == 1
    assert concluida.total_falhas == 0


@pytest.mark.django_db
def test_post_loja_deputado_mestre_email_cria_campanha(monkeypatch, admin_company):
    _envio_sincrono(monkeypatch)
    # montar (deputado), listar_prefeituras, listar_lojas(prefeitura selecionada)
    _gprb_mock(
        monkeypatch,
        fetchone_seq=[('tid',), ('tid',), ('tid',)],
        fetchall_seq=[
            [('m1', 'José Deputado', 'jose@loja.com', '5511988887777')],
            [('p1', 'Prefeitura Norte')],
            [('l1', 'Loja Estrela do Norte')],
        ],
    )
    r = _cliente_web(admin_company).post('/comunicacao/', {
        'canal': 'EMAIL', 'origem': 'prefeituras', 'assunto': 'Reunião',
        'corpo': 'Olá {{NOME}}', 'filtro_prefeitura': 'p1', 'filtro_loja': 'l1',
    })
    assert r.status_code == 200
    assert 'Campanha criada' in r.content.decode()

    campanha = Campanha.objects.get()
    assert campanha.destinatarios == [{'nome': 'José Deputado', 'email': 'jose@loja.com'}]
    assert campanha.filtros == {'prefeitura': 'p1', 'loja': 'l1'}
    _aguardar_status(campanha.id)


@pytest.mark.django_db
def test_post_sem_destinatarios_validos_nao_cria_campanha(monkeypatch, admin_company):
    _gprb_mock(
        monkeypatch,
        fetchone_seq=[('tid',), ('tid',)],
        fetchall_seq=[
            [('p1', 'Prefeitura Norte', 'João Prefeito', '', '')],
            [('p1', 'Prefeitura Norte')],
        ],
    )
    r = _cliente_web(admin_company).post('/comunicacao/', {
        'canal': 'EMAIL', 'origem': 'prefeituras', 'assunto': 'Oi',
        'corpo': 'Olá', 'filtro_prefeitura': '',
    })
    assert 'Nenhum destinatário' in r.content.decode()
    assert Campanha.objects.count() == 0


# --- Endpoints JSON do WhatsApp ---

@pytest.mark.django_db
def test_zap_status_requer_login():
    assert Client().get('/comunicacao/zap-status/').status_code == 302


@pytest.mark.django_db
def test_zap_status_json_contrato(admin_company):
    r = _cliente_web(admin_company).get('/comunicacao/zap-status/')
    assert r.status_code == 200
    dados = r.json()
    assert {'configurado', 'conectado', 'detalhe', 'erro'} <= set(dados)
    assert isinstance(dados['configurado'], bool)
    assert isinstance(dados['conectado'], bool)


@pytest.mark.django_db
def test_zap_qrcode_json_contrato(admin_company):
    r = _cliente_web(admin_company).get('/comunicacao/zap-qrcode/')
    assert r.status_code == 200
    dados = r.json()
    assert {'logado', 'qr_base64', 'erro'} <= set(dados)
    assert isinstance(dados['logado'], bool)


# --- Modelo ---

@pytest.mark.django_db
def test_campanha_origens():
    c = Campanha(canal='EMAIL', corpo='x', origem='prefeituras')
    assert c.get_origem_display() == 'Coletivo (Prefeituras / Lojas)'
    c2 = Campanha(canal='EMAIL', corpo='x', origem='individual')
    assert c2.get_origem_display() == 'Individual (uma pessoa)'
