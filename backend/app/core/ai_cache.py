"""Simple in-memory TTL cache for AI responses.

Used for:
- Field explanations: keyed by requirement_item_id, TTL 24h
- Standard info: keyed by standard_id, TTL 7d

Thread-safe via dict atomicity in CPython. Not shared across workers.
For multi-worker setups, replace with Redis-backed cache.
"""

from datetime import UTC, datetime, timedelta
from typing import Any


class AIResponseCache:
    def __init__(self):
        self._store: dict[str, tuple[Any, datetime]] = {}

    def get(self, namespace: str, key: str | int) -> Any | None:
        cache_key = f"{namespace}:{key}"
        entry = self._store.get(cache_key)
        if entry is None:
            return None
        value, expires_at = entry
        if datetime.now(UTC) > expires_at:
            del self._store[cache_key]
            return None
        return value

    def set(self, namespace: str, key: str | int, value: Any, ttl: timedelta) -> None:
        cache_key = f"{namespace}:{key}"
        self._store[cache_key] = (value, datetime.now(UTC) + ttl)

    def invalidate(self, namespace: str, key: str | int) -> None:
        cache_key = f"{namespace}:{key}"
        self._store.pop(cache_key, None)

    def clear(self, namespace: str | None = None) -> None:
        if namespace is None:
            self._store.clear()
        else:
            prefix = f"{namespace}:"
            keys_to_remove = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._store[k]


# Singleton shared across requests within a single worker
ai_cache = AIResponseCache()

# TTL constants matching TZ-AIAssistance 12.1
FIELD_EXPLAIN_TTL = timedelta(hours=24)
STANDARD_INFO_TTL = timedelta(days=7)
