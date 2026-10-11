"""The Vale pages call their listed leader Delegado in visible copy."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'contatos' / 'templates' / 'contatos'


def test_consult_page_calls_the_leader_delegado():
    source = (TEMPLATES / 'prefeituras.html').read_text(encoding='utf-8')

    assert '>Delegado</th>' in source
    assert 'Grão-Mestre' not in source


def test_create_and_edit_pages_call_the_leader_delegado():
    for name in ('prefeitura_nova.html', 'prefeitura_editar.html'):
        source = (TEMPLATES / name).read_text(encoding='utf-8')
        assert '>Delegado</label>' in source
        assert 'E-mail do Delegado' in source
        assert 'Grão-Mestre' not in source
        assert 'grão-mestre' not in source

    source = (TEMPLATES / 'prefeitura_nova.html').read_text(encoding='utf-8')
    assert 'Nome do delegado' in source


def test_delete_page_calls_the_leader_delegado():
    source = (TEMPLATES / 'prefeitura_excluir.html').read_text(encoding='utf-8')

    assert 'Delegado: {{ prefeitura.prefeito' in source
    assert 'Grão-Mestre' not in source
