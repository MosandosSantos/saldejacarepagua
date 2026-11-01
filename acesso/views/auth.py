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

    numero = numero.lstrip('0')
    digits = numero.isdigit()
    numero_int = int(numero) if digits else None
    usuario = None
    membro = (
        Membro.objects.filter(cadastro_numero=numero_int).first()
        if numero_int is not None else None
    )
    if membro is not None:
        usuario = Usuario.objects.filter(membro_id=membro.pk).first()
        if usuario is None and (membro.email or '').strip():
            # Fallback do piloto: espelho criado antes da migração de backfill.
            usuario = Usuario.objects.filter(
                email__iexact=membro.email.strip(),
            ).first()
    if usuario is None:
        # Conta administrativa sem membro: cadastro_numero próprio da conta.
        usuario = (
            Usuario.objects.filter(cadastro_numero=numero_int).first()
            if numero_int is not None else None
        )
    if usuario is None and digits:
        # Conta pelo celular cadastrado (contas administrativas sem membro).
        # Aceita com e sem DDI/formato: tentamos o '21999417097' cru e as
        # formas salvas com máscara, pois o campo celular é texto livre.
        celular_variacoes = [numero, numero if numero.startswith('9') else '9' + numero]
        for variacao in celular_variacoes:
            usuario = Usuario.objects.filter(
                membro_id__isnull=True, celular=variacao
            ).first()
            if usuario is not None:
                break
        if usuario is None:
            usuario = (
                Usuario.objects.filter(
                    membro_id__isnull=True, celular__endswith=numero
                ).first()
            )
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
            return render(request, 'acesso/login.html', _login_context(erro, eh_saldorer, request))

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

    return render(request, 'acesso/login.html', _login_context(erro, eh_saldorer, request))


def _agenda_publica(ano=None, mes=None, loja_id=''):
    """Dados públicos e limitados da agenda por mês, sem dados identificáveis de loja."""
    from calendar import Calendar, monthrange
    from datetime import date
    from django.utils import timezone
    from tarefas.models import Evento
    from contatos.models import Loja

    hoje_dt = timezone.localdate()
    ano = int(ano or hoje_dt.year)
    mes = int(mes or hoje_dt.month)
    if not 1 <= mes <= 12 or not 1900 <= ano <= 2200:
        ano, mes = hoje_dt.year, hoje_dt.month
    inicio = date(ano, mes, 1)
    fim = date(ano, mes, monthrange(ano, mes)[1])
    identificadores_loja = [
        str(loja_id)
        for loja_id in Loja.objects.filter(situacao='ATIVA').order_by('id').values_list('pk', flat=True)
    ]
    identificadores_eventos = (
        Evento.objects.values_list('loja_id', flat=True).distinct().order_by('loja_id')
    )
    for evento_loja_id in identificadores_eventos:
        evento_loja_id = str(evento_loja_id)
        if evento_loja_id not in identificadores_loja:
            identificadores_loja.append(evento_loja_id)

    lojas_publicas = []
    loja_id_por_filtro = {}
    filtro_por_loja = {}
    for identificador in identificadores_loja:
        filtro = f'loja-{len(lojas_publicas) + 1}'
        lojas_publicas.append({'id': filtro, 'rotulo': f'Loja {len(lojas_publicas) + 1}'})
        loja_id_por_filtro[filtro] = identificador
        filtro_por_loja[identificador] = filtro

    eventos_qs = Evento.objects.filter(
        data_inicio__date__lte=fim,
        data_fim__date__gte=inicio,
    ).order_by('data_inicio')
    if loja_id and loja_id in loja_id_por_filtro:
        eventos_qs = eventos_qs.filter(loja_id=loja_id_por_filtro[loja_id])
    elif loja_id:
        eventos_qs = eventos_qs.none()

    eventos = []
    por_dia = {}
    tz = timezone.get_current_timezone()

    def _registro(ev):
        inicio_local = timezone.localtime(ev.data_inicio, tz)
        fim_local = timezone.localtime(ev.data_fim, tz)
        return {
            'titulo': ev.titulo,
            'tipo': ev.get_tipo_display(),
            'hora': inicio_local.strftime('%H:%M'),
            'inicio': inicio_local,
            'fim': fim_local,
            'loja_id': filtro_por_loja.get(str(ev.loja_id), ''),
        }

    for ev in eventos_qs:
        registro = _registro(ev)
        eventos.append(registro)
        d = timezone.localdate(ev.data_inicio)
        por_dia.setdefault(d, []).append(registro)

    # Kanban por mês: colunas do ano inteiro, agrupando os eventos por mês.
    eventos_ano_qs = Evento.objects.filter(
        data_inicio__date__lte=date(ano, 12, 31),
        data_fim__date__gte=date(ano, 1, 1),
    ).order_by('data_inicio')
    if loja_id and loja_id in loja_id_por_filtro:
        eventos_ano_qs = eventos_ano_qs.filter(loja_id=loja_id_por_filtro[loja_id])
    elif loja_id:
        eventos_ano_qs = eventos_ano_qs.none()
    por_mes = {}
    for ev in eventos_ano_qs:
        local = timezone.localtime(ev.data_inicio, tz)
        registro = _registro(ev)
        registro['data_curta'] = local.strftime('%d/%m')
        por_mes.setdefault(local.month, []).append(registro)

    MESES_PT = [
        '', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    DIAS_PT = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']
    cal = Calendar(firstweekday=6)
    semanas = []
    for i in range(0, len(list(cal.itermonthdates(ano, mes))), 7):
        datas = list(cal.itermonthdates(ano, mes))[i:i + 7]
        semanas.append([{
            'dia': d.day,
            'data': d,
            'hoje': d == hoje_dt,
            'outro_mes': d.month != mes,
            'eventos': por_dia.get(d, []),
        } for d in datas])

    meses_kanban = []
    for numero in range(1, 13):
        eventos_do_mes = por_mes.get(numero, [])
        meses_kanban.append({
            'numero': numero,
            'nome': MESES_PT[numero],
            'atual': numero == mes,
            'total': len(eventos_do_mes),
            'eventos': eventos_do_mes,
        })

    dias_kanban = []
    for numero in range(1, fim.day + 1):
        d = date(ano, mes, numero)
        dias_kanban.append({
            'data': d,
            'dia': numero,
            'nome_semana': DIAS_PT[d.weekday() + 1 if d.weekday() < 6 else 0],
            'total': len(por_dia.get(d, [])),
            'eventos': por_dia.get(d, []),
        })

    return {
        'mes_nome': MESES_PT[mes],
        'ano': ano,
        'mes': mes,
        'semanas': semanas,
        'meses_kanban': meses_kanban,
        'dias_semana': ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'],
        'dias_kanban': dias_kanban,
        'lojas': lojas_publicas,
        'eventos': eventos,
        'tem_eventos': bool(eventos),
    }


def exportar_agenda_publica(request):
    """Exporta eventos do mês/filtro selecionado em iCalendar, sem expor a loja."""
    from django.http import HttpResponse
    from django.utils import timezone
    from tarefas.ical import _fold_line, _ical_escape

    try:
        ano, mes = int(request.GET.get('ano', '')), int(request.GET.get('mes', ''))
    except (TypeError, ValueError):
        agenda = _agenda_publica()
    else:
        agenda = _agenda_publica(ano=ano, mes=mes, loja_id=request.GET.get('loja', ''))
    linhas = [
        'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Sal da Baixada//Agenda Publica//PT',
        f"X-WR-CALNAME:Agenda {agenda['mes_nome']} {agenda['ano']}", 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
    ]
    inicio_mes = f"{agenda['ano']}-{agenda['mes']:02d}-01"
    fim_mes = f"{agenda['ano']}-{agenda['mes']:02d}-01"
    for indice, ev in enumerate(agenda['eventos']):
        linhas.extend([
            'BEGIN:VEVENT',
            f"UID:agenda-publica-{agenda['ano']}-{agenda['mes']}-{indice}@saldabaixada",
            f"DTSTAMP:{timezone.now().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{ev['inicio'].strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{ev['fim'].strftime('%Y%m%dT%H%M%S')}",
            _fold_line(f"SUMMARY:{_ical_escape(ev['titulo'])}"),
            _fold_line(f"CATEGORIES:{_ical_escape(ev['tipo'])}"),
            'END:VEVENT',
        ])
    linhas.extend(['END:VCALENDAR', ''])
    response = HttpResponse('\r\n'.join(linhas), content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="agenda-{agenda["ano"]}-{agenda["mes"]:02d}.ics"'
    )
    return response


def _contagem_vales():
    """Contagem pública de lojas e membros ativos dos Vales ativos.

    Devolve {'lojas': n, 'membros': n}; zeros quando não há dados.
    Só números agregados — nenhum nome ou identificador é exposto.

    Como não há mais tenant, conta todos os registros ativos do sistema.
    """
    from django.db.models import Count

    from contatos.models import Loja, Membro, Vale

    # Como não há mais tenant, conta todos os vales ativos
    total_vales = Vale.objects.filter(status='ATIVA').count()

    # Conta todas as lojas ativas (sem filtro de tenant)
    total_lojas = Loja.objects.filter(situacao='ATIVA').count()

    # Conta membros ativos
    total_membros = Membro.objects.filter(situacao='ATIVO').count()

    # Distribui lojas por profile (corpo)
    # Como não há tenant, conta todas as lojas e agrupa por perfil
    perfil_counts = {}
    for loja in Loja.objects.filter(situacao='ATIVA'):
        perfil = loja.corpo
        if perfil not in perfil_counts:
            perfil_counts[perfil] = 0
        perfil_counts[perfil] += 1

    return {
        'total_vales': total_vales,
        'total_lojas': total_lojas,
        'total_membros': total_membros,
        'perfil_counts': perfil_counts,
    }


def _grafico_lojas_efetivos():
    """Efetivos por loja para o mini-gráfico da home de login."""
    from contatos.models import Loja, Membro, Vale, Filiacao

    # Como não há mais tenant, conta todas as lojas ativas ativas
    lojas = Loja.objects.filter(situacao='ATIVA').order_by('numero', 'nome')
    dados = []
    for loja in lojas:
        qtd = (
            Filiacao.objects.filter(loja=loja, membro__situacao='ATIVO')
            .values('membro_id')
            .distinct()
            .count()
        )
        if not qtd:
            qtd = Membro.objects.filter(lojas=loja, situacao='ATIVO').count()
        label = (loja.numero or '').strip()
        if not label:
            nome = (loja.nome or '').strip()
            # pegar abreviatura
            if nome:
                # tentar pegar siglas/palavras
                partes = nome.replace('.', ' ').split()
                if len(partes) >= 2:
                    label = (partes[0][:3] + partes[-1][:3]).upper()
                else:
                    label = nome[:4].upper()
            else:
                label = 'LOJA'
        dados.append({'label': label.upper(), 'count': int(qtd)})
    return dados


def _sessoes_no_ano():
    """Quantidade de sessões/eventos no ano corrente para exibição pública."""
    try:
        from tarefas.models import Evento
        from django.utils import timezone

        hoje = timezone.localdate()
        return Evento.objects.filter(data_inicio__year=hoje.year).count()
    except Exception:
        return 0


def _login_context(erro, eh_saldorer, request=None):
    """Build a public-only widget context; never pass the secret to templates."""
    try:
        params = request.GET if request is not None else {}
        agenda = _agenda_publica(
            ano=params.get('ano'), mes=params.get('mes'), loja_id=params.get('loja', ''),
        )
    except DBError:
        logger.warning('Agenda pública indisponível na home do login', exc_info=True)
        agenda = []
    try:
        contagem = _contagem_vales()
    except DBError:
        logger.warning('Contagem do Vale indisponível na home do login', exc_info=True)
        contagem = {'lojas': 0, 'membros': 0}
    try:
        grafico_lojas = _grafico_lojas_efetivos()
    except DBError:
        grafico_lojas = []
    try:
        sessoes_ano = _sessoes_no_ano()
    except Exception:
        sessoes_ano = 0
    return {
        'erro': erro,
        'agenda': agenda,
        'agenda_export_url': '/login/agenda/exportar/',
        'contagem': contagem,
        'grafico_lojas': grafico_lojas,
        'sessoes_ano': sessoes_ano,
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
