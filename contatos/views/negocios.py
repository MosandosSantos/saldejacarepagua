"""Negocios (deals) do contato — criar, editar, principal, excluir e orcamento em PDF."""

from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from acesso.decorators import (
    e_admin_do_tenant,
    filtro_tenant,
    nicho_da_sessao,
    web_login_required,
    web_requer_edicao,
)
from acesso.models import Tenant
from automacoes.engine import disparar
from contatos.models import (
    Contato,
    criar_negocio,
    registrar_movimentacao,
    tornar_principal,
)
from contatos.scoring import atualizar_score
from contatos.views.helpers import (
    _decorar,
    _membros_do_tenant,
    _responsavel_do_post,
    _tenant_id,
)
from core.utils import parse_brl
from recepcao.models import etapa_map_do_tenant, etapas_do_tenant


def _valor_do_post(request, negocio=None):
    """Lê e valida o valor (R$) vindo do formulário de negócio; devolve (Decimal, erro)."""
    raw = (request.POST.get('valor', '') or '').strip()
    if not raw:
        return Decimal(0), None
    v = parse_brl(raw)
    if v < 0:
        return (negocio.valor if negocio else Decimal(0)), 'O valor não pode ser negativo.'
    return v, None


def _fechar_se_necessario(contato, stage):
    if stage == 'fechado':
        from emails.servico import marcar_conversoes

        marcar_conversoes(contato)


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
            _fechar_se_necessario(contato, stage)
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
            _fechar_se_necessario(contato, stage)
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
