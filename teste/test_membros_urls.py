from django.urls import resolve, reverse


def test_member_crud_has_canonical_members_urls():
    assert reverse('membros:novo') == '/membros/novo/'
    assert reverse('membros:detalhe', kwargs={'pk': '6'}) == '/membros/6/'
    assert reverse('membros:editar', kwargs={'pk': '6'}) == '/membros/6/editar/'
    assert reverse('membros:excluir', kwargs={'pk': '6'}) == '/membros/6/excluir/'

    assert resolve('/membros/novo/').func.__name__ == 'membro_novo'
    assert resolve('/membros/6/').func.__name__ == 'membro_detalhe'
    assert resolve('/membros/6/editar/').func.__name__ == 'membro_editar'
    assert resolve('/membros/6/excluir/').func.__name__ == 'membro_excluir'


def test_legacy_contacts_member_url_remains_an_alias():
    match = resolve('/contatos/membro/6/')

    assert match.url_name == 'membro_detalhe'
    assert match.func.__name__ == 'membro_detalhe'
