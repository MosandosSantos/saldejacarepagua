"""The Vale pages call their listed leader Delegado; the create form says Grão Mestre."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'contatos' / 'templates' / 'contatos'


def test_consult_page_has_no_leader_column():
    # A tabela só lista Vale(Potência)/Secretaria/Tesouraria — o líder aparece na consulta individual.
    source = (TEMPLATES / 'prefeituras.html').read_text(encoding='utf-8')

    assert '>Delegado</th>' not in source
    assert 'Grão-Mestre' not in source


def test_edit_page_calls_the_leader_delegado():
    source = (TEMPLATES / 'prefeitura_editar.html').read_text(encoding='utf-8')
    assert '>Delegado</label>' in source
    assert 'E-mail do Delegado' in source
    assert 'Grão-Mestre' not in source
    assert 'grão-mestre' not in source


def test_create_page_calls_the_leader_grao_mestre():
    source = (TEMPLATES / 'prefeitura_nova.html').read_text(encoding='utf-8')
    assert '>Grão Mestre</label>' in source
    assert 'E-mail do Grão Mestre' in source
    assert 'Nome do grão mestre' in source
    assert 'Grão-Mestre' not in source
    assert 'grão-mestre' not in source


def test_delete_page_calls_the_leader_delegado():
    source = (TEMPLATES / 'prefeitura_excluir.html').read_text(encoding='utf-8')

    assert 'Delegado: {{ prefeitura.prefeito' in source
    assert 'Grão-Mestre' not in source
