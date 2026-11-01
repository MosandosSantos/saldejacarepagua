from types import SimpleNamespace
from unittest.mock import Mock

from django.template.loader import render_to_string
from django.urls import resolve, reverse

from contatos.models import Filiacao
from contatos.views.gprb_membros import _formatar_membro_lista


def test_member_crud_has_canonical_members_urls():
    assert reverse('membros:novo') == '/membros/novo/'
    assert reverse('membros:detalhe', kwargs={'pk': '6'}) == '/membros/6/'
    assert reverse('membros:editar', kwargs={'pk': '6'}) == '/membros/6/editar/'
    assert reverse('membros:excluir', kwargs={'pk': '6'}) == '/membros/6/excluir/'

    assert resolve('/membros/novo/').func.__name__ == 'membro_novo'
    assert resolve('/membros/6/').func.__name__ == 'membro_detalhe'
    assert resolve('/membros/6/editar/').func.__name__ == 'membro_editar'
    assert resolve('/membros/6/excluir/').func.__name__ == 'membro_excluir'


def test_filiacao_tracks_unknown_initiation_and_status_by_default():
    filiacao = Filiacao()
    assert filiacao.iniciado is None
    assert filiacao.ativo is None
    for campo in ('iniciado', 'ativo'):
        assert Filiacao._meta.get_field(campo).null


def test_member_drill_down_uses_link_status_and_excludes_inactive_shops():
    lojas = [
        SimpleNamespace(pk=1, nome='Loja ativa', situacao='ATIVA'),
        SimpleNamespace(pk=2, nome='Loja inativa', situacao='INATIVA'),
        SimpleNamespace(pk=3, nome='Sem filiação', situacao='ATIVA'),
    ]
    membro = Mock()
    membro.pk = 7
    membro.nome = 'Membro'
    membro.situacao = 'ATIVO'
    membro.cadastro_numero = 42
    membro.lojas.all.return_value.order_by.return_value = lojas
    membro.filiacoes.all.return_value = [
        SimpleNamespace(loja_id=1, iniciado=True, ativo=False),
    ]
    membro.graus.select_related.return_value.order_by.return_value.first.return_value = None
    membro.graus.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = None

    dados = _formatar_membro_lista(membro, 2026, False, {})

    assert dados['lojas_expandir'] == [
        {'loja': 'Loja ativa', 'iniciado': True, 'ativo': False},
        {'loja': 'Sem filiação', 'iniciado': None, 'ativo': None},
    ]


def test_member_drill_down_renders_link_information_and_empty_state():
    html = render_to_string('contatos/lista.html', {
        'itens': [
            {'id': 7, 'nome': 'Membro', 'lojas_expandir': [
                {'loja': 'Loja <segura>', 'iniciado': True, 'ativo': False},
                {'loja': 'Outra loja', 'iniciado': False, 'ativo': True},
                {'loja': 'Sem dados', 'iniciado': None, 'ativo': None},
            ]},
            {'id': 8, 'nome': 'Sem lojas', 'lojas_expandir': []},
        ],
    })
    assert 'Loja &lt;segura&gt;' in html
    assert 'Iniciação' in html
    assert 'Cargo' in html
    assert 'Não iniciado' in html
    assert 'Iniciado' in html
    assert 'Inativo' in html
    assert 'Ativo' in html
    assert 'Não informado' in html
    assert 'Nenhuma loja ativa vinculada a este membro.' in html
    assert 'aria-label="Expandir lojas do membro"' in html
    assert 'class="expand-icon' in html
    assert 'aria-hidden="true">+</span>' in html
    assert 'rounded-full bg-[#5b8def]/15 font-display' not in html
    assert 'Loja simbólica' not in html
    assert 'colspan="5"' not in html
    assert 'id="detalhe-7" style="display:none;"' in html
    assert "linha.style.display = aberto ? 'none' : '';" in html
    assert 'onclick="alternarDetalhe' not in html
    assert "document.querySelectorAll('.btn-expand-membro')" in html
    assert "botao.addEventListener('click'" in html
    inicio_nome = html.index('aria-controls="detalhe-7"')
    fim_nome = html.index('>Membro</span>', inicio_nome)
    assert inicio_nome < fim_nome


def test_legacy_contacts_member_url_remains_an_alias():
    match = resolve('/contatos/membro/6/')

    assert match.url_name == 'membro_detalhe'
    assert match.func.__name__ == 'membro_detalhe'
