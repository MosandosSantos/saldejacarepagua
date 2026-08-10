"""Views web do Funil (kanban) — listagem por etapa, mover cartao e cadastro rapido de lead."""

from datetime import timedelta
from decimal import Decimal

from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from acesso.decorators import (
    filtro_tenant,
    nicho_da_sessao,
    pode_editar,
    tenant_id_da_sessao,
    web_login_required,
    web_requer_edicao,
)
from automacoes.engine import disparar
from contatos.models import Contato, Negocio, criar_negocio, registrar_movimentacao, so_digitos
from contatos.scoring import atualizar_score, completude_do_contato, nivel_do_score
from core.dominio import ORIGENS, SEG_FALLBACK, SEGS
from funil.models import etapa_map_do_tenant, etapas_do_tenant


def _brl_curto(n):
    n = float(n)
    if n >= 1000:
        return 'R$ ' + '{:.1f}'.format(n / 1000).replace('.0', '').replace('.', ',') + 'k'
    return 'R$ ' + str(int(n))


def _card_dict(negocio, stage_map):
    """Dados de um cartão do kanban (usado pelo board e pelo cadastro rápido)."""
    c = negocio.contato
    sg = SEGS.get(c.seg, SEG_FALLBACK)
    return {
        'id': negocio.id,  # id do NEGÓCIO — a URL /funil/{id}/mover/ move o deal
        'contato_id': c.id,  # ficha do contato (link do cartão)
        'nome': negocio.titulo or c.nome,
        'empresa': c.empresa,
        'valor': _brl_curto(negocio.valor),
        'seg_label': sg['label'],
        'seg_color': sg['color'],
        'score': c.lead_score,
        'score_nivel': nivel_do_score(c.lead_score),
        'completude': completude_do_contato(c, negocio=negocio),
    }


def _cards_do_kanban(negocios, stages):
    """Monta as colunas do quadro a partir dos negócios (cada cartão = um negócio)."""
    stage_map = {s['key']: s for s in stages}
    colunas = []
    for st in stages:
        items = [n for n in negocios if n.stage == st['key']]
        # Exibe no máximo 30 cards por coluna (sem scroll vertical); o contador
        # e a soma seguem refletindo o total real de negócios da coluna.
        cards = [_card_dict(n, stage_map) for n in items[:30]]
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
    negocios = filtro_tenant(
        request, Negocio.objects.select_related('contato').prefetch_related('contato__tags')
    )
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
        'origens': ORIGENS,
    })


@web_login_required
@web_requer_edicao
def novo_lead(request):
    """Cadastro rápido de lead — cria contato 'pobre' + negócio no funil (AJAX).

    Formulário mínimo (nome + etapa, com telefone/e-mail opcionais): o perfil
    nasce com poucos dados (contato pobre) e enriquece quando alguém completa a
    ficha. Responde JSON com o cartão renderizado e os totais do board para o
    kanban inserir o cartão sem reload.
    """
    if request.method != 'POST':
        return HttpResponseBadRequest('Método não permitido.')
    tid = tenant_id_da_sessao(request)
    nicho = nicho_da_sessao(request)
    stages = etapas_do_tenant(tid, nicho)
    stage_map = etapa_map_do_tenant(tid, nicho)
    nome = (request.POST.get('nome') or '').strip()
    tel = (request.POST.get('tel') or '').strip()
    email = (request.POST.get('email') or '').strip().lower()
    origem = (request.POST.get('origem') or '').strip()
    stage = request.POST.get('stage', '')
    raw_valor = (request.POST.get('valor') or '').strip()

    erros = []
    if not nome:
        erros.append('Informe o nome do lead.')
    if stage not in stage_map:
        erros.append('Escolha uma etapa válida.')
    if origem and origem not in ORIGENS:
        erros.append('Origem inválida.')
    valor = Decimal('0')
    if raw_valor:
        try:
            valor = (
                Decimal(raw_valor.replace('.', '').replace(',', '.'))
                if ',' in raw_valor else Decimal(raw_valor.replace(',', '.'))
            )
        except Exception:
            erros.append('Informe um valor válido (ex.: 1.500,00).')
        else:
            if valor < 0:
                erros.append('O valor não pode ser negativo.')
    if tel:
        digitos = so_digitos(tel)
        if filtro_tenant(request, Contato.objects.filter(tel_normalizado=digitos)).exists():
            erros.append('Já existe um contato com este telefone.')
    if erros:
        return JsonResponse({'ok': False, 'erros': erros}, status=400)

    contato = Contato.objects.create(
        nome=nome,
        tel=tel or '—',
        email=email or '—',
        seg='',
        origem=origem or '—',
        tenant_id=tid,
    )
    negocio = criar_negocio(contato, stage=stage, valor=valor, tenant_id=tid)
    negocio.responsavel_id = request.session.get('usuario_id')
    negocio.save(update_fields=['responsavel'])
    registrar_movimentacao(negocio, '', stage, request.session.get('usuario_id'))
    disparar('contato_criado', tenant_id=tid, contato=contato, negocio=negocio)
    disparar('negocio_criado', tenant_id=tid, contato=contato, negocio=negocio)
    atualizar_score(contato)

    html = render_to_string('funil/_card.html', {
        'card': _card_dict(negocio, stage_map),
        'stages': stages,
        'col': {'key': stage},
        'web_pode_editar': True,
    })
    board = _dados_board(request)
    return JsonResponse({
        'ok': True,
        'html': html,
        'coluna': stage,
        'colunas': board['colunas'],
        'total_funil': board['total_funil'],
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
