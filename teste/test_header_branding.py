import re

import pytest
from django.test import Client


@pytest.mark.django_db
def test_header_exibe_vales_marca_amorio_e_logo(tenant_aurora, usuario_operacional):
    client = Client()
    session = client.session
    session['usuario_id'] = usuario_operacional.id
    session['usuario'] = {
        'nome': usuario_operacional.nome,
        'email': usuario_operacional.email,
        'role': usuario_operacional.role,
        'tenant_id': usuario_operacional.tenant_id,
    }
    session['nicho'] = 'saude'
    session.save()

    response = client.get('/dashboard/')

    assert response.status_code == 200
    html = response.content.decode('utf-8')
    link_vales = re.search(
        r'<a href="/vales/"[^>]*>(.*?)</a>', html, re.DOTALL,
    )
    assert link_vales is not None
    assert 'Vale' in link_vales.group(1)
    assert 'AMORIO' in html
    assert 'src="/static/img/logow.webp"' in html
    assert 'href="/static/img/logow.webp"' in html
