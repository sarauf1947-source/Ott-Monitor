# -*- coding: utf-8 -*-
"""OTT Monitor - Redis Cache Utility"""
import json
import logging
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID
import redis.asyncio as aioredis
from config import settings

logger = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):   return str(obj)
        if isinstance(obj, datetime): return obj.isoformat()
        return super().default(obj)


def _serialize(data: Any) -> str:   return json.dumps(data, cls=JSONEncoder)
def _deserialize(raw: str) -> Any:  return json.loads(raw)


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
    try:
        raw = await redis_client.get(key)
        return _deserialize(raw) if raw is not None else None
    except Exception as e:
        logger.warning(f"Redis GET error '{key}': {e}")
        return None


async def cache_set(key: str, value: Any, ttl: int = settings.REDIS_TTL_DEFAULT) -> bool:
    try:
        await redis_client.setex(key, ttl, _serialize(value))
        return True
    except Exception as e:
        logger.warning(f"Redis SET error '{key}': {e}")
        return False


async def cache_delete(key: str) -> bool:
    try:
        await redis_client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Redis DEL error '{key}': {e}")
        return False


async def cache_delete_pattern(pattern: str) -> int:
    try:
        keys = await redis_client.keys(pattern)
        return await redis_client.delete(*keys) if keys else 0
    except Exception as e:
        logger.warning(f"Redis pattern delete error '{pattern}': {e}")
        return 0


class CacheKeys:
    DASHBOARD_SUMMARY = "ott:dashboard:summary"
    CHANNEL_LIST      = "ott:channels:list"

    @staticmethod
    def channel_status(channel_id: str) -> str:
        return f"ott:channel:{channel_id}:status"

    @staticmethod
    def channel_metrics(channel_id: str) -> str:
        return f"ott:channel:{channel_id}:metrics"
