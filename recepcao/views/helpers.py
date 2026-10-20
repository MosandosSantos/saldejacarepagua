"""Funcoes auxiliares compartilhadas entre as views do funil.

Otimizado para performance:
  - Imports no topo do modulo
  - Indice invertido para prefeituras (O(1) lookup)
  - List comprehensions em vez de loops
"""

import logging
from datetime import timedelta

from django.core.cache import cache
from django.db import DatabaseError, OperationalError, ProgrammingError
from django.db.models import Max, Q
from django.utils import timezone

from acesso.decorators import tenant_id_da_sessao
from acesso.models import tenant_gprb
from candidatos.models import Candidato
from candidatos.oficialato import NIVEL_PARA_COLUNA_KANBAN
from contatos.models import Vale
from contatos.scoring import completude_do_contato, nivel_do_score
from core.dominio import SEG_FALLBACK, SEGS
from core.gprb import connect as gprb_connect
from core.gprb.connection import resolve_tenant_code
from core.utils import brl_curto as _brl_curto

logger = logging.getLogger(__name__)


def tenant_id_da_sessao_ou_padrao(request):
    """Tenant da sessao; admin_saas resolve para o tenant GPRB canonico."""
    tid = tenant_id_da_sessao(request)
    if tid is None:
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

    if candidato.status not in (Candidato.Status.FICHA_ENVIADA, Candidato.Status.EM_ANALISE):
        return ''

    updated = candidato.updated_at
    if not updated:
        return ''

    if hasattr(updated, 'date'):
        updated = updated.date()

    return updated.strftime('%d/%m/%Y') if updated else ''


# Cache do indice invertido de prefeituras
_prefeituras_cache = {}
_prefeituras_por_nome = {}


def prefeituras_map():
    """Retorna dict {id: {nome, sigla}} das prefeituras com cache."""
    tenant_code = resolve_tenant_code()

    if tenant_code in _prefeituras_cache:
        return _prefeituras_cache[tenant_code]

    cache_key = f'recepcao_prefeituras_map:{tenant_code}'
    result = cache.get(cache_key)
    if result is not None:
        _prefeituras_cache[tenant_code] = result
        _init_indice_invertido(result, tenant_code)
        return result

    try:
        conn = gprb_connect()
        try:
            cur = conn.cursor()
            cur.execute(
                'SELECT p.id, p.nome, p.sigla FROM prefeitura p '
                'JOIN tenant t ON t.id = p."tenantId" '
                'WHERE t.code = %s ORDER BY p.nome',
                (tenant_code,),
            )
            result = {r[0]: {'nome': r[1], 'sigla': r[2]} for r in cur.fetchall()}
        finally:
            conn.close()
    except (DatabaseError, OperationalError, ProgrammingError, AttributeError, TypeError, ValueError):
        logger.exception('Falha ao buscar prefeituras GPRB; usando mapa vazio')
        result = {}

    cache.set(cache_key, result, timeout=3600)
    _prefeituras_cache[tenant_code] = result
    _init_indice_invertido(result, tenant_code)
    return result


def _init_indice_invertido(prefs, tenant_code):
    """Cria indice invertido {nome: id} para lookup O(1)."""
    _prefeituras_por_nome[tenant_code] = {v['nome']: k for k, v in prefs.items()}


def prefeitura_info(valor):
    """Resolve {nome, sigla} da prefeitura — O(1) com indice invertido."""
    if not valor:
        return {'nome': '', 'sigla': ''}

    tenant_code = resolve_tenant_code()
    prefs = prefeituras_map()

    # O(1): busca por UUID
    if valor in prefs:
        return prefs[valor]

    # O(1): busca por nome (indice invertido)
    if tenant_code not in _prefeituras_por_nome:
        _init_indice_invertido(prefs, tenant_code)

    pf_id = _prefeituras_por_nome[tenant_code].get(valor)
    if pf_id and pf_id in prefs:
        return prefs[pf_id]

    return {'nome': valor, 'sigla': ''}


def cards_candidatos(tid, limite=30, prefeitura=None, loja=None):
    """Cards de candidatos para a coluna 'suplica' do kanban (com cache).

    Args:
        tid: ID do tenant
        limite: Limite máximo de cards (padrão 30)
        prefeitura: Filtro opcional por prefeitura — string ou lista de
            padrões (iconta: id do Vale como string e/ou nome do Vale)
        loja: Filtro opcional por nome da loja do candidato
    """

    # Usa versão do cache para invalidação eficiente
    # Invalidação automática ao renomear/editar Vale: inclui max Vale.updated_at.
    try:
        vale_rev = Vale.objects.filter(tenant_id=tid).aggregate(m=Max('updated_at'))['m']
        vale_rev = int(vale_rev.timestamp()) if vale_rev else 0
    except (AttributeError, TypeError, ValueError, DatabaseError, OperationalError, ProgrammingError):
        vale_rev = 0

    version_key = f'recepcao_cards_candidatos_version_{tid}'
    version = cache.get(version_key, 0)

    # Inclui prefeitura e versão na chave do cache
    padroes_pf = [prefeitura] if isinstance(prefeitura, str) else list(prefeitura or [])
    pf_key = '_'.join(p.replace(' ', '_') for p in padroes_pf) or 'todas'
    loja_key = loja.replace(' ', '_') if loja else 'todas'
    cache_key = f'recepcao_cards_candidatos_{tid}_{limite}_{pf_key}_{loja_key}_v{version}_vr{vale_rev}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    qs = Candidato.objects.filter(
        tenant_id=tid,
        status__in=Candidato.STATUS_KANBAN,
    )

    # Filtro por prefeitura (id string e/ou nome — candidatos guardam os dois)
    if padroes_pf:
        filtro_pf = Q()
        for padrao in padroes_pf:
            filtro_pf |= Q(prefeitura__icontains=padrao)
        qs = qs.filter(filtro_pf)

    # Filtro por loja (armazenada como nome no candidato)
    if loja:
        qs = qs.filter(loja__icontains=loja)

    cands = list(qs.order_by('-created_at')[:limite])
    vales_locais = _vales_locais_por_tenant(tid) if cands else {}

    result = [_card_candidato(c, vales_locais) for c in cands]
    cache.set(cache_key, result, timeout=300)  # 5 minutos; cache_key already includes vales version? no
    return result


def _vales_locais_por_tenant(tenant_id):
    """Map local tenant Vale(s) to their name by several stable keys."""
    vales = list(Vale.objects.filter(tenant_id=tenant_id).values('id', 'nome'))
    mapa = {}
    for vale in vales:
        mapa[str(vale['id'])] = vale['nome']
        mapa[vale['nome'].casefold()] = vale['nome']
        mapa[str(tenant_id)] = mapa.get(str(tenant_id), vale['nome'])
    return mapa


def _card_candidato(c, vales_locais=None):
    """Monta dict de um candidato (extraido para clareza)."""
    # A coluna segue o nível de revisão quando existe; depois da aprovação o
    # status tem prioridade (ex.: APROVADO → prefeito).
    coluna = NIVEL_PARA_COLUNA_KANBAN.get(c.status) or NIVEL_PARA_COLUNA_KANBAN.get(c.revisao_atual, 'suplica')
    prefeitura = (c.prefeitura or '').strip()
    tenant_key = str(getattr(c, 'tenant_id', ''))
    nome_vale = (
        (vales_locais or {}).get(prefeitura)
        or (vales_locais or {}).get(prefeitura.casefold())
        or (vales_locais or {}).get(tenant_key)
    )

    return {
        'tipo': 'candidato',
        'id': f'cand-{c.id}',
        'pk': c.id,
        'nome': c.nome_completo,
        'status': c.status,
        'status_label': c.get_status_display(),
        'status_cor': Candidato.COR_STATUS_KANBAN.get(c.status, '#94a3b8'),
        'prefeitura': (
            {'nome': nome_vale, 'sigla': ''}
            if nome_vale else prefeitura_info(c.prefeitura)
        ),
        'loja': c.loja,
        'email': c.email,
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
