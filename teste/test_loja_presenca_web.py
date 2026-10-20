"""Presença de membros no detalhe da própria Loja."""
import datetime
import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.conf import settings
from django.test import Client

from acesso.models import Tenant, Usuario
from acesso.session import iniciar_sessao
from contatos.models import Loja, Membro, Vale
from tarefas.models import Evento, PresencaEvento

pytestmark = pytest.mark.django_db


@pytest.fixture
def quadro_presenca_loja():
    sufixo = uuid4().hex
    tenant = Tenant.objects.create(nome='Vale Presença', slug=f'presenca-{sufixo}')
    Vale.objects.create(
        tenant=tenant,
        nome='Vale Presença',
        sigla=sufixo[:10].upper(),
    )
    outra_tenant = Tenant.objects.create(
        nome='Vale Externo', slug=f'externo-{sufixo}',
    )
    loja = Loja.objects.create(tenant=tenant, nome='Loja Presença')
    outra_loja = Loja.objects.create(tenant=tenant, nome='Outra Loja')
    loja_externa = Loja.objects.create(tenant=outra_tenant, nome='Loja Externa')

    membro_metade = Membro.objects.create(tenant=tenant, nome='Membro Metade')
    membro_baixa = Membro.objects.create(tenant=tenant, nome='Membro Baixa')
    membro_abaixo_limite = Membro.objects.create(
        tenant=tenant, nome='Membro Abaixo do Limite',
    )
    membro_sem_chamada = Membro.objects.create(tenant=tenant, nome='Membro Sem Chamada')
    membro_de_outro_tenant = Membro.objects.create(
        tenant=outra_tenant, nome='Membro de Outro Tenant',
    )
    loja.membros.add(
        membro_metade,
        membro_baixa,
        membro_abaixo_limite,
        membro_sem_chamada,
        membro_de_outro_tenant,
    )

    def criar_evento(event_loja):
        inicio = datetime.datetime(2026, 10, 1, 20, tzinfo=datetime.UTC)
        return Evento.objects.create(
            titulo='Sessão de teste',
            tipo='sessao',
            data_inicio=inicio,
            data_fim=inicio + datetime.timedelta(hours=2),
            loja_id=str(event_loja.pk),
        )

    evento_um = criar_evento(loja)
    evento_dois = criar_evento(loja)
    evento_outra_loja = criar_evento(outra_loja)
    evento_outra_loja_dois = criar_evento(outra_loja)
    evento_externo = criar_evento(loja_externa)

    PresencaEvento.objects.create(evento=evento_um, membro=membro_metade, presente=True)
    PresencaEvento.objects.create(evento=evento_dois, membro=membro_metade, presente=False)
    PresencaEvento.objects.create(evento=evento_um, membro=membro_baixa, presente=False)
    for chamada in range(101):
        evento = criar_evento(loja)
        PresencaEvento.objects.create(
            evento=evento,
            membro=membro_abaixo_limite,
            presente=chamada < 50,
        )
    # Chamadas de outras Lojas não devem alterar os percentuais exibidos aqui.
    PresencaEvento.objects.create(evento=evento_outra_loja, membro=membro_metade, presente=True)
    PresencaEvento.objects.create(evento=evento_outra_loja, membro=membro_baixa, presente=True)
    PresencaEvento.objects.create(
        evento=evento_outra_loja_dois, membro=membro_baixa, presente=True,
    )
    PresencaEvento.objects.create(
        evento=evento_externo, membro=membro_de_outro_tenant, presente=True,
    )

    usuario = Usuario.objects.create(
        nome='Operador Presença',
        email=f'operador-{sufixo}@example.test',
        senha='senha-teste',
        role='operacional',
        tenant=tenant,
    )
    cliente = Client()
    sessao = cliente.session
    iniciar_sessao(SimpleNamespace(session=sessao), usuario)
    sessao.save()
    cliente.cookies[settings.SESSION_COOKIE_NAME] = sessao.session_key

    return {
        'cliente': cliente,
        'loja': loja,
        'loja_externa': loja_externa,
        'membro_metade': membro_metade,
        'membro_baixa': membro_baixa,
        'membro_abaixo_limite': membro_abaixo_limite,
        'membro_sem_chamada': membro_sem_chamada,
        'membro_de_outro_tenant': membro_de_outro_tenant,
    }


def test_detalhe_da_loja_mostra_percentual_so_das_chamadas_da_loja(quadro_presenca_loja):
    quadro = quadro_presenca_loja

    resposta = quadro['cliente'].get(f"/contatos/loja/{quadro['loja'].pk}/")

    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert 'Membros e presença' in html
    assert 'Membro Metade' in html
    assert 'data-presenca="50"' in html
    assert 'Membro Baixa' in html
    assert 'data-presenca="0"' in html
    assert 'Membro Sem Chamada' in html
    assert 'data-presenca="-"' in html
    assert 'Membro de Outro Tenant' not in html
    linhas = re.findall(r'<tr\b[^>]*>(.*?)</tr>', html, re.DOTALL)
    linha_baixa = next(linha for linha in linhas if 'Membro Baixa' in linha)
    linha_metade = next(linha for linha in linhas if 'Membro Metade' in linha)
    linha_abaixo_limite = next(
        linha for linha in linhas if 'Membro Abaixo do Limite' in linha
    )
    valor_baixo = re.search(r'<span data-presenca="0" class="([^"]+)"', linha_baixa)
    valor_metade = re.search(r'<span data-presenca="50" class="([^"]+)"', linha_metade)
    valor_abaixo_limite = re.search(
        r'<span data-presenca="50" class="([^"]+)"', linha_abaixo_limite,
    )
    assert valor_baixo and 'text-red-400' in valor_baixo.group(1)
    assert valor_metade and 'text-red-400' not in valor_metade.group(1)
    assert valor_abaixo_limite and 'text-red-400' in valor_abaixo_limite.group(1)


def test_detalhe_nao_abre_loja_de_outro_tenant(quadro_presenca_loja):
    quadro = quadro_presenca_loja

    resposta = quadro['cliente'].get(
        f"/contatos/loja/{quadro['loja_externa'].pk}/",
    )

    assert resposta.status_code == 404


def test_lista_expandida_retorna_presenca_de_cada_membro_da_loja(quadro_presenca_loja):
    quadro = quadro_presenca_loja

    resposta = quadro['cliente'].get(
        f"/contatos/loja/{quadro['loja'].pk}/membros-json/",
    )

    assert resposta.status_code == 200
    membros = {membro['nome']: membro for membro in resposta.json()['membros']}
    assert membros['Membro Metade']['presenca'] == 50
    assert membros['Membro Metade']['presenca_abaixo_50'] is False
    assert membros['Membro Baixa']['presenca'] == 0
    assert membros['Membro Baixa']['presenca_abaixo_50'] is True
    assert membros['Membro Abaixo do Limite']['presenca'] == 50
    assert membros['Membro Abaixo do Limite']['presenca_abaixo_50'] is True
    assert membros['Membro Sem Chamada']['presenca'] is None
    assert membros['Membro Sem Chamada']['presenca_abaixo_50'] is False
    assert 'Membro de Outro Tenant' not in membros
