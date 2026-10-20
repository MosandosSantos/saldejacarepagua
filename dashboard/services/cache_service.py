"""Cache service com composition para o dashboard.

Separa a logica de cache da logica de negocio.
Permite testes com cache fake e facil substituicao do backend.
"""

import logging
from typing import Any, Protocol

from django.core.cache import cache

logger = logging.getLogger(__name__)


class CacheBackend(Protocol):
    """Interface para backends de cache."""
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, timeout: int) -> None: ...
    def delete(self, key: str) -> None: ...


class DjangoCacheBackend:
    """Backend de cache usando django.core.cache."""

    def __init__(self, cache_instance=None):
        self._cache = cache_instance or cache

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any, timeout: int = 30) -> None:
        self._cache.set(key, value, timeout=timeout)

    def delete(self, key: str) -> None:
        self._cache.delete(key)


class FakeCacheBackend:
    """Backend de cache para testes (in-memory)."""

    def __init__(self):
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, value: Any, timeout: int = 30) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class DashboardCache:
    """Cache para dados do dashboard com invalidacao por tenant."""

    PREFIX = 'dash'

    def __init__(self, backend: CacheBackend = None, timeout: int = 30):
        self._backend = backend or DjangoCacheBackend()
        self._timeout = timeout

    def _make_key(self, tid, nicho, suffix=''):
        key = f'{self.PREFIX}:{tid}:{nicho}'
        return f'{key}:{suffix}' if suffix else key

    def get_kpis(self, tid, nicho):
        """Busca KPIs cached ou None."""
        return self._backend.get(self._make_key(tid, nicho, 'kpis'))

    def set_kpis(self, tid, nicho, data):
        """Armazena KPIs no cache."""
        self._backend.set(self._make_key(tid, nicho, 'kpis'), data, self._timeout)

    def get_funil(self, tid, nicho):
        """Busca dados do funil cached."""
        return self._backend.get(self._make_key(tid, nicho, 'funil'))

    def set_funil(self, tid, nicho, data):
        """Armazena dados do funil."""
        self._backend.set(self._make_key(tid, nicho, 'funil'), data, self._timeout)

    def invalidate(self, tid, nicho):
        """Invalida todos os dados do dashboard para um tenant."""
        for suffix in ('kpis', 'funil', 'origem', 'segmento'):
            self._backend.delete(self._make_key(tid, nicho, suffix))
