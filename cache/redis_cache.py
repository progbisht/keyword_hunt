import json
import os
import logging
from typing import Optional
from dotenv import load_dotenv
from models.keyword import KeywordDiscoveryResult

load_dotenv()

logger = logging.getLogger("cache")


def get_redis_url() -> Optional[str]:
    return os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")


def _get_cache_key(seed_keyword: str) -> str:
    clean_seed = seed_keyword.strip().lower()
    return f"kw_discovery:{clean_seed}"


async def get_cached_discovery(seed_keyword: str) -> Optional[KeywordDiscoveryResult]:
    """Retrieves cached KeywordDiscoveryResult from Upstash Redis if available."""
    redis_url = get_redis_url()
    if not redis_url:
        return None

    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(redis_url, decode_responses=True)
        try:
            key = _get_cache_key(seed_keyword)
            cached_data = await client.get(key)
            if cached_data:
                logger.info(f"⚡ Cache HIT in Upstash Redis for seed: '{seed_keyword}'")
                parsed = json.loads(cached_data)
                return KeywordDiscoveryResult(**parsed)
        finally:
            await client.aclose()
    except Exception as e:
        logger.warning(f"⚠️ Redis cache lookup failed: {e}")

    return None


async def set_cached_discovery(
    result: KeywordDiscoveryResult, ttl_seconds: int = 604800
) -> bool:
    """Caches KeywordDiscoveryResult in Upstash Redis (default TTL: 7 days)."""
    redis_url = get_redis_url()
    if not redis_url:
        return False

    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(redis_url, decode_responses=True)
        try:
            key = _get_cache_key(result.seed_keyword)
            payload = json.dumps(result.model_dump())
            await client.set(key, payload, ex=ttl_seconds)
            logger.info(f"💾 Saved cached result to Upstash Redis for seed: '{result.seed_keyword}' (TTL: {ttl_seconds}s)")
            return True
        finally:
            await client.aclose()
    except Exception as e:
        logger.warning(f"⚠️ Redis cache set failed: {e}")
        return False
