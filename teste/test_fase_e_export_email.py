"""Testes da Fase E — exportacao CSV, negocios estagnados e e-mail marketing."""
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from contatos.models import Contato, Negocio, criar_negocio
from emails.models import EmailEnviado, ModeloEmail


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = ''
    s.save()
    return c


# ---------------------------------------------------------------------------
# Exportação CSV
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_exportar_contatos_csv(tenant_aurora, admin_company):
    co = Contato.objects.create(nome='Ana Teste', seg='beleza', tenant=tenant_aurora,
                                email='ana@teste.com', empresa='Aurora')
    criar_negocio(co, stage='comunicacao', valor=1500.50, tenant_id=tenant_aurora.id)
    r = _cliente_web(admin_company).get('/contatos/exportar/')
    assert r.status_code == 200
    assert r['Content-Type'].startswith('text/csv')
    conteudo = r.content.decode('utf-8-sig')  # BOM removido pelo decode
    assert 'Ana Teste' in conteudo
    assert 'ana@teste.com' in conteudo
    assert '1500,50' in conteudo
    assert 'comunicacao' in conteudo


@pytest.mark.django_db
def test_exportar_contatos_isolado_por_tenant(tenant_aurora, tenant_beta, admin_company):
    Contato.objects.create(nome='Sigiloso Beta', seg='', tenant=tenant_beta, email='beta@x.com')
    r = _cliente_web(admin_company).get('/contatos/exportar/')
    assert 'Sigiloso Beta' not in r.content.decode('utf-8-sig')


@pytest.mark.django_db
def test_exportar_negocios_csv(tenant_aurora, admin_company):
    co = Contato.objects.create(nome='Ana Teste', seg='', tenant=tenant_aurora)
    criar_negocio(co, titulo='Laser CO2', stage='diploma', valor=3000, tenant_id=tenant_aurora.id)
    r = _cliente_web(admin_company).get('/contatos/exportar/negocios/')
    assert r.status_code == 200
    conteudo = r.content.decode('utf-8-sig')
    assert 'Ana Teste' in conteudo
    assert 'Laser CO2' in conteudo
    assert '3000,00' in conteudo or '3000' in conteudo
    assert 'Sim' in conteudo  # principal


@pytest.mark.django_db
def test_csv_bloqueia_injecao_de_formula(tenant_aurora, admin_company):
    """CSV injection: celulas com =,+,-,@ viram texto (apostrofo) no Excel."""
    Contato.objects.create(nome='=1+1', seg='', tenant=tenant_aurora, observacoes='@cmd|calc')
    conteudo = _cliente_web(admin_company).get('/contatos/exportar/').content.decode('utf-8-sig')
    assert "'=1+1" in conteudo
    assert "'@cmd|calc" in conteudo


# ---------------------------------------------------------------------------
# Negócios estagnados
# ---------------------------------------------------------------------------

def _negocio_antigo(tenant, stage='comunicacao', dias=10, nome='Ana'):
    co = Contato.objects.create(nome=nome, seg='', tenant=tenant)
    n = criar_negocio(co, stage=stage, valor=1000, tenant_id=tenant.id)
    Negocio.objects.filter(pk=n.id).update(updated_at=timezone.now() - timedelta(days=dias))
    return n


@pytest.mark.django_db
def test_estagnados_aparecem_no_funil(tenant_aurora, admin_company):
    n = _negocio_antigo(tenant_aurora, dias=10)
    html = _cliente_web(admin_company).get('/recepcao/').content.decode()
    assert 'Negócios parados' in html
    assert n.contato.nome in html
    assert 'parado há 10 dias' in html


@pytest.mark.django_db
def test_estagnados_nao_mostra_recente(tenant_aurora, admin_company):
    co = Contato.objects.create(nome='Recente', seg='', tenant=tenant_aurora)
    criar_negocio(co, stage='comunicacao', valor=1000, tenant_id=tenant_aurora.id)  # updated_at = agora
    html = _cliente_web(admin_company).get('/recepcao/').content.decode()
    assert 'Negócios parados' not in html


@pytest.mark.django_db
def test_estagnados_ignoram_fechados(tenant_aurora, admin_company):
    _negocio_antigo(tenant_aurora, stage='diploma', dias=30)
    html = _cliente_web(admin_company).get('/recepcao/').content.decode()
    assert 'Negócios parados' not in html


@pytest.mark.django_db
def test_dias_configuravel(tenant_aurora, admin_company):
    _negocio_antigo(tenant_aurora, dias=5)
    html = _cliente_web(admin_company).get('/recepcao/?dias=3').content.decode()
    assert 'Negócios parados' in html  # com janela de 3 dias o de 5 aparece


# ---------------------------------------------------------------------------
# E-mail marketing — templates
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_criar_modelo_email(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/emails/novo/', {
        'nome': 'Lembrete de retorno',
        'assunto': 'Olá {{nome}}, volte para a clínica!',
        'corpo': 'Oi {{nome}}, saudades da {{empresa}}.',
    })
    assert r.status_code == 302
    modelo = ModeloEmail.objects.get(nome='Lembrete de retorno')
    assert modelo.tenant_id == tenant_aurora.id
    html = c.get('/emails/').content.decode()
    assert 'Lembrete de retorno' in html


@pytest.mark.django_db
def test_modelo_isolado_por_tenant(tenant_aurora, tenant_beta, admin_company):
    ModeloEmail.objects.create(tenant=tenant_aurora, nome='Da Aurora', assunto='X', corpo='Y')
    from teste.conftest import criar_usuario
    beta_admin = criar_usuario('Beta', 'beta@b.com', 'admin_company', tenant_beta)
    html = _cliente_web(beta_admin).get('/emails/').content.decode()
    assert 'Da Aurora' not in html


@pytest.mark.django_db
def test_viewer_nao_cria_modelo(tenant_aurora, usuario_viewer):
    r = _cliente_web(usuario_viewer).post('/emails/novo/', {
        'nome': 'X', 'assunto': 'Y', 'corpo': 'Z',
    })
    assert r.status_code == 302
    assert not ModeloEmail.objects.filter(nome='X').exists()


@pytest.mark.django_db
def test_admin_saas_sem_tenant_nao_cria_modelo(admin_saas):
    """admin_saas (sem tenant) não quebra o módulo — volta pro dashboard sem criar."""
    r = _cliente_web(admin_saas).post('/emails/novo/', {
        'nome': 'X', 'assunto': 'Y', 'corpo': 'Z',
    })
    assert r.status_code == 302
    assert r.url == '/dashboard/'
    assert not ModeloEmail.objects.filter(nome='X').exists()


# ---------------------------------------------------------------------------
# E-mail marketing — envio individual e campanha
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_envio_individual_simulado(tenant_aurora, admin_company):
    co = Contato.objects.create(nome='Ana Teste', seg='', tenant=tenant_aurora, email='ana@teste.com')
    modelo = ModeloEmail.objects.create(
        tenant=tenant_aurora, nome='Boas vindas', assunto='Oi {{nome}}', corpo='Olá {{nome}}!',
    )
    r = _cliente_web(admin_company).post(f'/emails/enviar/{co.id}/', {'modelo_id': modelo.id})
    assert r.status_code == 302
    envio = EmailEnviado.objects.get(contato=co)
    assert envio.destinatario == 'ana@teste.com'
    assert envio.assunto == 'Oi Ana Teste'
    assert envio.corpo.startswith('Olá Ana Teste!')
    assert envio.status == 'simulado'  # sem SMTP configurado
    assert f'/emails/aberto/{envio.token}/' in envio.corpo  # pixel de abertura


@pytest.mark.django_db
def test_envio_individual_requer_edicao(tenant_aurora, usuario_viewer):
    co = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora, email='ana@x.com')
    modelo = ModeloEmail.objects.create(tenant=tenant_aurora, nome='M', assunto='A', corpo='B')
    r = _cliente_web(usuario_viewer).post(f'/emails/enviar/{co.id}/', {'modelo_id': modelo.id})
    assert r.status_code == 302
    assert not EmailEnviado.objects.filter(contato=co).exists()


@pytest.mark.django_db
def test_campanha_filtra_publico(tenant_aurora, admin_company):
    with_email = Contato.objects.create(nome='Com Email', seg='beleza', tenant=tenant_aurora, email='a@x.com')
    sem_email = Contato.objects.create(nome='Sem Email', seg='beleza', tenant=tenant_aurora)
    outro_seg = Contato.objects.create(nome='Outro Seg', seg='odonto', tenant=tenant_aurora, email='b@x.com')
    modelo = ModeloEmail.objects.create(tenant=tenant_aurora, nome='Camp', assunto='{{nome}}', corpo='Corpo')
    c = _cliente_web(admin_company)
    r = c.post('/emails/campanha/', {'modelo_id': modelo.id, 'seg': 'beleza'})
    assert r.status_code == 302
    envios = EmailEnviado.objects.all()
    assert envios.count() == 1  # só o com e-mail no segmento
    assert envios.first().contato == with_email
    assert EmailEnviado.objects.filter(contato=sem_email).count() == 0
    assert EmailEnviado.objects.filter(contato=outro_seg).count() == 0
    # pré-visualização de público
    html = c.get(f'/emails/campanha/?modelo_id={modelo.id}&seg=beleza').content.decode()
    assert 'público estimado' in html.lower() or 'Público estimado' in html


@pytest.mark.django_db
def test_pixel_rastreia_abertura(tenant_aurora, admin_company):
    co = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora, email='ana@x.com')
    envio = EmailEnviado.objects.create(
        tenant=tenant_aurora, contato=co, assunto='A', corpo='B', destinatario='ana@x.com',
    )
    c = _cliente_web(admin_company)
    r = c.get(f'/emails/aberto/{envio.token}/')
    assert r.status_code == 200
    assert r['Content-Type'].startswith('image/gif')
    envio.refresh_from_db()
    assert envio.aberto_em is not None
    primeiro = envio.aberto_em
    c.get(f'/emails/aberto/{envio.token}/')
    envio.refresh_from_db()
    assert envio.aberto_em == primeiro  # não sobrescreve

    # pixel não exige login e token desconhecido é 404
    r = Client().get(f'/emails/aberto/{envio.token}/')
    assert r.status_code == 200
    assert Client().get('/emails/aberto/00000000-0000-0000-0000-000000000000/').status_code == 404
