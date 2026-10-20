"""Data backfill contract for the Loja body field."""

from uuid import uuid4

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from acesso.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)

MIGRATE_FROM = [('contatos', '0025_grau_grau_numero_4_33')]


def test_existing_lojas_receive_perfeicao_when_migrated():
    suffix = uuid4().hex
    tenant = Tenant.objects.create(
        nome='Loja corpo migration',
        slug=f'loja-corpo-{suffix}',
    )
    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATE_FROM)
    try:
        old_apps = executor.loader.project_state(MIGRATE_FROM).apps
        Loja = old_apps.get_model('contatos', 'Loja')
        loja = Loja.objects.create(
            tenant_id=tenant.pk,
            nome='Loja antes da migration',
            numero='14',
        )
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        executor.migrate(targets)
        migrated_apps = executor.loader.project_state(targets).apps
        MigratedLoja = migrated_apps.get_model('contatos', 'Loja')
        migrated = MigratedLoja.objects.get(pk=loja.pk)

        assert migrated.corpo == 'perfeicao'
        assert migrated.nome == 'Loja antes da migration'
        assert migrated.numero == '14'
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
