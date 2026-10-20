from datetime import date

import pytest
from django.template.loader import render_to_string


def _criar_membro_com_graus(tenant, nome, numeros, situacao='ATIVO'):
    from contatos.models import Grau, GrauMembro, Membro

    membro = Membro.objects.create(
        tenant=tenant, nome=nome, situacao=situacao,
    )
    for numero in numeros:
        grau, _ = Grau.objects.get_or_create(
            numero=numero,
            defaults={'nome': f'Grau {numero}'},
        )
        GrauMembro.objects.create(
            tenant=tenant, membro=membro, grau=grau, data=date(2026, 10, 12),
        )
    return membro


@pytest.mark.django_db
def test_dashboard_pyramid_counts_active_members_by_highest_degree_and_tenant(
    tenant_aurora, tenant_beta,
):
    from dashboard.views import _buscar_dados_baii

    _criar_membro_com_graus(tenant_aurora, 'Base', [4, 14])
    _criar_membro_com_graus(tenant_aurora, 'Grau 15', [15])
    _criar_membro_com_graus(tenant_aurora, 'Maior grau prevalece', [4, 18])
    _criar_membro_com_graus(tenant_aurora, 'Grau 19', [19])
    _criar_membro_com_graus(tenant_aurora, 'Grau 30', [30])
    _criar_membro_com_graus(tenant_aurora, 'Grau 31', [31])
    _criar_membro_com_graus(tenant_aurora, 'Grau 32', [32])
    _criar_membro_com_graus(tenant_aurora, 'Grau 33', [33])
    _criar_membro_com_graus(tenant_aurora, 'Inativo', [33], situacao='INATIVO')
    _criar_membro_com_graus(tenant_aurora, 'Sem grau', [])
    _criar_membro_com_graus(tenant_beta, 'Outro tenant', [33])

    dados = _buscar_dados_baii(tenant_aurora.pk)
    fatias = dados['baii_ativos']

    assert [
        (fatia['name'], fatia.get('label'), fatia['count'])
        for fatia in fatias
    ] == [
        ('4–14', 'Perfeição', 1),
        ('15–18', 'Capítulo', 2),
        ('19–30', 'Kadosh', 2),
        ('31–32', 'Consistório', 2),
        ('33', 'SCREAA', 1),
    ]
    assert dados['baii_ativos_total'] == 8
    assert all(fatia['name'] in dados['baii_ativos_svg'] for fatia in fatias)

    html = render_to_string('dashboard/partials/_baii.html', {
        'baii': fatias,
        'baii_svg': dados['baii_ativos_svg'],
        'baii_total': dados['baii_ativos_total'],
    })
    for rotulo in (
        '4–14 · Perfeição',
        '15–18 · Capítulo',
        '19–30 · Kadosh',
        '31–32 · Consistório',
        '33 · SCREAA',
    ):
        assert rotulo in html


@pytest.mark.django_db
def test_dashboard_pyramid_keeps_empty_degree_bands(tenant_aurora):
    from dashboard.views import _buscar_dados_baii

    _criar_membro_com_graus(tenant_aurora, 'Membro da base', [14])

    dados = _buscar_dados_baii(tenant_aurora.pk)

    assert [
        (fatia['name'], fatia['count']) for fatia in dados['baii_ativos']
    ] == [
        ('4–14', 1),
        ('15–18', 0),
        ('19–30', 0),
        ('31–32', 0),
        ('33', 0),
    ]
    assert dados['baii_ativos_svg']
