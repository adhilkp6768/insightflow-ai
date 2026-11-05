import os

# Environment must be set before the application reads settings.
# ruff: noqa: E402

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret-key-with-32-characters-min"
os.environ["REDIS_URL"] = ""
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["JOBS_INLINE"] = "true"
os.environ["ENVIRONMENT"] = "test"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import get_engine, get_session_factory, reset_engine
from app.main import create_app
from app.models import Base


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    reset_engine()
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(create_app()) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)
    reset_engine()
    get_settings.cache_clear()


@pytest.fixture
def db_session(client):
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def register(
    client: TestClient,
    email: str = "ada@example.com",
    password: str = "password123",
    full_name: str = "Ada Lovelace",
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 201, response.text
    return response.json()
