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
from django.db import Error as DBError

logger = logging.getLogger(__name__)


_ERRO_ATIVACAO = (
    'Sua conta ainda não foi ativada. Abra o link de ativação '
    'enviado por e-mail (válido por 72 horas) e defina sua senha.'
)


def _credencial_por_numero(numero, senha):
    """Resolve a conta pelo número de cadastro — do membro ou da própria conta.

    Devolve (usuario, pendente); (None, False) quando credencial inválida.
    Número sem conta é testado contra hash dummy para equalizar o tempo
    de resposta (sem enumeração de números de cadastro válidos).
    """
    from contatos.models import Membro

    numero = int(numero)
    usuario = None
    membro = (
        Membro.objects.select_related('tenant')
        .filter(cadastro_numero=numero)
        .first()
    )
    if membro is not None:
        usuario = Usuario.objects.filter(membro_id=membro.pk).first()
        if usuario is None and (membro.email or '').strip():
            # Fallback do piloto: espelho criado antes da migração de backfill.
            usuario = Usuario.objects.filter(
                tenant_id=membro.tenant_id,
                email__iexact=membro.email.strip(),
            ).first()
    if usuario is None:
        # Conta administrativa sem membro: cadastro_numero próprio da conta.
        usuario = Usuario.objects.filter(cadastro_numero=numero).first()
    if usuario is None:
        check_password(senha, _HASH_DUMMY)
        return None, False
    if not check_password(senha, usuario.senha):
        return None, False
    return usuario, usuario.pendente_ativacao


def login_web(request):
    """POST /login/ — valida credenciais e abre sessao.

    Identificação: número de cadastro do membro (fase piloto aceita também
    o e-mail da conta, exclusivamente para contas sem membro vinculado).
    """
    if request.session.get('usuario_id'):
        return redirect('dashboard:index')

    erro = None
    eh_saldorer = is_saldorer(request)

    if request.method == 'POST':
        if not settings.CLOUDFLARE_TURNSTILE_CONFIGURED:
            erro = 'Verificação humana indisponível. Tente novamente mais tarde.'
            return render(request, 'acesso/login.html', _login_context(erro, eh_saldorer))

        identifier = request.POST.get('identifier', '').strip()
        email = request.POST.get('email', '').strip().lower()  # compat: form antigo
        senha = request.POST.get('senha', '')
        ip = client_ip(request)

        login_id = identifier or email

        if login_bloqueado(ip, login_id):
            erro = 'Muitas tentativas. Aguarde alguns minutos e tente novamente.'
        elif not login_id or not senha:
            erro = 'Informe o número de cadastro e a senha.'
        elif not verify_turnstile_token(request.POST.get('cf-turnstile-response', '')):
            erro = 'Confirme que você é humano para continuar.'
        elif login_id.isdigit():
            # Número de cadastro do membro — papel-moeda do login neste piloto.
            usuario, pendente = _credencial_por_numero(login_id, senha)
            if usuario is not None:
                if pendente:
                    erro = _ERRO_ATIVACAO
                else:
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
            else:
                login_registrar_falha(ip, login_id)
                erro = 'Login ou senha inválidos.'
        elif '@' in login_id:
            # E-mail: valida primeiro no GPRB (contas administrativas), depois
            # no espelho local — reservado a contas sem membro vinculado.
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
                if usuario is not None and usuario.membro_id is not None:
                    # Conta vinculada a membro: a porta de entrada é o número
                    # do cadastro — e-mail não abre sessão (anti-enumeracao).
                    check_password(senha, _HASH_DUMMY)
                    usuario = None
                senha_ok = (
                    check_password(senha, usuario.senha)
                    if usuario else check_password(senha, _HASH_DUMMY)
                )
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
                    erro = _ERRO_ATIVACAO
                else:
                    login_registrar_falha(ip, login_id)
                    erro = 'Login ou senha inválidos.'
        else:
            login_registrar_falha(ip, login_id)
            erro = 'Login ou senha inválidos.'

    return render(request, 'acesso/login.html', _login_context(erro, eh_saldorer))


def _agenda_publica():
    """Grade mensal das sessões para a dobra 'Calendário' da home (pública).

    Devolve {'mes_nome', 'ano', 'semanas': [...]}, onde cada semana é uma
    lista de 7 dias (domingo a sábado) e cada dia leva {'dia', 'hoje',
    'outro_mes', 'eventos': [{titulo, tipo_display, hora}]}. Dados mínimos:
    título, tipo e hora — sem loja_id nem descrição pública. O mês exibido
    é o corrente (a navegação de meses fica na agenda interna).
    """
    from calendar import Calendar, monthrange
    from datetime import date
    from django.utils import timezone
    from tarefas.models import Evento

    hoje_dt = timezone.localdate()
    cal = Calendar(firstweekday=6)  # semana começa no domingo (Google Calendar)

    dias = list(cal.itermonthdates(hoje_dt.year, hoje_dt.month))
    inicio = date(hoje_dt.year, hoje_dt.month, 1)
    fim = date(hoje_dt.year, hoje_dt.month, monthrange(hoje_dt.year, hoje_dt.month)[1])

    eventos = (
        Evento.objects.filter(data_inicio__date__gte=inicio, data_inicio__date__lte=fim)
        .order_by('data_inicio')
    )
    por_dia = {}
    for ev in eventos:
        d = timezone.localdate(ev.data_inicio)
        por_dia.setdefault(d, []).append({
            'titulo': ev.titulo,
            'tipo_display': ev.get_tipo_display(),
            'hora': ev.data_inicio.astimezone(timezone.get_current_timezone()).strftime('%H:%M'),
        })

    MESES_PT = [
        '', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]

    semanas = []
    for i in range(0, len(dias), 7):
        semana = []
        for d in dias[i:i + 7]:
            semana.append({
                'dia': d.day,
                'hoje': d == hoje_dt,
                'outro_mes': d.month != hoje_dt.month,
                'eventos': por_dia.get(d, []),
            })
        semanas.append(semana)

    return {
        'mes_nome': MESES_PT[hoje_dt.month],
        'ano': hoje_dt.year,
        'semanas': semanas,
        'tem_eventos': bool(por_dia),
    }


def _contagem_vales():
    """Contagem pública de lojas e membros ativos dos Vales ativos.

    Devolve {'lojas': n, 'membros': n}; zeros quando não há dados.
    Só números agregados — nenhum nome ou identificador é exposto.
    """
    from contatos.models import Loja, Membro, Vale

    tenant_ids = list(
        Vale.objects.filter(status='ATIVA').values_list('tenant_id', flat=True)
    )
    return {
        'lojas': Loja.objects.filter(tenant_id__in=tenant_ids, situacao='ATIVA').count(),
        'membros': Membro.objects.filter(tenant_id__in=tenant_ids, situacao='ATIVO').count(),
    }


def _login_context(erro, eh_saldorer):
    """Build a public-only widget context; never pass the secret to templates."""
    try:
        agenda = _agenda_publica()
    except DBError:
        logger.warning('Agenda pública indisponível na home do login', exc_info=True)
        agenda = []
    try:
        contagem = _contagem_vales()
    except DBError:
        logger.warning('Contagem do Vale indisponível na home do login', exc_info=True)
        contagem = {'lojas': 0, 'membros': 0}
    return {
        'erro': erro,
        'agenda': agenda,
        'contagem': contagem,
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
