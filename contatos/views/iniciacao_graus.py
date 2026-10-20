"""Authenticated page with members eligible for degree 9."""

from django.http import HttpResponseForbidden
from django.shortcuts import render

from acesso.decorators import web_login_required
from contatos.iniciacao_graus import candidatos_grau_9
from contatos.views.gprb_membros import _tem_vale_ativo, _tenant_ids_para_lista


@web_login_required
def iniciacao_graus(request):
    """Render current Grade 9 candidates in the authorized Vale scope."""
    if not _tem_vale_ativo(request):
        return HttpResponseForbidden(
            'Seu Vale não está ativo — candidatos a graus indisponíveis.',
        )

    candidatos = candidatos_grau_9(_tenant_ids_para_lista(request))
    return render(request, 'contatos/iniciacao_graus.html', {
        'candidatos': [
            {
                'id': candidato.membro.pk,
                'nome': candidato.membro.nome,
                'vale': candidato.vale_nome,
                'data_grau_4': candidato.data_grau_4,
                'presenca': round(candidato.presenca_percentual),
            }
            for candidato in candidatos
        ],
        'total': len(candidatos),
    })
