"""Views de CRUD de contatos — listar, detalhe, novo, editar, excluir e leads pobres.

As views de GPRB (prefeituras, lojas, membros) foram extraidas para:
- gprb_prefeituras.py
- gprb_lojas.py
- gprb_membros.py
todas usando o repository em repositories/gprb_repository.py
"""

from datetime import date

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from acesso.decorators import (
    e_admin_do_tenant,
    filtro_tenant,
    nicho_da_sessao,
    web_login_required,
    web_requer_edicao,
)
from contatos.forms import ContatoForm, NotaForm
from contatos.models import Contato, Movimentacao
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
from repositories import gprb_repository as repo
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
    uf = request.GET.get('uf', '').strip().upper()
    cidade = _limpar_texto(request.GET.get('cidade'))
    anuidade = request.GET.get('anuidade', '').strip()
    if anuidade not in ('em_dia', 'atrasada', 'nunca'):
        anuidade = ''

    filtros_ativos = bool(termo or situacao or prefeitura_id or loja_id
                          or uf or cidade or anuidade)

    qs_base = request.GET.copy()
    qs_base.pop('page', None)

    return {
        'termo': termo, 'situacao': situacao, 'prefeitura_id': prefeitura_id,
        'loja_id': loja_id, 'uf': uf, 'cidade': cidade,
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
        'lojas': row[14] or [],
        'nascimento': row[15],
        'criado_em': row[12],
        'anuidade': label, 'anuidade_cor': cor,
    }


@web_login_required
def lista(request):
    """Lista de membros do banco GPRB — busca + filtros acumulativos."""
    hoje = date.today()
    ano_corrente = hoje.year
    em_q1 = hoje.month <= 3

    filtros = _parse_filtros_lista(request)

    opcoes = repo.listar_membros_filtros()
    todos = repo.listar_membros({
        'termo': filtros['termo'], 'situacao': filtros['situacao'],
        'prefeitura_id': filtros['prefeitura_id'], 'loja_id': filtros['loja_id'],
        'uf': filtros['uf'], 'cidade': filtros['cidade'],
    })

    if filtros['anuidade']:
        todos = [r for r in todos
                 if _categoria_anuidade(r[13], ano_corrente, em_q1) == filtros['anuidade']]

    total = len(todos)
    page_num = request.GET.get('page', 1)
    paginator = Paginator(todos, 25)
    page_obj = paginator.get_page(page_num)
    membros = [_formatar_membro_lista(row, ano_corrente, em_q1) for row in page_obj]

    return render(request, 'contatos/lista.html', {
        'itens': membros, 'q': filtros['termo'],
        'page_obj': page_obj, 'paginator': paginator,
        'mostrados': len(membros), 'total': total, 'eh_membros': True,
        'situacao': filtros['situacao'], 'prefeitura': filtros['prefeitura_id'],
        'loja': filtros['loja_id'], 'uf': filtros['uf'],
        'cidade': filtros['cidade'],
        'anuidade': filtros['anuidade'], 'filtros_ativos': filtros['filtros_ativos'],
        'opcoes_prefeituras': opcoes['prefeituras'],
        'opcoes_lojas': opcoes['lojas'], 'opcoes_ufs': opcoes['ufs'],
        'opcoes_cidades': opcoes['cidades'],
        'qs': filtros['qs'],
    })


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
