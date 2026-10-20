"""API endpoints for the local Vale and Loja selectors in the Súplica modal."""

from django.http import JsonResponse

from acesso.decorators import web_login_required
from acesso.models import ROLE_ADM, ROLE_ADMIN_SAAS
from contatos.models import Loja, Vale
from recepcao.views.helpers import tenant_id_da_sessao_ou_padrao


def _tenant_id(request):
    """Use the same selected/default tenant as the initiation board and create flow."""
    return tenant_id_da_sessao_ou_padrao(request)


def _admin_global_vales(request):
    usuario = request.session.get('usuario') or {}
    return usuario.get('role') in (ROLE_ADMIN_SAAS, ROLE_ADM)


@web_login_required
def api_prefeituras(request):
    """Return active local Vales scoped to the effective tenant."""
    if _admin_global_vales(request):
        vales = Vale.objects.filter(status='ATIVA')
    else:
        tenant_id = _tenant_id(request)
        if tenant_id is None:
            return JsonResponse({'prefeituras': []})
        vales = Vale.objects.filter(tenant_id=tenant_id, status='ATIVA')

    prefeituras = list(vales.order_by('nome', 'id').values('id', 'nome'))
    return JsonResponse({'prefeituras': prefeituras})


@web_login_required
def api_lojas_por_prefeitura(request):
    """Return active local Lojas belonging to the selected Vale's tenant."""
    vale_id = request.GET.get('prefeitura_id', '').strip()
    if not vale_id:
        return JsonResponse({'lojas': []})

    if _admin_global_vales(request):
        vales = Vale.objects.filter(pk=vale_id, status='ATIVA')
    else:
        tenant_id = _tenant_id(request)
        if tenant_id is None:
            return JsonResponse({'lojas': []})
        vales = Vale.objects.filter(
            pk=vale_id,
            tenant_id=tenant_id,
            status='ATIVA',
        )

    vale = vales.first()
    if vale is None:
        return JsonResponse({'lojas': []})

    lojas = list(
        Loja.objects.filter(tenant_id=vale.tenant_id, situacao='ATIVA')
        .order_by('nome', 'id')
        .values('id', 'nome')
    )
    return JsonResponse({'lojas': lojas})
