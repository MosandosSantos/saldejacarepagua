"""The Vale pages display mensalidade terminology; the create form says anuidade (no data-field changes)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'contatos' / 'templates' / 'contatos'


def test_consult_page_has_no_mensalidade_column():
    # A tabela de consulta não exibe coluna de mensalidade.
    source = (TEMPLATES / 'prefeituras.html').read_text(encoding='utf-8')

    assert '>Mensalidade</th>' not in source
    assert '>Anuidade</th>' not in source


def test_edit_page_calls_the_amount_mensalidade():
    source = (TEMPLATES / 'prefeitura_editar.html').read_text(encoding='utf-8')
    assert '>Mensalidade</p>' in source
    assert 'Valor da Mensalidade (R$)' in source
    assert 'pagamento da mensalidade' in source
    assert 'Anuidade' not in source
    assert 'pagamento da anuidade' not in source


def test_create_page_calls_the_amount_anuidade():
    source = (TEMPLATES / 'prefeitura_nova.html').read_text(encoding='utf-8')
    assert '>Anuidade</p>' in source
    assert 'Valor da Anuidade (R$)' in source
    assert 'pagamento da anuidade' in source


def test_delete_summary_calls_the_amount_mensalidade():
    source = (TEMPLATES / 'prefeitura_excluir.html').read_text(encoding='utf-8')

    assert '· Mensalidade: {{ prefeitura.valor_fmt }}' in source
    assert 'Anuidade' not in source
