"""Permissões de escrita da agenda — todos exceto tesoureiro e viewer."""
from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect

# Perfis que NÃO podem escrever na agenda.
ROLES_SEM_ESCRITA_AGENDA = {'tesoureiro', 'viewer'}


def role_da_sessao(request):
    usuario = request.session.get('usuario')
    if isinstance(usuario, dict):
        return usuario.get('role')
    return None


def pode_escrever_agenda(request):
    """True quando o perfil da sessão pode criar/editar/excluir na agenda."""
    role = role_da_sessao(request)
    if not role:
        return False
    return role not in ROLES_SEM_ESCRITA_AGENDA


def pode_registrar_presenca(request):
    """Mesma regra de escrita: quem agenda, registra presença."""
    return pode_escrever_agenda(request)


def agenda_requer_escrita(view_func):
    """Bloqueia escrita da agenda para tesoureiro/viewer (e anônimos)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not pode_escrever_agenda(request):
            if request.method in ('GET', 'HEAD'):
                return redirect('agenda:lista')
            return HttpResponseForbidden('Sem permissão para alterar a agenda.')
        return view_func(request, *args, **kwargs)

    return _wrapped
