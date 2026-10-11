"""The Vale pages display mensalidade terminology without changing data fields."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'contatos' / 'templates' / 'contatos'


def test_consult_page_calls_the_amount_mensalidade():
    source = (TEMPLATES / 'prefeituras.html').read_text(encoding='utf-8')

    assert '>Mensalidade</th>' in source
    assert 'Anuidade' not in source


def test_create_and_edit_pages_call_the_amount_mensalidade():
    for name in ('prefeitura_nova.html', 'prefeitura_editar.html'):
        source = (TEMPLATES / name).read_text(encoding='utf-8')
        assert '>Mensalidade</p>' in source
        assert 'Valor da Mensalidade (R$)' in source
        assert 'pagamento da mensalidade' in source
        assert 'Anuidade' not in source
        assert 'pagamento da anuidade' not in source


def test_delete_summary_calls_the_amount_mensalidade():
    source = (TEMPLATES / 'prefeitura_excluir.html').read_text(encoding='utf-8')

    assert '· Mensalidade: {{ prefeitura.valor_fmt }}' in source
    assert 'Anuidade' not in source
