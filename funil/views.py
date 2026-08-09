"""Views web do Funil (kanban) — listagem por etapa e mover cartao."""

from datetime import timedelta

from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from acesso.decorators import filtro_tenant, nicho_da_sessao, pode_editar, tenant_id_da_sessao, web_login_required
from automacoes.engine import disparar
from contatos.models import Negocio, registrar_movimentacao
from contatos.scoring import atualizar_score, nivel_do_score
from core.dominio import SEG_FALLBACK, SEGS
from funil.models import etapa_map_do_tenant, etapas_do_tenant


def _brl_curto(n):
    n = float(n)
    if n >= 1000:
        return 'R$ ' + '{:.1f}'.format(n / 1000).replace('.0', '').replace('.', ',') + 'k'
    return 'R$ ' + str(int(n))


def _cards_do_kanban(negocios, stages):
    """Monta as colunas do quadro a partir dos negócios (cada cartão = um negócio)."""
    colunas = []
    for st in stages:
        items = [n for n in negocios if n.stage == st['key']]
        # Exibe no máximo 30 cards por coluna (sem scroll vertical); o contador
        # e a soma seguem refletindo o total real de negócios da coluna.
        cards = []
        for n in items[:30]:
            c = n.contato
            sg = SEGS.get(c.seg, SEG_FALLBACK)
            cards.append({
                'id': n.id,  # id do NEGÓCIO — a URL /funil/{id}/mover/ move o deal
                'contato_id': c.id,  # ficha do contato (link do cartão)
                'nome': n.titulo or c.nome,
                'empresa': c.empresa,
                'valor': _brl_curto(n.valor),
                'seg_label': sg['label'],
                'seg_color': sg['color'],
                'score': c.lead_score,
                'score_nivel': nivel_do_score(c.lead_score),
            })
        colunas.append({
            'key': st['key'],
            'name': st['name'],
            'color': st['color'],
            'count': len(items),
            'cards': cards,
            'ocultos': max(0, len(items) - 30),
            'soma': sum(float(n.valor) for n in items),
            'soma_label': _brl_curto(sum(float(n.valor) for n in items)),
        })
    return colunas


@web_login_required
def kanban(request):
    tid = tenant_id_da_sessao(request)
    nicho = nicho_da_sessao(request)
    stages = etapas_do_tenant(tid, nicho)
    stage_map = etapa_map_do_tenant(tid, nicho)
    negocios = filtro_tenant(request, Negocio.objects.select_related('contato'))
    termo = request.GET.get('q', '').strip().lower()
    if termo:
        negocios = negocios.filter(contato__nome__icontains=termo) | negocios.filter(contato__empresa__icontains=termo)

    colunas = _cards_do_kanban(list(negocios), stages)
    ativos = negocios.exclude(stage__in=['perdido', 'fechado'])
    total_funil = _brl_curto(sum(float(n.valor) for n in ativos))

    # Negócios estagnados (sem movimentação há X dias) — alerta de recuperação
    raw_dias = request.GET.get('dias', '')
    dias = int(raw_dias) if raw_dias.isdigit() else 7
    dias = max(1, min(dias, 90))
    agora = timezone.now()
    estagnados = [
        {
            'contato_id': n.contato_id,
            'nome': n.titulo or n.contato.nome,
            'stage': stage_map.get(n.stage, {'name': n.stage, 'color': '#888'}),
            'valor': _brl_curto(n.valor),
            'dias': (agora - n.updated_at).days,
        }
        for n in ativos.filter(updated_at__lt=agora - timedelta(days=dias))
        .select_related('contato')[:12]
    ]

    return render(request, 'funil/kanban.html', {
        'colunas': colunas,
        'stages': stages,
        'stage_map': stage_map,
        'total_funil': total_funil,
        'estagnados': estagnados,
        'dias': dias,
        'q': request.GET.get('q', ''),
    })


def _dados_board(request):
    """Contagens e somas atuais de cada coluna + total do funil (para o drag sem reload).

    Aplica o mesmo filtro de busca `q` da view kanban (o JS envia o termo junto
    no POST do mover) para que contador e aviso de ocultos batam com o que está
    na tela depois do drag.
    """
    stages = etapas_do_tenant(tenant_id_da_sessao(request), nicho_da_sessao(request))
    negocios = filtro_tenant(request, Negocio.objects.all())
    termo = (request.GET.get('q') or request.POST.get('q') or '').strip().lower()
    if termo:
        negocios = negocios.filter(contato__nome__icontains=termo) | negocios.filter(contato__empresa__icontains=termo)
    colunas = []
    for st in stages:
        items = [n for n in negocios if n.stage == st['key']]
        colunas.append({
            'key': st['key'],
            'count': len(items),
            'soma': _brl_curto(sum(float(n.valor) for n in items)),
        })
    ativos = negocios.exclude(stage__in=['perdido', 'fechado'])
    return {
        'ok': True,
        'colunas': colunas,
        'total_funil': _brl_curto(sum(float(n.valor) for n in ativos)),
    }


@web_login_required
def mover(request, pk):
    """Move um NEGÓCIO (deal) de etapa — pk é o id do negocio."""
    if request.method != 'POST':
        return HttpResponseBadRequest('Método não permitido.')
    if not pode_editar(request):
        # viewer (somente leitura): bloqueia a movimentação
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return HttpResponseForbidden('Somente leitura.')
        return redirect('funil:kanban')
    stage = request.POST.get('stage', '')
    if stage not in etapa_map_do_tenant(tenant_id_da_sessao(request), nicho_da_sessao(request)):
        return HttpResponseBadRequest('Etapa inválida.')
    negocio = get_object_or_404(filtro_tenant(request, Negocio.objects.all()), pk=pk)
    de_etapa = negocio.stage
    if negocio.stage != stage:
        registrar_movimentacao(negocio, negocio.stage, stage, request.session.get('usuario_id'))
        negocio.stage = stage
        negocio.save(update_fields=['stage', 'updated_at'])
        if stage == 'fechado':
            # S4 — a proposta enviada por e-mail converteu em venda
            from emails.servico import marcar_conversoes

            marcar_conversoes(negocio.contato)
        disparar(
            'negocio_movido',
            tenant_id=tenant_id_da_sessao(request),
            contato=negocio.contato,
            negocio=negocio,
            de_etapa=de_etapa,
            para_etapa=stage,
        )
        atualizar_score(negocio.contato)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(_dados_board(request))
    return redirect('funil:kanban')
