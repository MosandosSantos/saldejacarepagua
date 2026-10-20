import json
from types import SimpleNamespace
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings

from candidatos.models import Candidato
from candidatos.views import api as candidato_api
from contatos.models import Loja, Vale
from recepcao.views.helpers import cards_candidatos


class _QueryResult:
    """Small queryset double; tests never connect to a configured database."""

    def __init__(self, rows):
        self.rows = rows

    def order_by(self, *fields):
        return self

    def values(self, *fields):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, index):
        return self.rows[index]


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'candidate-local-options-tests',
    },
})
class CandidatoLocalOptionsTests(SimpleTestCase):
    def _request(self, path, query=None, tenant_id=42, role='delegado'):
        request = RequestFactory().get(path, query or {})
        request.session = {
            'usuario_id': 7,
            'usuario': {'role': role, 'tenant_id': tenant_id},
        }
        return request

    def test_api_prefeituras_returns_active_local_vales_for_session_tenant(self):
        local_vales = [{'id': 11, 'nome': 'Vale Centro'}]
        query = _QueryResult(local_vales)

        with (
            patch.object(Vale.objects, 'filter', return_value=query) as filtro_vales,
            patch(
                'core.gprb.opcoes_prefeituras_usuario',
                return_value=[{'id': 'external', 'nome': 'Vale externo'}],
            ) as opcoes_externas,
        ):
            response = candidato_api.api_prefeituras(
                self._request('/candidato/api/prefeituras/'),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content),
            {'prefeituras': [{'id': 11, 'nome': 'Vale Centro'}]},
        )
        filtro_vales.assert_called_once_with(tenant_id=42, status='ATIVA')
        opcoes_externas.assert_not_called()

    def test_api_prefeituras_shows_all_local_vales_to_saas_admin(self):
        vales = [
            {'id': 11, 'nome': 'Vale Centro'},
            {'id': 27, 'nome': 'Vale Norte'},
        ]

        with (
            patch.object(
                Vale.objects, 'filter', return_value=_QueryResult(vales),
            ) as filtro_vales,
            patch.object(candidato_api, '_tenant_id', return_value=42) as tenant_id,
        ):
            response = candidato_api.api_prefeituras(
                self._request(
                    '/candidato/api/prefeituras/',
                    tenant_id=None,
                    role='admin_saas',
                ),
            )

        self.assertEqual(
            json.loads(response.content),
            {'prefeituras': vales},
        )
        filtro_vales.assert_called_once_with(status='ATIVA')
        tenant_id.assert_not_called()

    def test_api_lojas_returns_active_local_stores_for_selected_vale(self):
        vale = SimpleNamespace(pk=11, tenant_id=42)
        lojas = [{'id': 21, 'nome': 'Loja Centro'}]

        with (
            patch.object(
                Vale.objects, 'filter', return_value=_QueryResult([vale]),
            ) as filtro_vales,
            patch.object(
                Loja.objects, 'filter', return_value=_QueryResult(lojas),
            ) as filtro_lojas,
            patch('core.gprb.connect', side_effect=AssertionError('GPRB não deve ser consultado')) as conectar_gprb,
        ):
            response = candidato_api.api_lojas_por_prefeitura(
                self._request('/candidato/api/lojas/', {'prefeitura_id': '11'}),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content),
            {'lojas': [{'id': 21, 'nome': 'Loja Centro'}]},
        )
        filtro_vales.assert_called_once_with(pk='11', tenant_id=42, status='ATIVA')
        filtro_lojas.assert_called_once_with(tenant_id=42, situacao='ATIVA')
        conectar_gprb.assert_not_called()

    def test_api_lojas_allows_saas_admin_to_choose_any_local_vale(self):
        vale = SimpleNamespace(pk=11, tenant_id=99)
        lojas = [{'id': 21, 'nome': 'Loja Centro'}]

        with (
            patch.object(
                Vale.objects, 'filter', return_value=_QueryResult([vale]),
            ) as filtro_vales,
            patch.object(
                Loja.objects, 'filter', return_value=_QueryResult(lojas),
            ) as filtro_lojas,
            patch.object(candidato_api, '_tenant_id', return_value=42) as tenant_id,
        ):
            response = candidato_api.api_lojas_por_prefeitura(
                self._request(
                    '/candidato/api/lojas/',
                    {'prefeitura_id': '11'},
                    tenant_id=None,
                    role='admin_saas',
                ),
            )

        self.assertEqual(
            json.loads(response.content),
            {'lojas': [{'id': 21, 'nome': 'Loja Centro'}]},
        )
        filtro_vales.assert_called_once_with(pk='11', status='ATIVA')
        filtro_lojas.assert_called_once_with(tenant_id=99, situacao='ATIVA')
        tenant_id.assert_not_called()

    def test_candidate_card_shows_name_vale_and_store_without_test_mx_prefix(self):
        candidato = SimpleNamespace(
            id=8,
            nome_completo='Mariana Silva',
            cpf='123.456.789-00',
            status=Candidato.Status.EM_ANALISE,
            revisao_atual='DM',
            prefeitura='730420e3-b98b-4d20-8115-fb5392841964',
            loja='Loja Centro',
            tenant_id=42,
            email='',
            grau='MX',
            updated_at=None,
            data_aprovacao=None,
            get_status_display=lambda: 'Em análise',
        )

        with (
            patch.object(
                Candidato.objects, 'filter',
                return_value=_QueryResult([candidato]),
            ),
            patch.object(
                Vale.objects, 'filter',
                return_value=_QueryResult([{'id': 11, 'nome': 'Vale Centro'}]),
            ) as filtro_vales,
            patch('recepcao.views.helpers.cache.get', side_effect=[0, None]),
            patch('recepcao.views.helpers.cache.set'),
            patch(
                'recepcao.views.helpers.prefeitura_info',
                return_value={
                    'nome': '730420e3-b98b-4d20-8115-fb5392841964',
                    'sigla': 'VC',
                },
            ) as resolver_externo,
        ):
            cards = cards_candidatos(42)

        html = render_to_string('recepcao/kanban.html', {
            'web_pode_editar': False,
            'web_eh_admin': False,
            'colunas': [{
                'key': 'suplica',
                'name': 'Súplica',
                'color': '#94a3b8',
                'count': 1,
                'cards': cards,
                'ocultos': 0,
                'soma': '',
            }],
        })

        self.assertIn('Mariana Silva', html)
        self.assertIn('Vale: Vale Centro', html)
        self.assertIn('Loja: Loja Centro', html)
        self.assertNotIn('CPF:', html)
        self.assertNotIn('MX Mariana Silva', html)
        self.assertNotIn('>MX</span>', html)
        self.assertEqual(filtro_vales.call_count, 2)
        self.assertEqual(filtro_vales.call_args_list[0].kwargs, {'tenant_id': 42})
        resolver_externo.assert_not_called()
