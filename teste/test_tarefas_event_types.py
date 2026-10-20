import re
from html import unescape

from django.test import RequestFactory

from tarefas.models import Evento, TIPOS_EVENTO
from tarefas.views import ranking


def _ranking_html(monkeypatch):
    monkeypatch.setattr(Evento.objects, 'filter', lambda **kwargs: [])
    request = RequestFactory().get('/tarefas/ranking/')
    request.session = {'usuario_id': 1, 'usuario': {'loja_id': 'loja-teste'}}
    return ranking(request).content.decode()


def test_ranking_event_selector_lists_initiation_degrees_then_posse_and_other(monkeypatch):
    html = _ranking_html(monkeypatch)
    select = re.search(
        r'<select id="evento-tipo"[^>]*>(.*?)</select>', html, re.DOTALL,
    )
    assert select is not None
    options = [
        (value, unescape(label.strip()))
        for value, label in re.findall(
            r'<option value="([^"]*)">(.*?)</option>', select.group(1), re.DOTALL,
        )
    ]

    expected = [
        (f'iniciacao_grau_{grau}', f'Iniciação do grau {grau}')
        for grau in range(4, 33)
    ] + [('posse', 'Posse'), ('outros', 'Outros')]
    assert options == expected


def test_modal_evento_nao_tem_campo_de_fim(monkeypatch):
    """Novo evento pede só o início; o fim é derivado no backend (padrão 2h)."""
    html = _ranking_html(monkeypatch)

    assert not re.search(r'<label for="evento-fim"', html)
    assert not re.search(r'<input[^>]*id="evento-fim"', html)
    # A listagem continua exibindo o horário (coluna "Horário") dos eventos existentes.
    assert re.search(r'<th[^>]*>Horário</th>', html)


def test_legacy_event_types_remain_readable():
    choices = dict(TIPOS_EVENTO)

    assert choices['sessao'] == 'Sessão'
    assert choices['reuniao'] == 'Reunião'
    assert choices['trabalho'] == 'Trabalho'
    assert choices['ritual'] == 'Ritual'
