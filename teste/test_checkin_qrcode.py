"""Check-in do irmão via QRCode (auto-presença) + trava de data da chamada.

- Botão/tra goes: POST /presenca/ em sessão futura → 400 (GET segue 200).
- QRCode: token assinado por evento, página pública com dados da sessão,
  irmão autentica (celular + senha) e a presença é registrada sozinha.
- Guardrail: excluir o evento apaga as presenças (CASCADE).
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client
from django.utils import timezone

from acesso.models import Tenant, Usuario
from acesso.session import iniciar_sessao
from contatos.models import Loja, Membro, Vale
from tarefas.checkin import assinar_evento, conferir_token
from tarefas.models import Evento, PresencaEvento

pytestmark = pytest.mark.django_db(transaction=True)

SENHA = 'senha123'


def _mundo(fim_relativo_horas=-1, duracao_horas=2):
    """Tenant + loja + secretário + irmão (login e membro, mesmo e-mail)."""
    sufixo = uuid4().hex
    tenant = Tenant.objects.create(nome='Vale Checkin', slug=f'chk-{sufixo}')
    vale = Vale.objects.create(tenant=tenant, nome='Vale C', sigla='VC')
    loja = Loja.objects.create(tenant=tenant, nome='Loja Checkin')
    fim = timezone.now() + timedelta(hours=fim_relativo_horas)
    inicio = fim - timedelta(hours=duracao_horas)
    evento = Evento.objects.create(
        titulo='Sessão Checkin', tipo='sessao',
        data_inicio=inicio, data_fim=fim, loja_id=str(loja.pk),
    )
    secretario = Usuario.objects.create(
        nome='Secretário', email=f'sec-{sufixo}@example.test',
        senha=make_password(SENHA), role='secretario',
        tenant=tenant, loja_id=str(loja.pk),
    )
    email_irmao = f'irmao-{sufixo}@example.test'
    irmao_login = Usuario.objects.create(
        nome='Irmão Login', email=email_irmao,
        senha=make_password(SENHA), role='viewer', tenant=tenant,
    )
    membro = Membro.objects.create(
        tenant=tenant, nome='Irmão Checkin', email=email_irmao, situacao='ATIVO',
        cadastro_numero=777,
    )
    irmao_login.membro = membro
    irmao_login.save(update_fields=['membro'])
    membro.lojas.add(loja)
    return SimpleNamespace(
        tenant=tenant, vale=vale, loja=loja, evento=evento,
        secretario=secretario, irmao_login=irmao_login, membro=membro,
        email_irmao=email_irmao,
    )


def _cliente(usuario):
    client = Client(enforce_csrf_checks=False, raise_request_exception=False)
    sess = client.session
    iniciar_sessao(SimpleNamespace(session=sess), usuario)
    sess.save()
    client.cookies['sessionid'] = sess.session_key
    return client


def _url_checkin(evento):
    return f'/tarefas/checkin/{evento.pk}/?t={assinar_evento(evento.pk)}'


# ── Token ────────────────────────────────────────────────────────────

def test_token_vale_para_o_evento_e_recusa_outro_ou_adulterado():
    mundo = _mundo()
    token = assinar_evento(mundo.evento.pk)
    assert conferir_token(mundo.evento.pk, token) is True
    assert conferir_token(mundo.evento.pk + 999999, token) is False
    assert conferir_token(mundo.evento.pk, token + 'x') is False
    assert conferir_token(mundo.evento.pk, '') is False


# ── Página pública ───────────────────────────────────────────────────

def test_get_checkin_mostra_dados_da_sessao():
    mundo = _mundo()
    resposta = Client().get(_url_checkin(mundo.evento))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert 'Sessão Checkin' in html
    assert 'Loja Checkin' in html
    assert 'name="identifier"' in html
    assert 'name="senha"' in html


def test_get_checkin_sem_token_da_404():
    mundo = _mundo()
    assert Client().get(f'/tarefas/checkin/{mundo.evento.pk}/').status_code == 404
    assert Client().get(f'/tarefas/checkin/{mundo.evento.pk}/?t=lixo').status_code == 404


def test_get_fora_da_janela_avisa():
    mundo = _mundo(fim_relativo_horas=72)
    html = Client().get(_url_checkin(mundo.evento)).content.decode()
    assert 'fora da janela' in html


# ── POST: auto-presença ──────────────────────────────────────────────

def _post_checkin(evento, identifier, senha):
    return Client().post(
        f'/tarefas/checkin/{evento.pk}/',
        {'t': assinar_evento(evento.pk), 'identifier': identifier,
         'senha': senha, 'cf-turnstile-response': 'x'},
    )


def test_post_checkin_registra_presenca_do_irmao():
    mundo = _mundo()
    with patch('tarefas.views.verify_turnstile_token', return_value=True):
        resposta = _post_checkin(mundo.evento, mundo.email_irmao, SENHA)
    assert resposta.status_code == 200
    assert 'Presença registrada' in resposta.content.decode()
    assert PresencaEvento.objects.get(
        evento=mundo.evento, membro=mundo.membro,
    ).presente is True


def test_post_checkin_senha_errada_nao_registra():
    mundo = _mundo()
    with patch('tarefas.views.verify_turnstile_token', return_value=True):
        resposta = _post_checkin(mundo.evento, mundo.email_irmao, 'errada')
    assert 'Login ou senha inválidos' in resposta.content.decode()
    assert PresencaEvento.objects.filter(evento=mundo.evento).count() == 0


def test_post_checkin_em_cadastro_numero_registra_presenca():
    """Login do check-in pelo número de cadastro do membro (+ senha da conta)."""
    mundo = _mundo()
    with patch('tarefas.views.verify_turnstile_token', return_value=True):
        resposta = _post_checkin(mundo.evento, '777', SENHA)
    assert resposta.status_code == 200
    assert 'Presença registrada' in resposta.content.decode()
    assert PresencaEvento.objects.get(
        evento=mundo.evento, membro=mundo.membro,
    ).presente is True


def test_post_checkin_em_cadastro_numero_senha_errada_nao_registra():
    mundo = _mundo()
    with patch('tarefas.views.verify_turnstile_token', return_value=True):
        resposta = _post_checkin(mundo.evento, '777', 'errada')
    assert 'Login ou senha inválidos' in resposta.content.decode()
    assert PresencaEvento.objects.filter(evento=mundo.evento).count() == 0


def test_post_checkin_em_cadastro_numero_sem_conta_negado():
    """Membro com número de cadastro mas sem conta ligada não entra (sem senha)."""
    mundo = _mundo()
    solto = Membro.objects.create(
        tenant=mundo.tenant, nome='Irmão Sem Conta', email=f'solto-{uuid4().hex}@example.test',
        situacao='ATIVO', cadastro_numero=888,
    )
    solto.lojas.add(mundo.loja)
    with patch('tarefas.views.verify_turnstile_token', return_value=True):
        resposta = _post_checkin(mundo.evento, '888', SENHA)
    assert 'Login ou senha inválidos' in resposta.content.decode()
    assert PresencaEvento.objects.filter(evento=mundo.evento).count() == 0


def test_get_checkin_mostra_campo_numero_de_cadastro():
    mundo = _mundo()
    html = Client().get(_url_checkin(mundo.evento)).content.decode()
    assert 'Número do cadastro' in html
    assert 'Celular' not in html


def test_post_checkin_quem_nao_e_da_loja_negado():
    mundo = _mundo()
    outro = Usuario.objects.create(
        nome='Forasteiro', email=f'fora-{uuid4().hex}@example.test',
        senha=make_password(SENHA), role='viewer', tenant=mundo.tenant,
    )
    with patch('tarefas.views.verify_turnstile_token', return_value=True):
        resposta = _post_checkin(mundo.evento, outro.email, SENHA)
    assert 'não é de um irmão desta loja' in resposta.content.decode()
    assert PresencaEvento.objects.filter(evento=mundo.evento).count() == 0


def test_post_checkin_fora_da_janela_recusado():
    mundo = _mundo(fim_relativo_horas=72)
    with patch('tarefas.views.verify_turnstile_token', return_value=True):
        resposta = _post_checkin(mundo.evento, mundo.email_irmao, SENHA)
    assert 'fora da janela' in resposta.content.decode()
    assert PresencaEvento.objects.filter(evento=mundo.evento).count() == 0


# ── Geração do QRCode ────────────────────────────────────────────────

def test_qrcode_exige_permissao_e_devolve_url_assinada():
    mundo = _mundo()
    anonimo = Client().get(f'/tarefas/eventos/{mundo.evento.pk}/qrcode/')
    assert anonimo.status_code == 302  # login exigido

    sem_perm = _cliente(mundo.irmao_login).get(
        f'/tarefas/eventos/{mundo.evento.pk}/qrcode/')
    assert sem_perm.status_code == 403

    dados = _cliente(mundo.secretario).get(
        f'/tarefas/eventos/{mundo.evento.pk}/qrcode/').json()
    assert dados['ok'] is True
    assert dados['qr'].startswith('data:image/png;base64,')
    token = parse_qs(urlparse(dados['url']).query)['t'][0]
    assert conferir_token(mundo.evento.pk, token) is True
