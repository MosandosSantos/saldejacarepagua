"""Carteiras (Sprint 3 do PRD HAZON — Gestão de bases)."""

from django.shortcuts import get_object_or_404, redirect, render

from acesso.decorators import e_admin_do_tenant, filtro_tenant, nicho_da_sessao, web_login_required
from contatos.models import Carteira, Contato
from contatos.views.helpers import _decorar, _tenant_id
from funil.models import etapa_map_do_tenant


def _carteiras_scope(request):
    """Queryset de carteiras escopado ao tenant da sessão (admin_saas ve todas)."""
    qs = Carteira.objects.all()
    tid = _tenant_id(request)
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return qs


@web_login_required
def carteiras(request):
    """Lista as carteiras do tenant e cria novas (apenas admin cria)."""
    erros = []
    sucesso = None
    if request.method == 'POST' and e_admin_do_tenant(request):
        nome = (request.POST.get('nome') or '').strip()
        descricao = (request.POST.get('descricao') or '').strip()
        if not nome:
            erros.append('Informe o nome da carteira.')
        else:
            tid = _tenant_id(request)
            qs = Carteira.objects.all() if tid is None else Carteira.objects.filter(tenant_id=tid)
            if qs.filter(nome__iexact=nome).exists():
                erros.append(f'Já existe uma carteira chamada "{nome}".')
            else:
                carteira = Carteira(nome=nome, descricao=descricao)
                if tid is not None:
                    carteira.tenant_id = tid
                carteira.save()
                sucesso = f'Carteira "{nome}" criada.'

    itens = []
    for c in _carteiras_scope(request).prefetch_related('contatos'):
        total_contatos = c.contatos.count()
        fechados = c.contatos.filter(negocios__stage='fechado').distinct().count()
        itens.append({
            'id': c.id,
            'nome': c.nome,
            'descricao': c.descricao,
            'total': total_contatos,
            'fechados': fechados,
            'criada_em': c.created_at,
        })
    return render(request, 'contatos/carteiras.html', {
        'itens': itens,
        'erros': erros,
        'sucesso': sucesso,
        'nome': request.POST.get('nome', '') if request.method == 'POST' else '',
        'descricao': request.POST.get('descricao', '') if request.method == 'POST' else '',
    })


@web_login_required
def carteira_detalhe(request, pk):
    """Detalhe da carteira — lista os contatos associados, com filtro por etapa."""
    nicho = nicho_da_sessao(request)
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho)
    carteira = get_object_or_404(_carteiras_scope(request), pk=pk)

    # Editar (nome/descrição) e excluir — só admin
    erros = []
    sucesso = None
    if request.method == 'POST':
        if not e_admin_do_tenant(request):
            return redirect('contatos:carteira_detalhe', pk=pk)
        acao = request.POST.get('acao', '')
        if acao == 'editar':
            nome = (request.POST.get('nome') or '').strip()
            if not nome:
                erros.append('Informe o nome da carteira.')
            else:
                carteira.nome = nome
                carteira.descricao = (request.POST.get('descricao') or '').strip()
                carteira.save()
                sucesso = 'Carteira atualizada.'
        elif acao == 'excluir':
            # Contatos ficam sem carteira (SET_NULL) — nenhum dado é perdido
            carteira.delete()
            return redirect('contatos:carteiras')

    contatos = (
        carteira.contatos.select_related('carteira')
        .prefetch_related('negocios', 'tags')
    )
    etapa = request.GET.get('etapa', '')
    if etapa:
        # distinct(): um contato com vários negócios na mesma etapa não pode
        # aparecer duplicado na tabela (a contagem do resumo já usa distinct)
        contatos = contatos.filter(negocios__stage=etapa).distinct()
    contatos = contatos.order_by('nome')
    itens = [_decorar(c, stage_map) for c in contatos]

    # Resumo por etapa para os filtros
    resumo_etapas = []
    for s in etapa_map_do_tenant(_tenant_id(request), nicho).values():
        qtd = carteira.contatos.filter(negocios__stage=s['key']).distinct().count()
        resumo_etapas.append({
            'key': s['key'],
            'name': s['name'],
            'color': s['color'],
            'qtd': qtd,
        })

    return render(request, 'contatos/carteira_detalhe.html', {
        'carteira': {
            'id': carteira.id,
            'nome': carteira.nome,
            'descricao': carteira.descricao,
            'total': len(itens),
        },
        'itens': itens,
        'etapa_ativa': etapa,
        'resumo_etapas': resumo_etapas,
        'erros': erros,
        'sucesso': sucesso,
    })
