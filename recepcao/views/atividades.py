"""Criacao de tarefas/atividades vinculadas a um contato a partir do funil (AJAX).

Extraido de views.py para separar responsabilidade de criacao de atividades.
"""

import re as _re
from datetime import date, time

from django.http import HttpResponseBadRequest, JsonResponse

from acesso.decorators import (
    nicho_da_sessao,
    tenant_id_da_sessao,
    web_login_required,
    web_requer_edicao,
)
from contatos.models import Contato
from tarefas.models import PRIORIDADES, Tarefa


@web_login_required
@web_requer_edicao
def nova_atividade(request):
    """Cria uma tarefa/atividade vinculada a um contato a partir do funil (AJAX)."""
    if request.method != 'POST':
        return HttpResponseBadRequest('Metodo nao permitido.')
    tid = tenant_id_da_sessao(request)
    titulo = (request.POST.get('titulo') or '').strip()
    contato_id = request.POST.get('contato_id', '')
    prioridade = request.POST.get('prioridade', 'media')
    vencimento_raw = (request.POST.get('vencimento') or '').strip()
    hora_raw = (request.POST.get('hora') or '').strip()
    descricao = (request.POST.get('descricao') or '').strip()

    erros, vencimento, hora, cid = _validar_atividade(
        titulo, prioridade, vencimento_raw, hora_raw, contato_id, tid
    )

    if erros:
        return JsonResponse({'ok': False, 'erros': erros}, status=400)

    tarefa = Tarefa.objects.create(
        tenant_id=tid,
        titulo=titulo,
        descricao=descricao,
        contato_id=cid,
        responsavel_id=request.session.get('usuario_id'),
        prioridade=prioridade,
        vencimento=vencimento,
        hora=hora,
        criado_por_id=request.session.get('usuario_id'),
    )
    return JsonResponse({
        'ok': True,
        'msg': f'Atividade "{tarefa.titulo}" criada com sucesso!',
    })


def _validar_atividade(titulo, prioridade, vencimento_raw, hora_raw, contato_id, tid):
    """Valida dados da atividade e retorna (erros, vencimento, hora, contato_id)."""
    erros = []
    if not titulo:
        erros.append('Informe o titulo da atividade.')
    if prioridade not in dict(PRIORIDADES):
        erros.append('Prioridade invalida.')

    vencimento = _validar_data(vencimento_raw, erros)
    hora = _validar_hora(hora_raw, erros)
    cid = _validar_contato(contato_id, tid)

    return erros, vencimento, hora, cid


def _validar_data(vencimento_raw, erros):
    """Valida e retorna data de vencimento."""
    if not vencimento_raw:
        return None
    try:
        return date.fromisoformat(vencimento_raw)
    except ValueError:
        erros.append('Data invalida.')
        return None


def _validar_hora(hora_raw, erros):
    """Valida e retorna hora."""
    if not hora_raw:
        return None
    if not _re.fullmatch(r'\d{1,2}:\d{2}', hora_raw):
        erros.append('Hora invalida (use HH:MM).')
        return None
    try:
        return time.fromisoformat(hora_raw)
    except ValueError:
        erros.append('Hora invalida.')
        return None


def _validar_contato(contato_id, tid):
    """Valida e retorna contato_id se valido."""
    if not contato_id or not contato_id.isdigit():
        return None
    if Contato.objects.filter(tenant_id=tid, pk=contato_id).exists():
        return int(contato_id)
    return None
