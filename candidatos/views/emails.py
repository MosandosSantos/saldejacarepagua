"""Envio de e-mails de notificação de candidatos."""

import logging
import smtplib
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from candidatos.models import Candidato, CandidatoObservacao

logger = logging.getLogger(__name__)


def _gerar_link_candidato(request, candidato):
    """Gera link público para o candidato preencher a ficha."""
    if not candidato.access_token:
        candidato.generate_access_token()
        candidato.token_expires_at = timezone.now() + timedelta(days=7)
        candidato.save(update_fields=['access_token', 'token_expires_at', 'updated_at'])

    return request.build_absolute_uri(f'/candidato/{candidato.access_token}/')


def enviar_email_candidato(request, candidato, link):
    """Envia e-mail HTML com convite gentil para o candidato preencher a ficha."""
    assunto = '✦ Convite — Candidatura ao AMORIO'
    corpo_texto = f'''Prezado Senhor {candidato.nome_completo},

É com grande honra que comunicamos o recebimento de sua indicação para integrar
os quadros do AMORIO.

Acesse o link abaixo para preencher sua Ficha de Súplica:

{link}

Link válido por 7 dias · uso único.

Fraternalmente,
Supremo Conselho do Grau 33 do Rito Escocês Antigo e Aceito
da Maçonaria para a República Federativa do Brasil
'''
    corpo_html = render_to_string('candidatos/email_convite.html', {
        'nome': candidato.nome_completo.split()[0] if candidato.nome_completo else '',
        'link': link,
        'logo_url': request.build_absolute_uri('/static/img/logow.webp'),
        'app_brand_name': settings.APP_BRAND_NAME,
    })

    msg = EmailMultiAlternatives(
        assunto,
        corpo_texto,
        settings.DEFAULT_FROM_EMAIL,
        [candidato.email],
    )
    msg.attach_alternative(corpo_html, 'text/html')
    msg.send(fail_silently=False)


def enviar_email_convite_async(request_host, candidato_id, link, logo_url, nome, email_destino):
    """Envia o e-mail de convite em background — não bloqueia a resposta HTTP."""
    assunto = '✦ Convite — Candidatura ao AMORIO'
    corpo_texto = f'''Prezado Senhor {nome},

É com grande honra que comunicamos o recebimento de sua indicação para integrar
os quadros do AMORIO.

Acesse o link abaixo para preencher sua Ficha de Súplica:

{link}

Link válido por 7 dias · uso único.

Fraternalmente,
Supremo Conselho do Grau 33 do Rito Escocês Antigo e Aceito
da Maçonaria para a República Federativa do Brasil
'''
    corpo_html = render_to_string('candidatos/email_convite.html', {
        'nome': nome.split()[0] if nome else '',
        'link': link,
        'logo_url': logo_url,
        'app_brand_name': settings.APP_BRAND_NAME,
    })
    msg = EmailMultiAlternatives(
        assunto, corpo_texto, settings.DEFAULT_FROM_EMAIL, [email_destino],
    )
    msg.attach_alternative(corpo_html, 'text/html')
    try:
        msg.send(fail_silently=False)
    except (OSError, ValueError, smtplib.SMTPException):
        logger.exception('Falha ao enviar e-mail de convite (candidato %s)', candidato_id)
        return

    Candidato.objects.filter(
        pk=candidato_id, status=Candidato.Status.EM_ANALISE,
    ).update(status=Candidato.Status.FICHA_ENVIADA)


def enviar_email_aprovacao(request, candidato):
    """Envia e-mail de aprovação ao candidato."""
    link = _gerar_link_candidato(request, candidato)
    corpo = f'''
Prezado Senhor {candidato.nome_completo.split()[0] if candidato.nome_completo else 'Candidato'},

Parabéns! Sua candidatura foi aprovada pelo AMORIO.

Agora você pode acessar o portal do candidato para completar seu cadastro:

{link}

Fraternalmente,
Supremo Conselho do Grau 33 do Rito Escocês Antigo e Aceito
da Maçonaria para a República Federativa do Brasil
'''
    msg = EmailMultiAlternatives(
        '✓ Candidatura Aprovada — AMORIO',
        corpo,
        settings.DEFAULT_FROM_EMAIL,
        [candidato.email],
    )
    try:
        msg.send(fail_silently=False)
    except (OSError, ValueError, smtplib.SMTPException):
        logger.exception('Falha ao enviar e-mail de aprovação (candidato %s)', candidato.id)


def enviar_email_encaminhamento(request, candidato):
    """Envia e-mail de encaminhamento ao candidato."""
    link = _gerar_link_candidato(request, candidato)
    corpo = f'''
Prezado Senhor {candidato.nome_completo.split()[0] if candidato.nome_completo else 'Candidato'},

Sua candidatura foi encaminhada para a próxima etapa de revisão.

Para completar seu cadastro, acesse:
{link}

Fraternalmente,
Supremo Conselho do Grau 33 do Rito Escocês Antigo e Aceito
da Maçonaria para a República Federativa do Brasil
'''
    msg = EmailMultiAlternatives(
        '→ Candidatura Encaminhada — AMORIO',
        corpo,
        settings.DEFAULT_FROM_EMAIL,
        [candidato.email],
    )
    try:
        msg.send(fail_silently=False)
    except (OSError, ValueError, smtplib.SMTPException):
        logger.exception('Falha ao enviar e-mail de encaminhamento (candidato %s)', candidato.id)


def enviar_email_devolucao(request, candidato):
    """Envia e-mail de devolução ao candidato com observações."""
    observacoes = CandidatoObservacao.objects.filter(
        candidato=candidato,
    ).order_by('-created_at')[:1]
    ultima_obs = observacoes.first()

    corpo = f'''
Prezado Senhor {candidato.nome_completo.split()[0] if candidato.nome_completo else 'Candidato'},

Sua candidatura foi devolvida para revisão.

Observações recebidas:

{ultima_obs.texto if ultima_obs else 'Sem observações adicionais.'}

Por favor, ajuste os itens acima e reenvie sua candidatura quando estiver pronto.

Fraternalmente,
Supremo Conselho do Grau 33 do Rito Escocês Antigo e Aceito
da Maçonaria para a República Federativa do Brasil
'''
    msg = EmailMultiAlternatives(
        '✕ Candidatura Devolvida — AMORIO',
        corpo,
        settings.DEFAULT_FROM_EMAIL,
        [candidato.email],
    )
    try:
        msg.send(fail_silently=False)
    except (OSError, ValueError, smtplib.SMTPException):
        logger.exception('Falha ao enviar e-mail de devolução (candidato %s)', candidato.id)
