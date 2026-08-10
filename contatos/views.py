"""Views web de contatos — listar, detalhe, criar, editar, excluir, notas, tags, negocios, importacao e campos personalizados (escopadas por tenant)."""

import csv
import re
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from acesso.decorators import (
    e_admin_do_tenant,
    filtro_tenant,
    nicho_da_sessao,
    web_login_required,
    web_requer_admin,
    web_requer_edicao,
)
from acesso.models import Tenant
from automacoes.engine import disparar
from contatos.forms import CampoForm, ContatoForm, NotaForm
from contatos.importador import (
    CAMPOS_IMPORTAVEIS,
    LIMITE_TAMANHO,
    importar_linhas,
    normalizar_data,
    parse_csv,
    sugerir_mapeamento,
)
from contatos.models import (
    CampoPersonalizado,
    Carteira,
    Contato,
    Movimentacao,
    Negocio,
    Tag,
    ValorCampoPersonalizado,
    criar_negocio,
    registrar_movimentacao,
    so_digitos,
    tornar_principal,
)
from contatos.scoring import NIVEIS, atualizar_score, completude_do_contato, nivel_do_score
from core.dominio import SEG_FALLBACK, SEGS
from funil.models import etapa_map_do_tenant, etapas_do_tenant

CORES_TAG = ['#74b3c6', '#7fe3c4', '#fbbf24', '#c084fc', '#fb923c', '#60a5fa', '#4ade80', '#f472b6']

# Campos renderizados fora do loop do formulario (secao empresa e tags)
CAMPOS_FORA_DO_LOOP = ['tags', 'nova_tag', 'cnpj', 'razao_social', 'cnae', 'endereco', 'responsavel']


def _brl(n):
    return 'R$ {:,.2f}'.format(float(n)).replace(',', 'X').replace('.', ',').replace('X', '.')


def _iniciais(nome):
    partes = [p for p in (nome or '').split() if p]
    if not partes:
        return '?'
    return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else '')).upper()


def _tenant_id(request):
    return request.session.get('usuario', {}).get('tenant_id')


def _tags_do_tenant(request):
    tid = _tenant_id(request)
    if tid is None:
        return Tag.objects.all()
    return Tag.objects.filter(tenant_id=tid)


def _membros_do_tenant(request):
    """Membros (vendedores) do tenant da sessão para o select de responsável."""
    tid = _tenant_id(request)
    if tid is None:
        return []
    from acesso.models import ROLES_DE_TENANT, Usuario

    return [
        {'id': u.id, 'nome': u.nome}
        for u in Usuario.objects.filter(tenant_id=tid, role__in=ROLES_DE_TENANT).order_by('nome')
    ]


def _responsavel_do_post(request):
    """Id do responsável (vendedor) do formulário, validado no tenant da sessão."""
    tid = _tenant_id(request)
    raw = request.POST.get('responsavel', '')
    if not raw.isdigit() or tid is None:
        return None
    from acesso.models import Usuario

    return Usuario.objects.filter(tenant_id=tid, pk=raw).values_list('id', flat=True).first()


def _campos_do_tenant(request):
    """Campos personalizados ativos do tenant da sessao (admin_saas ve todos)."""
    tid = _tenant_id(request)
    qs = CampoPersonalizado.objects.filter(ativo=True)
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return list(qs)


def _campos_scope(tid):
    """Queryset de campos personalizados escopado ao tenant (admin_saas ve todos)."""
    qs = CampoPersonalizado.objects.all()
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return qs


def _erros_do_form(form):
    return [msg for campo_erros in form.errors.values() for msg in campo_erros]


def _nome_ja_existe(tid, nome, excluir_pk=None):
    qs = _campos_scope(tid).filter(nome=nome)
    if excluir_pk is not None:
        qs = qs.exclude(pk=excluir_pk)
    return qs.exists()


def _campos_com_valores(request, campos, contato=None, erros=None):
    """Campos prontos para o template do formulario, com valor atual e erro (se houver)."""
    erros = erros or {}
    valores = {}
    if request.method != 'POST' and contato is not None:
        valores = {v.campo_id: v.valor for v in contato.valores_campos.all()}
    itens = []
    for c in campos:
        if request.method == 'POST':
            valor = request.POST.get(f'campo_{c.id}', '')
        else:
            valor = valores.get(c.id, '')
        itens.append({
            'id': c.id,
            'nome': c.nome,
            'tipo': c.tipo,
            'obrigatorio': c.obrigatorio,
            'opcoes': [o.strip() for o in c.opcoes.split(',') if o.strip()],
            'valor': valor,
            'erro': erros.get(c.id, ''),
        })
    return itens


def _validar_valores_campos(request, campos):
    """Valida campos obrigatorios e tipos numerico/data; devolve {campo_id: mensagem}."""
    erros = {}
    for c in campos:
        valor = (request.POST.get(f'campo_{c.id}', '') or '').strip()
        if c.obrigatorio and not valor:
            erros[c.id] = 'Campo obrigatório.'
            continue
        if not valor:
            continue
        if c.tipo == 'numero':
            try:
                float(valor.replace(',', '.'))
            except ValueError:
                erros[c.id] = 'Informe um número válido.'
        elif c.tipo == 'data' and normalizar_data(valor) is None:
            erros[c.id] = 'Informe uma data válida (dd/mm/aaaa).'
    return erros


def _salvar_valores_campos(request, contato, campos):
    """Grava (ou remove) os valores dos campos personalizados do contato."""
    for c in campos:
        valor = (request.POST.get(f'campo_{c.id}', '') or '').strip()
        if c.tipo == 'data':
            m = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', valor)
            if m:
                valor = f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'
        if valor:
            ValorCampoPersonalizado.objects.update_or_create(
                contato=contato, campo=c, defaults={'valor': valor},
            )
        else:
            contato.valores_campos.filter(campo=c).delete()


def _formata_valor_campo(tipo, valor):
    """Formatacao de exibicao na ficha (sim/nao e datas ISO)."""
    if tipo == 'sim_nao':
        return 'Sim' if valor == 'sim' else 'Não'
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', valor) if tipo == 'data' else None
    if m:
        return f'{m.group(3)}/{m.group(2)}/{m.group(1)}'
    return valor


def _valores_para_ficha(contato):
    """Valores preenchidos do contato, ordenados pela ordem do campo."""
    itens = []
    for v in contato.valores_campos.select_related('campo').order_by('campo__ordem', 'campo__id'):
        if v.valor:
            itens.append({'nome': v.campo.nome, 'valor': _formata_valor_campo(v.campo.tipo, v.valor)})
    return itens


def _coluna_post(request, campo):
    """Indice de coluna escolhido no mapeamento (ou -1 quando vazio)."""
    raw = request.POST.get(f'col_{campo}', '')
    return int(raw) if raw.isdigit() else -1


def _tags_marcadas(form):
    """Ids das tags selecionadas (como strings) para renderizar os checkboxes do formulario."""
    if form.is_bound:
        return [str(i) for i in form.data.getlist('tags')]
    return [str(i) for i in (form.initial.get('tags') or [])]


def _decorar(c, stage_map):
    negocio = getattr(c, 'negocio', None)
    stage = negocio.stage if negocio else ''
    valor = negocio.valor if negocio else 0
    nivel = nivel_do_score(c.lead_score)
    return {
        'id': c.id,
        'nome': c.nome,
        'empresa': c.empresa,
        'tel': c.tel,
        'email': c.email,
        'valor': _brl(valor),
        'seg': SEGS.get(c.seg, SEG_FALLBACK),
        'stage': stage_map.get(stage, {'name': stage, 'color': '#888'}),
        'procedimento': c.procedimento,
        'ultima_consulta': c.ultima_consulta,
        'origem': c.origem,
        'pagamento': c.pagamento,
        'nascimento': c.nascimento,
        'cpf': c.cpf,
        'cidade': c.cidade,
        'bairro': c.bairro,
        'observacoes': c.observacoes,
        'cnpj': c.cnpj,
        'razao_social': c.razao_social,
        'cnae': c.cnae,
        'endereco': c.endereco,
        'responsavel': c.responsavel,
        'cargo': c.cargo,
        'carteira': {'id': c.carteira_id, 'nome': c.carteira.nome} if c.carteira_id else None,
        'score': c.lead_score,
        'score_nivel': nivel,
        'score_label': NIVEIS[nivel]['label'],
        'score_cor': NIVEIS[nivel]['cor'],
        'completude': completude_do_contato(c),
        'tags': [{'id': t.id, 'nome': t.nome, 'cor': t.cor} for t in c.tags.all()],
    }


def _decorar_nota(n):
    autor = n.autor
    return {
        'id': n.id,
        'texto': n.texto,
        'created_at': n.created_at,
        'autor': autor.nome if autor else '—',
        'autor_iniciais': _iniciais(autor.nome if autor else ''),
    }


@web_login_required
def lista(request):
    nicho = nicho_da_sessao(request)
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho)
    contatos = (
        filtro_tenant(request, Contato.objects.all())
        .select_related('carteira')
        .prefetch_related('negocios', 'tags')
    )
    termo = request.GET.get('q', '').strip()
    if termo:
        contatos = contatos.filter(nome__icontains=termo) | contatos.filter(empresa__icontains=termo)
    tag_id = request.GET.get('tag', '')
    tag_ativa = int(tag_id) if tag_id.isdigit() else None
    if tag_ativa is not None:
        contatos = contatos.filter(tags__id=tag_ativa)
    carteira_id = request.GET.get('carteira', '')
    carteira_ativa = int(carteira_id) if carteira_id.isdigit() else None
    if carteira_ativa is not None:
        contatos = contatos.filter(carteira_id=carteira_ativa)
    # Ordenação por prioridade (lead score) ou padrão (id)
    ordem = request.GET.get('ord', '')
    if ordem == 'score':
        contatos = contatos.order_by('-lead_score', 'id')
    items = [_decorar(c, stage_map) for c in contatos]
    tid = _tenant_id(request)
    carteiras = (
        Carteira.objects.all()
        if tid is None else Carteira.objects.filter(tenant_id=tid)
    )
    # Contatos com perfil básico — contagem global (não depende dos filtros ativos)
    base_pobres = filtro_tenant(request, Contato.objects.all()).prefetch_related('negocios', 'tags')
    pobres = sum(1 for c in base_pobres if completude_do_contato(c)['nivel'] == 'pobre')
    return render(request, 'contatos/lista.html', {
        'itens': items,
        'q': termo,
        'ord': ordem,
        'tag_ativa': tag_ativa,
        'carteira_ativa': carteira_ativa,
        'tags_filtro': [{'id': t.id, 'nome': t.nome, 'cor': t.cor} for t in _tags_do_tenant(request)],
        'carteiras_filtro': [{'id': c.id, 'nome': c.nome} for c in carteiras],
        'mostrados': len(items),
        'total': filtro_tenant(request, Contato.objects.all()).count(),
        'pobres': pobres,
    })


@web_login_required
def detalhe(request, pk):
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho_da_sessao(request))
    contato = get_object_or_404(
        filtro_tenant(request, Contato.objects.all())
        .select_related('carteira')
        .prefetch_related('negocios__movimentacoes', 'negocios', 'tags'),
        pk=pk,
    )
    notas = [_decorar_nota(n) for n in contato.notas.select_related('autor').all()]
    negocios = [
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
    movimentacoes = [
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
    from emails.models import ModeloEmail
    from tarefas.models import PRIORIDADE_CORES

    tarefas = [
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

    return render(request, 'contatos/detalhe.html', {
        'contato': _decorar(contato, stage_map),
        'notas': notas,
        'negocios': negocios,
        'tarefas': tarefas,
        'movimentacoes': movimentacoes,
        'nota_form': NotaForm(),
        'campos_valores': _valores_para_ficha(contato),
        'modelos_email': [{'id': m.id, 'nome': m.nome} for m in filtro_tenant(request, ModeloEmail.objects.all())],
        'email_configurado': settings.EMAIL_CONFIGURADO,
    })


def _criar_e_anexar_tag(request, contato, nome):
    """Cria (se preciso) a tag do tenant da sessao e vincula ao contato."""
    nome = (nome or '').strip()
    if not nome:
        return
    tag, _ = Tag.objects.get_or_create(
        nome=nome[:40], tenant_id=_tenant_id(request), defaults={'cor': CORES_TAG[0]}
    )
    contato.tags.add(tag)


def _aplicar_nova_tag(request, contato):
    """Cria a tag digitada no formulario (campo nova_tag) e vincula ao contato."""
    _criar_e_anexar_tag(request, contato, request.POST.get('nova_tag', ''))


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
            negocio = criar_negocio(
                contato,
                stage=form.cleaned_data['stage'],
                valor=form.cleaned_data['valor'] or 0,
                tenant_id=tid,
            )
            registrar_movimentacao(negocio, '', negocio.stage, request.session.get('usuario_id'))
            # novo contato fica sob responsabilidade de quem cadastrou (metas por vendedor)
            if tid is not None:
                negocio.responsavel_id = request.session.get('usuario_id')
                negocio.save(update_fields=['responsavel'])
            disparar('contato_criado', tenant_id=tid, contato=contato, negocio=negocio)
            disparar('negocio_criado', tenant_id=tid, contato=contato, negocio=negocio)
            atualizar_score(contato)
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
            negocio_era_novo = negocio is None
            stage_antigo = negocio.stage if negocio else ''
            contato = form.save(commit=False)
            contato.save()
            form.save_m2m()
            _aplicar_nova_tag(request, contato)
            _salvar_valores_campos(request, contato, campos)
            tid = _tenant_id(request)
            if negocio is None:
                negocio = criar_negocio(contato, tenant_id=tid)
            negocio.stage = form.cleaned_data['stage']
            negocio.valor = form.cleaned_data['valor'] or 0
            negocio.titulo = contato.nome
            negocio.save()
            registrar_movimentacao(
                negocio, stage_antigo, negocio.stage, request.session.get('usuario_id')
            )
            if negocio_era_novo:
                disparar('negocio_criado', tenant_id=tid, contato=contato, negocio=negocio)
            elif stage_antigo != negocio.stage:
                disparar(
                    'negocio_movido',
                    tenant_id=tid,
                    contato=contato,
                    negocio=negocio,
                    de_etapa=stage_antigo,
                    para_etapa=negocio.stage,
                )
            if negocio.stage == 'fechado':
                from emails.servico import marcar_conversoes

                marcar_conversoes(contato)
            atualizar_score(contato)
            return redirect('contatos:detalhe', pk=contato.id)
    else:
        form = ContatoForm(instance=contato, nicho=nicho, tenant_id=_tenant_id(request))
    return render(request, 'contatos/formulario.html', {
        'form': form, 'titulo': 'Editar contato', 'editando': True, 'contato': contato,
        'tags_marcadas': _tags_marcadas(form),
        'campos_fora_do_loop': CAMPOS_FORA_DO_LOOP,
        'campos_personalizados': _campos_com_valores(request, campos, contato, erros_campos),
    })


def _valor_do_post(request, negocio=None):
    """Lê e valida o valor (R$) vindo do formulário de negócio; devolve (Decimal, erro)."""
    raw = (request.POST.get('valor', '') or '').strip()
    if not raw:
        return Decimal('0'), None
    try:
        v = Decimal(raw.replace('.', '').replace(',', '.')) if ',' in raw else Decimal(raw.replace(',', '.'))
    except Exception:
        return (negocio.valor if negocio else Decimal('0')), 'Informe um valor válido (ex.: 1.500,00).'
    if v < 0:
        return (negocio.valor if negocio else Decimal('0')), 'O valor não pode ser negativo.'
    return v, None


@web_login_required
@web_requer_edicao
def negocio_novo(request, pk):
    """Cria um novo negócio (deal) para o contato — não vira o principal."""
    nicho = nicho_da_sessao(request)
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho)
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    erros = []
    if request.method == 'POST':
        stage = request.POST.get('stage', '')
        valor, erro_valor = _valor_do_post(request)
        if erro_valor:
            erros.append(erro_valor)
        if stage not in stage_map:
            erros.append('Escolha uma etapa válida.')
        if not erros:
            negocio = criar_negocio(
                contato,
                titulo=(request.POST.get('titulo', '').strip() or contato.nome),
                stage=stage,
                valor=valor,
                tenant_id=_tenant_id(request),
                principal=None,  # a factory marca o primeiro como principal
            )
            negocio.responsavel_id = _responsavel_do_post(request)
            negocio.save(update_fields=['responsavel'])
            if request.POST.get('principal') == 'on':
                tornar_principal(negocio)
            registrar_movimentacao(negocio, '', stage, request.session.get('usuario_id'))
            disparar('negocio_criado', tenant_id=_tenant_id(request), contato=contato, negocio=negocio)
            if stage == 'fechado':
                from emails.servico import marcar_conversoes

                marcar_conversoes(contato)
            atualizar_score(contato)
            return redirect('contatos:detalhe', pk=contato.id)
    return render(request, 'contatos/negocio_form.html', {
        'contato': _decorar(contato, stage_map),
        'stages': etapas_do_tenant(_tenant_id(request), nicho),
        'vendedores': _membros_do_tenant(request),
        'titulo_form': 'Novo negócio',
        'negocio': None,
        'erros': erros,
        'valor': request.POST.get('valor', ''),
        'titulo_inicial': request.POST.get('titulo', ''),
        'principal_marcado': request.POST.get('principal') == 'on',
        'responsavel_id': request.POST.get('responsavel', ''),
    })


@web_login_required
@web_requer_edicao
def negocio_editar(request, pk, negocio_id):
    """Edita um negócio do contato (título, etapa, valor e principal)."""
    nicho = nicho_da_sessao(request)
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho)
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    negocio = get_object_or_404(contato.negocios.all(), pk=negocio_id)
    erros = []
    if request.method == 'POST':
        stage = request.POST.get('stage', '')
        valor, erro_valor = _valor_do_post(request, negocio)
        if erro_valor:
            erros.append(erro_valor)
        if stage not in stage_map:
            erros.append('Escolha uma etapa válida.')
        if not erros:
            stage_antigo = negocio.stage
            negocio.titulo = request.POST.get('titulo', '').strip() or contato.nome
            negocio.stage = stage
            negocio.valor = valor
            negocio.responsavel_id = _responsavel_do_post(request)
            negocio.save()
            if request.POST.get('principal') == 'on':
                tornar_principal(negocio)
            registrar_movimentacao(negocio, stage_antigo, stage, request.session.get('usuario_id'))
            if stage_antigo != stage:
                disparar(
                    'negocio_movido',
                    tenant_id=_tenant_id(request),
                    contato=contato,
                    negocio=negocio,
                    de_etapa=stage_antigo,
                    para_etapa=stage,
                )
            if stage == 'fechado':
                from emails.servico import marcar_conversoes

                marcar_conversoes(contato)
            atualizar_score(contato)
            return redirect('contatos:detalhe', pk=contato.id)
    return render(request, 'contatos/negocio_form.html', {
        'contato': _decorar(contato, stage_map),
        'stages': etapas_do_tenant(_tenant_id(request), nicho),
        'vendedores': _membros_do_tenant(request),
        'titulo_form': 'Editar negócio',
        'negocio': negocio,
        'erros': erros,
        'valor': request.POST.get('valor', str(negocio.valor).replace('.', ',')),
        'titulo_inicial': request.POST.get('titulo', negocio.titulo),
        'principal_marcado': negocio.principal or request.POST.get('principal') == 'on',
        'responsavel_id': request.POST.get('responsavel', negocio.responsavel_id or ''),
    })


@web_login_required
def negocio_tornar_principal(request, pk, negocio_id):
    """Marca um negócio como principal do contato (apenas admin)."""
    if not e_admin_do_tenant(request):
        return redirect('contatos:detalhe', pk=pk)
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    if request.method == 'POST':
        negocio = get_object_or_404(contato.negocios.all(), pk=negocio_id)
        tornar_principal(negocio)
    return redirect('contatos:detalhe', pk=pk)


@web_login_required
def negocio_excluir(request, pk, negocio_id):
    """Excluir negócio do contato — apenas admin."""
    if not e_admin_do_tenant(request):
        return redirect('contatos:detalhe', pk=pk)
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    if request.method == 'POST':
        contato.negocios.filter(pk=negocio_id).delete()
    return redirect('contatos:detalhe', pk=pk)


@web_login_required
def orcamento_pdf(request, pk, negocio_id):
    """Baixa o orçamento (proposta) do negócio em PDF — qualquer papel logado."""
    from contatos.orcamento import gerar_orcamento_pdf

    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    negocio = get_object_or_404(contato.negocios.all(), pk=negocio_id)
    tid = _tenant_id(request)
    tenant = Tenant.objects.filter(pk=tid).first() if tid is not None else None
    pdf = gerar_orcamento_pdf(tenant, contato, negocio)
    resposta = HttpResponse(pdf, content_type='application/pdf')
    resposta['Content-Disposition'] = (
        f'attachment; filename="orcamento-{contato.id}-{negocio.id}.pdf"'
    )
    return resposta


@web_login_required
def excluir(request, pk):
    """Excluir contato — apenas admin (operacional nao pode remover)."""
    if not e_admin_do_tenant(request):
        return redirect('contatos:lista')
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho_da_sessao(request))
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    if request.method == 'POST':
        contato.delete()
        return redirect('contatos:lista')
    return render(request, 'contatos/excluir.html', {'contato': _decorar(contato, stage_map)})


@web_login_required
def leads_pobres(request):
    """Perfil dos leads (rico x pobre) — quem o time deve enriquecer.

    Agrupa os contatos por nível de completude (pobre / médio / rico) com a
    aba `?nivel=`. Cada card mostra o que falta no perfil e atalho para
    completar a ficha já com foco no primeiro campo ausente (`?focar=`).
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
        'medio': {'rotulo': 'Médio', 'cor': '#fbbf24'},
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


@web_login_required
@web_requer_edicao
def importar(request):
    """Importacao de contatos via CSV — fluxo em 3 etapas: upload -> mapeamento -> relatorio."""
    nicho = nicho_da_sessao(request)
    tid = _tenant_id(request)
    cabecalhos = request.session.get('import_cabecalhos')
    linhas = request.session.get('import_linhas')
    tid = _tenant_id(request)
    carteiras = (
        Carteira.objects.all() if tid is None else Carteira.objects.filter(tenant_id=tid)
    ).order_by('nome')
    ctx = {
        'etapa': 'upload',
        'campos': CAMPOS_IMPORTAVEIS,
        'erro_upload': None,
        'avisos': [],
        'carteiras': [{'id': c.id, 'nome': c.nome} for c in carteiras],
    }

    if request.method == 'POST':
        etapa = request.POST.get('etapa', '')
        if etapa == 'upload':
            arquivo = request.FILES.get('arquivo')
            if not arquivo:
                ctx['erro_upload'] = 'Selecione um arquivo CSV para enviar.'
            elif arquivo.size > LIMITE_TAMANHO:
                ctx['erro_upload'] = 'Arquivo muito grande (máximo 5 MB).'
            else:
                tem_cab = request.POST.get('tem_cabecalho') == 'on'
                try:
                    cabecalhos, linhas = parse_csv(arquivo.read(), tem_cabecalho=tem_cab)
                except ValueError as exc:
                    ctx['erro_upload'] = str(exc)
                else:
                    request.session['import_cabecalhos'] = cabecalhos
                    request.session['import_linhas'] = linhas
                    request.session['import_nome_arquivo'] = arquivo.name
                    request.session['import_tem_cabecalho'] = tem_cab
                    ctx['etapa'] = 'mapear'
        elif etapa == 'importar':
            if not cabecalhos or not linhas:
                ctx['avisos'].append('Os dados do arquivo expiraram — envie o CSV novamente.')
            else:
                mapeamento = {campo: _coluna_post(request, campo) for campo, _ in CAMPOS_IMPORTAVEIS}
                if mapeamento.get('nome', -1) < 0:
                    ctx['etapa'] = 'mapear'
                    ctx['erro_mapeamento'] = 'O campo "Nome" é obrigatório — selecione a coluna que contém os nomes.'
                else:
                    tem_cab = request.session.get('import_tem_cabecalho', True)
                    raw_cart = request.POST.get('carteira_id', '')
                    carteira_id = int(raw_cart) if raw_cart.isdigit() else None
                    relatorio = importar_linhas(
                        cabecalhos, linhas, mapeamento, tid,
                        nicho=nicho,
                        etapas=etapas_do_tenant(tid, nicho),
                        pular_duplicadas=request.POST.get('pular_duplicadas') == 'sim',
                        inicio_linhas=2 if tem_cab else 1,
                        carteira_id=carteira_id,
                    )
                    for chave in ('import_cabecalhos', 'import_linhas', 'import_nome_arquivo', 'import_tem_cabecalho'):
                        request.session.pop(chave, None)
                    ctx['etapa'] = 'relatorio'
                    ctx['relatorio'] = relatorio
    elif cabecalhos and linhas:
        # GET com dados pendentes -> volta para o mapeamento
        ctx['etapa'] = 'mapear'

    if ctx['etapa'] == 'mapear':
        sugestoes = sugerir_mapeamento(cabecalhos)
        ctx.update({
            'cabecalhos': cabecalhos,
            'linhas_preview': linhas[:5],
            'nome_arquivo': request.session.get('import_nome_arquivo', 'arquivo.csv'),
            'total_linhas': len(linhas),
            'campos_mapeamento': [
                {'campo': c, 'rotulo': r, 'sugerido': sugestoes.get(c, -1)}
                for c, r in CAMPOS_IMPORTAVEIS
            ],
            'carteira_escolhida': request.POST.get('carteira_id', ''),
        })

    return render(request, 'contatos/importar.html', ctx)


@web_login_required
def baixar_modelo(request):
    """Baixa um CSV modelo (com BOM, para o Excel abrir com acentos)."""
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = 'attachment; filename="modelo_contatos.csv"'
    resposta.write('\ufeff')
    w = csv.writer(resposta, delimiter=';')
    w.writerow(['Nome', 'Telefone', 'E-mail', 'Empresa', 'Segmento', 'Etapa do funil',
                'Valor (R$)', 'Procedimento', 'Origem', 'Pagamento', 'Cidade', 'Bairro',
                'Nascimento', 'Observações', 'Tags'])
    w.writerow(['Maria da Silva', '(11) 98888-7777', 'maria@exemplo.com', 'Empresa Aurora',
                'Estética', 'Interessado', '1500,00', 'Laser CO2', 'Instagram', 'Particular',
                'São Paulo', 'Pinheiros', '15/03/1990', 'Cliente indicada pela Ana.', 'VIP, Retorno'])
    return resposta


@web_login_required
@web_requer_admin
def campos_personalizados(request):
    """Lista os campos do tenant e cria novos (nome unico por tenant) — apenas admin."""
    tid = _tenant_id(request)
    erros = []
    if request.method == 'POST':
        form = CampoForm(request.POST)
        nome_limpo = form.cleaned_data['nome'].strip() if form.is_valid() else ''
        if form.is_valid() and not _nome_ja_existe(tid, nome_limpo):
            campo = form.save(commit=False)
            campo.nome = nome_limpo
            if tid is not None:
                campo.tenant_id = tid
            campo.save()
            return redirect('contatos:campos')
        if not form.is_valid():
            erros = _erros_do_form(form)
        else:
            erros.append(f'Já existe um campo chamado "{nome_limpo}".')
    else:
        form = CampoForm()
    campos = [
        {
            'id': c.id,
            'nome': c.nome,
            'tipo': c.get_tipo_display(),
            'obrigatorio': c.obrigatorio,
            'ordem': c.ordem,
            'qtd_uso': c.valores.values('contato_id').distinct().count(),
        }
        for c in _campos_scope(tid)
    ]
    return render(request, 'contatos/campos.html', {
        'form': form, 'campos': campos, 'erros': erros,
    })


@web_login_required
@web_requer_admin
def editar_campo(request, pk):
    tid = _tenant_id(request)
    campo = get_object_or_404(_campos_scope(tid), pk=pk)
    erros = []
    if request.method == 'POST':
        form = CampoForm(request.POST, instance=campo)
        nome_limpo = form.cleaned_data['nome'].strip() if form.is_valid() else ''
        if form.is_valid() and not _nome_ja_existe(tid, nome_limpo, excluir_pk=campo.pk):
            campo.nome = nome_limpo
            form.save()
            return redirect('contatos:campos')
        if not form.is_valid():
            erros = _erros_do_form(form)
        else:
            erros.append(f'Já existe um campo chamado "{nome_limpo}".')
    else:
        form = CampoForm(instance=campo)
    return render(request, 'contatos/editar_campo.html', {
        'form': form, 'campo': campo, 'erros': erros,
    })


@web_login_required
@web_requer_admin
def excluir_campo(request, pk):
    tid = _tenant_id(request)
    campo = get_object_or_404(_campos_scope(tid), pk=pk)
    if request.method == 'POST':
        campo.delete()
        return redirect('contatos:campos')
    qtd = campo.valores.values('contato_id').distinct().count()
    return render(request, 'contatos/excluir_campo.html', {'campo': campo, 'qtd': qtd})


@web_login_required
@web_requer_edicao
def adicionar_nota(request, pk):
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    if request.method == 'POST':
        form = NotaForm(request.POST)
        if form.is_valid():
            nota = form.save(commit=False)
            nota.contato = contato
            nota.autor_id = request.session.get('usuario_id')
            nota.save()
            atualizar_score(contato)
    return redirect('contatos:detalhe', pk=contato.id)


@web_login_required
def excluir_nota(request, pk, nota_id):
    """Excluir nota — apenas admin."""
    if not e_admin_do_tenant(request):
        return redirect('contatos:detalhe', pk=pk)
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    if request.method == 'POST':
        contato.notas.filter(pk=nota_id).delete()
    return redirect('contatos:detalhe', pk=contato.id)


@web_login_required
@web_requer_edicao
def adicionar_tag(request, pk):
    contato = get_object_or_404(
        filtro_tenant(request, Contato.objects.all()).prefetch_related('tags'), pk=pk
    )
    if request.method == 'POST':
        _criar_e_anexar_tag(request, contato, request.POST.get('nome', ''))
    return redirect('contatos:detalhe', pk=contato.id)


@web_login_required
def remover_tag(request, pk, tag_id):
    """Remover tag do contato — apenas admin."""
    if not e_admin_do_tenant(request):
        return redirect('contatos:detalhe', pk=pk)
    contato = get_object_or_404(
        filtro_tenant(request, Contato.objects.all()).prefetch_related('tags'), pk=pk
    )
    if request.method == 'POST':
        contato.tags.remove(tag_id)
    return redirect('contatos:detalhe', pk=contato.id)


# ---------------------------------------------------------------------------
# Exportacao CSV (Fase E)
# ---------------------------------------------------------------------------


def _resposta_csv(nome_arquivo):
    """Resposta CSV com BOM (Excel abre acentos corretamente)."""
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    resposta.write('\ufeff')
    return resposta


def _csv_seguro(valor):
    """Previne injeção de fórmula no Excel (CSV injection): célula iniciando com
    `=`, `+`, `-` ou `@` vira texto com apóstrofo inicial."""
    texto = str(valor or '')
    if texto.startswith(('=', '+', '-', '@')):
        return "'" + texto
    return texto


@web_login_required
def exportar_csv(request):
    """Exporta os contatos do tenant (com o negócio principal) em CSV."""
    from datetime import date

    contatos = (
        filtro_tenant(request, Contato.objects.all())
        .prefetch_related('tags', 'negocios')
        .order_by('id')
    )
    resposta = _resposta_csv(f'contatos-{date.today().isoformat()}.csv')
    w = csv.writer(resposta, delimiter=';')
    w.writerow(['Nome', 'Empresa', 'Telefone', 'E-mail', 'Segmento', 'Procedimento',
                'Última consulta', 'Origem', 'Pagamento', 'Cidade', 'Bairro', 'Observações',
                'Tags', 'Negócio principal', 'Etapa', 'Valor (R$)'])
    for c in contatos:
        principal = c.negocios.filter(principal=True).first() or c.negocios.first()
        w.writerow([
            _csv_seguro(c.nome), _csv_seguro(c.empresa), _csv_seguro(c.tel), _csv_seguro(c.email),
            _csv_seguro(SEGS.get(c.seg, SEG_FALLBACK)['label']),
            _csv_seguro(c.procedimento), _csv_seguro(c.ultima_consulta), _csv_seguro(c.origem),
            _csv_seguro(c.pagamento), _csv_seguro(c.cidade), _csv_seguro(c.bairro),
            _csv_seguro(c.observacoes),
            _csv_seguro(', '.join(t.nome for t in c.tags.all())),
            _csv_seguro(principal.titulo if principal else ''),
            _csv_seguro(principal.stage if principal else ''),
            _csv_seguro(str(principal.valor).replace('.', ',') if principal and principal.valor else ''),
        ])
    return resposta


# ---------------------------------------------------------------------------
# Captura pública de lead (Fase H)
# ---------------------------------------------------------------------------

LIMITE_ENVIOS_POR_IP = 5


def captura_lead(request, token):
    """Página pública (sem login) — o lead preenche e vira contato + negócio.

    Proteções: token único por tenant (URL secreta), honeypot anti-robô e limite
    de envios por IP (janela de 1h, cache locmem). O lead entra na primeira etapa
    do pipeline do tenant com a origem configurada (Site/Instagram/WhatsApp).
    """
    tenant = get_object_or_404(Tenant.objects.all(), token_captura=token)
    erros = []
    sucesso = False
    desativado = not tenant.captura_ativa
    if request.method == 'POST' and tenant.captura_ativa:
        # Honeypot: robô preenche o campo invisível → responde sucesso sem gravar
        if request.POST.get('website'):
            sucesso = True
        else:
            nome = (request.POST.get('nome') or '').strip()
            tel = (request.POST.get('tel') or '').strip()
            email = (request.POST.get('email') or '').strip().lower()
            if not nome:
                erros.append('Informe seu nome.')
            if not tel and not email:
                erros.append('Informe pelo menos um telefone ou e-mail para contato.')
            if not erros:
                # Rate limit: só conta envios válidos (5/hora por IP) — erros de
                # digitação não bloqueiam o lead legítimo.
                ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
                chave = f'captura:{ip}'
                enviados = int(cache.get(chave, 0) or 0)
                if enviados >= LIMITE_ENVIOS_POR_IP:
                    erros.append('Muitos envios deste aparelho. Tente novamente mais tarde.')
                else:
                    cache.set(chave, enviados + 1, 3600)
                    seg = request.POST.get('seg', '')
                    if seg not in SEGS:
                        seg = ''
                    procedimento = (request.POST.get('procedimento') or '').strip() or '—'
                    origem = tenant.origem_captura or 'Site'
                    # Deduplicação: mesmo telefone normalizado (mesmo tenant) →
                    # atualiza o contato existente e registra um novo negócio,
                    # em vez de criar contato duplicado.
                    tel_digitos = so_digitos(tel)
                    contato = (
                        Contato.objects.filter(tenant_id=tenant.id, tel_normalizado=tel_digitos).first()
                        if tel_digitos else None
                    )
                    novo_contato = contato is None
                    if novo_contato:
                        contato = Contato.objects.create(
                            tenant=tenant,
                            nome=nome,
                            tel=tel or '—',
                            email=email or '—',
                            seg=seg,
                            procedimento=procedimento,
                            origem=origem,
                        )
                    else:
                        contato.nome = nome
                        if tel:
                            contato.tel = tel
                        if email:
                            contato.email = email
                        if seg:
                            contato.seg = seg
                        contato.procedimento = procedimento
                        contato.origem = origem
                        contato.save()
                    etapas = etapas_do_tenant(tenant.id, tenant.nicho)
                    stage = etapas[0]['key'] if etapas else 'interessado'
                    negocio = criar_negocio(contato, stage=stage, valor=0, tenant_id=tenant.id)
                    if novo_contato:
                        # só contatos realmente novos disparam o gatilho "Contato novo" —
                        # quem já existia (dedup por telefone) apenas ganha um negócio.
                        disparar('contato_criado', tenant_id=tenant.id, contato=contato, negocio=negocio)
                    disparar('negocio_criado', tenant_id=tenant.id, contato=contato, negocio=negocio)
                    atualizar_score(contato)
                    sucesso = True
    return render(request, 'contatos/captura.html', {
        'tenant': tenant,
        'erros': erros,
        'sucesso': sucesso,
        'desativado': desativado,
        'segs': SEGS,
    })


# ---------------------------------------------------------------------------
# Carteiras (Sprint 3 do PRD HAZON — Gestão de bases)
# ---------------------------------------------------------------------------


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


@web_login_required
def exportar_negocios_csv(request):
    """Exporta os negócios (deals) do tenant em CSV."""
    from datetime import date

    negocios = filtro_tenant(request, Negocio.objects.select_related('contato')).order_by('id')
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho_da_sessao(request))
    resposta = _resposta_csv(f'negocios-{date.today().isoformat()}.csv')
    w = csv.writer(resposta, delimiter=';')
    w.writerow(['Contato', 'Negócio', 'Etapa', 'Valor (R$)', 'Principal', 'Criado em', 'Atualizado em'])
    for n in negocios:
        w.writerow([
            _csv_seguro(n.contato.nome),
            _csv_seguro(n.titulo),
            _csv_seguro(stage_map.get(n.stage, {'name': n.stage})['name']),
            _csv_seguro(str(n.valor).replace('.', ',')),
            'Sim' if n.principal else '',
            n.created_at.strftime('%d/%m/%Y'),
            n.updated_at.strftime('%d/%m/%Y'),
        ])
    return resposta
