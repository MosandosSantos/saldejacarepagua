"""Testes da gestao de equipe e do RBAC web (sessao) — convite de membros e restricoes do operacional."""
import pytest
from django.test import Client

from acesso.models import Usuario
from contatos.models import Contato


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = ''
    s.save()
    return c


# --- Acesso à página de equipe ---

@pytest.mark.django_db
def test_operacional_nao_acessa_equipe(usuario_operacional):
    r = _cliente_web(usuario_operacional).get('/equipe/')
    assert r.status_code == 302
    assert r.url == '/dashboard/'


@pytest.mark.django_db
def test_admin_saas_sem_tenant_nao_acessa_equipe(admin_saas):
    r = _cliente_web(admin_saas).get('/equipe/')
    assert r.status_code == 302


@pytest.mark.django_db
def test_admin_company_acessa_equipe(admin_company, usuario_operacional):
    c = _cliente_web(admin_company)
    r = c.get('/equipe/')
    assert r.status_code == 200
    assert usuario_operacional.nome in r.content.decode()


# --- Convite de membros ---

@pytest.mark.django_db
def test_admin_company_convida_operacional(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/equipe/', {'nome': 'Ana Souza', 'email': 'ana@aurora.com',
                            'senha': 'senha123', 'papel': 'operacional'})
    assert r.status_code == 200
    u = Usuario.objects.get(email='ana@aurora.com')
    assert u.role == 'operacional'
    assert u.tenant_id == tenant_aurora.id
    assert 'Ana Souza foi adicionado' in r.content.decode()


@pytest.mark.django_db
def test_convite_isolado_por_tenant(tenant_aurora, tenant_beta, admin_company, usuario_operacional_beta):
    c = _cliente_web(admin_company)
    r = c.get('/equipe/')
    assert r.status_code == 200
    assert usuario_operacional_beta.nome not in r.content.decode()  # beta nao aparece na equipe da aurora


@pytest.mark.django_db
def test_email_duplicado_rejeitado(admin_company, usuario_operacional):
    c = _cliente_web(admin_company)
    r = c.post('/equipe/', {'nome': 'X', 'email': usuario_operacional.email,
                            'senha': 'senha123', 'papel': 'operacional'})
    assert 'Já existe um usuário'.encode() in r.content
    assert Usuario.objects.filter(email=usuario_operacional.email).count() == 1


@pytest.mark.django_db
def test_senha_curta_rejeitada(admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/equipe/', {'nome': 'Ana', 'email': 'ana@aurora.com',
                            'senha': '123', 'papel': 'operacional'})
    assert 'pelo menos 6 caracteres'.encode() in r.content
    assert not Usuario.objects.filter(email='ana@aurora.com').exists()


@pytest.mark.django_db
def test_operacional_nao_convida(usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.post('/equipe/', {'nome': 'X', 'email': 'x@aurora.com', 'senha': 'senha123',
                            'papel': 'operacional'})
    assert r.status_code == 302
    assert not Usuario.objects.filter(email='x@aurora.com').exists()


# --- Restricoes do operacional ---

@pytest.mark.django_db
def test_operacional_nao_exclui_contato(tenant_aurora, usuario_operacional):
    contato = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    c = _cliente_web(usuario_operacional)
    r = c.get(f'/contatos/{contato.id}/excluir/')
    assert r.status_code == 302
    assert r.url == '/contatos/'
    r = c.post(f'/contatos/{contato.id}/excluir/')
    assert Contato.objects.filter(pk=contato.id).exists()  # nao excluiu


@pytest.mark.django_db
def test_operacional_nao_acessa_campos(usuario_operacional):
    c = _cliente_web(usuario_operacional)
    assert c.get('/contatos/campos/').status_code == 302


@pytest.mark.django_db
def test_operacional_nao_ve_botao_excluir(tenant_aurora, usuario_operacional):
    Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    c = _cliente_web(usuario_operacional)
    r = c.get('/contatos/')
    assert r.status_code == 200
    assert "title=\"Excluir\"" not in r.content.decode()


@pytest.mark.django_db
def test_email_invalido_rejeitado(admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/equipe/', {'nome': 'Ana', 'email': 'abc', 'senha': 'senha123', 'papel': 'operacional'})
    assert 'e-mail válido'.encode() in r.content
    assert not Usuario.objects.filter(email='abc').exists()


@pytest.mark.django_db
def test_operacional_nao_exclui_nota(tenant_aurora, usuario_operacional, admin_company):
    from contatos.models import Nota
    contato = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    nota = Nota.objects.create(contato=contato, texto='x', autor=admin_company)
    c = _cliente_web(usuario_operacional)
    c.post(f'/contatos/{contato.id}/notas/{nota.id}/excluir/')
    assert Nota.objects.filter(pk=nota.id).exists()


@pytest.mark.django_db
def test_operacional_nao_remove_tag(tenant_aurora, usuario_operacional):
    from contatos.models import Tag
    contato = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    tag = Tag.objects.create(nome='VIP', tenant=tenant_aurora)
    contato.tags.add(tag)
    c = _cliente_web(usuario_operacional)
    c.post(f'/contatos/{contato.id}/tags/{tag.id}/remover/')
    assert contato.tags.filter(pk=tag.id).exists()


@pytest.mark.django_db
def test_admin_company_exclui_contato(tenant_aurora, admin_company):
    contato = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    c = _cliente_web(admin_company)
    r = c.post(f'/contatos/{contato.id}/excluir/')
    assert r.status_code == 302
    assert not Contato.objects.filter(pk=contato.id).exists()


# --- Transferência de dono ---

@pytest.mark.django_db
def test_dono_transfere_para_membro(tenant_aurora, admin_company, usuario_operacional):
    c = _cliente_web(admin_company)
    r = c.post('/config/', {'acao': 'transferir_dono', 'usuario_id': str(usuario_operacional.id)})
    assert r.status_code == 200
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.dono_id == usuario_operacional.id
    # o antigo dono continua admin da clínica (só perde a propriedade)
    admin_company.refresh_from_db()
    assert admin_company.role == 'admin_company'
    assert 'agora é o(a) novo(a) dono(a)' in r.content.decode()


@pytest.mark.django_db
def test_so_o_dono_transfere(tenant_aurora, admin_company, usuario_operacional):
    from teste.conftest import criar_usuario

    carlos = criar_usuario('Carlos', 'carlos@aurora.com', 'admin_company', tenant_aurora)
    tenant_aurora.dono = admin_company
    tenant_aurora.save(update_fields=['dono'])
    c = _cliente_web(carlos)  # outro admin_company, mas NÃO é o dono
    r = c.post('/config/', {'acao': 'transferir_dono', 'usuario_id': str(usuario_operacional.id)})
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.dono_id == admin_company.id  # nada mudou
    assert 'Somente o(a) dono(a) da empresa' in r.content.decode()


@pytest.mark.django_db
def test_nao_pode_transferir_para_si(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/config/', {'acao': 'transferir_dono', 'usuario_id': str(admin_company.id)})
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.dono_id is None  # dono ainda não definido (não transferiu)
    assert 'Você já é o(a) dono(a)' in r.content.decode()


@pytest.mark.django_db
def test_transferencia_isolada_por_tenant(
    tenant_aurora, admin_company, usuario_operacional_beta
):
    c = _cliente_web(admin_company)
    r = c.post('/config/', {'acao': 'transferir_dono', 'usuario_id': str(usuario_operacional_beta.id)})
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.dono_id is None  # membro de outro tenant não existe aqui
    assert 'não encontrado nesta empresa' in r.content.decode()


@pytest.mark.django_db
def test_equipe_mostra_badge_dono_e_botao(tenant_aurora, admin_company, usuario_operacional):
    tenant_aurora.dono = admin_company
    tenant_aurora.save(update_fields=['dono'])
    c = _cliente_web(admin_company)
    html = c.get('/config/').content.decode()
    assert '👑 Dono' in html
    assert 'Transferir dono' in html  # botão aparece para o operacional


@pytest.mark.django_db
def test_nao_dono_nao_ve_botao_transferir(tenant_aurora, admin_company, usuario_operacional):
    from teste.conftest import criar_usuario

    carlos = criar_usuario('Carlos', 'carlos@aurora.com', 'admin_company', tenant_aurora)
    tenant_aurora.dono = admin_company
    tenant_aurora.save(update_fields=['dono'])
    c = _cliente_web(carlos)
    html = c.get('/config/').content.decode()
    assert 'Transferir dono' not in html  # só o dono enxerga o botão
