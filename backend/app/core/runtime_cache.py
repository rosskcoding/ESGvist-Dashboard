from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, _CacheEntry[T]] = {}
        self._lock = asyncio.Lock()

    def _is_valid(self, entry: _CacheEntry[T] | None) -> bool:
        return entry is not None and entry.expires_at > time.monotonic()

    async def get(self, key: str) -> T | None:
        async with self._lock:
            entry = self._items.get(key)
            if not self._is_valid(entry):
                self._items.pop(key, None)
                return None
            return entry.value

    async def set(self, key: str, value: T) -> T:
        async with self._lock:
            self._items[key] = _CacheEntry(
                value=value,
                expires_at=time.monotonic() + self.ttl_seconds,
            )
            return value

    async def get_or_set(self, key: str, factory: Callable[[], Awaitable[T]]) -> T:
        cached = await self.get(key)
        if cached is not None:
            return cached

        async with self._lock:
            entry = self._items.get(key)
            if self._is_valid(entry):
                return entry.value

            value = await factory()
            self._items[key] = _CacheEntry(
                value=value,
                expires_at=time.monotonic() + self.ttl_seconds,
            )
            return value

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            self._items.pop(key, None)

    async def invalidate_where(self, predicate: Callable[[str], bool]) -> None:
        async with self._lock:
            keys = [key for key in self._items if predicate(key)]
            for key in keys:
                self._items.pop(key, None)
