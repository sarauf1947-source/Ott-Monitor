"""
OTT Monitor - Redis Cache Utility
Provides async caching helpers with JSON serialization.
"""

import json
import logging
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    """Extended JSON encoder supporting UUID and datetime."""
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def _serialize(data: Any) -> str:
    return json.dumps(data, cls=JSONEncoder)


def _deserialize(raw: str) -> Any:
    return json.loads(raw)


# Global async Redis client
redis_client = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
    max_connections=50,
)


async def cache_get(key: str) -> Optional[Any]:
    """Get a cached value. Returns None on miss or error."""
    try:
        raw = await redis_client.get(key)
        if raw is None:
            return None
        return _deserialize(raw)
    except Exception as e:
        logger.warning(f"Redis GET error for key '{key}': {e}")
        return None


async def cache_set(key: str, value: Any, ttl: int = settings.REDIS_TTL_DEFAULT) -> bool:
    """Set a value in cache with TTL (seconds). Returns True on success."""
    try:
        serialized = _serialize(value)
        await redis_client.setex(key, ttl, serialized)
        return True
    except Exception as e:
        logger.warning(f"Redis SET error for key '{key}': {e}")
        return False


async def cache_delete(key: str) -> bool:
    """Delete a cache key. Returns True on success."""
    try:
        await redis_client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Redis DEL error for key '{key}': {e}")
        return False


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a pattern. Returns number of deleted keys."""
    try:
        keys = await redis_client.keys(pattern)
        if keys:
            return await redis_client.delete(*keys)
        return 0
    except Exception as e:
        logger.warning(f"Redis pattern delete error for '{pattern}': {e}")
        return 0


async def cached(
    key: str,
    ttl: int,
    fetch_fn: Callable,
    *args,
    **kwargs,
) -> Any:
    """
    Cache-aside pattern helper.
    Tries cache first; calls fetch_fn on miss and stores result.
    """
    hit = await cache_get(key)
    if hit is not None:
        return hit
    result = await fetch_fn(*args, **kwargs)
    if result is not None:
        await cache_set(key, result, ttl=ttl)
    return result


# ── Cache Key Builders ─────────────────────────────────────────────────────────

class CacheKeys:
    DASHBOARD_SUMMARY = "ott:dashboard:summary"
    CHANNEL_LIST = "ott:channels:list"
    CHANNEL_STATUS = "ott:channel:{id}:status"
    CHANNEL_METRICS_LATEST = "ott:channel:{id}:metrics:latest"
    CHANNEL_ERRORS_RECENT = "ott:channel:{id}:errors:recent"
    ALERTS_OPEN = "ott:alerts:open"

    @staticmethod
    def channel_status(channel_id: str) -> str:
        return f"ott:channel:{channel_id}:status"

    @staticmethod
    def channel_metrics(channel_id: str) -> str:
        return f"ott:channel:{channel_id}:metrics:latest"

    @staticmethod
    def channel_errors(channel_id: str) -> str:
        return f"ott:channel:{channel_id}:errors:recent"
