"""Invalidação de cache do kanban de candidatos."""

from django.core.cache import cache


def invalidar_cache_kanban(tenant_id):
    """Invalida caches relacionados ao kanban.

    Limpa tanto o cache sem filtro quanto com filtros de prefeitura.
    """
    cache_keys_to_delete = [
        f'recepcao_cards_candidatos_{tenant_id}_30_todas',
        f'recepcao_cards_candidatos_{tenant_id}_50_todas',
        f'recepcao_cards_candidatos_{tenant_id}_30',
        f'recepcao_cards_candidatos_{tenant_id}_50',
    ]
    for key in cache_keys_to_delete:
        cache.delete(key)

    version_key = f'recepcao_cards_candidatos_version_{tenant_id}'
    current_version = cache.get(version_key, 0)
    cache.set(version_key, current_version + 1, timeout=3600)
