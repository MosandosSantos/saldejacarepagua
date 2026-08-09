"""Views web de agendamentos — agenda agrupada por dia (offset calculado a partir de hoje)."""

from datetime import date, datetime, time, timedelta

from django.shortcuts import render

from acesso.decorators import web_login_required
from agendamentos.models import Agendamento

SEMANA = ['domingo', 'segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado']
MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
         'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']


def _dia_util(base, n):
    d = base
    while d.weekday() >= 5:
        d += timedelta(days=1)
    somados = 0
    while somados < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            somados += 1
    return d


@web_login_required
def agenda(request):
    agendamentos = (
        Agendamento.objects.select_related('contato')
        .filter(contato__tenant_id=request.session.get('usuario', {}).get('tenant_id'))
        .order_by('offset_dias', 'hora')
    )
    tid = request.session.get('usuario', {}).get('tenant_id')
    if tid is None:
        agendamentos = Agendamento.objects.select_related('contato').order_by('offset_dias', 'hora')

    hoje = date.today()
    por_dia = {}
    for a in agendamentos:
        d = _dia_util(hoje, a.offset_dias)
        chave = f'{d.day:02d}/{d.month:02d}'
        if chave not in por_dia:
            por_dia[chave] = {
                'dia': f"{SEMANA[d.weekday()]}, {d.day} de {MESES[d.month - 1]}",
                'itens': [],
            }
        por_dia[chave]['itens'].append({
            'hora': a.hora,
            'tipo': a.tipo,
            'tipo_label': a.tipo_label,
            'nome': a.contato.nome if a.contato else '—',
            'empresa': a.contato.empresa if a.contato else '',
        })

    dias = [
        {'chave': k, 'dia': v['dia'], 'itens': v['itens']}
        for k, v in sorted(por_dia.items())
    ]
    return render(request, 'agendamentos/agenda.html', {'dias': dias})