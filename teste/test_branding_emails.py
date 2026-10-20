from email.utils import parseaddr
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.core import mail
from django.test import RequestFactory, override_settings

from acesso.ativacao import enviar_email_ativacao
from candidatos.views.emails import enviar_email_candidato
from core import settings as core_settings
from emails.servico import enviar_mensagem


def test_app_brand_name_is_amorio():
    assert getattr(settings, 'APP_BRAND_NAME', None) == 'SAL DA AMORIO'


@pytest.mark.parametrize(
    'configured_sender',
    ['sender@example.test', 'Old Name <sender@example.test>'],
)
def test_format_from_email_preserves_address_and_replaces_name(configured_sender):
    formatter = getattr(core_settings, 'format_from_email', lambda value: value)

    assert parseaddr(formatter(configured_sender)) == (
        'SAL DA AMORIO', 'sender@example.test',
    )


@override_settings(
    EMAIL_CONFIGURADO=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
def test_activation_email_uses_amorio_brand():
    mail.outbox.clear()
    usuario = SimpleNamespace(
        token_ativacao='token-de-teste', nome='Ana Teste', email='ana@example.test',
    )
    request = RequestFactory().get('/login/')

    status, _ = enviar_email_ativacao(request, usuario)

    assert status == 'enviado'
    mensagem = mail.outbox[-1]
    assert parseaddr(mensagem.from_email)[0] == 'SAL DA AMORIO'
    assert 'SAL DA AMORIO' in mensagem.subject
    assert 'SAL DA AMORIO' in mensagem.body


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def test_candidate_email_uses_amorio_signature_and_logo():
    mail.outbox.clear()
    candidato = SimpleNamespace(nome_completo='Ana Teste', email='ana@example.test')
    request = RequestFactory().get('/', HTTP_HOST='crm.example.test')

    enviar_email_candidato(request, candidato, 'https://crm.example.test/candidato/token/')

    mensagem = mail.outbox[-1]
    html = mensagem.alternatives[0][0]
    assert parseaddr(mensagem.from_email)[0] == 'SAL DA AMORIO'
    assert 'Prezado Senhor' in mensagem.body
    assert 'Fraternalmente' in mensagem.body
    assert 'SAL DA AMORIO' in html
    assert 'logow.webp' in html
    # Identidade institucional: Supremo Conselho do Grau 33 (REAA), não GPR.
    assert 'SUPREMO CONSELHO DO GRAU 33' in html
    assert 'Rito Escocês Antigo e Aceito' in html
    assert 'República Federativa do Brasil' in html
    assert 'Ordo ab Chao' in html
    assert 'Prezado Senhor' in html
    assert 'GRANDE PRIORADO' not in html


@override_settings(
    EMAIL_CONFIGURADO=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
def test_campaign_body_is_unchanged():
    mail.outbox.clear()
    subject = 'Assunto criado pelo usuário'
    body = 'Texto personalizado da campanha.'

    status = enviar_mensagem(subject, body, 'destinatario@example.test')

    assert status == 'enviado'
    mensagem = mail.outbox[-1]
    assert mensagem.subject == subject
    assert mensagem.body == body
    assert parseaddr(mensagem.from_email)[0] == 'SAL DA AMORIO'
