"""Dados do board para AJAX/drag — contagens e somas de cada coluna.

Otimizado para performance:
  - Query unica de agregacao (Count + Sum)
  - Sem query duplicada de candidatos
  - Imports no topo do modulo
"""

import logging

from django.db.models import Count, Q, Sum

from acesso.decorators import filtro_tenant, nicho_da_sessao
from contatos.models import Negocio
from recepcao.models import etapas_do_tenant
from recepcao.views.helpers import _brl_curto, cards_candidatos, tenant_id_da_sessao_ou_padrao
from django.db import Error as DBError

logger = logging.getLogger(__name__)


def dados_board(request, qtd_cand=0):
    """Contagens e somas atuais de cada coluna + total do funil.

    Candidatos contam na coluna do seu nível de revisão (DM → 'suplica';
    aprovado pelo Delegado → 'prefeito'...), com o mesmo filtro de
    visibilidade do kanban.
    """
    tid = tenant_id_da_sessao_ou_padrao(request)
    nicho = nicho_da_sessao(request)
    stages = etapas_do_tenant(tid, nicho)
    negocios = _buscar_negocios_filtrados(request)
    agg = _agregar_por_stage(negocios)

    return _montar_resultado(stages, agg, _contar_candidatos(request, tid))


def _contar_candidatos(request, tid):
    """Candidatos visíveis ao papel da sessão, contados por coluna."""
    from candidatos.oficialato import pode_ver_candidato

    papel = (request.session.get('usuario') or {}).get('role', '')
    try:
        cards = cards_candidatos(tid)
    except DBError:
        logger.exception('Falha ao montar cards de candidatos (tenant %s)', tid)
        return {}
    contagem = {}
    for card in cards:
        if papel and not pode_ver_candidato(card.get('revisao'), papel):
            continue
        coluna = card.get('coluna') or 'suplica'
        contagem[coluna] = contagem.get(coluna, 0) + 1
    return contagem


def _buscar_negocios_filtrados(request):
    """Busca negocios com filtro de tenant e busca por texto (otimizado com Q)."""
    negocios = filtro_tenant(request, Negocio.objects.all())
    termo = (request.GET.get('q') or request.POST.get('q') or '').strip().lower()

    if termo:
        negocios = negocios.filter(
            Q(contato__nome__icontains=termo) |
            Q(contato__empresa__icontains=termo)
        )

    return negocios


def _agregar_por_stage(negocios):
    """Agrega contagem e soma de valores por stage (1 query)."""
    return {
        r['stage']: r
        for r in negocios.values('stage').annotate(cnt=Count('id'), soma=Sum('valor'))
    }


def _montar_resultado(stages, agg, cand_por_coluna):
    """Monta o dicionario de resultado final."""
    colunas = []
    total_candidatos = 0

    for st in stages:
        # Ignora a coluna 'perdido' — não deve aparecer no kanban
        if st['key'] == 'perdido':
            continue

        r = agg.get(st['key'])
        cnt = (r['cnt'] if r else 0) + (cand_por_coluna.get(st['key'], 0))
        soma = float(r['soma'] or 0) if r else 0.0

        total_candidatos += cnt

        colunas.append({
            'key': st['key'],
            'count': cnt,
            'soma': _brl_curto(soma),
        })

    return {
        'ok': True,
        'colunas': colunas,
        'total_candidatos': total_candidatos,
    }
