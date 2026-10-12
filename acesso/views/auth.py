"""Views de autenticacao (login, logout, onboarding, tema)."""

import logging

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from acesso.decorators import web_login_required
from acesso.models import Usuario
from acesso.rate_limit import bloqueado as login_bloqueado
from acesso.rate_limit import limpar as login_limpar
from acesso.rate_limit import registrar_falha as login_registrar_falha
from acesso.session import iniciar_sessao
from acesso.turnstile import verify_turnstile_token
from .helpers import (
    _GPRB_ROLE_MAP,
    _HASH_DUMMY,
    client_ip,
    entrar_com_usuario_gprb,
    gprb_autenticar_seguro,
    is_saldorer,
)

logger = logging.getLogger(__name__)


def login_web(request):
    """POST /login/ — valida credenciais e abre sessao."""
    if request.session.get('usuario_id'):
        return redirect('dashboard:index')

    erro = None
    eh_saldorer = is_saldorer(request)

    if request.method == 'POST':
        if not settings.CLOUDFLARE_TURNSTILE_CONFIGURED:
            erro = 'Verificação humana indisponível. Tente novamente mais tarde.'
            return render(request, 'acesso/login.html', _login_context(erro, eh_saldorer))

        identifier = request.POST.get('identifier', '').strip()
        email = request.POST.get('email', '').strip().lower()
        senha = request.POST.get('senha', '')
        ip = client_ip(request)

        login_id = identifier or email

        if login_bloqueado(ip, login_id):
            erro = 'Muitas tentativas. Aguarde alguns minutos e tente novamente.'
        elif not login_id or not senha:
            erro = 'Informe seu celular e senha.'
        elif not verify_turnstile_token(request.POST.get('cf-turnstile-response', '')):
            erro = 'Confirme que você é humano para continuar.'
        else:
            gprb_user, eh_do_gprb = gprb_autenticar_seguro(login_id, senha)
            if gprb_user is not None:
                login_limpar(ip, login_id)
                entrar_com_usuario_gprb(
                    request, gprb_user, senha,
                    origem='saldorer' if eh_saldorer else 'gprb',
                )
                return redirect('dashboard:index')

            if eh_do_gprb:
                login_registrar_falha(ip, login_id)
                erro = 'Login ou senha inválidos.'
            else:
                usuario = Usuario.objects.filter(email__iexact=login_id).first()
                senha_ok = check_password(senha, usuario.senha) if usuario else check_password(senha, _HASH_DUMMY)
                if usuario is not None and senha_ok:
                    login_limpar(ip, login_id)
                    request.session.flush()
                    tenant = usuario.tenant
                    iniciar_sessao(
                        request, usuario,
                        nicho=tenant.nicho if tenant else '',
                        dispositivo=(request.META.get('HTTP_USER_AGENT', '') or '')[:140],
                    )
                    request.session['origem'] = 'crm'
                    return redirect('dashboard:index')
                if usuario is not None and usuario.pendente_ativacao:
                    erro = ('Sua conta ainda não foi ativada. Abra o link de ativação '
                            'enviado por e-mail (válido por 72 horas) e defina sua senha.')
                else:
                    login_registrar_falha(ip, login_id)
                    erro = 'Login ou senha inválidos.'

    return render(request, 'acesso/login.html', _login_context(erro, eh_saldorer))


def _login_context(erro, eh_saldorer):
    """Build a public-only widget context; never pass the secret to templates."""
    return {
        'erro': erro,
        'eh_saldorer': eh_saldorer,
        'turnstile_configured': settings.CLOUDFLARE_TURNSTILE_CONFIGURED,
        'turnstile_site_key': settings.CLOUDFLARE_TURNSTILE_SITE_KEY,
    }


@require_POST
def logout_web(request):
    """POST-only: evita logout CSRF via <img src="/logout/"> em site malicioso."""
    request.session.flush()
    messages.success(request, f'Você saiu da conta {settings.APP_BRAND_NAME}.')
    return redirect('acesso:login')


@web_login_required
def alternar_tema(request):
    """Troca o tema (claro/escuro) da sessão e volta para a página de origem."""
    if request.method == 'POST':
        tema = request.POST.get('tema', '')
        if tema in ('escuro', 'claro'):
            request.session['tema'] = tema
    voltar = request.POST.get('voltar') or request.META.get('HTTP_REFERER') or '/dashboard/'
    if url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()}, require_https=False):
        return redirect(voltar)
    return redirect('dashboard:index')
