"""Views web do app tarefas — lista com lembretes, criar/editar, concluir/reabrir/excluir.

As tarefas são escopadas por tenant; o vencimento alimenta os lembretes
(atrasadas, de hoje, próximas). Viewer só visualiza; admin exclui.
"""

import json
import logging
import re
import smtplib
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from acesso.decorators import (
    e_admin_do_tenant,
    filtro_tenant,
    pode_editar,
    web_login_required,
    web_requer_edicao,
    web_requer_tenant_context,
)
from acesso.models import Usuario
from contatos.models import Contato
from core.utils import iniciais as _iniciais
from core.utils import tenant_id as _tenant_id
from tarefas.ical import gerar_ics, gerar_ics_eventos, parse_ics
from tarefas.google_sync import remover_google, tentar_sincronizar
from tarefas.models import (
    PRIORIDADE_CORES,
    PRIORIDADES,
    Evento,
    Tarefa,
    concluir_tarefa,
    reabrir_tarefa,
)

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

    # Serializar eventos para JSON
    eventos_json = []
    for ev in eventos:
        pode_editar = bool(loja_id_usuario and ev.loja_id == loja_id_usuario)
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

    return render(request, 'tarefas/ranking.html', {
        'eventos_json': json.dumps(eventos_json),
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
        'hoje': hoje,
    })


# ---------------------------------------------------------------------------
# API JSON para eventos (CRUD)
# ---------------------------------------------------------------------------


def _obter_loja_usuario(request):
    """Retorna o loja_id do usuário logado (None se não tiver)."""
    return request.session.get('usuario', {}).get('loja_id') or None


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

    loja_id_usuario = _obter_loja_usuario(request)

    eventos_list = []
    for ev in eventos:
        pode_editar = bool(loja_id_usuario and ev.loja_id == loja_id_usuario)
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
        })

    return JsonResponse({'eventos': eventos_list})


@web_login_required
@require_POST
def evento_criar(request):
    """Cria um novo evento (só se o usuário tiver loja_id)."""
    loja_id = _obter_loja_usuario(request)
    if not loja_id:
        return JsonResponse({'erro': 'Usuário não vinculado a uma loja'}, status=403)

    try:
        dados = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON inválido'}, status=400)

    titulo = dados.get('titulo', '').strip()
    if not titulo:
        return JsonResponse({'erro': 'Título é obrigatório'}, status=400)

    try:
        data_inicio = datetime.fromisoformat(dados['data_inicio'])
        data_fim = datetime.fromisoformat(dados['data_fim'])
    except (KeyError, ValueError):
        return JsonResponse({'erro': 'Datas inválidas'}, status=400)

    if data_fim <= data_inicio:
        return JsonResponse({'erro': 'Data fim deve ser posterior à data início'}, status=400)

    evento = Evento.objects.create(
        titulo=titulo,
        descricao=dados.get('descricao', ''),
        tipo=dados.get('tipo', 'sessao'),
        data_inicio=data_inicio,
        data_fim=data_fim,
        loja_id=loja_id,
        criado_por_id=_usuario_id(request),
    )

    # Enviar email para membros da loja
    _enviar_email_novo_evento(evento)

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
    """Edita um evento (só se for da loja do usuário)."""
    loja_id = _obter_loja_usuario(request)
    if not loja_id:
        return JsonResponse({'erro': 'Usuário não vinculado a uma loja'}, status=403)

    try:
        evento = Evento.objects.get(pk=evento_id)
    except Evento.DoesNotExist:
        return JsonResponse({'erro': 'Evento não encontrado'}, status=404)

    if evento.loja_id != loja_id:
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
        evento.tipo = dados['tipo']
    if 'data_inicio' in dados:
        evento.data_inicio = datetime.fromisoformat(dados['data_inicio'])
    if 'data_fim' in dados:
        evento.data_fim = datetime.fromisoformat(dados['data_fim'])

    evento.save()

    # Auto-sync Google Calendar (best-effort)
    tentar_sincronizar(evento)

    return JsonResponse({'ok': True})


@web_login_required
@require_POST
def evento_excluir(request, evento_id):
    """Exclui um evento (só se for da loja do usuário)."""
    loja_id = _obter_loja_usuario(request)
    if not loja_id:
        return JsonResponse({'erro': 'Usuário não vinculado a uma loja'}, status=403)

    try:
        evento = Evento.objects.get(pk=evento_id)
    except Evento.DoesNotExist:
        return JsonResponse({'erro': 'Evento não encontrado'}, status=404)

    if evento.loja_id != loja_id:
        return JsonResponse({'erro': 'Sem permissão para excluir este evento'}, status=403)

    remover_google(evento)  # best-effort: apaga no Google antes do local
    evento.delete()
    return JsonResponse({'ok': True})


def _enviar_email_novo_evento(evento):
    """Envia email para todos os membros da loja quando um evento é criado."""
    if not getattr(settings, 'EMAIL_CONFIGURADO', False):
        logger.info('Email não configurado — simulação de envio para evento %s', evento.id)
        return

    # Busca membros ativos da loja no tenant externo configurado.
    from core.gprb.members import emails_membros_da_loja
    try:
        membros = emails_membros_da_loja(evento.loja_id)
    except Exception:
        logger.exception('Erro ao buscar membros para email (loja %s)', evento.loja_id)
        return

    if not membros:
        return

    assunto = f'Nova sessão agendada: {evento.titulo}'
    corpo = (
        f'Uma nova sessão foi agendada para sua loja:\n\n'
        f'Tipo: {evento.get_tipo_display()}\n'
        f'Título: {evento.titulo}\n'
        f'Data: {evento.data_inicio:%d/%m/%Y às %H:%M}\n'
        f'Até: {evento.data_fim:%d/%m/%Y às %H:%M}\n'
    )
    if evento.descricao:
        corpo += f'\\nDescrição: {evento.descricao}\n'

    for nome, email in membros:
        try:
            msg = EmailMultiAlternatives(
                subject=assunto,
                body=corpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
            )
            msg.send(fail_silently=False)
        except (OSError, smtplib.SMTPException):
            logger.warning('Falha ao enviar email para %s', email, exc_info=True)
