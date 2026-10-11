"""Tenant-scoped CRUD for locally stored Vales."""

from datetime import date

from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from acesso.decorators import (
    filtro_tenant,
    tenant_id_da_sessao,
    web_login_required,
    web_requer_edicao,
    web_requer_tenant_context,
)
from acesso.models import ROLE_ADMIN_SAAS
from contatos.importador import normalizar_valor
from contatos.models import Vale
from core.utils import brl


def _role(request):
    usuario = getattr(request, 'usuario_logado', None)
    snapshot = request.session.get('usuario', {})
    role = getattr(usuario, 'role', None)
    if role:
        return role
    return snapshot.get('role') if isinstance(snapshot, dict) else None


def _vales_do_request(request):
    """Return the authorized Vale queryset, or None for a tenantless non-SaaS user."""
    tenant_id = tenant_id_da_sessao(request)
    if tenant_id is None:
        return Vale.objects.all() if _role(request) == ROLE_ADMIN_SAAS else None
    return filtro_tenant(request, Vale.objects.all())


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
        'prefeito': vale.prefeito or '—',
        'telefone': vale.telefone or '—',
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
    vales = _vales_do_request(request)
    if vales is None:
        return HttpResponseForbidden('Tenant obrigatório.')
    vales = vales.order_by('nome', 'id')
    return render(request, 'contatos/prefeituras.html', {
        'prefeituras': [_para_contexto_vale(vale) for vale in vales],
        'total_pf': vales.count(),
    })


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def prefeitura_nova(request):
    """Create a local Vale in the effective tenant."""
    erro = None
    if request.method == 'POST':
        tenant_id = tenant_id_da_sessao(request)
        if tenant_id is None:
            return HttpResponseForbidden('Selecione um tenant para criar o Vale.')
        dados = _dados_do_post(request)
        if not dados['nome']:
            erro = 'Informe o nome do Vale.'
        else:
            Vale.objects.create(tenant_id=tenant_id, **dados)
            return redirect('contatos:prefeituras')

    return render(request, 'contatos/prefeitura_nova.html', {'erro': erro})


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def prefeitura_editar(request, pk):
    """Edit a local Vale, never a record in the external GPRB database."""
    vales = _vales_do_request(request)
    if vales is None:
        return HttpResponseForbidden('Tenant obrigatório.')
    vale = get_object_or_404(vales, pk=pk)
    erro = None

    if request.method == 'POST':
        dados = _dados_do_post(request)
        if not dados['nome']:
            erro = 'Informe o nome do Vale.'
        else:
            for campo, valor in dados.items():
                setattr(vale, campo, valor)
            vale.save()
            return redirect('contatos:prefeituras')

    return render(request, 'contatos/prefeitura_editar.html', {
        'prefeitura': _para_contexto_vale(vale),
        'erro': erro,
        'sucesso': None,
    })


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def prefeitura_excluir(request, pk):
    """Delete a local Vale; no external Loja relationship is queried."""
    vales = _vales_do_request(request)
    if vales is None:
        return HttpResponseForbidden('Tenant obrigatório.')
    vale = get_object_or_404(vales, pk=pk)
    if request.method == 'POST':
        vale.delete()
        return redirect('contatos:prefeituras')

    return render(request, 'contatos/prefeitura_excluir.html', {
        'prefeitura': _para_contexto_vale(vale),
        'lojas': 0,
        'erro': None,
    })
