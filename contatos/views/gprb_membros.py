"""Tenant-scoped local CRUD for Membros."""

from datetime import date as _date, datetime

from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from acesso.decorators import (
    tenant_id_da_sessao,
    web_login_required,
    web_requer_edicao,
)
from acesso.models import ROLE_ADM, ROLE_ADMIN_SAAS, ROLES_QUE_EDITAM
from acesso.tenant_context import resolve_tenant_id
from contatos.forms_graus import GrauMembroFormSet
from contatos.models import Grau, Loja, Membro, Vale

_CAMPOS_DATA = (
    'data_admissao',
    'data_nascimento',
    'apresentacao_mx',
    'apresentacao_ec',
    'armadura_cbcs',
    'data_emissao',
    'data_instalacao',
)
_CAMPOS_TEXTO = (
    'nome_historico', 'cpf', 'rito', 'cadastro_maconico', 'tipo_admissao',
    'escolaridade',
    'potencia', 'cargo', 'condicao', 'nacionalidade', 'naturalidade',
    'estado_civil', 'pai', 'mae', 'identidade', 'orgao_emissor', 'email',
    'celular', 'telefone_urgencia', 'endereco', 'numero', 'complemento',
    'bairro', 'cidade', 'uf', 'cep',
)


def _vale_do_request(request):
    tenant_id = tenant_id_da_sessao(request)
    if tenant_id is None:
        return None
    return Vale.objects.filter(tenant_id=tenant_id, status='ATIVA').first()


def _formatar_membro_lista(membro, ano_corrente, em_q1, percentuais_presenca):
    """Converte um Membro local em dict para o template da lista."""
    from contatos.views.crud import _cor_anuidade
    cor, label = _cor_anuidade(None, ano_corrente, em_q1)
    lojas = []
    for loja in membro.lojas.all().order_by('nome', 'id'):
        try:
            vale = loja.tenant.vales
            vale_nome, vale_sigla = vale.nome, vale.sigla
        except Vale.DoesNotExist:
            vale_nome, vale_sigla = '', ''
        lojas.append({
            'loja': loja.nome, 'sigla': vale_sigla, 'potencia': vale_nome,
            'anuidade_loja': None, 'presencas_loja': 0,
        })
    grau_atual = (
        membro.graus.select_related('grau').order_by('-grau__numero').first()
    )
    # Tempo de ser-mestre: anos desde a iniciação no grau 4° (Mestre).
    hoje = _date.today()
    iniciacao_mestre = (
        membro.graus.filter(grau__numero=4).order_by('data').values_list('data', flat=True).first()
    )
    # Tempo de supremos: anos completos e meses desde a iniciação no grau 4°.
    if iniciacao_mestre:
        anos = hoje.year - iniciacao_mestre.year
        meses = hoje.month - iniciacao_mestre.month
        if hoje.day < iniciacao_mestre.day:
            meses -= 1
        if meses < 0:
            anos -= 1
            meses += 12
        tempo_mestre = {'anos': anos, 'meses': meses}
    else:
        tempo_mestre = None
    loja_principal = next(iter(lojas), {}).get('loja', '')
    cadastro_exibicao = (
        str(membro.cadastro_numero)
        if membro.cadastro_numero is not None
        else (membro.cadastro_maconico or '')
    )
    return {
        'id': membro.pk, 'nome': membro.nome or '',
        'cadastro': cadastro_exibicao,
        'tempo_mestre': tempo_mestre,
        'cpf': membro.cpf or '',
        'cidade': membro.cidade or '', 'uf': membro.uf or '',
        'situacao': membro.situacao or '',
        'ativo': (membro.situacao or '') == 'ATIVO',
        'lojas': lojas,
        'grau_atual': (
            {'numero': grau_atual.grau.numero, 'nome': grau_atual.grau.nome}
            if grau_atual else None
        ),
        'loja_nome': loja_principal,
        'presencas_ano': 0,
        'presenca_percentual': percentuais_presenca.get(membro.pk),
        'nascimento': membro.data_nascimento,
        'criado_em': membro.created_at,
        'anuidade': label, 'anuidade_cor': cor,
    }


def _papel(request):
    """Papel efetivo do usuário da sessão (DB pela middleware, snapshot de backup)."""
    usuario = getattr(request, 'usuario_logado', None)
    snapshot = request.session.get('usuario', {})
    return getattr(usuario, 'role', None) or (
        snapshot.get('role') if isinstance(snapshot, dict) else None
    )


def _e_admin_saas(request):
    return _papel(request) == ROLE_ADMIN_SAAS


def _tenant_ids_para_lista(request):
    """Retorna lista de tenant_ids permitidos para listagem, ou None para todos."""
    if _e_admin_saas(request):
        return None  # admin_saas vê todos os tenants
    tenant_id = resolve_tenant_id(request)
    if tenant_id is None:
        return []  # sem tenant = sem dados
    return [tenant_id]


def _todas_vales_ativas():
    return Vale.objects.filter(status='ATIVA').order_by('nome', 'id')


def _tem_vale_ativo(request):
    """Verifica se o usuário (não admin_saas) tem Vale ativo no seu tenant."""
    if _e_admin_saas(request):
        return True
    tenant_id = resolve_tenant_id(request)
    if tenant_id is None:
        return False
    return Vale.objects.filter(tenant_id=tenant_id, status='ATIVA').exists()


@web_login_required
def membro_lista(request):
    """Lista de membros — admin_saas vê todos os tenants; demais veem apenas o seu."""
    from django.utils import timezone

    if not _tem_vale_ativo(request):
        return HttpResponseForbidden('Seu Vale não está ativo — lista de membros indisponível.')

    hoje = timezone.now().date()
    ano_corrente = hoje.year
    em_q1 = hoje.month <= 3

    # Filtros GET
    termo = (request.GET.get('q') or '').strip()
    situacao = (request.GET.get('situacao') or '').strip().upper()
    if situacao not in ('ATIVO', 'INATIVO'):
        situacao = ''
    prefeitura_id = (request.GET.get('prefeitura') or '').strip()
    loja_id = (request.GET.get('loja') or '').strip()
    uf = (request.GET.get('uf') or '').strip().upper()
    cidade = (request.GET.get('cidade') or '').strip()
    anuidade = (request.GET.get('anuidade') or '').strip()
    if anuidade not in ('em_dia', 'atrasada', 'nunca'):
        anuidade = ''

    corpos_pedidos = request.GET.getlist('corpo')
    corpos_escolhidos = [
        corpo for corpo in corpos_pedidos if corpo in dict(Loja.CORPO_CHOICES)
    ]
    # Corpo inválido na URL = resultado vazio (mesma regra de gprb_lojas).
    corpos_invalidos = len(corpos_escolhidos) != len(corpos_pedidos)

    # Grupos de grau — mesmo padrão de /membros/acompanhamento/
    # (GRAU_PRESETS é importado aqui para evitar import circular).
    from contatos.views.acompanhamento import GRAU_PRESETS
    grupos_pedidos = [
        g for g in request.GET.getlist('grupo_grau')
        if g in GRAU_PRESETS
    ]
    numeros_grau = set()
    graus_pedidos = request.GET.getlist('grau')
    grupos_invalidos = (
        len(grupos_pedidos) != len(request.GET.getlist('grupo_grau'))
        or any(
            not valor.isdigit() or not (4 <= int(valor) <= 33)
            for valor in graus_pedidos
        )
    )
    if not grupos_invalidos:
        numeros_grau = {int(v) for v in graus_pedidos if v.isdigit()}
        for grupo in grupos_pedidos:
            numeros_grau.update(GRAU_PRESETS[grupo]['numeros'])

    tenant_ids = _tenant_ids_para_lista(request)
    qs = Membro.objects.select_related('tenant').prefetch_related('lojas__tenant', 'graus__grau')
    if corpos_invalidos or grupos_invalidos:
        qs = qs.none()
    if tenant_ids is not None:
        qs = qs.filter(tenant_id__in=tenant_ids)
    if termo:
        qs = qs.filter(
            Q(nome__icontains=termo) | Q(email__icontains=termo)
            | Q(cpf__icontains=termo) | Q(celular__icontains=termo)
        )
    if situacao:
        qs = qs.filter(situacao=situacao)
    if prefeitura_id:
        try:
            vale = Vale.objects.get(pk=int(prefeitura_id))
        except (Vale.DoesNotExist, TypeError, ValueError):
            vale = None
        qs = qs.filter(tenant_id=vale.tenant_id) if vale else qs.none()
    if corpos_escolhidos:
        filtros_loja = {
            'lojas__corpo__in': corpos_escolhidos,
            'lojas__tenant_id': F('tenant_id'),
        }
        if loja_id:
            try:
                filtros_loja['lojas__pk'] = int(loja_id)
            except (TypeError, ValueError):
                qs = qs.none()
        qs = qs.filter(**filtros_loja).distinct()
    elif loja_id:
        try:
            qs = qs.filter(lojas__id=int(loja_id)).distinct()
        except (TypeError, ValueError):
            qs = qs.none()
    if uf:
        qs = qs.filter(uf=uf)
    if cidade:
        qs = qs.filter(cidade=cidade)
    if anuidade in ('em_dia', 'atrasada'):
        # O banco local não registra pagamentos: só 'nunca' tem resultado.
        qs = qs.none()
    if numeros_grau:
        qs = qs.filter(
            graus__tenant_id=F('tenant_id'),
            graus__grau__numero__in=numeros_grau,
        ).distinct()

    qs = qs.order_by('nome', 'id')
    total = qs.count()
    page_num = request.GET.get('page', 1)
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(page_num)
    # Percentual de presença em lote (uma consulta para toda a página).
    from tarefas.presencas import PresencaServico
    percentuais_presenca = PresencaServico.percentuais(list(page_obj.object_list))
    membros = [
        _formatar_membro_lista(membro, ano_corrente, em_q1, percentuais_presenca)
        for membro in page_obj.object_list
    ]

    base_opcoes = Membro.objects
    if tenant_ids is not None:
        base_opcoes = base_opcoes.filter(tenant_id__in=tenant_ids)
    vales_opcoes = _todas_vales_ativas()
    if tenant_ids is not None:
        vales_opcoes = vales_opcoes.filter(tenant_id__in=tenant_ids)
    lojas_opcoes = Loja.objects
    if tenant_ids is not None:
        lojas_opcoes = lojas_opcoes.filter(tenant_id__in=tenant_ids)

    qs_paginacao = request.GET.copy()
    qs_paginacao.pop('page', None)

    return render(request, 'contatos/lista.html', {
        'pode_criar_membro': _pode_criar_membro(request),
        'itens': membros, 'q': termo,
        'page_obj': page_obj, 'paginator': paginator,
        'mostrados': len(membros), 'total': total, 'eh_membros': True,
        'qs': qs_paginacao.urlencode(),
        'situacao': situacao, 'prefeitura': prefeitura_id,
        'loja': loja_id, 'uf': uf,
        'cidade': cidade,
        'anuidade': anuidade,
        'filtros_ativos': bool(termo or situacao or prefeitura_id or loja_id or uf or cidade or anuidade or corpos_escolhidos or numeros_grau),
        'corpos_filtro': [
            {
                'valor': valor, 'rotulo': rotulo,
                'faixa': CORPO_FAIXA[valor],
                'selecionado': valor in corpos_escolhidos,
            }
            for valor, rotulo in Loja.CORPO_CHOICES
        ],
        'grupos_grau': [
            {
                'valor': valor,
                'nome': preset['nome'],
                'faixa': preset['faixa'],
                'selecionado': valor in grupos_pedidos,
            }
            for valor, preset in GRAU_PRESETS.items()
        ],
        'opcoes_prefeituras': [
            {'id': str(v.pk), 'nome': v.nome} for v in vales_opcoes
        ],
        'opcoes_lojas': [
            {'id': str(loja.pk), 'nome': loja.nome}
            for loja in lojas_opcoes.order_by('nome', 'id')
        ],
        'opcoes_ufs': list(
            base_opcoes.exclude(uf='').order_by('uf').values_list('uf', flat=True).distinct()
        ),
        'opcoes_cidades': list(
            base_opcoes.exclude(cidade='').order_by('cidade').values_list('cidade', flat=True).distinct()
        ),
    })


def _membro_do_papel(request, pk):
    """Resolve (membro, vale) pelo papel da sessão.

    admin_saas localiza o membro globalmente pelo ID, independentemente de
    seleção no cabeçalho; o Vale associado é o do tenant do próprio membro
    (None quando o tenant não tem Vale ativo — módulos de escrita bloqueiam).
    Demais papéis exigem tenant efetivo com Vale ATIVA e ficam nele escopados.
    Retorna (None, None) quando o papel não tem contexto de tenant válido.
    """
    if _e_admin_saas(request):
        membro = get_object_or_404(
            Membro.objects.select_related('tenant').prefetch_related('lojas'), pk=pk,
        )
        vale = Vale.objects.filter(
            tenant_id=membro.tenant_id, status='ATIVA',
        ).first()
        return membro, vale

    tenant_id = resolve_tenant_id(request)
    vale = (
        Vale.objects.filter(tenant_id=tenant_id, status='ATIVA').first()
        if tenant_id else None
    )
    if tenant_id is None or vale is None:
        return None, None
    membro = get_object_or_404(
        Membro.objects.filter(tenant_id=tenant_id).select_related('tenant').prefetch_related('lojas'),
        pk=pk,
    )
    return membro, vale


def _iso(valor):
    if not valor:
        return ''
    if hasattr(valor, 'strftime'):
        return valor.strftime('%Y-%m-%d')
    return str(valor)[:10]


def _parse_data(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_campos_data(request):
    valores = {}
    for campo in _CAMPOS_DATA:
        raw = (request.POST.get(campo, '') or '').strip()
        valores[campo] = _parse_data(raw)
        if raw and valores[campo] is None:
            return None, f'Data inválida no campo {campo.replace("_", " ").title()}.'
    return valores, None


def _lojas_do_tenant(tenant_id):
    return Loja.objects.filter(tenant_id=tenant_id).order_by('nome', 'id')


FAIXA_GRAUS_CORPO = {
    'perfeicao': (4, 14),
    'rosa_cruz': (15, 18),
    'kadosh': (19, 30),
    'consistorio': (31, 32),
    'sc33': (33, 33),
}

CORPO_FAIXA = {
    'perfeicao': '4º-14º',
    'capitulo': '15º-18º',
    'kadosh': '19º-30º',
    'consistorio': '31º-32º',
    'sc33': '33º',
}


def _graus_da_loja(loja):
    """Catálogo de graus do corpo da loja (Perfeição 4-14, Capítulo 15-18 etc.)."""
    corpo = loja.corpo if loja else 'perfeicao'
    faixa = FAIXA_GRAUS_CORPO.get(corpo)
    if faixa is None:
        return []
    return list(
        Grau.objects.filter(numero__gte=faixa[0], numero__lte=faixa[1])
        .order_by('numero')
    )


def _aplicar_grau_do_post(membro, request, lojas):
    """Grava o grau escolhido no POST como grau atual do membro.

    O membro tem histórico em GrauMembro; o select "Grau (do corpo da loja)"
    alimenta esse histórico com a data de hoje quando não há registro do mesmo
    grau. Um grau sem loja selecionada é ignorado.
    """
    raw = (request.POST.get('grau') or '').strip()
    if not raw.isdigit() or not lojas:
        return
    grau = Grau.objects.filter(pk=int(raw)).first()
    if grau is None:
        return
    # valida faixa do corpo da loja selecionada
    corpo = lojas[0].corpo
    faixa = FAIXA_GRAUS_CORPO.get(corpo)
    if faixa and not (faixa[0] <= grau.numero <= faixa[1]):
        return
    ja_tem = membro.graus.filter(grau_id=grau.pk).exists()
    if ja_tem:
        return
    membro.graus.model.objects.create(
        tenant_id=membro.tenant_id, membro=membro, grau=grau, data=_date.today(),
    )


def _lojas_selecionadas(request, tenant_id):
    """Lojas do POST devem pertencer ao tenant do Vale (M2M — várias permitidas).

    Spec 008-filtros-corpo-listas: um Membro pode estar vinculado a várias Lojas
    do mesmo tenant; toda Loja enviada precisa pertencer a ele.
    """
    raw_ids = [value for value in request.POST.getlist('lojas') if value]
    try:
        ids = {int(value) for value in raw_ids}
    except (TypeError, ValueError):
        return None, 'Selecione somente lojas deste Vale.'
    lojas = list(_lojas_do_tenant(tenant_id).filter(pk__in=ids))
    if len(lojas) != len(ids):
        return None, 'Uma ou mais lojas não pertencem a este Vale.'
    return lojas, None


def _dados_do_post(request):
    nome = (request.POST.get('nome') or '').strip()
    if not nome:
        return None, 'Informe o nome do membro.'

    valores_data, erro_data = _parse_campos_data(request)
    if erro_data:
        return None, erro_data

    situacao = (request.POST.get('situacao') or 'ATIVO').strip().upper()
    if situacao not in ('ATIVO', 'INATIVO'):
        return None, 'Selecione uma situação válida.'

    dados = {'nome': nome, 'situacao': situacao}
    dados.update({campo: (request.POST.get(campo) or '').strip() for campo in _CAMPOS_TEXTO})
    if dados['potencia'] and dados['potencia'] not in dict(Membro.POTENCIA_CHOICES):
        return None, 'Selecione uma Potência do Simbolismo válida.'
    dados.update(valores_data)
    return dados, None


def _sugestoes(tenant_id):
    qs = Membro.objects.filter(tenant_id=tenant_id)

    def distintas(campo):
        return list(
            qs.exclude(**{campo: ''})
            .order_by(campo)
            .values_list(campo, flat=True)
            .distinct()
        )

    return {
        'potencias': [valor for valor, _rotulo in Membro.POTENCIA_CHOICES],
        'cargos': distintas('cargo'),
        'ritos': distintas('rito'),
        'tipos_admissao': distintas('tipo_admissao'),
        'escolaridades': distintas('escolaridade'),
        'estados_civis': distintas('estado_civil'),
    }


def _para_contexto_membro(membro, vale, para_form=False):
    lojas = [
        {
            'id': loja.pk,
            'nome': loja.nome,
            'prefeitura': vale.nome if vale else '—',
            'sigla': vale.sigla if vale else '—',
        }
        for loja in membro.lojas.all().order_by('nome', 'id')
    ]
    dados = {
        campo.name: getattr(membro, campo.name)
        for campo in Membro._meta.concrete_fields
        if campo.name != 'tenant'
    }
    if para_form:
        for campo in _CAMPOS_DATA:
            dados[campo] = _iso(dados.get(campo))
    dados.update({
        'id': membro.pk,
        'lojas': lojas,
        'lojas_ids': [loja['id'] for loja in lojas],
        'loja': ', '.join(loja['nome'] for loja in lojas) if lojas else '— sem loja vinculada —',
        'criado_em': membro.created_at,
        'atualizado_em': membro.updated_at,
    })
    return dados


def _atribuir_cadastro_numero(membro):
    """Atribui o próximo número de cadastro maçônico (1–9999999, único)."""
    if membro.cadastro_numero is not None:
        return
    ultimo = (
        Membro.objects.exclude(cadastro_numero=None)
        .order_by('-cadastro_numero')
        .values_list('cadastro_numero', flat=True)
        .first()
    )
    if ultimo and ultimo >= 9999999:
        raise IntegrityError('Limite de números de cadastro (9999999) esgotado.')
    # Atribui a partir do maior existente; reconta buscando um livre se colidir.
    membro.cadastro_numero = (ultimo or 0) + 1
    membro.save(update_fields=['cadastro_numero'])


def _salvar_membro(request, vale, membro=None):
    graus_formset = (
        GrauMembroFormSet(request.POST, instance=membro)
        if membro is not None else None
    )
    dados, erro = _dados_do_post(request)
    if erro:
        return None, erro, graus_formset

    lojas, erro = _lojas_selecionadas(request, vale.tenant_id)
    if erro:
        return None, erro, graus_formset

    if graus_formset is not None and not graus_formset.is_valid():
        erros = [
            mensagem
            for form in graus_formset
            for lista_erros in form.errors.values()
            for mensagem in lista_erros
        ]
        erros.extend(str(erro) for erro in graus_formset.non_form_errors())
        return None, ' '.join(erros) or 'Revise os graus e suas datas.', graus_formset

    cpf = dados['cpf']
    duplicado = Membro.objects.filter(tenant_id=vale.tenant_id, cpf=cpf)
    if membro is not None:
        duplicado = duplicado.exclude(pk=membro.pk)
    if cpf and duplicado.exists():
        return None, 'Já existe um membro com este CPF neste Vale.', graus_formset

    try:
        with transaction.atomic():
            if membro is None:
                membro = Membro.objects.create(tenant_id=vale.tenant_id, **dados)
                _atribuir_cadastro_numero(membro)
            else:
                for campo, valor in dados.items():
                    setattr(membro, campo, valor)
                membro.save()
                if membro.cadastro_numero is None:
                    _atribuir_cadastro_numero(membro)
            membro.lojas.set(lojas)
            # Grau do POST (select novo) — valida que o grau pertence ao corpo da loja.
            _aplicar_grau_do_post(membro, request, lojas)
            if graus_formset is not None:
                graus_formset.save()
    except IntegrityError:
        if cpf and duplicado.exists():
            return None, 'Já existe um membro com este CPF neste Vale.', graus_formset
        return None, 'Conflito ao salvar lojas ou graus duplicados.', graus_formset
    return membro, None, graus_formset


@web_login_required
def membro_detalhe(request, pk):
    resolvido = _membro_do_papel(request, pk)
    if resolvido is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para consultar membros.')
    membro, vale = resolvido
    membro_contexto = _para_contexto_membro(membro, vale)
    membro_contexto['vale_arquivado'] = vale is None
    return render(request, 'contatos/membro_detalhe.html', {
        'membro': membro_contexto,
    })


def _pode_criar_membro(request):
    """admin_saas/ADM incluem membros; editores do tenant, no Vale ativo do seu tenant.
    """
    papel = _papel(request)
    if papel in (ROLE_ADMIN_SAAS, ROLE_ADM):
        return True
    return papel in ROLES_QUE_EDITAM and _vale_do_request(request) is not None


@web_login_required
def lojas_por_vale(request):
    """AJAX: lojas de um Vale, cada uma com os graus do seu corpo."""
    vale_id = (request.GET.get('vale') or '').strip()
    if not vale_id.isdigit():
        return JsonResponse({'lojas': []})
    tenant_ids = _tenant_ids_para_lista(request)
    vales = _todas_vales_ativas().filter(pk=int(vale_id))
    if tenant_ids is not None:
        vales = vales.filter(tenant_id__in=tenant_ids)
    tenant_id = vales.values_list('tenant_id', flat=True).first()
    if tenant_id is None:
        return JsonResponse({'lojas': []})
    lojas = list(_lojas_do_tenant(tenant_id).order_by('nome', 'pk'))
    return JsonResponse({
        'lojas': [
            {
                'id': loja.pk, 'nome': loja.nome,
                'corpo': loja.corpo, 'corpo_display': loja.get_corpo_display(),
                'graus': [
                    {'id': grau.pk, 'label': f'{grau.numero}º — {grau.nome}' if grau.nome else f'{grau.numero}º'}
                    for grau in _graus_da_loja(loja)
                ],
            }
            for loja in lojas
        ],
    })


@web_login_required
@web_requer_edicao
def membro_novo(request):
    """Criação de membro — global (admin_saas/ADM escolhem o Vale) ou do tenant.

    Papéis globais sem tenant selecionado escolhem o Vale no formulário, a
    partir dos Vales ATIVAS; os demais ficam restritos ao tenant da sessão.
    """
    if not _pode_criar_membro(request):
        return HttpResponseForbidden('Sem permissão para incluir membros.')

    global_admin = _tenant_ids_para_lista(request) is None
    vales_opcoes = []
    if global_admin:
        vales_opcoes = list(Vale.objects.filter(status='ATIVA').order_by('nome', 'id'))

    def _resolver_vale():
        """Vale destino: POST vence; fallback = tenant da sessão."""
        if global_admin:
            vale_id = (request.POST.get('vale_id') or request.GET.get('vale') or '').strip()
            if vale_id:
                for vale in vales_opcoes:
                    if str(vale.pk) == vale_id:
                        return vale
            if request.method == 'POST':
                return None  # escolha obrigatória no POST
            return None
        return _vale_do_request(request)

    vale = _resolver_vale()
    lojas = _lojas_do_tenant(vale.tenant_id) if vale else []
    erro = None
    if request.method == 'POST':
        if vale is None:
            erro = 'Selecione o Vale em que o membro será cadastrado.'
        else:
            membro, erro, _ = _salvar_membro(request, vale)
            if membro is not None:
                return redirect('membros:detalhe', pk=membro.pk)

    return render(request, 'contatos/membro_novo.html', {
        'vale': vale,
        'vales_opcoes': vales_opcoes,
        'global_admin': global_admin,
        'lojas': lojas,
        'sugestoes': _sugestoes(vale.tenant_id) if vale else {
            'potencias': [v for v, _ in Membro.POTENCIA_CHOICES],
            'cargos': [], 'ritos': [], 'tipos_admissao': [],
            'escolaridades': [], 'estados_civis': [],
        },
        'erro': erro,
    })


@web_login_required
@web_requer_edicao
def membro_editar(request, pk):
    # Escopo vem do membro (tenant persistido) — não da seleção de cabeçalho.
    resolvido = _membro_do_papel(request, pk)
    if resolvido is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para alterar membros.')
    membro, vale = resolvido
    if vale is None:
        # Escrita exige Vale ativo: arquivado/ausente bloqueia mesmo para admin_saas.
        return HttpResponseForbidden('Este Vale não está ativo — consulta disponível apenas no detalhe.')

    erro = None
    sucesso = request.GET.get('sucesso')
    graus_formset = GrauMembroFormSet(instance=membro)
    if request.method == 'POST':
        salvo, erro, graus_formset = _salvar_membro(request, vale, membro)
        if salvo is not None:
            return redirect(f'{request.path}?sucesso=1')

    membro_contexto = _para_contexto_membro(membro, vale, para_form=True)
    return render(request, 'contatos/membro_editar.html', {
        'membro': membro_contexto,
        'erro': erro,
        'sucesso': sucesso,
        'lojas': _lojas_do_tenant(vale.tenant_id),
        'sugestoes': _sugestoes(vale.tenant_id),
        'graus_formset': graus_formset,
    })


@web_login_required
@web_requer_edicao
def membro_excluir(request, pk):
    # Escopo vem do membro (tenant persistido) — não da seleção de cabeçalho.
    resolvido = _membro_do_papel(request, pk)
    if resolvido is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para alterar membros.')
    membro, vale = resolvido
    if vale is None:
        return HttpResponseForbidden('Este Vale não está ativo — exclusão bloqueada até reativação.')

    if request.method == 'POST':
        acao = request.POST.get('acao', '')
        if acao == 'inativar':
            membro.situacao = 'INATIVO'
            membro.save(update_fields=['situacao', 'updated_at'])
        else:
            membro.delete()
        return redirect('contatos:lista')

    return render(request, 'contatos/membro_excluir.html', {
        'membro': _para_contexto_membro(membro, vale),
    })
