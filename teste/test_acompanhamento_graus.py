from datetime import timedelta
from html.parser import HTMLParser
from io import StringIO
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.core.management import call_command, get_commands
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from django.utils import timezone

from acesso.models import ROLE_ADMIN_SAAS, ROLE_DELEGADO, Tenant, Usuario
from contatos.models import Grau, GrauMembro, HistoricoCargo, Loja, Membro, Vale
from tarefas.models import Evento, PresencaEvento

pytestmark = pytest.mark.django_db


def _colunas_da_tabela(modelo):
    with connection.cursor() as cursor:
        descricao = connection.introspection.get_table_description(
            cursor, modelo._meta.db_table,
        )
    return {coluna.name for coluna in descricao}


def test_membro_table_does_not_keep_legacy_ritual_date_columns():
    colunas = _colunas_da_tabela(Membro)

    assert not {
        'data_iniciacao',
        'data_passagem',
        'data_elevacao',
    } & colunas


def test_historico_cargo_keeps_data_passagem_column():
    assert 'data_passagem' in _colunas_da_tabela(HistoricoCargo)


def test_acompanhamento_url_resolves_to_its_own_view():
    assert resolve('/membros/acompanhamento/').url_name == 'acompanhamento'


def test_limpeza_graus_command_is_registered():
    assert get_commands().get('limpar_historico_graus_teste') == 'contatos'


def test_limpeza_graus_sem_confirmacao_apenas_reporta():
    call_command('seed_graus', verbosity=0)
    tenant = Tenant.objects.create(nome='Limpeza teste', slug='limpeza-graus')
    membro = Membro.objects.create(tenant=tenant, nome='Membro de teste')
    grau = Grau.objects.get(numero=10)
    GrauMembro.objects.create(
        tenant=tenant, membro=membro, grau=grau, data='2010-01-01',
    )
    output = StringIO()

    call_command('limpar_historico_graus_teste', stdout=output)

    assert GrauMembro.objects.filter(membro=membro).count() == 1
    assert '1' in output.getvalue()


def test_limpeza_graus_com_confirmacao_apaga_e_reporta_quantidade():
    call_command('seed_graus', verbosity=0)
    tenant = Tenant.objects.create(nome='Limpeza teste 2', slug='limpeza-graus-2')
    membros = [
        Membro.objects.create(tenant=tenant, nome=f'Membro de teste {indice}')
        for indice in range(2)
    ]
    graus = [Grau.objects.get(numero=10), Grau.objects.get(numero=11)]
    for membro, grau in zip(membros, graus, strict=True):
        GrauMembro.objects.create(
            tenant=tenant, membro=membro, grau=grau, data='2010-01-01',
        )
    output = StringIO()

    call_command('limpar_historico_graus_teste', confirm=True, stdout=output)

    assert GrauMembro.objects.count() == 0
    assert '2' in output.getvalue()


def _tenant_vale(nome, sigla):
    suffix = uuid4().hex
    tenant = Tenant.objects.create(nome=nome, slug=f'{sigla.lower()}-{suffix}')
    vale = Vale.objects.create(
        tenant=tenant, nome=nome, sigla=f'{sigla}{suffix[:4]}',
    )
    return tenant, vale


def _cliente(tenant, role=ROLE_DELEGADO):
    suffix = uuid4().hex
    usuario = Usuario.objects.create(
        nome='Usuário de acompanhamento',
        email=f'acompanhamento-{suffix}@example.test',
        senha=make_password('senha-teste'),
        role=role,
        tenant=tenant,
    )
    client = Client()
    session = client.session
    session['usuario_id'] = usuario.pk
    session['usuario'] = {
        'nome': usuario.nome,
        'email': usuario.email,
        'role': usuario.role,
        'tenant_id': tenant.pk if tenant else None,
    }
    session.save()
    return client


def _registrar_grau(membro, numero, data):
    grau = Grau.objects.get(numero=numero)
    return GrauMembro.objects.create(
        tenant_id=membro.tenant_id,
        membro=membro,
        grau=grau,
        data=data,
    )


class _NomeMembroParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.membros = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        nome = attributes.get('data-member-name')
        if tag == 'a' and nome:
            self.membros[nome] = {
                'class': attributes.get('class', ''),
                'presenca': attributes.get('data-presence'),
            }


class _PrimaryFilterRowParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.div_depth = 0
        self.primary_depth = None
        self.select_names = []
        self.action_tags = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'div':
            if attributes.get('data-filter-row') == 'primary':
                self.primary_depth = self.div_depth
            self.div_depth += 1
        elif self.primary_depth is not None:
            if tag == 'select':
                self.select_names.append(attributes.get('name'))
            elif tag in ('button', 'a'):
                self.action_tags.append(tag)

    def handle_endtag(self, tag):
        if tag == 'div' and self.div_depth:
            self.div_depth -= 1
            if self.primary_depth == self.div_depth:
                self.primary_depth = None


class _TableColumnParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.columns = []
        self.degree_numbers = []
        self.empty_colspan = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'th':
            self.columns.append(attributes.get('data-column'))
            if attributes.get('data-grau'):
                self.degree_numbers.append(int(attributes['data-grau']))
        elif tag == 'td' and attributes.get('colspan'):
            self.empty_colspan = int(attributes['colspan'])


class _PresetCheckboxParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.checkboxes = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'input' and attributes.get('name') == 'grupo_grau':
            self.checkboxes[attributes['value']] = 'checked' in attributes


def test_acompanhamento_exibe_trinta_colunas_com_datas_e_lojas():
    call_command('seed_graus', verbosity=0)
    tenant, vale = _tenant_vale('Vale Aurora', 'VA')
    lojas = [
        Loja.objects.create(tenant=tenant, nome=f'Loja Aurora {indice}')
        for indice in (1, 2)
    ]
    membro = Membro.objects.create(
        tenant=tenant, nome='Ana Acompanhamento', situacao='ATIVO',
    )
    membro.lojas.set(lojas)
    _registrar_grau(membro, 10, '2015-03-14')
    client = _cliente(tenant)

    response = client.get('/membros/acompanhamento/')
    html = response.content.decode()

    assert response.status_code == 200
    assert html.count('data-grau=') == 30
    assert 'data-grau="4"' in html and 'data-grau="33"' in html
    assert vale.nome in html
    assert 'Loja Aurora 1' in html and 'Loja Aurora 2' in html
    assert '14/03/2015' in html


def test_acompanhamento_tabela_remove_colunas_de_vale_e_loja():
    call_command('seed_graus', verbosity=0)
    tenant, _ = _tenant_vale('Vale Sem Coluna', 'VSC')
    Loja.objects.create(tenant=tenant, nome='Loja Sem Coluna')
    membro = Membro.objects.create(tenant=tenant, nome='Membro Colunas')
    _registrar_grau(membro, 10, '2015-03-14')
    response = _cliente(tenant).get('/membros/acompanhamento/')
    parser = _TableColumnParser()
    parser.feed(response.content.decode())

    assert response.status_code == 200
    assert parser.columns == ['member', 'presence'] + ['degree-date'] * 30


def test_acompanhamento_pagina_vinte_e_preserva_filtros():
    call_command('seed_graus', verbosity=0)
    tenant, vale = _tenant_vale('Vale Paginação', 'VP')
    loja = Loja.objects.create(tenant=tenant, nome='Loja Paginação')
    for indice in range(21):
        membro = Membro.objects.create(
            tenant=tenant, nome=f'Membro Página {indice:02}',
        )
        membro.lojas.add(loja)
        _registrar_grau(membro, 10, '2010-01-01')
    client = _cliente(tenant)
    filtros = {'vale': str(vale.pk), 'loja': str(loja.pk), 'grau': ['10']}

    primeira_pagina = client.get('/membros/acompanhamento/', filtros)
    segunda_pagina = client.get(
        '/membros/acompanhamento/', {**filtros, 'page': '2'},
    )

    assert primeira_pagina.status_code == 200
    assert primeira_pagina.context['page_obj'].paginator.per_page == 20
    assert len(primeira_pagina.context['linhas']) == 20
    assert 'aria-label="Paginação"' in primeira_pagina.content.decode()
    pagina_2 = next(
        page for page in primeira_pagina.context['pagination_urls']['pages']
        if page['number'] == 2
    )
    params_pagina_2 = parse_qs(urlparse(pagina_2['url']).query)
    assert params_pagina_2['vale'] == [str(vale.pk)]
    assert params_pagina_2['loja'] == [str(loja.pk)]
    assert params_pagina_2['grau'] == ['10']
    assert 'vale=' in primeira_pagina.context['pagination_urls']['next']
    assert 'loja=' in primeira_pagina.context['pagination_urls']['next']
    assert 'grau=10' in primeira_pagina.context['pagination_urls']['next']
    assert segunda_pagina.status_code == 200
    assert len(segunda_pagina.context['linhas']) == 1


def test_acompanhamento_renderiza_checkboxes_das_faixas_de_grau():
    tenant, _ = _tenant_vale('Vale Presets', 'VPS')
    response = _cliente(tenant).get('/membros/acompanhamento/')
    parser = _PresetCheckboxParser()
    parser.feed(response.content.decode())

    assert response.status_code == 200
    assert parser.checkboxes == {
        'perfeicao': False,
        'rosa_cruz': False,
        'kadosh': False,
        'consistorio': False,
        'sc33': False,
    }
    for label in ('Perfeição', 'Capítulo', 'Kadosh', 'Consistório', 'SC33'):
        assert label in response.content.decode()
    assert 'Rosa Cruz' not in response.content.decode()


@pytest.mark.parametrize(
    ('grupo', 'graus_incluidos', 'graus_excluidos'),
    [
        ('perfeicao', (4, 14), (15,)),
        ('rosa_cruz', (15, 18), (14, 19)),
        ('kadosh', (19, 30), (18, 31)),
        ('consistorio', (31, 32), (30, 33)),
        ('sc33', (33,), (32,)),
    ],
)
def test_preset_grau_filtra_faixa_inclusiva(grupo, graus_incluidos, graus_excluidos):
    call_command('seed_graus', verbosity=0)
    tenant, _ = _tenant_vale(f'Vale {grupo}', f'V{grupo[:2].upper()}')
    membros = {}
    for numero in (*graus_incluidos, *graus_excluidos):
        membro = Membro.objects.create(tenant=tenant, nome=f'Membro grau {numero}')
        _registrar_grau(membro, numero, '2010-01-01')
        membros[numero] = membro

    response = _cliente(tenant).get(
        '/membros/acompanhamento/', {'grupo_grau': grupo},
    )
    html = response.content.decode()

    assert response.status_code == 200
    for numero in graus_incluidos:
        assert f'Membro grau {numero}' in html
    for numero in graus_excluidos:
        assert f'Membro grau {numero}' not in html


@pytest.mark.parametrize(
    ('grupo', 'graus_visiveis'),
    [
        ('perfeicao', tuple(range(4, 15))),
        ('rosa_cruz', tuple(range(15, 19))),
        ('kadosh', tuple(range(19, 31))),
        ('consistorio', (31, 32)),
        ('sc33', (33,)),
    ],
)
def test_acompanhamento_colunas_correspondem_ao_corpo(grupo, graus_visiveis):
    call_command('seed_graus', verbosity=0)
    tenant, _ = _tenant_vale(f'Vale Colunas {grupo}', f'VC{grupo[:1]}')
    response = _cliente(tenant).get(
        '/membros/acompanhamento/', {'grupo_grau': grupo},
    )
    parser = _TableColumnParser()
    parser.feed(response.content.decode())

    assert response.status_code == 200
    assert parser.columns == ['member', 'presence'] + ['degree-date'] * len(graus_visiveis)
    assert parser.degree_numbers == list(graus_visiveis)
    assert parser.empty_colspan == 2 + len(graus_visiveis)


def test_acompanhamento_multiplos_corpos_mostram_uniao_das_colunas():
    call_command('seed_graus', verbosity=0)
    tenant, _ = _tenant_vale('Vale Colunas União', 'VCU')
    response = _cliente(tenant).get('/membros/acompanhamento/', {
        'grupo_grau': ['perfeicao', 'kadosh'],
    })
    parser = _TableColumnParser()
    parser.feed(response.content.decode())
    esperado = list(range(4, 15)) + list(range(19, 31))

    assert response.status_code == 200
    assert parser.columns == ['member', 'presence'] + ['degree-date'] * len(esperado)
    assert parser.degree_numbers == esperado
    assert parser.empty_colspan == 2 + len(esperado)


def test_presets_e_graus_manuais_combinam_por_or():
    call_command('seed_graus', verbosity=0)
    tenant, _ = _tenant_vale('Vale União', 'VU')
    membros = {}
    for numero in (4, 10, 15):
        membro = Membro.objects.create(tenant=tenant, nome=f'Membro união {numero}')
        _registrar_grau(membro, numero, '2010-01-01')
        membros[numero] = membro

    response = _cliente(tenant).get('/membros/acompanhamento/', {
        'grupo_grau': ['rosa_cruz'], 'grau': ['4'],
    })
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Membro união 4' in html
    assert 'Membro união 15' in html
    assert 'Membro união 10' not in html


def test_sem_corpo_selecionado_lista_todos_os_membros():
    call_command('seed_graus', verbosity=0)
    tenant, _ = _tenant_vale('Vale Todos Graus', 'VT')
    membro_com_grau = Membro.objects.create(tenant=tenant, nome='Membro com grau')
    _registrar_grau(membro_com_grau, 18, '2010-01-01')
    Membro.objects.create(tenant=tenant, nome='Membro sem grau')

    response = _cliente(tenant).get('/membros/acompanhamento/')
    html = response.content.decode()
    parser = _PresetCheckboxParser()
    parser.feed(html)

    assert response.status_code == 200
    assert set(parser.checkboxes) == {
        'perfeicao', 'rosa_cruz', 'kadosh', 'consistorio', 'sc33',
    }
    assert not any(parser.checkboxes.values())
    assert 'Membro com grau' in html
    assert 'Membro sem grau' in html


def test_preset_grau_desconhecido_nao_remove_filtro():
    tenant, _ = _tenant_vale('Vale Preset Inválido', 'VPI')
    Membro.objects.create(tenant=tenant, nome='Membro que não deve aparecer')

    response = _cliente(tenant).get(
        '/membros/acompanhamento/', {'grupo_grau': 'nao-existe'},
    )

    assert response.status_code == 200
    assert 'Membro que não deve aparecer' not in response.content.decode()


def test_filtro_multi_grau_usa_or_sem_duplicar_membro():
    call_command('seed_graus', verbosity=0)
    tenant, _ = _tenant_vale('Vale Filtro', 'VF')
    membros = [
        Membro.objects.create(tenant=tenant, nome=nome)
        for nome in ('Tem Grau 10', 'Tem Grau 18', 'Tem somente Grau 11')
    ]
    _registrar_grau(membros[0], 10, '2010-01-01')
    _registrar_grau(membros[1], 18, '2018-01-01')
    _registrar_grau(membros[2], 11, '2011-01-01')
    client = _cliente(tenant)

    response = client.get(
        '/membros/acompanhamento/', {'grau': ['10', '18']},
    )
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Tem Grau 10' in html
    assert 'Tem Grau 18' in html
    assert 'Tem somente Grau 11' not in html
    assert html.count('data-membro-row=') == 2


def test_filtros_vale_e_loja_sao_aplicados():
    tenant_a, vale_a = _tenant_vale('Vale Leste', 'VL')
    tenant_b, _ = _tenant_vale('Vale Oeste', 'VO')
    loja_a = Loja.objects.create(tenant=tenant_a, nome='Loja Leste')
    loja_b = Loja.objects.create(tenant=tenant_b, nome='Loja Oeste')
    membro_a = Membro.objects.create(tenant=tenant_a, nome='Membro Leste')
    membro_b = Membro.objects.create(tenant=tenant_b, nome='Membro Oeste')
    membro_a.lojas.add(loja_a)
    membro_b.lojas.add(loja_b)
    client = _cliente(None, role=ROLE_ADMIN_SAAS)

    response = client.get('/membros/acompanhamento/', {
        'vale': str(vale_a.pk), 'loja': str(loja_a.pk),
    })
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Membro Leste' in html
    assert 'Membro Oeste' not in html
    assert html.count('data-membro-row=') == 1


@pytest.mark.parametrize(
    ('ordenar', 'direcao', 'esperado'),
    [
        ('nome', 'asc', ['Ana Ordem', 'Bob Ordem', 'Zoe Ordem']),
        ('nome', 'desc', ['Zoe Ordem', 'Bob Ordem', 'Ana Ordem']),
        ('vale', 'asc', ['Ana Ordem', 'Bob Ordem', 'Zoe Ordem']),
        ('vale', 'desc', ['Zoe Ordem', 'Bob Ordem', 'Ana Ordem']),
        ('loja', 'asc', ['Zoe Ordem', 'Bob Ordem', 'Ana Ordem']),
        ('loja', 'desc', ['Ana Ordem', 'Bob Ordem', 'Zoe Ordem']),
        ('grau', 'asc', ['Ana Ordem', 'Zoe Ordem', 'Bob Ordem']),
        ('grau', 'desc', ['Bob Ordem', 'Zoe Ordem', 'Ana Ordem']),
    ],
)
def test_acompanhamento_ordenacao_por_campo_e_direcao(ordenar, direcao, esperado):
    call_command('seed_graus', verbosity=0)
    tenant_z, _ = _tenant_vale('Vale Zulu', 'VZ')
    tenant_a, _ = _tenant_vale('Vale Alpha', 'VA')
    tenant_m, _ = _tenant_vale('Vale Mike', 'VM')
    loja_z_b = Loja.objects.create(tenant=tenant_z, nome='Loja B')
    loja_z_a = Loja.objects.create(tenant=tenant_z, nome='Loja A')
    loja_a = Loja.objects.create(tenant=tenant_a, nome='Loja C')
    loja_m = Loja.objects.create(tenant=tenant_m, nome='Loja B')
    zoe = Membro.objects.create(tenant=tenant_z, nome='Zoe Ordem')
    ana = Membro.objects.create(tenant=tenant_a, nome='Ana Ordem')
    bob = Membro.objects.create(tenant=tenant_m, nome='Bob Ordem')
    zoe.lojas.set([loja_z_b, loja_z_a])
    ana.lojas.add(loja_a)
    bob.lojas.add(loja_m)
    _registrar_grau(zoe, 18, '2018-01-01')
    _registrar_grau(ana, 10, '2010-01-01')
    _registrar_grau(bob, 33, '2020-01-01')
    client = _cliente(None, role=ROLE_ADMIN_SAAS)

    response = client.get('/membros/acompanhamento/', {
        'ordenar': ordenar, 'direcao': direcao,
    })
    html = response.content.decode()

    assert response.status_code == 200
    assert all(nome in html for nome in esperado)
    posicoes = [html.index(nome) for nome in esperado]
    assert posicoes == sorted(posicoes)


def test_acompanhamento_isola_tenant_e_admin_saas_ve_todos():
    tenant_a, _ = _tenant_vale('Vale Tenant A', 'TA')
    tenant_b, _ = _tenant_vale('Vale Tenant B', 'TB')
    Membro.objects.create(tenant=tenant_a, nome='Visível Tenant A')
    Membro.objects.create(tenant=tenant_b, nome='Visível Tenant B')

    resposta_comum = _cliente(tenant_a).get('/membros/acompanhamento/')
    resposta_admin = _cliente(None, role=ROLE_ADMIN_SAAS).get(
        '/membros/acompanhamento/',
    )

    assert resposta_comum.status_code == 200
    assert 'Visível Tenant A' in resposta_comum.content.decode()
    assert 'Visível Tenant B' not in resposta_comum.content.decode()
    assert resposta_admin.status_code == 200
    assert 'Visível Tenant A' in resposta_admin.content.decode()
    assert 'Visível Tenant B' in resposta_admin.content.decode()


def test_acompanhamento_nao_adiciona_consultas_por_membro():
    call_command('seed_graus', verbosity=0)
    tenant, _ = _tenant_vale('Vale Consultas', 'VC')
    loja = Loja.objects.create(tenant=tenant, nome='Loja Consultas')
    client = _cliente(tenant)

    primeiro = Membro.objects.create(tenant=tenant, nome='Membro Consulta 0')
    primeiro.lojas.add(loja)
    _registrar_grau(primeiro, 10, '2010-01-01')
    with CaptureQueriesContext(connection) as consultas_unico:
        resposta_unico = client.get('/membros/acompanhamento/')
    assert resposta_unico.status_code == 200

    for indice in range(1, 25):
        membro = Membro.objects.create(
            tenant=tenant, nome=f'Membro Consulta {indice}',
        )
        membro.lojas.add(loja)
        _registrar_grau(membro, 10, '2010-01-01')

    with CaptureQueriesContext(connection) as consultas_pagina:
        resposta_pagina = client.get('/membros/acompanhamento/')
    assert resposta_pagina.status_code == 200

    assert len(consultas_pagina) <= len(consultas_unico) + 3


def test_nome_fica_vermelho_somente_quando_presenca_menor_que_50_porcento():
    tenant, _ = _tenant_vale('Vale Presença', 'VP')
    loja = Loja.objects.create(tenant=tenant, nome='Loja Presença')
    membro_49 = Membro.objects.create(tenant=tenant, nome='Presença 49')
    membro_50 = Membro.objects.create(tenant=tenant, nome='Presença 50')
    membro_sem_chamada = Membro.objects.create(
        tenant=tenant, nome='Presença sem chamada',
    )
    for membro, total, presentes in (
        (membro_49, 100, 49),
        (membro_50, 2, 1),
    ):
        membro.lojas.add(loja)
        for indice in range(total):
            inicio = timezone.now() + timedelta(minutes=indice)
            evento = Evento.objects.create(
                titulo=f'Chamada {membro.nome} {indice}',
                data_inicio=inicio,
                data_fim=inicio + timedelta(hours=1),
                loja_id=str(loja.pk),
            )
            PresencaEvento.objects.create(
                evento=evento,
                membro=membro,
                presente=indice < presentes,
            )
    membro_sem_chamada.lojas.add(loja)
    response = _cliente(tenant).get('/membros/acompanhamento/')
    parser = _NomeMembroParser()
    parser.feed(response.content.decode())

    assert response.status_code == 200
    assert set(parser.membros) == {
        'Presença 49', 'Presença 50', 'Presença sem chamada',
    }
    assert 'text-red-400' in parser.membros['Presença 49']['class']
    assert parser.membros['Presença 49']['presenca'] == '49'
    assert 'text-red-400' not in parser.membros['Presença 50']['class']
    assert parser.membros['Presença 50']['presenca'] == '50'
    assert 'text-red-400' not in parser.membros['Presença sem chamada']['class']
    assert parser.membros['Presença sem chamada']['presenca'] == '-'


def test_acompanhamento_alinha_acoes_com_selects_e_deixa_corpos_abaixo():
    tenant, _ = _tenant_vale('Vale Filtros na linha', 'VF')
    response = _cliente(tenant).get('/membros/acompanhamento/')
    html = response.content.decode()
    parser = _PrimaryFilterRowParser()
    parser.feed(html)
    primary_start = html.find('data-filter-row="primary"')
    bodies_start = html.find('data-filter-section="bodies"')

    assert response.status_code == 200
    assert parser.select_names == ['vale', 'loja']
    assert 'select name="grau"' not in html
    assert parser.action_tags == ['button', 'a', 'button', 'button']
    assert primary_start >= 0
    assert bodies_start > primary_start
    assert primary_start < html.index('<span>Filtrar</span>') < bodies_start
    assert primary_start < html.index('<span>Limpar</span>') < bodies_start


def test_acompanhamento_remove_seletores_de_ordenacao_redundantes():
    tenant, _ = _tenant_vale('Vale Filtros simples', 'VS')
    response = _cliente(tenant).get('/membros/acompanhamento/')
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Ordenar por' not in html
    assert 'Grau mais alto' not in html
    assert 'Direção' not in html
