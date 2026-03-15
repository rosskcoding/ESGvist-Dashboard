"""
Redis connection management.

Used for background jobs, caching, and optional token/session storage.
"""

from functools import lru_cache

import redis.asyncio as redis

from app.config import settings


@lru_cache
def get_redis() -> redis.Redis:
    """
    Get a singleton Redis client.

    Note: connection is established lazily on first command.
    """
    return redis.from_url(
        str(settings.redis_url),
        encoding="utf-8",
        decode_responses=True,
    )


async def close_redis() -> None:
    """Close Redis client connection pool."""
    client = get_redis()
    await client.aclose()






