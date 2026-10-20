"""Views de CRUD de contatos — listar, detalhe, novo, editar, excluir e leads pobres.

As views de GPRB (prefeituras, lojas, membros) foram extraidas para:
- gprb_prefeituras.py
- gprb_lojas.py
- gprb_membros.py
todas usando o repository em repositories/gprb_repository.py
"""

from datetime import date

from django.conf import settings
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from acesso.decorators import (
    e_admin_do_tenant,
    filtro_tenant,
    nicho_da_sessao,
    tenant_id_da_sessao,
    web_login_required,
    web_requer_edicao,
    web_requer_tenant_context,
)
from contatos.forms import ContatoForm, NotaForm
from contatos.models import Contato, Loja, Membro, Movimentacao, Vale
from contatos.scoring import completude_do_contato
from contatos.services import atualizar_negocio_do_contato, criar_negocio_para_contato
from contatos.views.campos import (
    _campos_com_valores,
    _campos_do_tenant,
    _salvar_valores_campos,
    _validar_valores_campos,
    _valores_para_ficha,
)
from contatos.views.helpers import (
    CAMPOS_FORA_DO_LOOP,
    _brl,
    _decorar,
    _decorar_nota,
    _iniciais,
    _tags_marcadas,
    _tenant_id,
)
from contatos.views.notas_tags import _aplicar_nova_tag
from emails.models import ModeloEmail
from recepcao.models import etapa_map_do_tenant
from tarefas.models import PRIORIDADE_CORES

# ---- Helpers de lista() ----

def _limpar_texto(texto):
    """Remove caracteres de encoding quebrado (U+FFFD) e espacos extras."""
    return (texto or '').replace('\ufffd', '').strip()


def _parse_filtros_lista(request):
    """Extrai e normaliza todos os filtros GET da listagem de membros."""
    termo = request.GET.get('q', '').strip()
    situacao = request.GET.get('situacao', '').strip().upper()
    if situacao not in ('ATIVO', 'INATIVO'):
        situacao = ''
    prefeitura_id = request.GET.get('prefeitura', '').strip()
    loja_id = request.GET.get('loja', '').strip()
    corpos = request.GET.getlist('corpo')
    uf = request.GET.get('uf', '').strip().upper()
    cidade = _limpar_texto(request.GET.get('cidade'))
    anuidade = request.GET.get('anuidade', '').strip()
    if anuidade not in ('em_dia', 'atrasada', 'nunca'):
        anuidade = ''

    filtros_ativos = bool(
        termo or situacao or prefeitura_id or loja_id or corpos
        or uf or cidade or anuidade
    )

    qs_base = request.GET.copy()
    qs_base.pop('page', None)

    return {
        'termo': termo, 'situacao': situacao, 'prefeitura_id': prefeitura_id,
        'loja_id': loja_id, 'corpos': corpos, 'uf': uf, 'cidade': cidade,
        'anuidade': anuidade, 'filtros_ativos': filtros_ativos,
        'qs': qs_base.urlencode(),
    }


def _categoria_anuidade(ultima_anuidade, ano_corrente, em_q1):
    """Classifica a anuidade do membro em 'em_dia', 'atrasada' ou 'nunca'."""
    if ultima_anuidade is None:
        return 'nunca'
    if ultima_anuidade >= ano_corrente:
        return 'em_dia'
    return 'atrasada'


def _cor_anuidade(ultima_anuidade, ano_corrente, em_q1):
    """Retorna (cor, label) para exibicao do chip de anuidade."""
    if ultima_anuidade is None:
        return 'red', 'Nao'
    if ultima_anuidade >= ano_corrente:
        return 'green', str(ultima_anuidade)
    if ultima_anuidade == ano_corrente - 1 and em_q1:
        return 'orange', str(ultima_anuidade)
    return 'red', str(ultima_anuidade)


def _formatar_membro_lista(row, ano_corrente, em_q1):
    """Converte uma tupla do repository em dict para o template."""
    ultima = row[13]
    cor, label = _cor_anuidade(ultima, ano_corrente, em_q1)
    return {
        'id': row[0], 'nome': row[1] or '', 'email': row[2] or '',
        'celular': row[3] or '', 'cpf': row[4] or '',
        'cidade': row[5] or '', 'uf': row[6] or '',
        'situacao': row[7] or '',
        'ativo': (row[7] or '') == 'ATIVO',
        'lojas': row[14] or [],
        'presencas_ano': row[15] or 0,
        'nascimento': row[16],
        'criado_em': row[12],
        'anuidade': label, 'anuidade_cor': cor,
    }


@web_login_required
def lista(request):
    """Lista de membros do banco local — busca + filtros acumulativos.

    Papéis: admin_saas enxerga todos os tenants (identidade global, sem
    seleção de cabeçalho); ADM e demais papéis ficam escopados ao tenant da
    conta e exigem Vale ativa.
    """
    from django.db.models import F, Q

    from acesso.models import ROLE_ADMIN_SAAS

    hoje = date.today()
    ano_corrente = hoje.year
    em_q1 = hoje.month <= 3

    filtros = _parse_filtros_lista(request)

    usuario = getattr(request, 'usuario_logado', None)
    snapshot = request.session.get('usuario', {})
    role = getattr(usuario, 'role', None) or (
        snapshot.get('role') if isinstance(snapshot, dict) else None
    )
    if role == ROLE_ADMIN_SAAS:
        tenant_ids = None
    else:
        tid = tenant_id_da_sessao(request)
        vale_ativo = (
            Vale.objects.filter(tenant_id=tid, status='ATIVA').first()
            if tid else None
        )
        if vale_ativo is None:
            return HttpResponseForbidden(
                'Selecione um tenant ativo com Vale para consultar membros.',
            )
        tenant_ids = [tid]

    qs = Membro.objects.order_by('nome', 'id')
    if tenant_ids is not None:
        qs = qs.filter(tenant_id__in=tenant_ids)
    if filtros['termo']:
        termo = filtros['termo']
        qs = qs.filter(
            Q(nome__icontains=termo) | Q(email__icontains=termo)
            | Q(cpf__icontains=termo) | Q(celular__icontains=termo),
        )
    if filtros['situacao']:
        qs = qs.filter(situacao=filtros['situacao'])
    if filtros['prefeitura_id']:
        try:
            vale = Vale.objects.get(pk=int(filtros['prefeitura_id']))
        except (Vale.DoesNotExist, TypeError, ValueError):
            vale = None
        qs = qs.filter(tenant_id=vale.tenant_id) if vale else qs.none()
    loja_pk = None
    if filtros['loja_id']:
        try:
            loja_pk = int(filtros['loja_id'])
        except (TypeError, ValueError):
            qs = qs.none()
    corpos = filtros['corpos']
    if any(corpo not in dict(Loja.CORPO_CHOICES) for corpo in corpos):
        qs = qs.none()
    elif corpos:
        filtros_loja = {
            'lojas__corpo__in': corpos,
            'lojas__tenant_id': F('tenant_id'),
        }
        if loja_pk is not None:
            filtros_loja['lojas__pk'] = loja_pk
        qs = qs.filter(**filtros_loja).distinct()
    elif loja_pk is not None:
        qs = qs.filter(lojas__id=loja_pk).distinct()
    if filtros['uf']:
        qs = qs.filter(uf=filtros['uf'])
    if filtros['cidade']:
        qs = qs.filter(cidade=filtros['cidade'])
    if filtros['anuidade'] in ('em_dia', 'atrasada'):
        # O banco local não registra pagamentos: só 'nunca' tem resultado.
        qs = qs.none()

    total = qs.count()
    page_num = request.GET.get('page', 1)
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(page_num)
    # Percentual de presença em lote (uma consulta para a página inteira).
    from tarefas.presencas import PresencaServico
    percentuais_presenca = PresencaServico.percentuais(list(page_obj.object_list))
    membros = [
        _formatar_membro_local(membro, ano_corrente, em_q1, percentuais_presenca)
        for membro in page_obj.object_list.prefetch_related(
            'lojas__tenant', 'graus__grau',
        )
    ]

    base_opcoes = Membro.objects
    if tenant_ids is not None:
        base_opcoes = base_opcoes.filter(tenant_id__in=tenant_ids)
    vales_opcoes = Vale.objects.filter(status='ATIVA')
    if tenant_ids is not None:
        vales_opcoes = vales_opcoes.filter(tenant_id__in=tenant_ids)
    lojas_opcoes = Loja.objects
    if tenant_ids is not None:
        lojas_opcoes = lojas_opcoes.filter(tenant_id__in=tenant_ids)

    return render(request, 'contatos/lista.html', {
        'itens': membros, 'q': filtros['termo'],
        'page_obj': page_obj, 'paginator': paginator,
        'mostrados': len(membros), 'total': total, 'eh_membros': True,
        'situacao': filtros['situacao'], 'prefeitura': filtros['prefeitura_id'],
        'loja': filtros['loja_id'], 'uf': filtros['uf'],
        'cidade': filtros['cidade'],
        'anuidade': filtros['anuidade'], 'filtros_ativos': filtros['filtros_ativos'],
        'corpos_filtro': [
            {
                'valor': valor,
                'rotulo': rotulo,
                'selecionado': valor in corpos,
            }
            for valor, rotulo in Loja.CORPO_CHOICES
        ],
        'opcoes_prefeituras': [
            {'id': str(v.pk), 'nome': v.nome} for v in vales_opcoes.order_by('nome', 'id')
        ],
        'opcoes_lojas': [
            {'id': str(l.pk), 'nome': l.nome} for l in lojas_opcoes.order_by('nome', 'id')
        ],
        'opcoes_ufs': list(
            base_opcoes.exclude(uf='').order_by('uf').values_list('uf', flat=True).distinct()
        ),
        'opcoes_cidades': list(
            base_opcoes.exclude(cidade='').order_by('cidade').values_list('cidade', flat=True).distinct()
        ),
        'qs': filtros['qs'],
    })


def _formatar_membro_local(membro, ano_corrente, em_q1, percentuais_presenca):
    """Converte um Membro local em dict para o template da lista."""
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
    # Grau mais alto conquistado (historico de graus), se houver.
    grau_atual = (
        membro.graus.select_related('grau').order_by('-grau__numero').first()
    )
    loja_principal = next(iter(lojas), {}).get('loja', '')
    return {
        'id': membro.pk, 'nome': membro.nome or '', 'email': membro.email or '',
        'celular': membro.celular or '', 'cpf': membro.cpf or '',
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


def _serializar_negocios(contato, stage_map):
    """Serializa negocios do contato para o template."""
    return [
        {
            'id': n.id,
            'titulo': n.titulo,
            'stage': stage_map.get(n.stage, {'name': n.stage, 'color': '#888'}),
            'valor': _brl(n.valor),
            'principal': n.principal,
            'created_at': n.created_at,
            'qtd_movs': len(n.movimentacoes.all()),
        }
        for n in contato.negocios.all()
    ]


def _serializar_movimentacoes(contato, stage_map):
    """Serializa movimentacoes do contato para o template."""
    return [
        {
            'de': stage_map.get(m.de_stage, {'name': m.de_stage, 'color': '#888'}) if m.de_stage else None,
            'para': stage_map.get(m.para_stage, {'name': m.para_stage, 'color': '#888'}),
            'negocio_titulo': m.negocio.titulo or contato.nome,
            'autor': m.autor.nome if m.autor else '—',
            'autor_iniciais': _iniciais(m.autor.nome if m.autor else ''),
            'created_at': m.created_at,
        }
        for m in (Movimentacao.objects.filter(negocio__contato=contato)
                  .select_related('negocio', 'autor')
                  .order_by('-created_at', '-id'))
    ]


def _serializar_tarefas(contato):
    """Serializa tarefas do contato para o template."""
    return [
        {
            'id': t.id,
            'titulo': t.titulo,
            'prioridade': t.prioridade,
            'prioridade_cor': PRIORIDADE_CORES.get(t.prioridade, '#94a3b8'),
            'vencimento': t.vencimento,
            'atrasada': t.atrasada,
            'concluida': t.concluida,
            'concluida_em': t.concluida_em,
            'responsavel_nome': t.responsavel.nome if t.responsavel else '',
            'responsavel_iniciais': _iniciais(t.responsavel.nome if t.responsavel else ''),
        }
        for t in contato.tarefas.select_related('responsavel').order_by('concluida', 'vencimento', 'hora', 'id')
    ]


@web_login_required
def detalhe(request, pk):
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho_da_sessao(request))
    contato = get_object_or_404(
        filtro_tenant(request, Contato.objects.all())
        .select_related('carteira')
        .prefetch_related('negocios__movimentacoes', 'negocios', 'tags'),
        pk=pk,
    )

    return render(request, 'contatos/detalhe.html', {
        'contato': _decorar(contato, stage_map),
        'notas': [_decorar_nota(n) for n in contato.notas.select_related('autor').all()],
        'negocios': _serializar_negocios(contato, stage_map),
        'tarefas': _serializar_tarefas(contato),
        'movimentacoes': _serializar_movimentacoes(contato, stage_map),
        'nota_form': NotaForm(),
        'campos_valores': _valores_para_ficha(contato),
        'modelos_email': [{'id': m.id, 'nome': m.nome} for m in filtro_tenant(request, ModeloEmail.objects.all())],
        'email_configurado': settings.EMAIL_CONFIGURADO,
    })


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def novo(request):
    nicho = nicho_da_sessao(request)
    campos = _campos_do_tenant(request)
    erros_campos = {}
    if request.method == 'POST':
        form = ContatoForm(request.POST, nicho=nicho, tenant_id=_tenant_id(request))
        erros_campos = _validar_valores_campos(request, campos)
        if form.is_valid() and not erros_campos:
            contato = form.save(commit=False)
            tid = _tenant_id(request)
            if tid is not None:
                contato.tenant_id = tid
            contato.save()
            form.save_m2m()
            _aplicar_nova_tag(request, contato)
            _salvar_valores_campos(request, contato, campos)
            criar_negocio_para_contato(
                contato,
                stage=form.cleaned_data['stage'],
                valor=form.cleaned_data['valor'] or 0,
                tenant_id=tid,
                usuario_id=request.session.get('usuario_id'),
            )
            return redirect('contatos:detalhe', pk=contato.id)
    else:
        form = ContatoForm(nicho=nicho, tenant_id=_tenant_id(request))
    return render(request, 'contatos/formulario.html', {
        'form': form, 'titulo': 'Novo contato', 'editando': False,
        'tags_marcadas': _tags_marcadas(form),
        'campos_fora_do_loop': CAMPOS_FORA_DO_LOOP,
        'campos_personalizados': _campos_com_valores(request, campos, None, erros_campos),
    })


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def editar(request, pk):
    nicho = nicho_da_sessao(request)
    contato = get_object_or_404(
        filtro_tenant(request, Contato.objects.all()).prefetch_related('tags'), pk=pk
    )
    campos = _campos_do_tenant(request)
    erros_campos = {}
    if request.method == 'POST':
        form = ContatoForm(request.POST, instance=contato, nicho=nicho, tenant_id=_tenant_id(request))
        erros_campos = _validar_valores_campos(request, campos)
        if form.is_valid() and not erros_campos:
            negocio = getattr(contato, 'negocio', None)
            contato.save()
            form.save_m2m()
            _aplicar_nova_tag(request, contato)
            _salvar_valores_campos(request, contato, campos)
            tid = _tenant_id(request)
            if tid is not None:
                contato.tenant_id = tid
                contato.save()
            negocio = getattr(contato, 'negocio', None)
            if negocio and tid is not None:
                atualizar_negocio_do_contato(
                    contato, negocio,
                    stage=form.cleaned_data['stage'],
                    valor=form.cleaned_data['valor'] or 0,
                    tenant_id=tid,
                    usuario_id=request.session.get('usuario_id'),
                    stage_antigo=negocio.stage,
                )
            elif not negocio and tid is not None:
                criar_negocio_para_contato(
                    contato,
                    stage=form.cleaned_data['stage'],
                    valor=form.cleaned_data['valor'] or 0,
                    tenant_id=tid,
                    usuario_id=request.session.get('usuario_id'),
                )
            return redirect('contatos:detalhe', pk=contato.id)
    else:
        form = ContatoForm(instance=contato, nicho=nicho, tenant_id=_tenant_id(request))
    return render(request, 'contatos/formulario.html', {
        'form': form, 'titulo': 'Editar contato', 'editando': True, 'contato': contato,
        'tags_marcadas': _tags_marcadas(form),
        'campos_fora_do_loop': CAMPOS_FORA_DO_LOOP,
        'campos_personalizados': _campos_com_valores(request, campos, contato, erros_campos),
    })

@web_login_required
@web_requer_tenant_context
def excluir(request, pk):
    """Excluir contato — apenas admin (operacional nao pode remover)."""
    if not e_admin_do_tenant(request):
        return redirect('contatos:lista')
    if request.method == 'POST':
        get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk).delete()
        return redirect('contatos:lista')
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho_da_sessao(request))
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    return render(request, 'contatos/excluir.html', {'contato': _decorar(contato, stage_map)})


@web_login_required
def leads_pobres(request):
    """Perfil dos leads (rico x pobre) — quem o time deve enriquecer.

    Agrupa os contatos por nivel de completude (pobre / medio / rico) com a
    aba `?nivel=`. Cada card mostra o que falta no perfil e atalho para
    completar a ficha ja com foco no primeiro campo ausente (`?focar=`).
    """
    tid = _tenant_id(request)
    nicho = nicho_da_sessao(request)
    stage_map = etapa_map_do_tenant(tid, nicho)
    contatos = (
        filtro_tenant(request, Contato.objects.all())
        .select_related('carteira')
        .prefetch_related('negocios', 'tags')
    )
    agrupados = {'pobre': [], 'medio': [], 'rico': []}
    for c in contatos:
        comp = completude_do_contato(c)
        negocio = getattr(c, 'negocio', None)
        agrupados[comp['nivel']].append({
            'id': c.id,
            'nome': c.nome,
            'tel': c.tel,
            'email': c.email,
            'empresa': c.empresa,
            'origem': c.origem,
            'created_at': c.created_at,
            'stage': stage_map.get(negocio.stage if negocio else '', {'name': '—', 'color': '#888'}),
            'valor': _brl(negocio.valor) if negocio else 'R$ 0,00',
            'completude': comp,
        })
    for lista in agrupados.values():
        lista.sort(key=lambda i: i['completude']['total'])
    nivel = request.GET.get('nivel', 'pobre')
    if nivel not in agrupados:
        nivel = 'pobre'
    tabs = {
        'pobre': {'rotulo': 'Pobre', 'cor': '#fb923c'},
        'medio': {'rotulo': 'Medio', 'cor': '#fbbf24'},
        'rico': {'rotulo': 'Completo', 'cor': '#7fe3c4'},
    }
    return render(request, 'contatos/leads_pobres.html', {
        'itens': agrupados[nivel],
        'total': len(agrupados[nivel]),
        'nivel': nivel,
        'nivel_opcoes': [
            {'chave': k, 'rotulo': tabs[k]['rotulo'], 'cor': tabs[k]['cor'],
             'qtd': len(agrupados[k])}
            for k in ('pobre', 'medio', 'rico')
        ],
        'cor_nivel': tabs[nivel]['cor'],
        'rotulo_nivel': tabs[nivel]['rotulo'],
    })
