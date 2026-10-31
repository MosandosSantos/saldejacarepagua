"""The Prefeitura-backed business entity is displayed as Potência in the UI."""

from pathlib import Path

from django.urls import reverse

from acesso.context_processors import _nav_itens


ROOT = Path(__file__).resolve().parents[1]


def test_vale_follows_dashboard_and_uses_the_existing_page():
    items = _nav_itens(url_name='index', app_atual='dashboard')
    labels = [item['label'] for item in items]

    assert labels[:2] == ['Dashboard', 'Potência']
    assert items[1]['url'] == reverse('vales')


def test_vale_screens_use_potencia_copy():
    contatos_templates = ROOT / 'contatos' / 'templates' / 'contatos'

    source = (contatos_templates / 'prefeituras.html').read_text(encoding='utf-8')
    assert '<h1 class="hazon-titulo">Potências</h1>' in source
    assert 'Incluir Potência' in source
    assert '<h1 class="hazon-titulo">Vales</h1>' not in source
    assert 'Incluir Vale' not in source

    for template, label in (
        ('prefeitura_nova.html', 'Nova Potência'),
        ('prefeitura_editar.html', 'Alterar Potência'),
        ('prefeitura_excluir.html', 'Arquivar Potência'),
    ):
        assert label in (contatos_templates / template).read_text(encoding='utf-8')
