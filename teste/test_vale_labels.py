"""The Prefeitura-backed business entity is displayed as Vale in the UI."""

import re
from pathlib import Path

from django.urls import reverse

from acesso.context_processors import _nav_itens


ROOT = Path(__file__).resolve().parents[1]
POTENCIA_OTHER_CONCEPTS = (
    'Potência do Simbolismo',
    'Potência no Simbolismo',
    # Placeholder do select "Potência do Simbolismo" — reticência tipográfica
    # (U+2026) e não "..." (a forma antiga continua aceita).
    'Potência…',
    'Potência...',
)


def test_vale_follows_dashboard_and_uses_the_existing_page():
    items = _nav_itens(url_name='index', app_atual='dashboard')
    labels = [item['label'] for item in items]

    assert labels[:2] == ['Dashboard', 'Vale']
    assert items[1]['url'] == reverse('vales')


def test_prefeitura_entity_no_longer_uses_potencia_in_templates():
    pattern = re.compile(r'\bpotênci(?:a|as)\b', re.IGNORECASE)
    remaining = []
    template_roots = [ROOT / 'templates']
    template_roots.extend(
        directory / 'templates'
        for directory in ROOT.iterdir()
        if directory.is_dir() and not directory.name.startswith('.')
    )

    for template_root in template_roots:
        if not template_root.is_dir():
            continue
        for template in template_root.rglob('*.html'):
            for line_number, line in enumerate(
                template.read_text(encoding='utf-8').splitlines(), 1
            ):
                if pattern.search(line) and not any(
                    concept in line for concept in POTENCIA_OTHER_CONCEPTS
                ):
                    relative = template.relative_to(ROOT)
                    remaining.append(f'{relative}:{line_number}: {line.strip()}')

    assert not remaining, '\n'.join(remaining)

    contatos_templates = ROOT / 'contatos' / 'templates' / 'contatos'
    assert '<h1 class="hazon-titulo">Vales</h1>' in (
        contatos_templates / 'prefeituras.html'
    ).read_text(encoding='utf-8')
    for template, label in (
        ('prefeitura_nova.html', 'Novo Vale'),
        ('prefeitura_editar.html', 'Alterar Vale'),
        ('prefeitura_excluir.html', 'Arquivar Vale'),
    ):
        assert label in (contatos_templates / template).read_text(encoding='utf-8')
