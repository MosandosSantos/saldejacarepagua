"""Fluxo de ativacao de conta criada sem senha (PRD-USUARIOS-SEM-SENHA).

Rotinas unicas para:
- criar a conta pendente (sem senha utilizavel, token de uso unico, 72h);
- (re)gerar o token de ativacao com limite de reenvios;
- montar e disparar o e-mail de ativacao via emails.servico.enviar_mensagem.

O envio em desenvolvimento (sem SMTP configurado) roda em MODO SIMULACAO:
a rotina devolve o link para a view exibir/logar — ninguem fica sem acesso
por falta de SMTP.
"""

import logging
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.utils import timezone

from acesso.models import (
    SENHA_PENDENTE,
    USUARIO_ATIVO,
    USUARIO_PENDENTE_SENHA,
    Usuario,
)
from emails.servico import enviar_mensagem

logger = logging.getLogger(__name__)

# Validade do link de ativacao: 72 horas (PRD §4.2).
PRAZO_ATIVACAO = timedelta(hours=72)

# Limite de reenvios do link por usuario pendente (PRD §5).
LIMITE_REENVIOS = 3

ASSUNTO_ATIVACAO = 'Ative seu acesso ao GPRBRCRM'


def criar_usuario_pendente(*, nome, email, celular='', papel, criado_por, tenant_id=None,
                           prefeitura_id=''):
    """Cria um usuario pendente (sem senha) com token de ativacao valido por 72h.

    Retorna o `Usuario` criado. A conta nao autentica enquanto `pendente_senha`.
    """
    usuario = Usuario.objects.create(
        nome=nome,
        email=email,
        celular=(celular or '').strip(),
        senha=SENHA_PENDENTE,  # hash inutilizavel — so o proprio usuario define a senha
        role=papel,
        status=USUARIO_PENDENTE_SENHA,
        criado_por=criado_por,
        tenant_id=tenant_id,
        prefeitura_id=(prefeitura_id or '').strip(),
    )
    _gerar_token(usuario)
    return usuario


def _gerar_token(usuario):
    """(Re)gera o token de ativacao de uso unico com validade de 72h."""
    usuario.token_ativacao = secrets.token_urlsafe(32)  # 256 bits
    usuario.ativacao_expira_em = timezone.now() + PRAZO_ATIVACAO
    usuario.save(update_fields=['token_ativacao', 'ativacao_expira_em'])
    return usuario.token_ativacao


def reenviar_ativacao(usuario):
    """Reenvia o link de um usuario pendente (novo token, +72h), respeitando o limite.

    Retorna o novo token ou None quando o limite de reenvios foi atingido
    (ou o usuario nao esta pendente — nao faz nada e devolve None).
    """
    if not usuario.pendente_ativacao:
        return None
    if usuario.reenvios_ativacao >= LIMITE_REENVIOS:
        return None
    token = _gerar_token(usuario)
    usuario.reenvios_ativacao += 1
    usuario.save(update_fields=['reenvios_ativacao'])
    return token


def montar_link_ativacao(request, usuario):
    """Link absoluto de ativacao do usuario (para o corpo do e-mail)."""
    from django.urls import reverse

    return request.build_absolute_uri(reverse('ativar_conta', args=[usuario.token_ativacao]))


def enviar_email_ativacao(request, usuario, token=None):
    """Dispara o e-mail de ativacao. Sem SMTP (dev), loga o link e roda em simulacao.

    Retorna a tupla (status, link): status em 'enviado' | 'simulado' | 'erro'.
    Em 'simulado', o link vai ao log para o administrador repassar em dev.
    """
    token = token or usuario.token_ativacao
    link = request.build_absolute_uri(reverse('ativar_conta', args=[token]))
    corpo = (
        f'Olá, {usuario.nome or usuario.email}!\n\n'
        'Sua conta de acesso ao GPRBRCRM foi criada. Para definir sua senha e '
        'começar a usar o sistema, abra o link abaixo (válido por 72 horas):\n\n'
        f'{link}\n\n'
        'Se você não pediu este acesso, ignore este e-mail.\n\n'
        'Atenciosamente,\nEquipe GPRBRCRM'
    )
    status = enviar_mensagem(ASSUNTO_ATIVACAO, corpo, usuario.email)
    if status == 'simulado':
        # Dev sem SMTP: registra o link para o admin conseguir repassar/testar.
        logger.warning('[modo simulação] link de ativação de %s: %s', usuario.email, link)
    return status, link


def ativar_senha(usuario, senha):
    """Grava a senha escolhida pelo proprio usuario e ativa a conta.

    Limpa o token (uso unico) e registra `ativado_em`. Retorna o usuario.
    """
    usuario.senha = make_password(senha)
    usuario.status = USUARIO_ATIVO
    usuario.token_ativacao = None
    usuario.ativacao_expira_em = None
    usuario.ativado_em = timezone.now()
    usuario.save(update_fields=['senha', 'status', 'token_ativacao', 'ativacao_expira_em', 'ativado_em'])
    return usuario
