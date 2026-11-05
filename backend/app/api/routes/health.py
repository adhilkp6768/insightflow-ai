from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import get_engine

router = APIRouter()


def _database_status() -> str:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return "error"
    return "ok"


def _redis_status(url: str) -> str:
    if not url.strip():
        return "skipped"
    client = Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    try:
        client.ping()
    except RedisError:
        return "error"
    finally:
        client.close()
    return "ok"


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "name": settings.app_name, "version": settings.app_version}


@router.get("/health/ready")
def readiness() -> JSONResponse:
    checks = {
        "database": {"status": _database_status()},
        "redis": {"status": _redis_status(get_settings().redis_url)},
    }
    ready = all(item["status"] in {"ok", "skipped"} for item in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ok" if ready else "unavailable", "checks": checks},
    )
