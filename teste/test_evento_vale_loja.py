"""Escopo de Vale/Loja no modal Novo Evento (regras por cargo).

- admin_saas/ADM: qualquer Vale/Loja (com tenant selecionado).
- delegado: só lojas do Vale dele (prefeitura_id).
- presidente de loja/secretário: apenas a loja deles.
- demais cargos: sem botão e POST recusado.
"""
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.models import (
    ROLE_ADMIN_SAAS, ROLE_DELEGADO, ROLE_SECRETARIO, ROLE_TESOUREIRO,
    Tenant, Usuario,
)
from acesso.session import iniciar_sessao
from contatos.models import Loja, Vale
from tarefas.models import Evento

pytestmark = pytest.mark.django_db(transaction=True)


def _mundo():
    """Tenants/vales/lojas/usuarios de teste (ids únicos por execução)."""
    sufixo = uuid4().hex
    tenant_a = Tenant.objects.create(nome='Vale A', slug=f'vale-a-{sufixo}')
    tenant_b = Tenant.objects.create(nome='Vale B', slug=f'vale-b-{sufixo}')
    vale_a = Vale.objects.create(tenant=tenant_a, nome='Vale A', sigla=sufixo[:2] + 'A')
    vale_b = Vale.objects.create(tenant=tenant_b, nome='Vale B', sigla=sufixo[:2] + 'B')
    loja1 = Loja.objects.create(tenant=tenant_a, nome='Loja A1')
    loja2 = Loja.objects.create(tenant=tenant_a, nome='Loja A2')
    loja3 = Loja.objects.create(tenant=tenant_b, nome='Loja B1')

    def _usuario(role, loja_id='', prefeitura_id='', tenant=None):
        return Usuario.objects.create(
            nome=f'Usuário {sufixo} {role}',
            email=f'ev-{sufixo}-{role}@example.test',
            senha=make_password('senha123'),
            role=role,
            tenant=tenant,
            loja_id=str(loja_id),
            prefeitura_id=str(prefeitura_id),
        )

    delegado = _usuario('delegado', tenant=tenant_a, prefeitura_id=vale_a.pk)
    secretario = _usuario('secretario', tenant=tenant_a, loja_id=loja1.pk)
    tesoureiro = _usuario('tesoureiro', tenant=tenant_a, loja_id=loja1.pk)
    admin = _usuario('admin_saas', tenant=None)
    return SimpleNamespace(
        tenant_a=tenant_a, tenant_b=tenant_b, vale_a=vale_a, vale_b=vale_b,
        loja1=loja1, loja2=loja2, loja3=loja3,
        delegado=delegado, secretario=secretario, tesoureiro=tesoureiro, admin=admin,
    )


def _cliente(usuario, admin_tenant_id=None):
    client = Client(enforce_csrf_checks=False, raise_request_exception=False)
    sess = client.session
    iniciar_sessao(SimpleNamespace(session=sess), usuario)
    if admin_tenant_id is not None:
        sess['admin_tenant_id'] = admin_tenant_id
    sess.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = sess.session_key
    return client


def _payload(loja=None):
    dados = {
        'titulo': "Evento de teste",
        'data_inicio': '2026-11-10T19:00',
        'tipo': 'iniciacao_grau_4',
    }
    if loja is not None:
        dados['loja'] = loja
    return dados


def test_delegado_cria_evento_na_loja_do_vale_dele():
    """Delegado: POST com JSON e loja do próprio Vale grava com o id da loja."""
    mundo = _mundo()
    client = _cliente(mundo.delegado)

    resposta = client.post(
        '/tarefas/eventos/criar/',
        json.dumps(_payload(mundo.loja1.pk)),
        content_type='application/json',
    )

    assert resposta.status_code == 200, resposta.content
    ev = Evento.objects.get(loja_id=str(mundo.loja1.pk))
    assert ev.titulo == 'Evento de teste'


def test_delegado_fora_do_vale_403():
    mundo = _mundo()
    client = _cliente(mundo.delegado)
    resposta = client.post(
        '/tarefas/eventos/criar/',
        json.dumps(_payload(mundo.loja3.pk)),
        content_type='application/json',
    )
    assert resposta.status_code == 403


def test_secretario_so_para_a_loja_dele():
    mundo = _mundo()
    client = _cliente(mundo.secretario)

    ok = client.post(
        '/tarefas/eventos/criar/',
        json.dumps(_payload(mundo.loja1.pk)),
        content_type='application/json',
    )
    assert ok.status_code == 200

    fora = client.post(
        '/tarefas/eventos/criar/',
        json.dumps(_payload(mundo.loja2.pk)),
        content_type='application/json',
    )
    assert fora.status_code == 403


def test_secretario_sem_loja_no_payload_usa_loja_da_sessao():
    mundo = _mundo()
    client = _cliente(mundo.secretario)

    resposta = client.post(
        '/tarefas/eventos/criar/',
        json.dumps({
            'titulo': 'Evento fallback',
            'data_inicio': '2026-11-10T19:00',
            'tipo': 'iniciacao_grau_4',
        }),
        content_type='application/json',
    )

    assert resposta.status_code == 200
    assert Evento.objects.get(titulo='Evento fallback').loja_id == str(mundo.loja1.pk)


def test_tesoureiro_nao_cria_nem_ve_botao():
    mundo = _mundo()
    client = _cliente(mundo.tesoureiro)

    resposta = client.post(
        '/tarefas/eventos/criar/',
        json.dumps(_payload(mundo.loja1.pk)),
        content_type='application/json',
    )
    assert resposta.status_code == 403

    pagina = client.get('/tarefas/ranking/')
    assert pagina.context['pode_criar_evento'] is False


def test_admin_sem_tenant_cria_com_loja_escolhida_no_modal():
    """Admin sem tenant: a escolha explícita do Vale/Loja no modal é o contexto."""
    mundo = _mundo()
    client = _cliente(mundo.admin)

    resposta = client.post(
        '/tarefas/eventos/criar/',
        json.dumps(_payload(mundo.loja3.pk)),
        content_type='application/json',
    )

    assert resposta.status_code == 200, resposta.content
    ev = Evento.objects.get(loja_id=str(mundo.loja3.pk))
    assert ev.titulo == 'Evento de teste'


def test_admin_sem_tenant_sem_loja_da_400_json_e_nao_html():
    """Sem contexto e sem escolha: JSON 400 com mensagem visível no alert.

    Antes era 403 HTML (decorator) e o front calava — por isso 'salvar não
    salvava' sem feedback. Agora sempre JSON legível pelo JS.
    """
    mundo = _mundo()
    client = _cliente(mundo.admin)

    resposta = client.post(
        '/tarefas/eventos/criar/',
        content_type='application/json',
        data=json.dumps({'titulo': 'Sem contexto', 'data_inicio': '2026-11-10T19:00'}),
    )

    assert resposta.status_code == 400
    assert resposta['Content-Type'].startswith('application/json')
    assert 'erro' in resposta.json()


def test_admin_com_tenant_cria_qualquer_lugar():
    mundo = _mundo()
    client = _cliente(mundo.admin, admin_tenant_id=mundo.tenant_b.pk)

    resposta = client.post(
        '/tarefas/eventos/criar/',
        json.dumps(_payload(mundo.loja3.pk)),
        content_type='application/json',
    )

    assert resposta.status_code == 200
    assert Evento.objects.get(loja_id=str(mundo.loja3.pk)).titulo == "Evento de teste"


def test_admin_sem_tenant_edita_e_exclui_evento_de_qualquer_loja():
    mundo = _mundo()
    ev = Evento.objects.create(
        titulo='Reunião B1', tipo='sessao',
        data_inicio='2026-11-10T19:00', data_fim='2026-11-10T21:00',
        loja_id=str(mundo.loja3.pk),
    )
    client = _cliente(mundo.admin)

    editado = client.post(
        f'/tarefas/eventos/{ev.pk}/editar/',
        json.dumps({'titulo': 'Reunião B1 (editada)'}),
        content_type='application/json',
    )
    excluido = client.post(f'/tarefas/eventos/{ev.pk}/excluir/')

    assert editado.status_code == 200, editado.content
    assert excluido.status_code == 200, excluido.content
    assert not Evento.objects.filter(pk=ev.pk).exists()


def test_delegado_edita_evento_do_vale_dele_e_recusa_fora():
    mundo = _mundo()
    do_vale = Evento.objects.create(
        titulo='Toque local', tipo='sessao',
        data_inicio='2026-11-10T19:00', data_fim='2026-11-10T21:00',
        loja_id=str(mundo.loja2.pk),
    )
    de_fora_vale = Evento.objects.create(
        titulo='Toque alheio', tipo='sessao',
        data_inicio='2026-11-10T19:00', data_fim='2026-11-10T21:00',
        loja_id=str(mundo.loja3.pk),
    )
    client = _cliente(mundo.delegado)

    ok = client.post(
        f'/tarefas/eventos/{do_vale.pk}/editar/',
        json.dumps({'titulo': 'Toque local (editado)'}),
        content_type='application/json',
    )
    recusado = client.post(
        f'/tarefas/eventos/{de_fora_vale.pk}/editar/',
        json.dumps({'titulo': 'Invasão'}),
        content_type='application/json',
    )

    assert ok.status_code == 200
    do_vale.refresh_from_db()
    assert do_vale.titulo == 'Toque local (editado)'
    assert recusado.status_code == 403
    de_fora_vale.refresh_from_db()
    assert de_fora_vale.titulo == 'Toque alheio'


def test_secretario_edita_so_o_da_sua_loja():
    mundo = _mundo()
    da_loja = Evento.objects.create(
        titulo='Sessão A1', tipo='sessao',
        data_inicio='2026-11-10T19:00', data_fim='2026-11-10T21:00',
        loja_id=str(mundo.loja1.pk),
    )
    de_outra = Evento.objects.create(
        titulo='Sessão A2', tipo='sessao',
        data_inicio='2026-11-10T19:00', data_fim='2026-11-10T21:00',
        loja_id=str(mundo.loja2.pk),
    )
    client = _cliente(mundo.secretario)

    ok = client.post(
        f'/tarefas/eventos/{da_loja.pk}/editar/',
        json.dumps({'titulo': 'Sessão A1 (editada)'}),
        content_type='application/json',
    )
    recusado = client.post(
        f'/tarefas/eventos/{de_outra.pk}/editar/',
        json.dumps({'titulo': 'Invasão'}),
        content_type='application/json',
    )

    assert ok.status_code == 200
    da_loja.refresh_from_db()
    assert da_loja.titulo == 'Sessão A1 (editada)'
    assert recusado.status_code == 403


def test_ranking_delegado_ve_so_o_vale_dele_e_botao():
    mundo = _mundo()
    client = _cliente(mundo.delegado)

    pagina = client.get('/tarefas/ranking/')
    assert pagina.status_code == 200
    assert pagina.context['pode_criar_evento'] is True
    # Contexto agora é a lista Python em si (o filtro `js` serializa no template).
    assert [v['id'] for v in pagina.context['vales_evento']] == [str(mundo.vale_a.pk)]
    lojas_ctx = pagina.context['lojas_evento']
    assert {str(l['id']) for l in lojas_ctx} == {str(mundo.loja1.pk), str(mundo.loja2.pk)}


def test_ranking_injeta_arrays_js_e_nao_strings_json():
    """Regressão: vales/lojas/eventos saem como arrays no script inline.

    O bug: a view serializava com json.dumps e o filtro `js` re-serializava,
    gerando strings entre aspas — o JS quebrava na carga (`.filter is not a
    function`) e o clique em "Novo Evento" não fazia nada.
    """
    mundo = _mundo()
    client = _cliente(mundo.admin, admin_tenant_id=mundo.tenant_a.pk)

    pagina = client.get('/tarefas/ranking/')
    conteudo = pagina.content.decode()

    for variavel in ('eventos', 'valesData', 'lojasData'):
        inicio = conteudo.index(f'var {variavel} = ')
        depois_do_igual = conteudo[inicio + len(f'var {variavel} = '):]
        primeiro = depois_do_igual.lstrip()[:1]
        assert primeiro == '[', f'{variavel} não é array (começa com {primeiro!r})'
    assert 'var lojasData = "[' not in conteudo
