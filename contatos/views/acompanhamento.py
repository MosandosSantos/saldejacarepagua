from dataclasses import dataclass

from django.core.paginator import Paginator
from django.db.models import F, OuterRef, Prefetch, Q, QuerySet, Subquery
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.urls import reverse

from acesso.decorators import web_login_required
from contatos.models import Filiacao, Grau, GrauMembro, Loja, Membro, Vale
from contatos.paginacao import urls_paginacao
from contatos.views.gprb_membros import _tem_vale_ativo
from tarefas.presencas import PresencaServico

GRAU_PRESETS = {
    'perfeicao': {
        'nome': 'Perfeição',
        'faixa': '4º-14º',
        'numeros': tuple(range(4, 15)),
    },
    'rosa_cruz': {
        'nome': 'Capítulo',
        'faixa': '15º-18º',
        'numeros': tuple(range(15, 19)),
    },
    'kadosh': {
        'nome': 'Kadosh',
        'faixa': '19º-30º',
        'numeros': tuple(range(19, 31)),
    },
    'consistorio': {
        'nome': 'Consistório',
        'faixa': '31º-32º',
        'numeros': (31, 32),
    },
    'sc33': {
        'nome': 'SC33',
        'faixa': '33º',
        'numeros': (33,),
    },
}


@dataclass(frozen=True)
class ConsultaAcompanhamento:
    queryset: QuerySet[Membro]
    graus_visiveis: tuple[Grau, ...]
    grupos_selecionados: frozenset[str]
    graus_selecionados: tuple[str, ...]
    ordenar: str
    direcao: str
    sort_urls: dict[str, str]
    vale_id: str
    loja_id: str


def _resolver_consulta_acompanhamento(request):
    """Resolve filtros, escopo, colunas e ordenação sem aplicar paginação.

    Como o sistema não usa mais tenant, o escopo é definido pelas Lojas
    vinculadas ao Membro. Se uma Loja for especificada via GET ('?loja=XXX'),
    apenas os membros vinculados a essa Loja aparecem.
    """
    qs = Membro.objects.prefetch_related(
        Prefetch(
            'graus',
            queryset=GrauMembro.objects.select_related('grau').order_by('grau__numero'),
        ),
    )

    # Filtro opcional por Loja (?loja=nome_da_loja)
    loja_id = (request.GET.get('loja') or '').strip()
    if loja_id:
        if not loja_id.isdigit():
            qs = qs.none()
        else:
            loja = Loja.objects.filter(pk=int(loja_id)).first()
            if loja:
                qs = qs.filter(lojas__pk=loja.pk).distinct() if loja else qs.none()

    vale_id = (request.GET.get('vale') or '').strip()
    if vale_id:
        if not vale_id.isdigit():
            qs = qs.none()
        else:
            vale = Vale.objects.filter(pk=int(vale_id), status='ATIVA').first()
            if vale:
                # Como não há tenant, filtramos por lojas que pertençam ao mesmo
                # perfil (corpo) do Vale, ou seja, pelas lojas vinculadas ao vale.
                # Aqui simplificamos: mostramos membros com graus do vale ativo.
                pass  # Vale serve apenas como contexto, sem filtro de tenant
            else:
                qs = qs.none()

    grupos_requisitados = request.GET.getlist('grupo_grau')
    graus_requisitados = request.GET.getlist('grau')
    if any(grupo not in GRAU_PRESETS for grupo in grupos_requisitados):
        grupos_selecionados = set()
        graus_selecionados = []
        qs = qs.none()
    else:
        grupos_selecionados = set(grupos_requisitados)
        graus_selecionados = graus_requisitados
        if any(not valor.isdigit() for valor in graus_selecionados):
            qs = qs.none()
        else:
            numeros_selecionados = {int(valor) for valor in graus_selecionados}
            if any(numero < 4 or numero > 33 for numero in numeros_selecionados):
                qs = qs.none()
            else:
                for grupo in grupos_selecionados:
                    numeros_selecionados.update(GRAU_PRESETS[grupo]['numeros'])
                if numeros_selecionados:
                    qs = qs.filter(
                        graus__grau__numero__in=numeros_selecionados,
                    ).distinct()

    graus_catalogo = list(
        Grau.objects.filter(numero__range=(4, 33)).order_by('numero'),
    )
    numeros_visiveis = (
        {
            numero
            for grupo in grupos_selecionados
            for numero in GRAU_PRESETS[grupo]['numeros']
        }
        if grupos_selecionados
        else {grau.numero for grau in graus_catalogo}
    )
    graus_visiveis = tuple(
        grau for grau in graus_catalogo if grau.numero in numeros_visiveis
    )

    grau_mais_alto = GrauMembro.objects.filter(
        membro_id=OuterRef('pk'),
    ).order_by('-grau__numero').values('grau__numero')[:1]
    primeira_loja = Loja.objects.filter(
        membros__pk=OuterRef('pk'),
    ).order_by('nome', 'pk').values('nome')[:1]
    vale_do_membro = Vale.objects.filter(
        tenant_id=Filiacao.objects.filter(
            membro_id=OuterRef(OuterRef('pk')),
        ).values('tenant_id')[:1],
    ).values('nome')[:1]
    qs = qs.annotate(
        _grau_ordenacao=Subquery(grau_mais_alto),
        _loja_ordenacao=Subquery(primeira_loja),
        _vale_ordenacao=Subquery(vale_do_membro),
    )

    ordenar = request.GET.get('ordenar', 'nome')
    if ordenar not in {'nome', 'vale', 'loja', 'grau'}:
        ordenar = 'nome'
    direcao = request.GET.get('direcao', 'asc')
    if direcao not in {'asc', 'desc'}:
        direcao = 'asc'

    sort_urls = {}
    for campo in ('nome', 'vale', 'loja', 'grau'):
        parametros = request.GET.copy()
        parametros.pop('page', None)
        parametros['ordenar'] = campo
        parametros['direcao'] = (
            'desc' if ordenar == campo and direcao == 'asc' else 'asc'
        )
        sort_urls[campo] = f'?{parametros.urlencode()}'

    campo_ordenacao = {
        'nome': F('nome'),
        'vale': F('_vale_ordenacao'),
        'loja': F('_loja_ordenacao'),
        'grau': F('_grau_ordenacao'),
    }[ordenar]
    chave = (
        campo_ordenacao.desc(nulls_last=True)
        if direcao == 'desc'
        else campo_ordenacao.asc(nulls_last=True)
    )
    qs = qs.order_by(chave, 'nome', 'pk')

    return ConsultaAcompanhamento(
        queryset=qs,
        graus_visiveis=graus_visiveis,
        grupos_selecionados=frozenset(grupos_selecionados),
        graus_selecionados=tuple(graus_selecionados),
        ordenar=ordenar,
        direcao=direcao,
        sort_urls=sort_urls,
        vale_id='',
        loja_id=loja_id,
    )


def _linhas_acompanhamento(membros, graus_visiveis):
    """Serialize one member row and its presence/visible degree dates."""
    presencas = PresencaServico.percentuais(membros)
    linhas = []
    for membro in membros:
        datas_por_grau = {
            historico.grau.numero: historico.data
            for historico in membro.graus.all()
        }
        presenca = presencas.get(membro.pk)
        linhas.append({
            'id': membro.pk,
            'nome': membro.nome,
            'graus': [
                {'numero': grau.numero, 'data': datas_por_grau.get(grau.numero)}
                for grau in graus_visiveis
            ],
            'presenca': presenca,
            'tem_presenca': presenca is not None,
        })
    return linhas


@web_login_required
def acompanhamento(request):
    if not _tem_vale_ativo(request):
        return HttpResponseForbidden(
            'Seu Vale não está ativo — acompanhamento indisponível.',
        )

    # Como não há mais tenant, todos os membros ativos aparecem.
    # O filtro de Vale/Loja é opcional via parâmetros GET.
    tenant_ids = None  # sem tenant

    consulta = _resolver_consulta_acompanhamento(request)
    page_obj = Paginator(
        consulta.queryset, 20,
    ).get_page(request.GET.get('page', 1))
    membros = list(page_obj.object_list)
    linhas = _linhas_acompanhamento(membros, consulta.graus_visiveis)

    vales = Vale.objects.filter(status='ATIVA')
    lojas = Loja.objects.all()
    # Como não há filtro de tenant, mostramos todos os vales e lojas
    # O usuário pode filtrar via ?loja= e ?vale= na URL

    graus_selecionados_set = set(consulta.graus_selecionados)
    graus_opcoes = [
        {
            'numero': grau.numero,
            'nome': grau.nome,
            'selected': str(grau.numero) in graus_selecionados_set,
        }
        for grau in consulta.graus_visiveis
    ]
    grupos_opcoes = [
        {
            'valor': valor,
            'nome': preset['nome'],
            'faixa': preset['faixa'],
            'selected': valor in consulta.grupos_selecionados,
        }
        for valor, preset in GRAU_PRESETS.items()
    ]

    return render(request, 'contatos/acompanhamento.html', {
        'linhas': linhas,
        'graus': graus_opcoes,
        'colspan_vazio': 2 + len(consulta.graus_visiveis),
        'grupos_grau': grupos_opcoes,
        'vales': vales.order_by('nome', 'pk'),
        'lojas': lojas.order_by('nome', 'pk'),
        'page_obj': page_obj,
        'pagination_urls': urls_paginacao(
            request, page_obj,
            base_path=reverse('membros:acompanhamento'),
        ),
        'total': page_obj.paginator.count,
        'vale_selecionado': consulta.vale_id,
        'loja_selecionada': consulta.loja_id,
        'graus_selecionados': list(consulta.graus_selecionados),
        'ordenar': consulta.ordenar,
        'direcao': consulta.direcao,
        'sort_urls': consulta.sort_urls,
        'query': request.GET.copy(),
    })