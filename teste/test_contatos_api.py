"""Testes dos endpoints de contatos (/api/v1/contatos) — auth obrigatoria + isolamento por tenant."""
import pytest

from contatos.models import Contato, Negocio


@pytest.fixture
def contato_existente(tenant_aurora):
    contato = Contato.objects.create(
        nome='Mariana Fontes',
        empresa='Clínica Aurora',
        tel='(11) 98888-7777',
        email='mariana@aurora.com',
        seg='derma',
        procedimento='Laser CO2',
        origem='Instagram',
        pagamento='Particular',
        tenant=tenant_aurora,
    )
    Negocio.objects.create(
        contato=contato, titulo=contato.nome, stage='comunicacao',
        valor=14500.00, tenant=tenant_aurora,
    )
    return contato


@pytest.mark.django_db(transaction=True)
def test_lista_contatos_sem_token_rejeitado(client):
    resp = client.get('/api/v1/contatos')

    assert resp.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_lista_contatos_vazio(client, headers_operacional):
    resp = client.get('/api/v1/contatos', headers=headers_operacional)

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db(transaction=True)
def test_cria_contato(client, headers_operacional):
    resp = client.post('/api/v1/contatos', headers=headers_operacional, json={
        'nome': 'Ana Souza',
        'seg': 'beleza',
        'stage': 'suplica',
        'valor': 1500.5,
        'procedimento': 'Harmonização facial',
        'origem': 'Instagram',
        'pagamento': 'Particular',
    })

    assert resp.status_code == 201
    dados = resp.json()
    assert dados['id'] > 0
    assert dados['nome'] == 'Ana Souza'
    assert dados['stage'] == 'suplica'
    assert dados['valor'] == 1500.5
    assert dados['procedimento'] == 'Harmonização facial'
    assert dados['empresa'] == '—'
    assert dados['tel'] == '—'
    assert dados['updated_at'] is not None


@pytest.mark.django_db(transaction=True)
def test_cria_contato_sem_nome_rejeitado(client, headers_operacional):
    resp = client.post('/api/v1/contatos', headers=headers_operacional,
                       json={'seg': 'beleza', 'stage': 'suplica'})

    assert resp.status_code == 422


@pytest.mark.django_db(transaction=True)
def test_cria_contato_com_valor_negativo_rejeitado(client, headers_operacional):
    resp = client.post('/api/v1/contatos', headers=headers_operacional, json={
        'nome': 'X', 'seg': 'beleza', 'stage': 'suplica', 'valor': -5,
    })

    assert resp.status_code == 422


@pytest.mark.django_db(transaction=True)
def test_obtem_contato_por_id(client, contato_existente, headers_operacional):
    resp = client.get(f'/api/v1/contatos/{contato_existente.id}', headers=headers_operacional)

    assert resp.status_code == 200
    assert resp.json()['nome'] == 'Mariana Fontes'
    assert resp.json()['empresa'] == 'Clínica Aurora'


@pytest.mark.django_db(transaction=True)
def test_obtem_contato_inexistente(client, headers_operacional):
    resp = client.get('/api/v1/contatos/99999', headers=headers_operacional)

    assert resp.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_atualiza_contato(client, contato_existente, headers_operacional):
    resp = client.put(f'/api/v1/contatos/{contato_existente.id}', headers=headers_operacional, json={
        'nome': 'Mariana Fontes Atualizada',
        'seg': 'derma',
        'stage': 'diploma',
        'valor': 18000.00,
        'procedimento': 'Laser CO2 + Toxina',
    })

    assert resp.status_code == 200
    dados = resp.json()
    assert dados['nome'] == 'Mariana Fontes Atualizada'
    assert dados['stage'] == 'diploma'
    assert dados['valor'] == 18000.0
    assert dados['email'] == '—'


@pytest.mark.django_db(transaction=True)
def test_atualiza_contato_inexistente(client, headers_operacional):
    resp = client.put('/api/v1/contatos/99999', headers=headers_operacional, json={
        'nome': 'X', 'seg': 'beleza', 'stage': 'suplica',
    })

    assert resp.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_move_etapa_do_contato(client, contato_existente, headers_operacional):
    resp = client.patch(f'/api/v1/contatos/{contato_existente.id}/stage',
                        headers=headers_operacional, json={'stage': 'iniciacao'})

    assert resp.status_code == 200
    assert resp.json()['stage'] == 'iniciacao'


@pytest.mark.django_db(transaction=True)
def test_move_etapa_contato_inexistente(client, headers_operacional):
    resp = client.patch('/api/v1/contatos/99999/stage', headers=headers_operacional,
                        json={'stage': 'diploma'})

    assert resp.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_move_etapa_com_stage_vazio_rejeitado(client, contato_existente, headers_operacional):
    resp = client.patch(f'/api/v1/contatos/{contato_existente.id}/stage',
                        headers=headers_operacional, json={'stage': ''})

    assert resp.status_code == 422


@pytest.mark.django_db(transaction=True)
def test_exclui_contato(client, contato_existente, headers_operacional):
    resp = client.delete(f'/api/v1/contatos/{contato_existente.id}', headers=headers_operacional)

    assert resp.status_code == 204
    assert not Contato.objects.filter(pk=contato_existente.id).exists()


@pytest.mark.django_db(transaction=True)
def test_exclui_contato_inexistente(client, headers_operacional):
    resp = client.delete('/api/v1/contatos/99999', headers=headers_operacional)

    assert resp.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_fluxo_completo_crud(client, headers_operacional):
    criar = client.post('/api/v1/contatos', headers=headers_operacional, json={
        'nome': 'Fluxo Completo', 'seg': 'fisio', 'stage': 'suplica', 'valor': 800,
    })
    contato_id = criar.json()['id']

    lista = client.get('/api/v1/contatos', headers=headers_operacional)
    assert any(item['id'] == contato_id for item in lista.json())

    mover = client.patch(f'/api/v1/contatos/{contato_id}/stage', headers=headers_operacional,
                         json={'stage': 'diploma'})
    assert mover.json()['stage'] == 'diploma'

    excluir = client.delete(f'/api/v1/contatos/{contato_id}', headers=headers_operacional)
    assert excluir.status_code == 204

    sumido = client.get(f'/api/v1/contatos/{contato_id}', headers=headers_operacional)
    assert sumido.status_code == 404


# --- Isolamento multi-tenant ---

@pytest.mark.django_db(transaction=True)
def test_tenant_nao_ve_contato_de_outro_tenant(client, contato_existente, headers_operacional_beta):
    lista = client.get('/api/v1/contatos', headers=headers_operacional_beta)
    assert lista.status_code == 200
    assert all(item['id'] != contato_existente.id for item in lista.json())

    obter = client.get(f'/api/v1/contatos/{contato_existente.id}', headers=headers_operacional_beta)
    assert obter.status_code == 404

    atualizar = client.put(f'/api/v1/contatos/{contato_existente.id}', headers=headers_operacional_beta,
                           json={'nome': 'X', 'seg': 'beleza', 'stage': 'suplica'})
    assert atualizar.status_code == 404

    mover = client.patch(f'/api/v1/contatos/{contato_existente.id}/stage', headers=headers_operacional_beta,
                         json={'stage': 'diploma'})
    assert mover.status_code == 404

    excluir = client.delete(f'/api/v1/contatos/{contato_existente.id}', headers=headers_operacional_beta)
    assert excluir.status_code == 404
    assert Contato.objects.filter(pk=contato_existente.id).exists()


@pytest.mark.django_db(transaction=True)
def test_admin_saas_ve_todos_os_tenants(client, contato_existente, headers_admin_saas):
    resp = client.get('/api/v1/contatos', headers=headers_admin_saas)

    assert resp.status_code == 200
    assert any(item['id'] == contato_existente.id for item in resp.json())


@pytest.mark.django_db(transaction=True)
def test_contato_criado_fica_no_tenant_do_usuario(client, headers_operacional, headers_operacional_beta):
    criado = client.post('/api/v1/contatos', headers=headers_operacional, json={
        'nome': 'Só da Aurora', 'seg': 'odonto', 'stage': 'suplica',
    })
    assert criado.status_code == 201
    contato_id = criado.json()['id']

    do_beta = client.get('/api/v1/contatos', headers=headers_operacional_beta)
    assert all(item['id'] != contato_id for item in do_beta.json())

    do_aurora = client.get('/api/v1/contatos', headers=headers_operacional)
    assert any(item['id'] == contato_id for item in do_aurora.json())
