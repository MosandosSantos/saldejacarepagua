"""Views web do app tarefas — lista com lembretes, criar/editar, concluir/reabrir/excluir.

As tarefas são escopadas por tenant; o vencimento alimenta os lembretes
(atrasadas, de hoje, próximas). Viewer só visualiza; admin exclui.
"""

import json
import logging
import psycopg
import re
import smtplib
import threading
from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render as _render, get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from acesso.decorators import (
    e_admin_do_tenant,
    filtro_tenant,
    pode_editar,
    web_login_required,
    web_requer_edicao,
    web_requer_tenant_context,
)
from acesso.models import ROLE_ADM, ROLE_ADMIN_SAAS, ROLE_DELEGADO, ROLE_PRESIDENTE_CORPO, ROLE_SECRETARIO, tenant_gprb, Usuario
from acesso.rate_limit import bloqueado as login_bloqueado
from acesso.rate_limit import limpar as login_limpar
from acesso.rate_limit import registrar_falha as login_registrar_falha
from acesso.tenant_context import resolve_tenant_id
from acesso.turnstile import verify_turnstile_token
from acesso.views.helpers import client_ip, gprb_autenticar_seguro
from contatos.models import Contato, Loja, Membro, Vale
from core.utils import iniciais as _iniciais
from core.utils import tenant_id as _tenant_id
from tarefas.ical import gerar_ics, gerar_ics_eventos, parse_ics
from tarefas.google_sync import remover_google, tentar_sincronizar
from tarefas.presencas import PresencaServico
from tarefas.models import (
    concluir_tarefa,
    ConfirmacaoEvento as Conf,
    ConfirmacaoEvento,
    EmailEventoFila,
    Evento,
    PRIORIDADE_CORES,
    PRIORIDADES,
    reabrir_tarefa,
    Tarefa,
    TIPOS_EVENTO_SELETOR,
)
from django.template import TemplateSyntaxError

logger = logging.getLogger(__name__)


def _usuario_id(request):
    return request.session.get('usuario_id')


def _voltar(request, padrao='tarefas:lista'):
    """Redireciona de volta (POST `voltar` ou Referer) validando o host (anti-open-redirect)."""
    voltar = request.POST.get('voltar') or request.META.get('HTTP_REFERER') or ''
    if url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()}, require_https=False):
        return redirect(voltar)
    return redirect(padrao)


# _iniciais → importado de core.utils


def _decorar(t):
    return {
        'id': t.id,
        'titulo': t.titulo,
        'descricao': t.descricao,
        'prioridade': t.prioridade,
        'prioridade_cor': PRIORIDADE_CORES.get(t.prioridade, '#94a3b8'),
        'vencimento': t.vencimento,
        'hora': t.hora,
        'hora_label': t.hora.strftime('%H:%M') if t.hora else '',
        'atrasada': t.atrasada,
        'contato_id': t.contato_id,
        'contato_nome': t.contato.nome if t.contato else '',
        'responsavel_nome': t.responsavel.nome if t.responsavel else '',
        'responsavel_iniciais': _iniciais(t.responsavel.nome if t.responsavel else ''),
        'concluida': t.concluida,
        'concluida_em': t.concluida_em,
    }


def _opcoes(request):
    """Contatos e membros do tenant para os selects dos formulários."""
    contatos = [
        {'id': c.id, 'nome': c.nome}
        for c in filtro_tenant(request, Contato.objects.all()).order_by('nome')
    ]
    membros = [
        {'id': u.id, 'nome': u.nome}
        for u in Usuario.objects.filter(tenant_id=_tenant_id(request)).order_by('nome')
    ]
    return contatos, membros


def _parse_vencimento(raw, erros):
    """Converte a data ISO do formulário; None quando vazia; erro anexado se inválida."""
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        erros.append('Informe uma data de vencimento válida (aaaa-mm-dd, ex.: 2026-08-10).')
        return None


def _parse_hora(raw, erros):
    """Converte o horário HH:MM do formulário; None quando vazio; erro se inválido."""
    raw = (raw or '').strip()
    if not raw:
        return None
    if not re.fullmatch(r'\d{1,2}:\d{2}', raw):
        erros.append('Informe uma hora válida (HH:MM, ex.: 09:30).')
        return None
    try:
        return time.fromisoformat(raw)
    except ValueError:
        erros.append('Informe uma hora válida (HH:MM, ex.: 09:30).')
        return None


def _valida_prioridade(raw):
    return raw if raw in dict(PRIORIDADES) else 'media'


def _contato_do_tenant(tid, raw):
    """Id do contato se pertencer ao tenant da sessão (senão None) — impede
    referência cruzada entre clínicas via POST manipulado."""
    if raw.isdigit() and Contato.objects.filter(tenant_id=tid, pk=raw).exists():
        return int(raw)
    return None


def _membro_do_tenant(tid, raw):
    """Id do responsável se pertencer ao tenant da sessão (senão None)."""
    if raw.isdigit() and Usuario.objects.filter(tenant_id=tid, pk=raw).exists():
        return int(raw)
    return None


@web_login_required
@web_requer_tenant_context
def lista(request):
    """Página de tarefas: criar rápido no topo + seções atrasadas/hoje/próximas/concluídas."""
    tid = _tenant_id(request)
    hoje = date.today()
    qs = filtro_tenant(request, Tarefa.objects.select_related('contato', 'responsavel'))
    termo = request.GET.get('q', '').strip()
    if termo:
        qs = qs.filter(titulo__icontains=termo) | qs.filter(contato__nome__icontains=termo)

    erros = []
    if request.method == 'POST' and request.POST.get('acao') == 'criar':
        if not pode_editar(request):
            erros.append('Voce nao tem permissao para criar tarefas. Peça ao admin da empresa.')
        else:
            titulo = (request.POST.get('titulo', '') or '').strip()
            if not titulo:
                erros.append('Informe o titulo da tarefa.')
            else:
                vencimento = _parse_vencimento(request.POST.get('vencimento', ''), erros)
                hora = _parse_hora(request.POST.get('hora', ''), erros)
                if not erros:
                    Tarefa.objects.create(
                        tenant_id=tid,
                        titulo=titulo,
                        descricao=(request.POST.get('descricao', '') or '').strip(),
                        contato_id=_contato_do_tenant(tid, request.POST.get('contato_id', '')),
                        responsavel_id=_membro_do_tenant(tid, request.POST.get('responsavel_id', '')),
                        prioridade=_valida_prioridade(request.POST.get('prioridade', 'media')),
                        vencimento=vencimento,
                        hora=hora,
                        criado_por_id=_usuario_id(request),
                    )
                    return redirect('tarefas:lista')

    abertas = qs.filter(concluida=False)
    atrasadas = [_decorar(t) for t in abertas.filter(vencimento__lt=hoje).order_by('vencimento', 'hora')]
    hoje_lista = [_decorar(t) for t in abertas.filter(vencimento=hoje).order_by('vencimento', 'hora')]
    proximas = [_decorar(t) for t in abertas.filter(vencimento__gt=hoje).order_by('vencimento', 'hora')[:50]]
    sem_data = [_decorar(t) for t in abertas.filter(vencimento__isnull=True).order_by('-created_at')]
    concluidas = [
        _decorar(t) for t in qs.filter(concluida=True).order_by('-concluida_em', '-id')[:20]
    ]

    contatos, membros = _opcoes(request)
    msg_importacao = request.session.pop('msg_importacao', '')
    return render(request, 'tarefas/lista.html', {
        'atrasadas': atrasadas, 'hoje': hoje_lista, 'proximas': proximas,
        'sem_data': sem_data, 'concluidas': concluidas,
        'q': termo, 'erros': erros,
        'contatos': contatos, 'membros': membros,
        'total_abertas': abertas.count(),
        'msg_importacao': msg_importacao,
    })


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def editar(request, pk):
    tarefa = get_object_or_404(filtro_tenant(request, Tarefa.objects.all()), pk=pk)
    erros = []
    if request.method == 'POST':
        titulo = (request.POST.get('titulo', '') or '').strip()
        if not titulo:
            erros.append('Informe o título da tarefa.')
        else:
            vencimento = _parse_vencimento(request.POST.get('vencimento', ''), erros)
            hora = _parse_hora(request.POST.get('hora', ''), erros)
            if not erros:
                tarefa.titulo = titulo
                tarefa.descricao = (request.POST.get('descricao', '') or '').strip()
                tarefa.contato_id = _contato_do_tenant(tarefa.tenant_id, request.POST.get('contato_id', ''))
                tarefa.responsavel_id = _membro_do_tenant(tarefa.tenant_id, request.POST.get('responsavel_id', ''))
                tarefa.prioridade = _valida_prioridade(request.POST.get('prioridade', 'media'))
                tarefa.vencimento = vencimento
                tarefa.hora = hora
                tarefa.save()
                return redirect('tarefas:lista')
    contatos, membros = _opcoes(request)
    return render(request, 'tarefas/editar.html', {
        'tarefa': _decorar(tarefa),
        'contatos': contatos, 'membros': membros,
        'erros': erros,
    })


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def concluir(request, pk):
    """Marca como concluída (POST) e volta para a origem (ficha ou lista)."""
    if request.method == 'POST':
        tarefa = get_object_or_404(filtro_tenant(request, Tarefa.objects.all()), pk=pk)
        concluir_tarefa(tarefa)
    return _voltar(request)


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def reabrir(request, pk):
    if request.method == 'POST':
        tarefa = get_object_or_404(filtro_tenant(request, Tarefa.objects.all()), pk=pk)
        reabrir_tarefa(tarefa)
    return _voltar(request)


@web_login_required
@web_requer_tenant_context
def excluir(request, pk):
    """Excluir tarefa — apenas admin (operacional volta)."""
    if not e_admin_do_tenant(request):
        return redirect('tarefas:lista')
    if request.method == 'POST':
        tarefa = get_object_or_404(filtro_tenant(request, Tarefa.objects.all()), pk=pk)
        tarefa.delete()
    return _voltar(request)


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def nova_para_contato(request, contato_id):
    """Criação rápida de follow-up direto da ficha do contato."""
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=contato_id)
    if request.method == 'POST':
        titulo = (request.POST.get('titulo', '') or '').strip()
        if titulo:
            Tarefa.objects.create(
                tenant_id=_tenant_id(request),
                titulo=titulo,
                contato=contato,
                responsavel_id=_usuario_id(request),
                prioridade=_valida_prioridade(request.POST.get('prioridade', 'media')),
                vencimento=_parse_vencimento(request.POST.get('vencimento', ''), []),
                hora=_parse_hora(request.POST.get('hora', ''), []),
                criado_por_id=_usuario_id(request),
            )
    return redirect('contatos:detalhe', pk=contato.id)


@web_login_required
@require_GET
def exportar_calendario_ics(request):
    """Exporta os eventos da agenda como arquivo .ics (Google Calendar)."""
    qs = Evento.objects.all().order_by('data_inicio')
    ics_bytes = gerar_ics_eventos(qs)
    response = HttpResponse(ics_bytes, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="agenda-sessoes.ics"'
    return response


@web_login_required
def exportar_ics(request):
    """Exporta todas as tarefas abertas do tenant como arquivo .ics (Google Calendar)."""
    tid = _tenant_id(request)
    qs = Tarefa.objects.filter(tenant_id=tid).select_related('contato', 'responsavel')
    ics_bytes = gerar_ics(qs)
    response = HttpResponse(ics_bytes, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="GPRBRCRM-tarefas.ics"'
    return response


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def importar_ics(request):
    """Importa tarefas de um arquivo .ics (compatível com Google Calendar)."""
    if request.method != 'POST':
        return redirect('tarefas:lista')

    arquivo = request.FILES.get('arquivo_ics')
    if not arquivo:
        return redirect('tarefas:lista')

    try:
        conteudo = arquivo.read()
        eventos = parse_ics(conteudo)
    except (OSError, ValueError, TypeError):
        logger.warning('Falha ao ler arquivo .ics de %s', _usuario_id(request), exc_info=True)
        return redirect('tarefas:lista')

    tid = _tenant_id(request)
    uid = _usuario_id(request)
    criadas = 0

    for ev in eventos:
        titulo = (ev.get('titulo') or '').strip()
        if not titulo:
            continue
        Tarefa.objects.create(
            tenant_id=tid,
            titulo=titulo,
            descricao=ev.get('descricao', ''),
            vencimento=ev.get('vencimento'),
            hora=ev.get('hora'),
            prioridade=ev.get('prioridade', 'media'),
            concluida=ev.get('concluida', False),
            criado_por_id=uid,
        )
        criadas += 1

    # Salvar msg na session para exibir na lista
    request.session['msg_importacao'] = f'{criadas} tarefa(s) importada(s) com sucesso!'
    return redirect('tarefas:lista')


def _linhas_ranking(members, member_stats):
    """Linhas elegíveis do ranking (regras do PRD §8), sem ordenação ainda.

    Usado tanto na tabela (com os filtros aplicados) quanto nos KPIs
    estáticos (chamado com todos os membros, sem filtro de classe/loja).
    """
    from core.gprb import _months_between, _years_between

    hoje = date.today()
    linhas = []
    for i, m in enumerate(members):
        # Regra: sem anuidade paga → não entra no ranking
        if not m.get('anuidade_ok', False):
            continue

        recepcao = m['recepcao']
        tempo_meses = _months_between(recepcao, hoje) if recepcao else 0

        # Regra: tempo mínimo não atingido → não entra no ranking
        threshold = 18 if m.get('classe_abbr') == 'MX' else 24
        if tempo_meses < threshold:
            continue

        stats = member_stats.get(m['id'], {})
        total_present = stats.get('totalPresent', 0)
        total_absent = stats.get('totalAbsent', 0)
        total_recorded = stats.get('totalRecorded', 0)
        percentage = stats.get('percentage', 0)

        # Regra: menos de 4 presenças → não entra no ranking
        if total_present < 4:
            continue

        idade = _years_between(m['data_nascimento'], hoje) if m['data_nascimento'] else 0

        linhas.append({
            'id': m['id'], 'nome': m['nome'],
            'classe': m['classe_abbr'], 'classe_nome': m['classe_nome'],
            'recepcao': recepcao,
            'tempo_meses': tempo_meses,
            'idade': idade,
            'total_present': total_present,
            'total_absent': total_absent,
            'total_recorded': total_recorded,
            'percentage': percentage,
            'loja_nome': m.get('loja_nome', ''),
            'prefeitura_sigla': m.get('prefeitura_sigla', ''),
            'original_index': i,
        })
    return linhas


@web_login_required
def ranking(request):
    """Agenda de sessões da loja maçonica — calendário estilo Google Calendar."""
    usuario = request.session.get('usuario', {})
    loja_id_usuario = usuario.get('loja_id', '')

    # Parâmetros de data (mês/ano atual ou via GET)
    hoje = date.today()
    ano = int(request.GET.get('ano', hoje.year))
    mes = int(request.GET.get('mes', hoje.month))
    if mes < 1: mes = 1
    if mes > 12: mes = 12

    # Primeiro e último dia do mês
    data_inicio_mes = date(ano, mes, 1)
    if mes == 12:
        data_fim_mes = date(ano + 1, 1, 1) - timedelta(days=1)
    else:
        data_fim_mes = date(ano, mes + 1, 1) - timedelta(days=1)

    # Buscar eventos do mês (todas as lojas visíveis)
    eventos = Evento.objects.filter(
        data_inicio__date__lte=data_fim_mes,
        data_fim__date__gte=data_inicio_mes,
    )

    # RSVP: contadores por evento — confirmações (VOU), ausências (NAO_VOU)
    # e total de e-mails enviados — para exibição na agenda.
    ids_mes = [ev.id for ev in eventos]
    n_vou = {}
    n_nao_vou = {}
    n_enviados = {}
    if ids_mes:
        for linha in ConfirmacaoEvento.objects.filter(
            evento_id__in=ids_mes, resposta__in=('VOU', 'NAO_VOU'),
        ).values('evento_id', 'resposta').annotate(total=Count('id')):
            if linha['resposta'] == 'VOU':
                n_vou[linha['evento_id']] = linha['total']
            else:
                n_nao_vou[linha['evento_id']] = linha['total']
        for linha in EmailEventoFila.objects.filter(
            evento_id__in=ids_mes, situacao='ENVIADO',
        ).values('evento_id').annotate(total=Count('id')):
            n_enviados[linha['evento_id']] = linha['total']

    # Serializar eventos para JSON (admin_saas/ADM podem editar/deletar todos)
    eventos_json = []
    for ev in eventos:
        pode_editar = bool(loja_id_usuario and ev.loja_id == loja_id_usuario) or _eh_usuario_global(request)
        eventos_json.append({
            'id': ev.id,
            'titulo': ev.titulo,
            'descricao': ev.descricao,
            'tipo': ev.tipo,
            'tipo_display': ev.get_tipo_display(),
            'data_inicio': ev.data_inicio.strftime('%Y-%m-%dT%H:%M'),
            'data_fim': ev.data_fim.strftime('%Y-%m-%dT%H:%M'),
            'loja_id': ev.loja_id,
            'pode_editar': pode_editar,
            'sessao_passada': ev.sessao_encerrada,
            'conf_vou': n_vou.get(ev.id, 0),
            'conf_nao_vou': n_nao_vou.get(ev.id, 0),
            'emails_enviados': n_enviados.get(ev.id, 0),
        })

    # Navegação (mês anterior/próximo)
    if mes == 1:
        mes_anterior = 12
        ano_anterior = ano - 1
    else:
        mes_anterior = mes - 1
        ano_anterior = ano

    if mes == 12:
        proximo_mes = 1
        proximo_ano = ano + 1
    else:
        proximo_mes = mes + 1
        proximo_ano = ano

    # Nomes dos meses em português
    MESES_PT = [
        '', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]

    # Vale(s) e Loja(s) disponíveis no modal, conforme o cargo
    vales, lojas, vale_fixado, loja_do_usuario_pk = _escopo_evento(request)

    return render(request, 'tarefas/ranking.html', {
        'eventos': eventos_json,
        'ano': ano,
        'mes': mes,
        'mes_nome': MESES_PT[mes],
        'data_inicio_mes': data_inicio_mes,
        'data_fim_mes': data_fim_mes,
        'ano_anterior': ano_anterior,
        'mes_anterior': mes_anterior,
        'proximo_ano': proximo_ano,
        'proximo_mes': proximo_mes,
        'loja_id_usuario': loja_id_usuario,
        'tipos_evento_select': TIPOS_EVENTO_SELETOR,
        'hoje': hoje,
        'pode_criar_evento': bool(lojas)
        or loja_do_usuario_pk is not None
        or bool(loja_id_usuario and _cargo_da_sessao(request) in (
            ROLE_ADMIN_SAAS, ROLE_ADM, ROLE_DELEGADO,
            ROLE_PRESIDENTE_CORPO, ROLE_SECRETARIO,
        )),
        'vales_evento': [
            {'id': str(v.pk), 'nome': v.nome, 'sigla': v.sigla, 'tenant_id': v.tenant_id}
            for v in vales
        ],
        'lojas_evento': [
            {'id': str(l.pk), 'nome': l.nome, 'tenant_id': l.tenant_id, 'corpo': l.corpo}
            for l in lojas
        ],
        'vale_fixado': vale_fixado, 'loja_do_usuario_pk': loja_do_usuario_pk,
    })


# ---------------------------------------------------------------------------
# API JSON para eventos (CRUD)
# ---------------------------------------------------------------------------


def _obter_loja_usuario(request):
    """Retorna o loja_id do usuário logado (None se não tiver)."""
    return request.session.get('usuario', {}).get('loja_id') or None


def _cargo_da_sessao(request):
    """Role ativa: usuário do banco primeiro, senão o snapshot da sessão."""
    usuario = getattr(request, 'usuario_logado', None)
    role = getattr(usuario, 'role', None)
    if role:
        return role
    snapshot = request.session.get('usuario', {})
    return snapshot.get('role') if isinstance(snapshot, dict) else None


def _eh_usuario_global(request):
    """admin_saas e ADM operam em todos os Vales/Lojas."""
    return _cargo_da_sessao(request) in (ROLE_ADMIN_SAAS, ROLE_ADM)


def _vale_do_delegado(request):
    """Vale do cargo delegado — vem do `prefeitura_id` do usuário."""
    if _cargo_da_sessao(request) != ROLE_DELEGADO:
        return None
    usuario = getattr(request, 'usuario_logado', None)
    snapshot = request.session.get('usuario', {})
    pid = getattr(usuario, 'prefeitura_id', None) or (
        snapshot.get('prefeitura_id') if isinstance(snapshot, dict) else None
    )
    pid = str(pid or '').strip()
    if not pid.isdigit():
        return None
    return Vale.objects.filter(pk=int(pid), status='ATIVA').first()


def _escopo_evento(request):
    """Conjunto de Vales/Lojas que o usuário pode articular nos eventos.

    - admin_saas/ADM: todos os Vales ATIVA e suas Lojas.
    - delegado: só o Vale dele (prefeitura_id), com as Lojas desse Vale.
    - presidente de loja/secretário: Vale do tenant e exclusivamente a Loja dele.
    - demais cargos: vazio (botão some e o POST é recusado).

    Devolve (vales, lojas, vale_fixado, loja_do_usuario_pk).
    """
    role = _cargo_da_sessao(request)
    if role in (ROLE_ADMIN_SAAS, ROLE_ADM):
        vales = list(Vale.objects.filter(status='ATIVA').order_by('nome', 'id'))
        lojas = list(Loja.objects.order_by('nome', 'id'))
        return vales, lojas, False, None
    if role == ROLE_DELEGADO:
        vale = _vale_do_delegado(request)
        if vale is None:
            return [], [], False, None
        lojas = list(Loja.objects.filter(tenant_id=vale.tenant_id).order_by('nome', 'id'))
        return [vale], lojas, True, None
    if role in (ROLE_PRESIDENTE_CORPO, ROLE_SECRETARIO):
        usuario = getattr(request, 'usuario_logado', None)
        tenant_id = getattr(usuario, 'tenant_id', None) if usuario is not None else None
        if tenant_id is None:
            tenant_id = (request.session.get('usuario') or {}).get('tenant_id')
        loja_do_usuario = None
        loja_id_sessao = _obter_loja_usuario(request)
        if loja_id_sessao and str(loja_id_sessao).isdigit():
            loja_do_usuario = Loja.objects.filter(
                pk=int(str(loja_id_sessao)), tenant_id=tenant_id,
            ).first()
        if tenant_id is None or loja_do_usuario is None:
            return [], [], False, None
        vale = Vale.objects.filter(tenant_id=tenant_id, status='ATIVA').first()
        if vale is None:
            return [], [], False, None
        return [vale], [loja_do_usuario], True, loja_do_usuario.pk
    return [], [], False, None


# Regra por corpo: a Loja só pode ter eventos de iniciação no grau dentro
# da faixa do corpo dela (Posse e Outros valem para qualquer corpo;
# "Especial" ainda não existe como tipo).
FAIXA_GRAU_POR_CORPO = {
    'perfeicao': (4, 14),
    'capitulo': (15, 18),
    'kadosh': (19, 30),
    'consistorio': (31, 32),
    'sc33': (33, 33),
}


def _tipo_valido_para_loja(tipo, loja):
    """Iniciação exige grau dentro da faixa do corpo da Loja.

    Posse, Outros e tipos legados ficam livres. Sem corpo conhecido (loja
    desconhecida/legada) o comportamento antigo é mantido.
    """
    tipo = str(tipo or '')
    if not tipo.startswith('iniciacao_grau_'):
        return True
    if loja is None or getattr(loja, 'corpo', '') not in FAIXA_GRAU_POR_CORPO:
        return True
    grau_txt = tipo[len('iniciacao_grau_'):]
    if not grau_txt.isdigit():
        return False
    minimo, maximo = FAIXA_GRAU_POR_CORPO[loja.corpo]
    return minimo <= int(grau_txt) <= maximo


def _erro_tipo_fora_da_faixa(loja):
    """Mensagem do corpo correspondente, indica a faixa permitida."""
    if loja is not None and getattr(loja, 'corpo', '') in FAIXA_GRAU_POR_CORPO:
        minimo, maximo = FAIXA_GRAU_POR_CORPO[loja.corpo]
        return (
            f'{loja.get_corpo_display()} só pode ter eventos do grau '
            f'{minimo}° ao {maximo}°'
        )
    return 'O tipo informado não é aplicável a esta Loja.'


def _loja_do_payload(request, valor):
    """Valida a loja enviada no payload contra o escopo do cargo.

    Devolve (loja | None, sem_escolha). "Sem escolha" preserva o fluxo antigo
    (fallback para a loja da sessão). Escolha fora do escopo → erro.
    """
    valor = str(valor or '').strip()
    if not valor.isdigit():
        return None, True
    _, lojas, _, _ = _escopo_evento(request)
    loja = next((lo for lo in lojas if str(lo.pk) == valor), None)
    if loja is None:
        return None, False
    return loja, False


def _pode_gerir_evento(request, evento):
    """Pode editar/excluir o evento: cargo da sessão vs. loja do evento.

    - admin_saas/ADM: qualquer evento.
    - delegado: eventos cuja loja pertence ao Vale dele (prefeitura_id).
    - presidente de loja/secretário: apenas o da loja dele (sessão).
    - demais cargos: negado.
    """
    valor_loja = str(evento.loja_id)
    if _eh_usuario_global(request):
        return True
    role = _cargo_da_sessao(request)
    loja_sessao = _obter_loja_usuario(request)
    if loja_sessao is not None and valor_loja == str(loja_sessao):
        return role in (ROLE_PRESIDENTE_CORPO, ROLE_SECRETARIO)
    if role == ROLE_DELEGADO:
        vale = _vale_do_delegado(request)
        if vale is not None and valor_loja.isdigit():
            loja = Loja.objects.filter(pk=int(valor_loja), tenant_id=vale.tenant_id).first()
            if loja is not None:
                return True
    return False


@web_login_required
@require_GET
def eventos_json(request):
    """Retorna eventos do mês como JSON para o calendário."""
    hoje = date.today()
    ano = int(request.GET.get('ano', hoje.year))
    mes = int(request.GET.get('mes', hoje.month))

    data_inicio_mes = date(ano, mes, 1)
    if mes == 12:
        data_fim_mes = date(ano + 1, 1, 1) - timedelta(days=1)
    else:
        data_fim_mes = date(ano, mes + 1, 1) - timedelta(days=1)

    eventos = Evento.objects.filter(
        data_inicio__date__lte=data_fim_mes,
        data_fim__date__gte=data_inicio_mes,
    )

    # Escopo por cargo calculado uma única vez (mesma regra do modal/criar).
    _, lojas_escopo, _, _ = _escopo_evento(request)
    lojas_permitidas = {str(l.pk) for l in lojas_escopo}
    loja_legado = _obter_loja_usuario(request)
    if loja_legado is not None:
        # Loja legada da sessão (p.ex. UUID do BANK GPRB) também é gerível.
        lojas_permitidas.add(str(loja_legado))

    eventos_list = []
    for ev in eventos:
        pode_editar = str(ev.loja_id) in lojas_permitidas
        eventos_list.append({
            'id': ev.id,
            'titulo': ev.titulo,
            'descricao': ev.descricao,
            'tipo': ev.tipo,
            'tipo_display': ev.get_tipo_display(),
            'data_inicio': ev.data_inicio.strftime('%Y-%m-%dT%H:%M'),
            'data_fim': ev.data_fim.strftime('%Y-%m-%dT%H:%M'),
            'loja_id': ev.loja_id,
            'pode_editar': pode_editar,
            'sessao_passada': ev.sessao_encerrada,
        })

    return JsonResponse({'eventos': eventos_list})


@require_http_methods(['GET', 'POST'])
def evento_confirmar(request, token):
    """Página pública de confirmação (RSVP) via token do e-mail. Sem login:
    o token única por (evento, destinatário) é a identificação; o POST
    registra a resposta (GET do preview do e-mail não grava nada)."""

    conf = Conf.objects.select_related('evento').filter(token=token).first()
    if conf is None:
        return _render(request, 'tarefas/confirmar.html', {'invalido': True})

    erro = None
    resposta = request.POST.get('resposta', '').strip()
    if request.method == 'POST':
        if conf.resposta:
            # Confirmação única: cada e-mail tem uma única resposta válida.
            erro = 'Sua resposta já foi registrada — a confirmação é única por e-mail.'
        elif resposta in ('VOU', 'NAO_VOU'):
            conf.resposta = resposta
            from django.utils import timezone as dj_tz
            conf.respondido_em = dj_tz.now()
            conf.save(update_fields=['resposta', 'respondido_em'])
        else:
            erro = 'Resposta inesperada — escolha Vou comparecer ou Não poderei.'

    contexto = {
        'conf': conf,
        'erro': erro,
        'salvo': request.method == 'POST' and erro is None,
        'tipo_display': conf.evento.get_tipo_display(),
        'inicio_display': f'{conf.evento.data_inicio:%d/%m/%Y às %H:%M}',
        'url_google': _url_google_calendar(conf.evento),
        'url_logo': f"{getattr(settings, 'BASE_URL', '').rstrip('/')}/static/img/logo.png",
    }
    loja = (
        Loja.objects.filter(pk=int(conf.evento.loja_id)).first()
        if str(conf.evento.loja_id).isdigit()
        else None
    )
    contexto['loja_nome'] = loja.nome if loja else 'Sua Loja'
    return _render(request, 'tarefas/confirmar.html', contexto)


@web_login_required
@require_POST
def evento_criar(request):
    """Cria um novo evento, escopado ao cargo (Vale/Loja permitidas)."""
    return _evento_criar_interno(request)


def _evento_criar_interno(request):
    try:
        dados = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON inválido'}, status=400)

    loja, sem_escolha = _loja_do_payload(request, dados.get('loja'))
    if not sem_escolha and loja is None:
        return JsonResponse({'erro': 'Loja fora do seu escopo para criação.'}, status=403)

    # Contexto de escrita S8: cargos de tenant já o têm na sessão; o admin_saas
    # (tenant None) só escreve com contexto, e a escolha explícita do Vale e da
    # Loja no modal é esse contexto — nunca o fallback mudo.
    contexto_tenant = resolve_tenant_id(request)
    if contexto_tenant is None:
        if not _eh_usuario_global(request):
            return JsonResponse({'erro': 'Selecione um tenant para alterar dados.'}, status=403)
        if loja is None:
            return JsonResponse(
                {'erro': 'Selecione o Vale e a Loja do evento para gravar.'},
                status=400,
            )
    if loja is not None:
        loja_id = str(loja.pk)
    else:
        _, _, _, loja_do_usuario_pk = _escopo_evento(request)
        loja_legado = _obter_loja_usuario(request)
        if loja_do_usuario_pk is not None:
            # Presidente de loja/secretário sem payload: a loja dele.
            loja_id = str(loja_do_usuario_pk)
        elif loja_legado and _cargo_da_sessao(request) in (
            ROLE_ADMIN_SAAS, ROLE_ADM, ROLE_DELEGADO,
            ROLE_PRESIDENTE_CORPO, ROLE_SECRETARIO,
        ):
            # Fallback legado: loja_id da sessão (p.ex. UUID do BANK GPRB).
            loja_id = str(loja_legado)
        elif not loja_legado:
            return JsonResponse({'erro': 'Selecione o Vale e a Loja do evento.'}, status=400)
        else:
            # Cargos fora da regra de criação (tesoureiro, viewer, etc.).
            return JsonResponse({'erro': 'Sem permissão para criar eventos.'}, status=403)

    titulo = dados.get('titulo', '').strip()
    if not titulo:
        return JsonResponse({'erro': 'Título é obrigatório'}, status=400)

    try:
        data_inicio = datetime.fromisoformat(dados['data_inicio'])
    except (KeyError, ValueError):
        return JsonResponse({'erro': 'Datas inválidas'}, status=400)

    if dados.get('data_fim'):
        try:
            data_fim = datetime.fromisoformat(dados['data_fim'])
        except ValueError:
            return JsonResponse({'erro': 'Datas inválidas'}, status=400)
    else:
        # O formulário não pede mais o horário de fim; usamos o mesmo padrão
        # de 2 horas que o form preenchia automaticamente (ex.: 19h → 21h).
        data_fim = data_inicio + timedelta(hours=2)

    if data_fim <= data_inicio:
        return JsonResponse({'erro': 'Data fim deve ser posterior à data início'}, status=400)

    # Todo evento deve estar associado a um grau — e o grau deve estar
    # dentro da faixa do corpo da Loja (ex.: Perfeição = graus 4 a 14).
    tipo = (dados.get('tipo') or '').strip()
    loja_referencia = loja
    if loja_referencia is None and str(loja_id).isdigit():
        loja_referencia = Loja.objects.filter(pk=int(loja_id)).first()
    if not tipo.startswith('iniciacao_grau_'):
        return JsonResponse(
            {'erro': 'Todo evento deve estar associado a um grau da Loja.'},
            status=400,
        )
    if not _tipo_valido_para_loja(tipo, loja_referencia):
        return JsonResponse(
            {'erro': _erro_tipo_fora_da_faixa(loja_referencia)},
            status=400,
        )

    evento = Evento.objects.create(
        titulo=titulo,
        descricao=dados.get('descricao', ''),
        tipo=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        loja_id=loja_id,
        criado_por_id=_usuario_id(request),
    )

    # Enviar email para membros da loja
    _enfileirar_email_novo_evento(evento)

    # Auto-sync Google Calendar (best-effort; falha não impede a gravação)
    tentar_sincronizar(evento)

    return JsonResponse({
        'ok': True,
        'evento': {
            'id': evento.id,
            'titulo': evento.titulo,
            'tipo': evento.tipo,
            'tipo_display': evento.get_tipo_display(),
            'data_inicio': evento.data_inicio.strftime('%Y-%m-%dT%H:%M'),
            'data_fim': evento.data_fim.strftime('%Y-%m-%dT%H:%M'),
        },
    })


@web_login_required
@require_POST
def evento_editar(request, evento_id):
    """Edita um evento conforme o escopo do cargo (Vale/Loja permitidas)."""
    try:
        evento = Evento.objects.get(pk=evento_id)
    except Evento.DoesNotExist:
        return JsonResponse({'erro': 'Evento não encontrado'}, status=404)

    if not _pode_gerir_evento(request, evento):
        return JsonResponse({'erro': 'Sem permissão para editar este evento'}, status=403)

    try:
        dados = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON inválido'}, status=400)

    if 'titulo' in dados:
        evento.titulo = dados['titulo']
    if 'descricao' in dados:
        evento.descricao = dados['descricao']
    if 'tipo' in dados:
        novo_tipo = str(dados.get('tipo') or '').strip()
        loja_do_evento = (
            Loja.objects.filter(pk=int(evento.loja_id)).first()
            if str(evento.loja_id).isdigit()
            else None
        )
        if novo_tipo != evento.tipo:
            # Mudando o tipo: exige um grau dentro da faixa do corpo.
            if not novo_tipo.startswith('iniciacao_grau_'):
                return JsonResponse(
                    {'erro': 'Todo evento deve estar associado a um grau da Loja.'},
                    status=400,
                )
            if not _tipo_valido_para_loja(novo_tipo, loja_do_evento):
                return JsonResponse(
                    {'erro': _erro_tipo_fora_da_faixa(loja_do_evento)},
                    status=400,
                )
            evento.tipo = novo_tipo
        # Tipo igual ao atual: mantém (eventos legados continuam editáveis).
    if 'data_inicio' in dados:
        novo_inicio = datetime.fromisoformat(dados['data_inicio'])
        if 'data_fim' in dados:
            evento.data_fim = datetime.fromisoformat(dados['data_fim'])
        else:
            # Sem campo de fim no form: preserva a duração original do evento
            # ao mover o início (o fim nunca pode ficar antes do início).
            duracao = evento.data_fim - evento.data_inicio
            evento.data_fim = max(novo_inicio + duracao, novo_inicio + timedelta(minutes=30))
        evento.data_inicio = novo_inicio
    if 'data_fim' in dados:
        evento.data_fim = datetime.fromisoformat(dados['data_fim'])

    evento.save()

    # Auto-sync Google Calendar (best-effort)
    tentar_sincronizar(evento)

    return JsonResponse({'ok': True})


@web_login_required
@require_POST
def evento_excluir(request, evento_id):
    """Exclui um evento (da loja do usuário, ou qualquer uma para admin)."""
    loja_id = _obter_loja_usuario(request)

    try:
        evento = Evento.objects.get(pk=evento_id)
    except Evento.DoesNotExist:
        return JsonResponse({'erro': 'Evento não encontrado'}, status=404)

    if not _pode_gerir_evento(request, evento):
        return JsonResponse({'erro': 'Sem permissão para excluir este evento'}, status=403)

    remover_google(evento)  # best-effort: apaga no Google antes do local
    evento.delete()
    return JsonResponse({'ok': True})


@web_login_required
def evento_presenca(request, evento_id):
    """Lista de chamada do evento (GET: estado atual; POST: grava presenças).

    Mesma permissão de gestão do evento: presidente/secretário da loja,
    delegado do Vale e admin — demais cargos recusados (403).
    """
    try:
        evento = Evento.objects.get(pk=evento_id)
    except Evento.DoesNotExist:
        return JsonResponse({'erro': 'Evento não encontrado'}, status=404)

    if not _pode_gerir_evento(request, evento):
        return JsonResponse({'erro': 'Sem permissão para a chamada deste evento'}, status=403)

    tenant_id = _tenant_para_chamada(request, evento)

    if request.method == 'POST':
        if not evento.sessao_encerrada:
            return JsonResponse(
                {'erro': 'A chamada só abre após o término da sessão.'}, status=400,
            )
        try:
            dados = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'erro': 'JSON inválido'}, status=400)
        presencas = dados.get('presencas')
        if not isinstance(presencas, list):
            return JsonResponse({'erro': "Envie {'presencas': [{'membro': id, 'presente': bool}]}"}, status=400)
        for item in presencas:
            if not isinstance(item, dict) or 'membro' not in item or 'presente' not in item:
                return JsonResponse({'erro': 'Item de presença mal formado'}, status=400)
        usuario = getattr(request, 'usuario_logado', None)
        PresencaServico.registrar_chamada(
            evento, presencas, usuario=usuario, tenant_id=tenant_id,
        )
        return PresencaServico.resposta_do_evento(evento, ok=True, tenant_id=tenant_id)

    return PresencaServico.resposta_do_evento(evento, tenant_id=tenant_id)


def _tenant_para_chamada(request, evento):
    """Tenant para espelhar irmãos do GPRB na lista de chamada.

    Loja local → tenant da loja; loja GPRB (UUID) → tenant da sessão com
    fallback para o tenant canônico GPRB (admin_saas não tem tenant).
    """
    valor = str(evento.loja_id or '').strip()
    if valor.isdigit():
        loja = Loja.objects.filter(pk=int(valor)).first()
        if loja is not None:
            return loja.tenant_id
    tid = (request.session.get('usuario') or {}).get('tenant_id')
    if tid:
        return tid

    canonico = tenant_gprb()
    return canonico.pk if canonico is not None else None


# ---------------------------------------------------------------------------
# QRCode + auto-presença do irmão (check-in público)
# ---------------------------------------------------------------------------


@web_login_required
def evento_relatorio_presenca(request, evento_id):
    """Folha de presença imprimível (A4) do evento — "primeiro teste".

    Folha 1 (MEMBROS): cabeçalho (loja, vale, tipo, observações, data),
    QRCode de check-in, tabela numerada N# / Nome / Nome histórico /
    Telefone / Grau (em branco) / Rubrica. Folha 2 (OFICIAIS E VISITANTES):
    mesmo cabeçalho e mesma tabela. Ambas terminam com assinaturas de
    Orador, Presidente e Delegado.
    """
    evento = get_object_or_404(Evento, pk=evento_id)
    if not _pode_gerir_evento(request, evento):
        return HttpResponseForbidden('Sem permissão para o relatório deste evento.')

    loja = None
    valor = str(evento.loja_id or '').strip()
    if valor.isdigit():
        loja = Loja.objects.filter(pk=int(valor)).first()
    vale = loja.tenant.vales if loja is not None else None

    # Membros ATIVOS da loja local, ordenados por nome.
    linhas = []
    membros = []
    if valor.isdigit():
        membros = list(
            Membro.objects.filter(lojas__pk=int(valor), situacao='ATIVO')
            .order_by('nome', 'pk')
        )
    for i, m in enumerate(membros, start=1):
        celular = (m.celular or '').strip()
        grau_atual = (
            m.graus.select_related('grau').order_by('-grau__numero').first()
            if getattr(m, 'pk', None) else None
        )
        linhas.append({
            'n': i,
            'nome': (m.nome or '').upper(),
            'nome_historico': getattr(m, 'nome_historico', '') or '',
            'telefone': celular,
            'grau': grau_atual.grau.numero if grau_atual else '',
        })

    contexto = {
        'evento': evento,
        'loja_nome': loja.nome if loja else '—',
        'vale_nome': vale.nome if vale else '—',
        'tipo_display': evento.get_tipo_display(),
        'data_display': f'{evento.data_inicio:%d/%m/%Y — %H:%M}',
        'linhas': linhas,
        'linhas_vazias': range(20),  # matriz em branco (Oficiais e Visitantes)
    }
    from tarefas.checkin import qr_data_uri, url_checkin

    try:
        url = url_checkin(request, evento)
        contexto['url_checkin'] = url
        contexto['qr_data'] = qr_data_uri(url)  # PNG embutido — imprime sem internet
    except (ImportError, ValueError, TypeError, OSError):
        logger.warning('QRCode indisponível no relatório do evento %s', evento.pk, exc_info=True)

    return render(request, 'tarefas/relatorio_presenca.html', contexto)


@web_login_required
def evento_qrcode(request, evento_id):
    """Gera o QRCode + link do check-in do evento (JSON, para o modal).

    Mesma permissão da chamada: quem gera é quem pode fazer a chamada.
    """
    try:
        evento = Evento.objects.get(pk=evento_id)
    except Evento.DoesNotExist:
        return JsonResponse({'erro': 'Evento não encontrado'}, status=404)
    if not _pode_gerir_evento(request, evento):
        return JsonResponse({'erro': 'Sem permissão para gerar o QRCode'}, status=403)
    from tarefas.checkin import qr_data_uri, url_checkin

    url = url_checkin(request, evento)
    return JsonResponse({'ok': True, 'url': url, 'qr': qr_data_uri(url)})


def _credencial_checkin(login_id, senha):
    """Autentica o irmão pela mesma credencial do login (número de cadastro).

    Devolve (membro, email, nome) ou None quando inválido. `membro` vem
    preenchido no caminho por número de cadastro; no caminho por e-mail
    (contas administrativas/GPRB) é None e a resolução usa o e-mail.
    """
    login_id = (login_id or '').strip()
    if not login_id or not senha:
        return None
    if login_id.isdigit():
        membro = Membro.objects.select_related('tenant').filter(
            cadastro_numero=int(login_id),
        ).first()
        usuario = (
            Usuario.objects.filter(membro_id=membro.pk).first()
            if membro is not None else None
        )
        if usuario is None or not check_password(senha, usuario.senha):
            return None
        return (membro, usuario.email, usuario.nome)
    # Compatibidade: e-mail ainda aceito para contas administrativas.
    gprb_user, eh_do_gprb = gprb_autenticar_seguro(login_id, senha)
    if gprb_user is not None:
        return (
            None,
            gprb_user['email'],
            gprb_user.get('name') or '',
        )
    if eh_do_gprb:
        return None
    usuario = Usuario.objects.filter(email__iexact=login_id).first()
    if usuario is not None and check_password(senha, usuario.senha):
        return (usuario.membro, usuario.email, usuario.nome)
    return None


def _membro_do_checkin(evento, tenant_id, membro, email):
    """Membro autenticado sendo irmão DAQUELA loja (None = não é da loja).

    Local: vínculo Membro↔Loja. Sem membro local (GPRB): espelho pelo
    e-mail do irmão autenticado.
    """
    valor = str(evento.loja_id or '').strip()
    if membro is not None:
        if valor.isdigit():
            return Membro.objects.filter(
                lojas__pk=int(valor), situacao='ATIVO', pk=membro.pk,
            ).first()
        return None
    email_key = (email or '').strip().lower()
    if not email_key:
        return None
    if valor.isdigit():
        return Membro.objects.filter(
            lojas__pk=int(valor), situacao='ATIVO', email__iexact=email,
        ).first()
    from core.gprb.members import irmaos_da_loja

    for irmao in irmaos_da_loja(valor):
        if (irmao.get('email') or '').strip().lower() == email:
            return PresencaServico.espelhar_irmao(tenant_id, irmao)
    return None


def checkin(request, evento_id):
    """Página pública de auto-presença via QRCode (GET: dados + form).

    POST autentica o irmão (número do cadastro + senha) e registra presente=True.
    Não abre sessão de CRM — só confirma a presença.
    """
    from tarefas.checkin import checkin_aberto, conferir_token, nome_da_loja

    try:
        evento = Evento.objects.get(pk=evento_id)
    except Evento.DoesNotExist:
        return render(request, 'tarefas/checkin.html', {
            'valido': False, 'erro': 'Sessão não encontrada.',
        }, status=404)

    token = request.GET.get('t', '') or request.POST.get('t', '')
    if not conferir_token(evento.pk, token):
        return render(request, 'tarefas/checkin.html', {
            'valido': False, 'erro': 'Link de check-in inválido ou de outra sessão.',
        }, status=404)

    aberto = checkin_aberto(evento)
    contexto = {
        'valido': True,
        'evento': evento,
        'loja_nome': nome_da_loja(evento),
        'aberto': aberto,
        'token': token,
        'sucesso': False,
        'erro': None,
        'turnstile_configured': settings.CLOUDFLARE_TURNSTILE_CONFIGURED,
        'turnstile_site_key': settings.CLOUDFLARE_TURNSTILE_SITE_KEY,
    }

    if request.method == 'POST':
        login_id = request.POST.get('identifier') or request.POST.get('email') or ''
        login_id = login_id.strip()
        senha = request.POST.get('senha', '')
        ip = client_ip(request)
        chave_limite = f'checkin:{evento.pk}:{login_id}'
        if not aberto:
            contexto['erro'] = 'Check-in fora da janela (abre 2h antes e fecha 24h após a sessão).'
        elif login_bloqueado(ip, chave_limite):
            contexto['erro'] = 'Muitas tentativas. Aguarde alguns minutos e tente novamente.'
        elif not login_id or not senha:
            contexto['erro'] = 'Informe o número do cadastro e a senha.'
        elif not verify_turnstile_token(request.POST.get('cf-turnstile-response', '')):
            contexto['erro'] = 'Confirme que você é humano para continuar.'
        else:
            credencial = _credencial_checkin(login_id, senha)
            if credencial is None:
                login_registrar_falha(ip, chave_limite)
                contexto['erro'] = 'Login ou senha inválidos.'
            else:
                membro, email, _nome = credencial
                tenant_id = _tenant_para_chamada(request, evento)
                membro = _membro_do_checkin(evento, tenant_id, membro, email)
                if membro is None:
                    login_registrar_falha(ip, chave_limite)
                    contexto['erro'] = 'Este login não é de um irmão desta loja.'
                else:
                    login_limpar(ip, chave_limite)
                    PresencaServico.registrar_chamada(
                        evento, [{'membro': membro.pk, 'presente': True}],
                        tenant_id=tenant_id,
                    )
                    contexto['sucesso'] = True
                    contexto['nome'] = membro.nome

    return render(request, 'tarefas/checkin.html', contexto)


def _url_google_calendar(evento):
    """Link "Adicionar ao Google Agenda" — abre a agenda pessoal do membro
    já preenchida (clicão 'Adicionar' fica do lado do Google)."""
    from urllib.parse import urlencode

    inicio = evento.data_inicio.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    fim = evento.data_fim.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    loja = (
        Loja.objects.filter(pk=int(evento.loja_id)).first()
        if str(evento.loja_id).isdigit()
        else None
    )
    detalhes = f'{evento.get_tipo_display()} — {loja.nome}' if loja else evento.get_tipo_display()
    local = ''
    if loja and (loja.cidade or loja.uf):
        local = ' — '.join([p for p in (loja.cidade, loja.uf) if p])
    parametros = {
        'action': 'TEMPLATE',
        'text': f'{evento.titulo} (SAL DO REAA)',
        'dates': f'{inicio}/{fim}',
        'details': f'{detalhes}\nAgenda de Sessões — Sal do REAA',
    }
    if local:
        parametros['location'] = local
    return 'https://calendar.google.com/calendar/render?' + urlencode(parametros)


def _corpo_email_novo_evento(evento, urls_conf=None):
    """Monta (assunto, texto, html) do aviso de novo evento — ilha do envio."""
    from django.template.loader import render_to_string

    loja = (
        Loja.objects.filter(pk=int(evento.loja_id)).first()
        if str(evento.loja_id).isdigit()
        else None
    )
    vale = None
    if loja is not None:
        try:
            vale = loja.tenant.vales
        except Vale.DoesNotExist:
            vale = None

    contexto = {
        'evento': evento,
        'tipo_display': evento.get_tipo_display(),
        'loja_nome': loja.nome if loja else 'sua loja',
        'vale_nome': vale.nome if vale else '',
        'url_logo': f"{getattr(settings, 'BASE_URL', '').rstrip('/')}/static/img/logo.png",
        'inicio_display': f'{evento.data_inicio:%d/%m/%Y às %H:%M}',
        'fim_display': f'{evento.data_fim:%d/%m/%Y às %H:%M}',
        'url_google': _url_google_calendar(evento),
        'url_vou': (urls_conf or {}).get('vou') or '',
        'url_nao': (urls_conf or {}).get('nao') or '',
        'modo_teste': bool(getattr(settings, 'EVENTO_EMAIL_PARA_TESTE', None)),
    }
    html = render_to_string('tarefas/emails/evento_novo.html', contexto)
    texto = (
        f'SAL DO REAA — Agenda de Sessões\n\n'
        f'{evento.get_tipo_display()}: {evento.titulo}\n'
        f'Loja: {contexto["loja_nome"]}\n'
        f'Início: {contexto["inicio_display"]}\n'
        f'Término previsto: {contexto["fim_display"]}\n'
        f'Adicionar ao Google Agenda: {contexto["url_google"]}\n'
        + (f'Observações: {evento.descricao}\n' if evento.descricao else '')
    )
    assunto = f'SAL DO REAA — Nova sessão agendada: {evento.titulo}'
    if urls_conf:
        texto += (
            f'\nConfirme sua presença:\n'
            f'Vou comparecer: {urls_conf["vou"]}\n'
            f'Não poderei: {urls_conf["nao"]}\n'
        )
    return assunto, texto, html


def _urls_confirmacao(evento, destinatario_email):
    """Link da página de confirmação (RSVP) destinatário dos avisos
    (por token). Devolve (url_vou, url_nao) apontando à mesma página —
    nela é que o POST registra a resposta (GET de e-mail client não grava).
    """
    from django.urls import reverse

    conf = ConfirmacaoEvento.objects.filter(
        evento=evento, responsavel_email=destinatario_email,
    ).first()
    if conf is None:
        return None, None
    base = getattr(settings, 'BASE_URL', '').rstrip('/')
    caminho = reverse('tarefas:evento_confirmar', args=[conf.token])
    return f'{base}{caminho}', f'{base}{caminho}'


_fila_email_trava = threading.Lock()
_fila_worker_vivo = False


def _processar_linha_fila(linha):
    """Envia um item da fila e devolve (situacao, erro)."""
    vou, nao = _urls_confirmacao(linha.evento, linha.destinatario_email)
    urls_conf = {'vou': vou, 'nao': nao} if vou else None
    try:
        assunto, texto, html = _corpo_email_novo_evento(linha.evento, urls_conf)
    except (TemplateSyntaxError, KeyError, ValueError, TypeError) as exc:
        return 'ERRO', f'{type(exc).__name__} ao montar e-mail: {exc}'
    try:
        msg = EmailMultiAlternatives(
            subject=assunto,
            body=texto,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[linha.destinatario_email],
        )
        msg.attach_alternative(html, 'text/html')
        msg.send(fail_silently=False)
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        # Falha de SMTP, rede ou cabecalho invalido marca ERRO e sai da fila
        # PENDENTE; o comando enviar_emails_eventos reprocessa depois.
        # Erro de programacao (ex.: `except KeyError`) sobe de proposito.
        return 'ERRO', f'{type(exc).__name__}: {exc}'
    return 'ENVIADO', ''


def _worker_fila_email():
    """Consome as linhas PENDENTE da fila e atualiza o status."""
    global _fila_worker_vivo
    from django.db import close_old_connections
    try:
        while True:
            close_old_connections()
            lote = list(
                EmailEventoFila.objects
                .filter(situacao='PENDENTE')
                .order_by('id')[:100]
            )
            if not lote:
                break
            for linha in lote:
                situacao, erro = _processar_linha_fila(linha)
                tentativa = linha.tentativas + 1
                kwargs = {
                    'situacao': situacao,
                    'tentativas': tentativa,
                    'erro': erro,
                }
                if situacao == 'ENVIADO':
                    from django.utils import timezone as dj_tz
                    kwargs['enviado_em'] = dj_tz.now()
                EmailEventoFila.objects.filter(pk=linha.pk).update(**kwargs)
            # Pequena pausa entre lotes — evita martelar o SMTP em rajadas.
            from time import sleep
            sleep(0.2)
    finally:
        _fila_lock_email_concluida()


def _fila_lock_email_concluida():
    global _fila_worker_vivo
    with _fila_email_trava:
        _fila_worker_vivo = False


def _disparar_worker_fila():
    global _fila_worker_vivo
    with _fila_email_trava:
        if _fila_worker_vivo:
            return
        _fila_worker_vivo = True
    thread = threading.Thread(target=_worker_fila_email, daemon=True)
    thread.start()


def _enfileirar_email_novo_evento(evento):
    """ENVIO ASSINCRONADO: grava os destinatários na fila e devolve o
    request imediatamente (o usuário libera a tela). O worker em background
    (thread) e o comando `enviar_emails_eventos` consomem a fila — trocar
    por RabbitMQ/Celery depois substitui apenas o executor."""
    if not getattr(settings, 'EMAIL_CONFIGURADO', False):
        logger.info('Email não configurado — simulação de envio para evento %s', evento.id)
        return

    # 1) Membros ativos da loja no relacionamento loja.membros (id, nome, email).
    from core.gprb.members import emails_membros_da_loja
    try:
        membros = emails_membros_da_loja(evento.loja_id)
    except (psycopg.Error, OSError, ValueError):
        logger.exception('Erro ao buscar membros para email (loja %s)', evento.loja_id)
        membros = []

    destinatarios = [(mid, nome, (email or '').strip()) for mid, nome, email in membros if (email or '').strip()]

    # 2) Delegado do Vale da loja.
    loja = (
        Loja.objects.filter(pk=int(evento.loja_id)).first()
        if str(evento.loja_id).isdigit()
        else None
    )
    vale = None
    if loja is not None:
        try:
            vale = loja.tenant.vales
        except Vale.DoesNotExist:
            vale = None
    if vale is not None and (vale.email or '').strip():
        destinatarios.append((None, vale.prefeito or 'Delegado do Vale', vale.email.strip()))

    if not destinatarios:
        logger.info('Sem destinatários para o aviso do evento %s', evento.id)
        return

    # Modo teste: redireciona TUDO para a lista definida em settings.
    alvos_teste = list(getattr(settings, 'EVENTO_EMAIL_PARA_TESTE', []) or [])
    if alvos_teste:
        logger.info(
            'Email do evento %s em MODO TESTE: %d destinatário(s) real(is) %s '
            'substituídos por %s',
            evento.id, len(destinatarios), [e for _, _, e in destinatarios], alvos_teste,
        )
        destinatarios = [(None, nome or 'Teste', email) for _m, nome, email in ((None, None, e) for e in alvos_teste)]

    # Tokens de confirmação (RSVP) por destinatário — são a credencial da
    # página de confirmação; reuso o mesmo token a cada reaproveitamento.
    for membro_id, nome, email in destinatarios:
        ConfirmacaoEvento.objects.get_or_create(
            evento=evento,
            responsavel_email=email,
            defaults={
                'membro_id': membro_id,
                'responsavel_nome': nome or '',
            },
        )

    # Enfileira (durável) e devolve o request sem esperar SMTP.
    EmailEventoFila.objects.bulk_create([
        EmailEventoFila(
            evento=evento,
            destinatario_nome=nome or '',
            destinatario_email=email,
            situacao='PENDENTE',
        )
        for _mid, nome, email in destinatarios
    ])
    logger.info('Evento %s: %d avisos enfileirados', evento.id, len(destinatarios))
    _disparar_worker_fila()
