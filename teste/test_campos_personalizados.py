"""Testes dos campos personalizados — gestão (tenant) e valores por contato."""
import pytest

from contatos.models import CampoPersonalizado, Contato, ValorCampoPersonalizado


def _cliente_logado(tenant):
    from django.contrib.auth.hashers import make_password
    from django.test import Client

    from acesso.models import Usuario

    u = Usuario.objects.create(
        nome='Dona Aurora', email='dona@campos.com', role='admin_company',
        tenant=tenant, senha=make_password('senha123'),
    )
    c = Client()
    s = c.session
    s['usuario_id'] = u.id
    s['usuario'] = {'nome': u.nome, 'email': u.email, 'role': u.role, 'tenant_id': u.tenant_id}
    s['nicho'] = ''
    s.save()
    return c


@pytest.mark.django_db
def test_cria_campo_personalizado(tenant_aurora):
    campo = CampoPersonalizado.objects.create(
        nome='Plano de saúde', tipo='lista', opcoes='Bronze, Prata, Ouro', tenant=tenant_aurora,
    )
    assert campo.get_tipo_display() == 'Lista'
    assert str(campo) == 'Plano de saúde'


@pytest.mark.django_db
def test_campo_escopado_por_tenant(tenant_aurora, tenant_beta):
    CampoPersonalizado.objects.create(nome='Plano', tenant=tenant_aurora)
    assert CampoPersonalizado.objects.filter(tenant=tenant_beta).count() == 0
    assert CampoPersonalizado.objects.filter(tenant=tenant_aurora).count() == 1


@pytest.mark.django_db
def test_valor_do_campo_no_contato(tenant_aurora):
    campo = CampoPersonalizado.objects.create(nome='Convênio', tenant=tenant_aurora)
    contato = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    ValorCampoPersonalizado.objects.create(contato=contato, campo=campo, valor='Unimed')
    assert contato.valores_campos.get(campo=campo).valor == 'Unimed'


@pytest.mark.django_db
def test_excluir_campo_apaga_valores(tenant_aurora):
    campo = CampoPersonalizado.objects.create(nome='Obs', tenant=tenant_aurora)
    contato = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    ValorCampoPersonalizado.objects.create(contato=contato, campo=campo, valor='x')
    campo.delete()
    assert not ValorCampoPersonalizado.objects.filter(contato=contato).exists()


# --- Fluxo web ---

BASE_POST = {
    'nome': 'Ana', 'seg': 'beleza', 'stage': 'suplica',
    'empresa': 'Clínica Aurora', 'tel': '(11) 98888-7777', 'email': 'ana@aurora.com',
    'valor': '1000', 'procedimento': 'Laser', 'ultima_consulta': '2026-01-15',
}


@pytest.mark.django_db
def test_fluxo_web_cria_contato_com_campo(tenant_aurora):
    c = _cliente_logado(tenant_aurora)
    campo = CampoPersonalizado.objects.create(
        nome='Plano', tipo='lista', opcoes='A, B', tenant=tenant_aurora,
    )
    resp = c.post('/contatos/novo/', {
        **BASE_POST, f'campo_{campo.id}': 'A',
    })
    assert resp.status_code == 302  # redireciona para a ficha
    contato = Contato.objects.get(nome='Ana')
    assert contato.valores_campos.get(campo=campo).valor == 'A'


@pytest.mark.django_db
def test_campo_obrigatorio_bloqueia_criacao(tenant_aurora):
    c = _cliente_logado(tenant_aurora)
    campo = CampoPersonalizado.objects.create(
        nome='Convênio', tipo='texto', obrigatorio=True, tenant=tenant_aurora,
    )
    resp = c.post('/contatos/novo/', {
        **BASE_POST, f'campo_{campo.id}': '',
    })
    assert resp.status_code == 200  # re-renderiza o formulario com erro
    assert not Contato.objects.filter(nome='Ana').exists()
    assert 'Campo obrigatório'.encode() in resp.content


@pytest.mark.django_db
def test_campo_obrigatorio_preenchido_permite_criar(tenant_aurora):
    c = _cliente_logado(tenant_aurora)
    campo = CampoPersonalizado.objects.create(
        nome='Convênio', tipo='texto', obrigatorio=True, tenant=tenant_aurora,
    )
    resp = c.post('/contatos/novo/', {
        **BASE_POST, f'campo_{campo.id}': 'Unimed',
    })
    assert resp.status_code == 302
    assert Contato.objects.get(nome='Ana').valores_campos.get(campo=campo).valor == 'Unimed'


@pytest.mark.django_db
def test_ficha_mostra_campos_formatados(tenant_aurora):
    c = _cliente_logado(tenant_aurora)
    sim = CampoPersonalizado.objects.create(nome='Retorno', tipo='sim_nao', tenant=tenant_aurora)
    data = CampoPersonalizado.objects.create(nome='Próxima consulta', tipo='data', tenant=tenant_aurora)
    contato = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    ValorCampoPersonalizado.objects.create(contato=contato, campo=sim, valor='sim')
    ValorCampoPersonalizado.objects.create(contato=contato, campo=data, valor='2026-09-01')

    resp = c.get(f'/contatos/{contato.id}/')
    html = resp.content.decode()
    assert 'Campos personalizados' in html
    assert 'Retorno' in html and 'Sim' in html
    assert 'Próxima consulta' in html and '01/09/2026' in html


@pytest.mark.django_db
def test_gestao_campos_isola_tenant(tenant_aurora, tenant_beta):
    c_beta = _cliente_logado(tenant_beta)
    CampoPersonalizado.objects.create(nome='Só da Aurora', tenant=tenant_aurora)

    resp = c_beta.get('/contatos/campos/')
    assert resp.status_code == 200
    assert 'Só da Aurora' not in resp.content.decode()

    # editar/excluir campo de outro tenant -> 404
    campo = CampoPersonalizado.objects.get(nome='Só da Aurora')
    assert c_beta.get(f'/contatos/campos/{campo.id}/editar/').status_code == 404
    assert c_beta.get(f'/contatos/campos/{campo.id}/excluir/').status_code == 404


@pytest.mark.django_db
def test_campo_com_espacos_e_salvo_limpo(tenant_aurora):
    c = _cliente_logado(tenant_aurora)
    c.post('/contatos/campos/', {'nome': '  Plano  ', 'tipo': 'texto', 'opcoes': '', 'ordem': '0'})
    campo = CampoPersonalizado.objects.get(tenant=tenant_aurora)
    assert campo.nome == 'Plano'

    # tentar criar de novo (limpo) -> bloqueado como duplicado
    resp = c.post('/contatos/campos/', {'nome': 'Plano', 'tipo': 'texto', 'opcoes': '', 'ordem': '0'})
    assert 'Já existe um campo'.encode() in resp.content
    assert CampoPersonalizado.objects.filter(tenant=tenant_aurora).count() == 1


@pytest.mark.django_db
def test_data_invalida_no_campo_bloqueia_contato(tenant_aurora):
    c = _cliente_logado(tenant_aurora)
    campo = CampoPersonalizado.objects.create(nome='Próxima', tipo='data', tenant=tenant_aurora)
    resp = c.post('/contatos/novo/', {**BASE_POST, f'campo_{campo.id}': '31/02/2026'})
    assert resp.status_code == 200  # re-renderiza com erro
    assert not Contato.objects.filter(nome='Ana').exists()
    assert 'Informe uma data válida'.encode() in resp.content


@pytest.mark.django_db
def test_criar_campo_duplicado_no_tenant(tenant_aurora):
    c = _cliente_logado(tenant_aurora)
    CampoPersonalizado.objects.create(nome='Plano', tenant=tenant_aurora)
    resp = c.post('/contatos/campos/', {
        'nome': 'Plano', 'tipo': 'texto', 'opcoes': '', 'ordem': '0',
    })
    assert resp.status_code == 200  # re-renderiza com erro
    assert 'Já existe um campo'.encode() in resp.content
    assert CampoPersonalizado.objects.filter(nome='Plano', tenant=tenant_aurora).count() == 1
