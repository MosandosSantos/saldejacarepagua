"""Authenticated exports for the filtered member-accompaniment table."""

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.http import require_GET

from acesso.decorators import web_login_required
from contatos.relatorio_acompanhamento import (
    gerar_pdf_acompanhamento,
    gerar_xlsx_acompanhamento,
)
from contatos.views.acompanhamento import (
    _linhas_acompanhamento,
    _resolver_consulta_acompanhamento,
)
from contatos.views.gprb_membros import _tem_vale_ativo, _tenant_ids_para_lista

_MIMES_EXPORTACAO = {
    'pdf': 'application/pdf',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


@web_login_required
@require_GET
def acompanhamento_exportar(request, formato):
    """Download all rows matching the current filters, without HTML pagination."""
    if not _tem_vale_ativo(request):
        return HttpResponseForbidden(
            'Seu Vale não está ativo — exportação do acompanhamento indisponível.',
        )
    if formato not in _MIMES_EXPORTACAO:
        return HttpResponseBadRequest('Formato de relatório inválido.')

    tenant_ids = _tenant_ids_para_lista(request)
    consulta = _resolver_consulta_acompanhamento(request, tenant_ids)
    membros = list(consulta.queryset)
    linhas = _linhas_acompanhamento(membros, consulta.graus_visiveis)
    gerado_em = timezone.localdate()

    if formato == 'pdf':
        conteudo = gerar_pdf_acompanhamento(
            linhas, consulta.graus_visiveis, gerado_em,
        )
        extensao = 'pdf'
    else:
        conteudo = gerar_xlsx_acompanhamento(
            linhas, consulta.graus_visiveis, gerado_em,
        )
        extensao = 'xlsx'

    resposta = HttpResponse(conteudo, content_type=_MIMES_EXPORTACAO[formato])
    resposta['Content-Disposition'] = (
        f'attachment; filename="acompanhamento-{gerado_em.isoformat()}.{extensao}"'
    )
    return resposta
