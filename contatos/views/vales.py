"""Tenant-scoped CRUD for locally stored Vales.

Since the system no longer uses multi-tenancy (tenant field removed from Loja/Membro),
the scope is now defined by the Membro↔Loja relationship and the Profile (corpo) of each Loja.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
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
from acesso.models import ROLE_ADM, ROLE_ADMIN_SAAS, ROLE_DELEGADO, ROLE_PRESIDENTE_CORPO
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
    """Apenas Admin Saas pode criar/excluir/reativar Vales (Potências).
    Admin ADM NÃO tem permissão para criar potências — esta é exclusiva do Admin Saas.
    """
    return _role(request) == ROLE_ADMIN_SAAS


def _pode_alterar_vale(request):
    """admin_saas e Presidente de Corpo (só da loja que preside) podem alterar Vales.
    O Admin ADM NÃO tem permissão para alterar potências — só o Admin Saas.
    """
    return _role(request) in (
        ROLE_ADMIN_SAAS, ROLE_PRESIDENTE_CORPO,
    )


def _vales_do_request(request):
    """Return the authorized Vale queryset, or None for a tenantless non-SaaS user."""
    if _role(request) in (ROLE_ADMIN_SAAS, ROLE_ADMIN_SAAS):
        return Vale.objects.filter(status='ATIVA')
    tenant_id = tenant_id_da_sessao(request)
    if tenant_id is None:
        return None
    return Vale.objects.filter(status='ATIVA')


def _vales_do_tenant_para_edicao(request):
    """Writes target one explicit tenant, except ADM (all Vales).

    admin_saas só grava com um tenant selecionado; sem seleção devolve None
    e as views respondem 403 (spec de isolamento de tenant).
    """
    if _role(request) == ROLE_ADMIN_SAAS:
        return Vale.objects.filter(status='ATIVA')
    tenant_id = tenant_id_da_sessao(request)
    if tenant_id is None:
        return None
    return Vale.objects.filter(status='ATIVA')


def _vale_visivel(request, pk):
    """Vale that the user can consult (same policy as listagem).

    User without tenant with active Vale receives None (the view responds 403);
    vale inexistente, inativo or other vale generates 404 — without leaking existence.
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


def _lojas_por_vale(vale):
    """Return lojas associated with the Vale's profile, based on Profile (corpo).

    Since there's no tenant, lojas are returned without tenant_id filter.
    The Vale's profile is determined by the set of profiles (corpos) of lojas
    with active members.
    """
    # Get all lojas since there's no tenant filter
    lojas = Loja.objects.all().order_by('nome', 'id')
    return lojas


def _membros_por_vale(vale):
    """Count active members associated with the Vale's profile.

    Since there's no tenant, we count members who have at least one Loja linked.
    """
    # Count active members who have at least one Loja linked
    membros_count = Membro.objects.filter(situacao='ATIVO').annotate(
        num_lojas=Count('lojas', distinct=True)
    ).filter(num_lojas__gt=0).count()
    return membros_count


@web_login_required
def prefeituras(request):
    """List local Vales visible to the current user."""

    vales = _vales_do_request(request)
    if vales is None:
        # If not admin and no tenant, try listing global vales
        vales = Vale.objects.filter(status='ATIVA')

    page_obj = Paginator(vales.order_by('nome', 'id'), 20).get_page(
        request.GET.get('page', 1),
    )
    vales = list(page_obj.object_list)
    # Since there's no tenant, we list all lojas without tenant filter
    lojas = Loja.objects.all().order_by('nome', 'id')

    # Build lojas_por_vale using the Profile (corpo) of lojas
    lojas_por_vale = {}
    for loja in lojas:
        # Agrupa lojas por profile (corpo)
        perfil = loja.corpo  # MMM, NAr, SAR, Tem, Malta
        if perfil not in lojas_por_vale:
            lojas_por_vale[perfil] = []
        lojas_por_vale[perfil].append({
            'id': loja.pk,
            'nome': loja.nome,
            'corpo': loja.get_corpo_display(),
            'membros_total': 0,  # será preenchido abaixo
        })

    # Preencher membros_total por profile
    # Conta membros ativos que têm lojas vinculadas (qualquer profile)
    perfil_counts = {}
    for m in Membro.objects.filter(situacao='ATIVO').annotate(
        num_lojas=Count('lojas', distinct=True)
    ).filter(num_lojas__gt=0):
        # Pega o profile da primeira loja vinculada
        for loja in m.lojas.all()[:1]:  # pega apenas a primeira loja para definir o profile
            perfil = loja.corpo
            if perfil not in perfil_counts:
                perfil_counts[perfil] = 0
            perfil_counts[perfil] += 1

    # Agora atribui ao lojas_por_vale
    for perfil, count in perfil_counts.items():
        if perfil in lojas_por_vale:
            # Ajusta o membros_total do primeiro item do profile
            lojas_por_vale[perfil][0]['membros_total'] = count

    vales_ctx = []
    for i, vale in enumerate(vales):
        ctx = _para_contexto_vale(vale)
        # Seleciona as lojas do profile correspondente (ou todas se não houver filtro)
        perfil_vale = vale.corpo if hasattr(vale, 'corpo') else 'perfeicao'
        ctx['lojas'] = lojas_por_vale.get(perfil_vale, [])
        ctx['lojas_count'] = len(ctx['lojas'])
        ctx['lojas_nomes'] = [loja['nome'] for loja in ctx['lojas']]
        ctx['membros_total'] = perfil_counts.get(perfil_vale, 0)
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
            # Como não há mais tenant, gravamos o session admin_tenant_id como o primeiro vale criado
            request.session['admin_tenant_id'] = vale.pk
            request.session.modified = True
            return redirect('vales')

    return render(request, 'contatos/prefeitura_nova.html', {'erro': erro})


@web_login_required
def prefeitura_detalhe(request, pk):
    """Mostra os detalhes de um Vale sem permitir edição."""
    vales = _vales_do_request(request)
    if vales is None:
        return HttpResponseForbidden('Selecione um tenant para consultar o Vale.')
    vale = get_object_or_404(vales, pk=pk)
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
                # Como não há mais tenant, não alteramos tenant.nome
                # Apenas salvamos o vale
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
        return redirect('vales')

    return render(request, 'contatos/prefeitura_excluir.html', {
        'prefeitura': _para_contexto_vale(vale),
    })


@web_login_required
@web_requer_edicao
def prefeitura_reativar(request, pk):
    """Reativar um Vale arquivado."""
    if not _pode_gerir_vale(request):
        return HttpResponseForbidden('Sem permissão para reativar um Vale.')
    vales = _vales_do_tenant_para_edicao(request)
    if vales is None:
        return HttpResponseForbidden('Selecione um tenant para reativar o Vale.')
    vale = get_object_or_404(vales, pk=pk)
    if request.method == 'POST':
        vale.status = 'ATIVA'
        vale.save(update_fields=['status', 'updated_at'])
        return redirect('vales')

    return render(request, 'contatos/prefeitura_reativar.html', {
        'prefeitura': _para_contexto_vale(vale),
    })