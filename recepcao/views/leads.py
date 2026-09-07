"""View de cadastro rapido de lead — apenas I/O HTTP.

A logica de negocio esta em lead_service.py (SRP).
"""

from django.http import HttpResponseBadRequest, JsonResponse
from django.template.loader import render_to_string

from acesso.decorators import nicho_da_sessao, web_login_required, web_requer_edicao
from recepcao.models import etapas_e_map_do_tenant
from recepcao.views.board import dados_board
from recepcao.views.helpers import card_dict, tenant_id_da_sessao_ou_padrao
from recepcao.views.lead_service import (
    LeadData,
    LeadService,
    LeadValidationError,
    parse_lead_data,
)


@web_login_required
@web_requer_edicao
def novo_lead(request):
    """Cadastro rapido de lead — cria contato 'pobre' + negocio no funil (AJAX).

    View focada em I/O HTTP:
      1. Extrai dados do request
      2. Chama o service
      3. Formata a resposta
    """
    if request.method != 'POST':
        return HttpResponseBadRequest('Metodo nao permitido.')

    tid = tenant_id_da_sessao_ou_padrao(request)
    nicho = nicho_da_sessao(request)
    if tid is None:
        return JsonResponse(
            {'ok': False, 'erros': ['Nenhuma empresa configurada no sistema.']},
            status=400,
        )

    # 1. Extrair e normalizar dados do request (I/O)
    dados = parse_lead_data(request.POST)

    # 2. Chamar service (logica de negocio)
    service = LeadService()
    try:
        result = service.criar_lead(
            dados=dados,
            tenant_id=tid,
            usuario_id=request.session.get('usuario_id'),
        )
    except LeadValidationError as e:
        return JsonResponse({'ok': False, 'erros': e.erros}, status=400)

    # 3. Formatar resposta HTTP
    stages, stage_map = etapas_e_map_do_tenant(tid, nicho)
    html = render_to_string('recepcao/_card.html', {
        'card': card_dict(result.negocio, stage_map),
        'stages': stages,
        'col': {'key': dados.stage},
        'web_pode_editar': True,
    })
    board = dados_board(request)

    return JsonResponse({
        'ok': True,
        'html': html,
        'coluna': dados.stage,
        'colunas': board['colunas'],
        'total_candidatos': board['total_candidatos'],
    })
