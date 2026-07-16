"""Redis-mijoz (lazy, global). Kalit-qurish faqat app.modules.tracking.keys orqali —
tenant-prefiks (t:{org}:) bitta joyda bo'lishi izolyatsiya-talabi (reja §4)."""

import redis.asyncio as aioredis

from app.config import get_settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _client
