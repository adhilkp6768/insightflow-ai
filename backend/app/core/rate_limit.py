import logging
import time

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)
_buckets: dict[str, list[float]] = {}


def _reject(window_seconds: int) -> None:
    raise AppError(
        "rate_limited",
        "Too many attempts. Try again shortly.",
        429,
        headers={"Retry-After": str(window_seconds)},
    )


def _redis_count(key: str, window_seconds: int) -> int | None:
    redis_url = get_settings().redis_url
    if not redis_url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(redis_url, socket_connect_timeout=0.3, socket_timeout=0.3)
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, window_seconds)
        return count
    except Exception:
        logger.warning("Redis rate limit is unavailable. This process will count attempts locally.")
        return None


def enforce_rate_limit(
    request: Request, *, scope: str, limit: int = 10, window_seconds: int = 60
) -> None:
    if not get_settings().rate_limit_enabled:
        return
    host = request.client.host if request.client else "unknown"
    key = f"insightflow:rate:{scope}:{host}"
    shared = _redis_count(key, window_seconds)
    if shared is not None:
        if shared > limit:
            _reject(window_seconds)
        return
    now = time.monotonic()
    recent = [stamp for stamp in _buckets.get(key, []) if now - stamp < window_seconds]
    if len(recent) >= limit:
        _reject(window_seconds)
    recent.append(now)
    _buckets[key] = recent
