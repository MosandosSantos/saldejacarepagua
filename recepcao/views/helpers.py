"""Funcoes auxiliares compartilhadas entre as views do funil.

Otimizado para performance:
  - Imports no topo do modulo
  - Indice invertido para prefeituras (O(1) lookup)
  - List comprehensions em vez de loops
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from acesso.decorators import nicho_da_sessao, tenant_id_da_sessao
from contatos.scoring import completude_do_contato, nivel_do_score
from core.dominio import SEG_FALLBACK, SEGS
from core.utils import brl_curto as _brl_curto
from recepcao.models import etapas_do_tenant, etapas_e_map_do_tenant


def tenant_id_da_sessao_ou_padrao(request):
    """Tenant da sessao; admin_saas resolve para o tenant GPRB canonico."""
    tid = tenant_id_da_sessao(request)
    if tid is None:
        from acesso.models import tenant_gprb
        _t = tenant_gprb()
        tid = _t.id if _t else None
    return tid


def card_dict(negocio, stage_map):
    """Dados de um cartao do kanban (usado pelo board e pelo cadastro rapido)."""
    c = negocio.contato
    sg = SEGS.get(c.seg, SEG_FALLBACK)
    return {
        'id': negocio.id,
        'contato_id': c.id,
        'nome': negocio.titulo or c.nome,
        'empresa': c.empresa,
        'valor': _brl_curto(negocio.valor),
        'seg_label': sg['label'],
        'seg_color': sg['color'],
        'score': c.lead_score,
        'score_nivel': nivel_do_score(c.lead_score),
        'completude': completude_do_contato(c, negocio=negocio),
    }


def cards_do_kanban(negocios, stages):
    """Monta as colunas do quadro em UMA passada."""
    stage_keys = [s['key'] for s in stages]
    por_stage = {k: [] for k in stage_keys}
    for n in negocios:
        if n.stage in por_stage:
            por_stage[n.stage].append(n)

    colunas = []
    for st in stages:
        items = por_stage[st['key']]
        stage_map = {st['key']: st}
        cards = [_card_dict_completo(n, stage_map) for n in items[:30]]
        soma = sum(float(n.valor) for n in items)
        colunas.append({
            'key': st['key'],
            'name': st['name'],
            'color': st['color'],
            'count': len(items),
            'cards': cards,
            'ocultos': max(0, len(items) - 30),
            'soma': soma,
            'soma_label': _brl_curto(soma),
        })
    return colunas, por_stage


def _card_dict_completo(negocio, stage_map):
    """Card dict com score e completude (usado pelo kanban principal)."""
    c = negocio.contato
    sg = SEGS.get(c.seg, SEG_FALLBACK)
    return {
        'id': negocio.id,
        'contato_id': c.id,
        'nome': negocio.titulo or c.nome,
        'empresa': c.empresa,
        'valor': _brl_curto(negocio.valor),
        'seg_label': sg['label'],
        'seg_color': sg['color'],
        'score': c.lead_score,
        'score_nivel': nivel_do_score(c.lead_score),
        'completude': completude_do_contato(c, negocio=negocio),
    }


def _data_envio(candidato):
    """Retorna a data de envio do e-mail de convite formatada."""
    from candidatos.models import Candidato

    if candidato.status not in (Candidato.Status.FICHA_ENVIADA, Candidato.Status.EM_ANALISE):
        return ''

    updated = candidato.updated_at
    if not updated:
        return ''

    if hasattr(updated, 'date'):
        updated = updated.date()

    return updated.strftime('%d/%m/%Y') if updated else ''


# Cache do indice invertido de prefeituras
_prefeituras_cache = None
_prefeituras_por_nome = None


def prefeituras_map():
    """Retorna dict {id: {nome, sigla}} das prefeituras com cache."""
    global _prefeituras_cache

    if _prefeituras_cache is not None:
        return _prefeituras_cache

    from django.core.cache import cache

    cache_key = 'recepcao_prefeituras_map'
    result = cache.get(cache_key)
    if result is not None:
        _prefeituras_cache = result
        return result

    try:
        from core.gprb import connect
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute('SELECT id, nome, sigla FROM prefeitura ORDER BY nome')
            result = {r[0]: {'nome': r[1], 'sigla': r[2]} for r in cur.fetchall()}
        finally:
            conn.close()
    except BaseException:
        result = {}

    cache.set(cache_key, result, timeout=3600)
    _prefeituras_cache = result
    _init_indice_invertido(result)
    return result


def _init_indice_invertido(prefs):
    """Cria indice invertido {nome: id} para lookup O(1)."""
    global _prefeituras_por_nome
    _prefeituras_por_nome = {v['nome']: k for k, v in prefs.items()}


def prefeitura_info(valor):
    """Resolve {nome, sigla} da prefeitura — O(1) com indice invertido."""
    if not valor:
        return {'nome': '', 'sigla': ''}

    prefs = prefeituras_map()

    # O(1): busca por UUID
    if valor in prefs:
        return prefs[valor]

    # O(1): busca por nome (indice invertido)
    global _prefeituras_por_nome
    if _prefeituras_por_nome is None:
        _init_indice_invertido(prefs)

    pf_id = _prefeituras_por_nome.get(valor)
    if pf_id and pf_id in prefs:
        return prefs[pf_id]

    return {'nome': valor, 'sigla': ''}


def cards_candidatos(tid, limite=30, prefeitura=None):
    """Cards de candidatos para a coluna 'suplica' do kanban (com cache).

    Args:
        tid: ID do tenant
        limite: Limite máximo de cards (padrão 30)
        prefeitura: Filtro opcional por nome da prefeitura
    """
    from django.core.cache import cache
    from candidatos.models import Candidato

    # Usa versão do cache para invalidação eficiente
    version_key = f'recepcao_cards_candidatos_version_{tid}'
    version = cache.get(version_key, 0)

    # Inclui prefeitura e versão na chave do cache
    pf_key = prefeitura.replace(' ', '_') if prefeitura else 'todas'
    cache_key = f'recepcao_cards_candidatos_{tid}_{limite}_{pf_key}_v{version}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    qs = Candidato.objects.filter(
        tenant_id=tid,
        status__in=Candidato.STATUS_KANBAN,
    )

    # Filtro por prefeitura
    if prefeitura:
        qs = qs.filter(prefeitura__icontains=prefeitura)

    cands = qs.order_by('-created_at')[:limite]

    result = [_card_candidato(c) for c in cands]
    cache.set(cache_key, result, timeout=300)  # 5 minutos
    return result


def _card_candidato(c):
    """Monta dict de um candidato (extraido para clareza)."""
    from candidatos.models import Candidato
    from candidatos.oficialato import NIVEL_PARA_COLUNA_KANBAN

    # A coluna segue o nível de revisão quando existe; depois da aprovação o
    # status tem prioridade (ex.: APROVADO → prefeito).
    coluna = NIVEL_PARA_COLUNA_KANBAN.get(c.status) or NIVEL_PARA_COLUNA_KANBAN.get(c.revisao_atual, 'suplica')

    return {
        'tipo': 'candidato',
        'id': f'cand-{c.id}',
        'pk': c.id,
        'nome': c.nome_completo,
        'status': c.status,
        'status_label': c.get_status_display(),
        'status_cor': Candidato.COR_STATUS_KANBAN.get(c.status, '#94a3b8'),
        'prefeitura': prefeitura_info(c.prefeitura),
        'loja': c.loja,
        'email': c.email,
        'grau': c.grau,
        'envio_email': _data_envio(c),
        'revisao': c.revisao_atual or '',
        'coluna': coluna,
        'data_aprovacao': c.data_aprovacao.isoformat() if c.data_aprovacao else '',
    }


def estagnados_da_lista(ativos, dias=7):
    """Filtra negocios estagnados (sem movimentacao ha X dias)."""
    agora = timezone.now()
    limite = agora - timedelta(days=dias)
    return [
        {
            'contato_id': n.contato_id,
            'nome': n.titulo or n.contato.nome,
            'stage': {'name': n.stage, 'color': '#888'},
            'valor': _brl_curto(n.valor),
            'dias': (agora - n.updated_at).days,
        }
        for n in ativos[:200] if n.updated_at < limite
    ][:12]
