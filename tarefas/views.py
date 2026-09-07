"""Views web do app tarefas — lista com lembretes, criar/editar, concluir/reabrir/excluir.

As tarefas são escopadas por tenant; o vencimento alimenta os lembretes
(atrasadas, de hoje, próximas). Viewer só visualiza; admin exclui.
"""

import locale
import logging
import re
from datetime import date, time

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from acesso.decorators import (
    e_admin_do_tenant,
    filtro_tenant,
    pode_editar,
    web_login_required,
    web_requer_edicao,
)
from acesso.models import Usuario
from contatos.models import Contato
from core.utils import iniciais as _iniciais
from core.utils import tenant_id as _tenant_id
from tarefas.ical import gerar_ics, parse_ics
from tarefas.models import (
    PRIORIDADE_CORES,
    PRIORIDADES,
    Tarefa,
    concluir_tarefa,
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
@web_requer_edicao
def concluir(request, pk):
    """Marca como concluída (POST) e volta para a origem (ficha ou lista)."""
    if request.method == 'POST':
        tarefa = get_object_or_404(filtro_tenant(request, Tarefa.objects.all()), pk=pk)
        concluir_tarefa(tarefa)
    return _voltar(request)


@web_login_required
@web_requer_edicao
def reabrir(request, pk):
    if request.method == 'POST':
        tarefa = get_object_or_404(filtro_tenant(request, Tarefa.objects.all()), pk=pk)
        reabrir_tarefa(tarefa)
    return _voltar(request)


@web_login_required
def excluir(request, pk):
    """Excluir tarefa — apenas admin (operacional volta)."""
    if not e_admin_do_tenant(request):
        return redirect('tarefas:lista')
    if request.method == 'POST':
        tarefa = get_object_or_404(filtro_tenant(request, Tarefa.objects.all()), pk=pk)
        tarefa.delete()
    return _voltar(request)


@web_login_required
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
def exportar_ics(request):
    """Exporta todas as tarefas abertas do tenant como arquivo .ics (Google Calendar)."""
    tid = _tenant_id(request)
    qs = Tarefa.objects.filter(tenant_id=tid).select_related('contato', 'responsavel')
    ics_bytes = gerar_ics(qs)
    response = HttpResponse(ics_bytes, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="GPRBRCRM-tarefas.ics"'
    return response


@web_login_required
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
    except Exception:
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
    from datetime import date

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
    """Página de ranking de presença (baseada no PRD-RANKING)."""
    from datetime import date

    from core.gprb import ranking_dados

    classe = request.GET.get('classe', 'MX').upper().strip()
    if classe not in ('MX', 'EN'):
        classe = 'MX'

    prefeitura_id = request.GET.get('prefeitura_id') or None
    loja_id = request.GET.get('loja_id') or None

    # Período fixo: últimos 24 meses
    data_inicio = date(date.today().year - 2, 1, 1)
    data_fim = date.today()

    # Tabela: com os filtros de classe/prefeitura/loja aplicados
    stats_por_membro = {}
    ranking_rows = []
    if True:
        dados = ranking_dados(
            classe=classe,
            loja_id=loja_id,
            prefeitura_id=prefeitura_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        stats_por_membro = {s['memberId']: s for s in dados['memberStats']}
        ranking_rows = _linhas_ranking(dados['members'], stats_por_membro)

    # KPIs: contagem de TODOS os elegíveis (MX e EN), SEM o filtro — estáticos
    dados_kpi = ranking_dados(
        classe=None,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
    stats_kpi = {s['memberId']: s for s in dados_kpi['memberStats']}
    linhas_kpi = _linhas_ranking(dados_kpi['members'], stats_kpi)
    total_ec = sum(1 for r in linhas_kpi if r['classe'] == 'EN')
    total_mx = sum(1 for r in linhas_kpi if r['classe'] == 'MX')
    total_ranking = len(linhas_kpi)

    # Sort composto — todos já são elegíveis (tempo, presença, anuidade OK)
    ranking_rows.sort(key=lambda x: (
        -x['tempo_meses'],
        -x['idade'],
        x['original_index'],
    ))

    # Atribuir posição RK
    for i, row in enumerate(ranking_rows, 1):
        row['rk'] = i

    # Prefeituras e lojas para filtro (degradação graciosa se o GPRB cair)
    from core.gprb import connect
    prefeituras = []
    lojas_da_prefeitura = []
    try:
        conn = connect()
        try:
            cur = conn.cursor()
            tid = request.session.get('usuario', {}).get('tenant_id')
            if not tid:
                # Sessão sem tenant (ex.: admin_saas): usa o tenant GPRB do ranking
                cur.execute("SELECT id FROM tenant WHERE code = 'GPRB'")
                _row = cur.fetchone()
                tid = _row[0] if _row else None
            if tid:
                cur.execute(
                    'SELECT id, nome FROM prefeitura WHERE "tenantId" = %s::text ORDER BY nome',
                    (str(tid),),
                )
                prefeituras = [{'id': r[0], 'nome': r[1]} for r in cur.fetchall()]
                if prefeitura_id:
                    cur.execute(
                        'SELECT id, COALESCE("nomeFantasia", "lojaMX", \'Loja \' || numero::text) '
                        'FROM loja WHERE "tenantId" = %s::text AND "prefeituraId" = %s::text '
                        'AND situacao = \'ATIVA\' ORDER BY 2',
                        (str(tid), prefeitura_id),
                    )
                    lojas_da_prefeitura = [{'id': r[0], 'nome': r[1]} for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        logger.exception('GPRB indisponível ao listar prefeituras/lojas: %s', e)
        prefeituras = []
        lojas_da_prefeitura = []

    # Formatar datas de recepção
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except Exception as e:
        logger.debug('Locale pt_BR.UTF-8 não disponível: %s', e)
    for row in ranking_rows:
        try:
            d = date.fromisoformat(row['recepcao']) if row['recepcao'] else None
            row['recepcao_fmt'] = d.strftime('%d/%m/%Y') if d else '—'
        except Exception:
            row['recepcao_fmt'] = row['recepcao'] or '—'

    return render(request, 'tarefas/ranking.html', {
        'ranking_rows': ranking_rows,
        'classe_selecionada': classe,
        'prefeituras': prefeituras,
        'prefeitura_selecionada': prefeitura_id or '',
        'lojas_da_prefeitura': lojas_da_prefeitura,
        'loja_selecionada': loja_id or '',
        'tem_filtros': bool(prefeitura_id or loja_id or classe != 'MX'),
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'total_ranking': total_ranking,
        'total_ec': total_ec,
        'total_mx': total_mx,
    })
