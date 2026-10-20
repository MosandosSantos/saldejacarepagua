"""View de importacao de leads — apenas I/O HTTP.

A logica de negocio esta em import_service.py (SRP).
Funcoes mantidas < 50 linhas via extracao de helpers.
"""

from django.http import HttpResponseBadRequest, JsonResponse

from acesso.decorators import nicho_da_sessao, web_login_required, web_requer_edicao
from recepcao.models import etapa_map_do_tenant, etapas_do_tenant
from recepcao.views.helpers import tenant_id_da_sessao_ou_padrao
from recepcao.views.import_service import ImportService, ImportValidationError


@web_login_required
@web_requer_edicao
def importar_leads(request):
    """Importa leads de um CSV — cria contato + negocio no funil (AJAX)."""
    if request.method != 'POST':
        return HttpResponseBadRequest('Metodo nao permitido.')

    tid = tenant_id_da_sessao_ou_padrao(request)
    nicho = nicho_da_sessao(request)
    if tid is None:
        return _erro('Nenhuma empresa configurada no sistema.')

    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return _erro('Selecione um arquivo .csv para importar.')

    conteudo = _ler_arquivo_csv(arquivo)
    if isinstance(conteudo, JsonResponse):
        return conteudo

    resultado = _importar(conteudo, tid, nicho, request)
    if isinstance(resultado, JsonResponse):
        return resultado

    return _resposta_sucesso(resultado)


def _ler_arquivo_csv(arquivo):
    """Le o conteudo do arquivo CSV tentando UTF-8 e Latin-1."""
    try:
        return arquivo.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        arquivo.seek(0)
        try:
            return arquivo.read().decode('latin-1')
        except (UnicodeDecodeError, OSError):
            return _erro('Nao foi possivel ler o arquivo. Use UTF-8 ou Latin-1.')


def _importar(conteudo, tid, nicho, request):
    """Chama o service de importacao."""
    stages = etapas_do_tenant(tid, nicho)
    stage_map = etapa_map_do_tenant(tid, nicho)
    etapa_padrao = _etapa_padrao(request, stage_map, stages)

    service = ImportService()
    try:
        return service.importar_csv(
            conteudo=conteudo,
            tenant_id=tid,
            stage_map=stage_map,
            etapa_padrao=etapa_padrao,
            usuario_id=request.session.get('usuario_id'),
        )
    except ImportValidationError as e:
        return _erro(e.erros)


def _etapa_padrao(request, stage_map, stages):
    """Resolve a etapa padrao para importacao."""
    etapa = request.POST.get('etapa_padrao', 'lead_capturado')
    if etapa not in stage_map:
        etapa = stages[0]['key'] if stages else 'lead_capturado'
    return etapa


def _resposta_sucesso(resultado):
    """Monta resposta de sucesso com mensagens de aviso."""
    msg = f'{resultado.criados} lead(s) importado(s) com sucesso!'
    if resultado.erros_linha:
        msg += ' Avisos: ' + '; '.join(resultado.erros_linha[:5])
        if len(resultado.erros_linha) > 5:
            msg += f' ... e mais {len(resultado.erros_linha) - 5} aviso(s).'
    return JsonResponse({'ok': True, 'msg': msg, 'criados': resultado.criados})


def _erro(msg):
    """Retorna JsonResponse de erro padronizado."""
    if isinstance(msg, list):
        return JsonResponse({'ok': False, 'erros': msg}, status=400)
    return JsonResponse({'ok': False, 'erros': [msg]}, status=400)
