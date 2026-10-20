"""Views de workflow de aprovação de candidatos."""

import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from acesso.decorators import web_login_required
from acesso.models import (
    ROLE_ADMIN_SAAS,
    ROLES_OFICIAIS,
    Usuario as _Usuario,
)
from acesso.session import obter_usuario_sessao

from candidatos.models import Candidato

from .cache import invalidar_cache_kanban
from .emails import (
    enviar_email_aprovacao,
    enviar_email_devolucao,
    enviar_email_encaminhamento,
)

logger = logging.getLogger(__name__)


@require_POST
def candidato_aprovar(request, pk):
    """Aprovação DEFINITIVA do candidato (status → APROVADO)."""
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    candidato = get_object_or_404(Candidato, pk=pk)
    papel = request.session.get('usuario', {}).get('role')

    if papel not in ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,):
        return JsonResponse({'erro': 'Sem permissão para aprovar'}, status=403)

    usuario = obter_usuario_sessao(request)
    autor_nome = usuario.get('nome') or 'Sistema'

    from candidatos.oficialato import aprovar_final, pode_aprovar_agora

    usuario_obj = _Usuario.objects.filter(pk=request.session.get('usuario_id')).first()
    if not pode_aprovar_agora(candidato, usuario_obj, papel):
        return JsonResponse({'ok': False, 'erro': 'A aprovação final só pode ser feita pelo Grão Prior, Grande Chanceler ou Admin (candidato em revisão).'}, status=403)

    ok, _status, _nivel, erro = aprovar_final(
        candidato, papel, autor_nome,
        observacao=request.POST.get('observacao', ''),
    )
    if not ok:
        return JsonResponse({'ok': False, 'erro': erro}, status=400)

    invalidar_cache_kanban(candidato.tenant_id)
    enviar_email_aprovacao(request, candidato)
    return JsonResponse({'ok': True, 'mensagem': 'Candidato aprovado com sucesso.'})


@require_POST
def candidato_devolver(request, pk):
    """Devolve o candidato ao nível ANTERIOR."""
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    candidato = get_object_or_404(Candidato, pk=pk)
    papel = request.session.get('usuario', {}).get('role')

    if papel not in ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,):
        return JsonResponse({'erro': 'Sem permissão para devolver'}, status=403)

    usuario = obter_usuario_sessao(request)
    autor_nome = usuario.get('nome') or 'Sistema'

    from candidatos.oficialato import devolver_nivel_captura_data

    ok, _novo_nivel, erro = devolver_nivel_captura_data(
        candidato, papel, autor_nome,
        observacao=request.POST.get('observacao', ''),
    )
    if not ok:
        return JsonResponse({'ok': False, 'erro': erro}, status=400)

    invalidar_cache_kanban(candidato.tenant_id)
    enviar_email_devolucao(request, candidato)
    return JsonResponse({'ok': True, 'mensagem': 'Candidato devolvido ao nível anterior. E-mail enviado ao candidato.'})


@require_POST
def candidato_aprovar_encaminhar(request, pk):
    """Aprovação de nível via botão "Aprovar": reputa quem está na vez no nível
    atual e encaminha para o próximo oficial."""
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    candidato = get_object_or_404(Candidato, pk=pk)
    papel = request.session.get('usuario', {}).get('role')

    if papel not in ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,):
        return JsonResponse({'erro': 'Sem permissão para aprovar'}, status=403)

    usuario = obter_usuario_sessao(request)
    autor_nome = usuario.get('nome') or 'Sistema'

    from candidatos.oficialato import avancar_nivel_captura_data

    ok, _novo_nivel, erro = avancar_nivel_captura_data(
        candidato, papel, autor_nome,
        observacao=request.POST.get('observacao', ''),
    )
    if not ok:
        return JsonResponse({'ok': False, 'erro': erro or 'Falha ao aprovar.'}, status=400)

    invalidar_cache_kanban(candidato.tenant_id)
    enviar_email_encaminhamento(request, candidato)
    return JsonResponse({'ok': True, 'mensagem': 'Aprovado e encaminhado para o próximo nível.'})
