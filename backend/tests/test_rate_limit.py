"""Shared rate limiting uses Redis when it answers, and this process when it does not."""

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.rate_limit import enforce_rate_limit


class _Client:
    host = "198.51.100.8"


class _Request:
    client = _Client()


def test_redis_counter_is_used_when_available(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    get_settings.cache_clear()
    counts = {"value": 0}

    class FakeRedis:
        def incr(self, _key):
            counts["value"] += 1
            return counts["value"]

        def expire(self, _key, _seconds):
            return True

    monkeypatch.setattr("redis.Redis.from_url", lambda *_args, **_kwargs: FakeRedis())
    try:
        for _ in range(10):
            enforce_rate_limit(_Request(), scope="redis-probe", limit=10)
        try:
            enforce_rate_limit(_Request(), scope="redis-probe", limit=10)
            raised = False
        except AppError as exc:
            raised = exc.status_code == 429
        assert raised
        assert counts["value"] == 11
    finally:
        get_settings.cache_clear()
