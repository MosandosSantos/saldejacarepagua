"""Tenant-scoped CRUD for locally stored Vales."""

from datetime import date

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from acesso.decorators import (
    filtro_tenant,
    tenant_id_da_sessao,
    web_login_required,
    web_requer_edicao,
)
from acesso.models import ROLE_ADM, ROLE_ADMIN_SAAS, ROLE_DELEGADO
from contatos.importador import normalizar_valor
from contatos.models import Loja, Membro, Vale
from contatos.paginacao import urls_paginacao
from contatos.vale_services import provisionar_vale
from core.utils import brl


def _role(request):
    usuario = getattr(request, 'usuario_logado', None)
    snapshot = request.session.get('usuario', {})
    role = getattr(usuario, 'role', None)
    if role:
        return role
    return snapshot.get('role') if isinstance(snapshot, dict) else None


def _pode_gerir_vale(request):
    """Apenas admin_saas e ADM podem criar/excluir/reativar Vales."""
    return _role(request) in (ROLE_ADMIN_SAAS, ROLE_ADM)


def _pode_alterar_vale(request):
    """admin_saas, ADM e Delegado podem alterar Vales."""
    return _role(request) in (ROLE_ADMIN_SAAS, ROLE_ADM, ROLE_DELEGADO)


def _vales_do_request(request):
    """Return the authorized Vale queryset, or None for a tenantless non-SaaS user."""
    if _role(request) in (ROLE_ADMIN_SAAS, ROLE_ADM):
        return Vale.objects.filter(status='ATIVA')
    tenant_id = tenant_id_da_sessao(request)
    if tenant_id is None:
        return None
    if not Vale.objects.filter(tenant_id=tenant_id, status='ATIVA').exists():
        return None
    return filtro_tenant(request, Vale.objects.filter(status='ATIVA'))


def _vales_do_tenant_para_edicao(request):
    """Writes target one explicit tenant, except ADM (all Vales).

    admin_saas só grava com um tenant selecionado; sem seleção devolve None
    e as views respondem 403 (spec de isolamento de tenant).
    """
    if _role(request) == ROLE_ADM:
        return Vale.objects.filter(status='ATIVA')
    tenant_id = tenant_id_da_sessao(request)
    if tenant_id is None:
        return None
    return Vale.objects.filter(tenant_id=tenant_id, status='ATIVA')


def _vale_visivel(request, pk):
    """Vale que o usuário pode consultar (mesma política da listagem) ou None.

    Usuário sem tenant com Vale ativo recebe None (a view responde 403);
    vale inexistente, inativo ou de outro tenant gera 404 — sem vazar existência.
    """
    vales = _vales_do_request(request)
    if vales is None:
        return None
    return get_object_or_404(vales, pk=pk)


def _data_anuidade(raw):
    """Convert the HTML date input to a date; return None if empty or invalid."""
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _dados_do_post(request):
    """Build local Vale field values from the existing form contract."""
    valor = (request.POST.get('valor_anuidade', '') or '').strip()
    return {
        'nome': request.POST.get('nome', '').strip(),
        'sigla': request.POST.get('sigla', '').strip(),
        'prefeito': request.POST.get('prefeito', '').strip(),
        'telefone': request.POST.get('telefone', '').strip(),
        'email': request.POST.get('email', '').strip(),
        'secretario_nome': request.POST.get('secretario_nome', '').strip(),
        'secretario_email': request.POST.get('secretario_email', '').strip(),
        'secretario_telefone': request.POST.get('secretario_telefone', '').strip(),
        'tesoureiro_nome': request.POST.get('tesoureiro_nome', '').strip(),
        'tesoureiro_email': request.POST.get('tesoureiro_email', '').strip(),
        'tesoureiro_telefone': request.POST.get('tesoureiro_telefone', '').strip(),
        'pix': request.POST.get('pix', '').strip(),
        'valor_anuidade': normalizar_valor(valor) if valor else None,
        'vencimento_anuidade': _data_anuidade(request.POST.get('vencimento_anuidade')),
    }


def _valor_formatado(valor):
    return brl(valor) if valor is not None else ''


def _data_formatada(valor):
    return valor.strftime('%d/%m/%Y') if valor else ''


def _para_contexto_vale(vale):
    """Keep the current DTL template contract while reading a local model."""
    return {
        'id': vale.pk,
        'nome': vale.nome,
        'sigla': vale.sigla,
        'status': vale.status,
        'prefeito': vale.prefeito,
        'telefone': vale.telefone,
        'email': vale.email,
        'secretario_nome': vale.secretario_nome,
        'secretario_email': vale.secretario_email,
        'secretario_telefone': vale.secretario_telefone,
        'tesoureiro_nome': vale.tesoureiro_nome,
        'tesoureiro_email': vale.tesoureiro_email,
        'tesoureiro_telefone': vale.tesoureiro_telefone,
        'pix': vale.pix,
        'valor_anuidade': vale.valor_anuidade,
        'valor_anuidade_fmt': _valor_formatado(vale.valor_anuidade),
        'valor_fmt': _valor_formatado(vale.valor_anuidade),
        'vencimento_anuidade': vale.vencimento_anuidade,
        'vencimento_fmt': _data_formatada(vale.vencimento_anuidade),
        'vencimento_iso': (
            vale.vencimento_anuidade.isoformat() if vale.vencimento_anuidade else ''
        ),
    }


@web_login_required
def prefeituras(request):
    """List local Vales visible to the current tenant."""
    from django.db.models import Count, F, Q


    vales = _vales_do_request(request)
    if vales is None:
        return HttpResponseForbidden('Tenant obrigatório.')
    page_obj = Paginator(vales.order_by('nome', 'id'), 20).get_page(
        request.GET.get('page', 1),
    )
    vales = list(page_obj.object_list)
    tenant_ids = [vale.tenant_id for vale in vales]
    lojas_por_vale = {}
    lojas = (
        Loja.objects
        .filter(tenant_id__in=tenant_ids)
        .annotate(
            membros_total=Count(
                'membros',
                filter=Q(membros__tenant_id=F('tenant_id')),
                distinct=True,
            ),
        )
        .order_by('nome', 'id')
    )
    for loja in lojas:
        lojas_por_vale.setdefault(loja.tenant_id, []).append({
            'id': loja.pk,
            'nome': loja.nome,
            'corpo': loja.get_corpo_display(),
            'membros_total': loja.membros_total,
        })
    membros_por_tenant = dict(
        Membro.objects
        .filter(tenant_id__in=tenant_ids, situacao='ATIVO')
        .values_list('tenant_id')
        .annotate(total=Count('id'))
        .values_list('tenant_id', 'total')
    )
    vales_ctx = []
    for vale in vales:
        ctx = _para_contexto_vale(vale)
        ctx['lojas'] = lojas_por_vale.get(vale.tenant_id, [])
        ctx['lojas_count'] = len(ctx['lojas'])
        ctx['lojas_nomes'] = [loja['nome'] for loja in ctx['lojas']]
        ctx['membros_total'] = membros_por_tenant.get(vale.tenant_id, 0)
        vales_ctx.append(ctx)
    return render(request, 'contatos/prefeituras.html', {
        'prefeituras': vales_ctx,
        'total_pf': page_obj.paginator.count,
        'page_obj': page_obj,
        'pagination_urls': urls_paginacao(
            request, page_obj, base_path=reverse('vales'),
        ),
        'pode_criar_vale': _pode_gerir_vale(request),
    })


@web_login_required
@web_requer_edicao
def prefeitura_nova(request):
    """Provision a new tenant and its Vale for admin_saas or ADM."""
    if not _pode_gerir_vale(request):
        return HttpResponseForbidden('Sem permissão para cadastrar um Vale.')

    erro = None
    if request.method == 'POST':
        dados = _dados_do_post(request)
        try:
            vale = provisionar_vale(dados)
        except ValidationError as exc:
            erro = '; '.join(exc.messages)
        else:
            request.session['admin_tenant_id'] = vale.tenant_id
            request.session.modified = True
            return redirect('vales')

    return render(request, 'contatos/prefeitura_nova.html', {'erro': erro})


@web_login_required
def prefeitura_detalhe(request, pk):
    """Mostra os detalhes de um Vale sem permitir edição."""
    vale = _vale_visivel(request, pk)
    if vale is None:
        return HttpResponseForbidden('Selecione um tenant para consultar o Vale.')
    return render(request, 'contatos/prefeitura_detalhe.html', {
        'prefeitura': _para_contexto_vale(vale),
    })


@web_login_required
@web_requer_edicao
def prefeitura_editar(request, pk):
    """Edit a local Vale, never a record in the external GPRB database."""
    if not _pode_alterar_vale(request):
        return HttpResponseForbidden('Sem permissão para alterar um Vale.')
    vales = _vales_do_tenant_para_edicao(request)
    if vales is None:
        return HttpResponseForbidden('Selecione um tenant para alterar o Vale.')
    vale = get_object_or_404(vales, pk=pk)
    erro = None

    if request.method == 'POST':
        dados = _dados_do_post(request)
        if not dados['nome']:
            erro = 'Informe o nome do Vale.'
        elif not dados['sigla']:
            erro = 'Informe a sigla do Vale.'
        elif Vale.objects.filter(sigla__iexact=dados['sigla']).exclude(pk=vale.pk).exists():
            erro = 'Essa sigla já está em uso.'
        else:
            with transaction.atomic():
                for campo, valor in dados.items():
                    setattr(vale, campo, valor)
                vale.save()
                tenant = vale.tenant
                if tenant.nome != vale.sigla:
                    tenant.nome = vale.sigla
                    tenant.save(update_fields=['nome', 'updated_at'])
            return redirect('vales')

    return render(request, 'contatos/prefeitura_editar.html', {
        'prefeitura': _para_contexto_vale(vale),
        'erro': erro,
        'sucesso': None,
    })


@web_login_required
@web_requer_edicao
def prefeitura_excluir(request, pk):
    """Archive a local Vale without deleting its tenant or related data."""
    if not _pode_gerir_vale(request):
        return HttpResponseForbidden('Sem permissão para arquivar um Vale.')
    vales = _vales_do_tenant_para_edicao(request)
    if vales is None:
        return HttpResponseForbidden('Selecione um tenant para excluir o Vale.')
    vale = get_object_or_404(vales, pk=pk)
    if request.method == 'POST':
        vale.status = 'INATIVA'
        vale.save(update_fields=['status', 'updated_at'])
        if _role(request) == ROLE_ADMIN_SAAS:
            request.session.pop('admin_tenant_id', None)
            request.session.modified = True
            return redirect('vales')
        return redirect('dashboard:index')

    return render(request, 'contatos/prefeitura_excluir.html', {
        'prefeitura': _para_contexto_vale(vale),
        'lojas': 0,
        'erro': None,
    })


@web_login_required
@require_POST
def prefeitura_reativar(request, pk):
    """Reativa um Vale arquivado sem alterar seus dados relacionados."""
    if not _pode_gerir_vale(request):
        return HttpResponseForbidden('Sem permissão para reativar um Vale.')

    vale = get_object_or_404(Vale, pk=pk, status='INATIVA')
    vale.status = 'ATIVA'
    vale.save(update_fields=['status', 'updated_at'])
    request.session['admin_tenant_id'] = vale.tenant_id
    request.session.modified = True
    return redirect('vales')
