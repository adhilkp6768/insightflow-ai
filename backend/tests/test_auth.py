from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models import ActivityLog, User
from tests.conftest import register


def test_password_hash_round_trip():
    stored = hash_password("password123")
    assert stored != "password123"
    assert verify_password("password123", stored)
    assert not verify_password("wrong-password", stored)


def test_register_login_and_me(client, db_session):
    created = register(client)
    assert created["token_type"] == "bearer"
    assert created["expires_in"] == 900
    assert created["user"]["email"] == "ada@example.com"
    assert "password" not in created["user"]

    activity = db_session.query(ActivityLog).filter_by(action="auth.register").one()
    assert activity.context.get("ip")
    assert "password" not in activity.context

    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {created['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["full_name"] == "Ada Lovelace"

    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": "Ada@Example.com", "password": "password123"},
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["user"]["email"] == "ada@example.com"


def test_duplicate_email_and_invalid_password(client):
    register(client)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"email": "ada@example.com", "password": "password123", "full_name": "Ada Lovelace"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_taken"

    rejected = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "wrong-password"},
    )
    assert rejected.status_code == 401
    assert rejected.json()["error"]["message"] == "Invalid email or password."

    missing = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )
    assert missing.status_code == 401
    assert missing.json()["error"]["message"] == "Invalid email or password."


def test_short_password_is_validation_error(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "ada@example.com", "password": "short", "full_name": "Ada Lovelace"},
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert any("8 characters" in item["msg"] for item in body["details"]["errors"])


def test_me_requires_access_token(client):
    anonymous = client.get("/api/v1/auth/me")
    assert anonymous.status_code == 401

    created = register(client)
    refresh_as_bearer = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {created['refresh_token']}"},
    )
    assert refresh_as_bearer.status_code == 401


def test_refresh_rotation_and_reuse_revokes_family(client):
    created = register(client)
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": created["refresh_token"]})
    assert rotated.status_code == 200
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh != created["refresh_token"]

    reused = client.post("/api/v1/auth/refresh", json={"refresh_token": created["refresh_token"]})
    assert reused.status_code == 401

    after_reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert after_reuse.status_code == 401


def test_logout_revokes_refresh_token(client):
    created = register(client)
    headers = {"Authorization": f"Bearer {created['access_token']}"}
    response = client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": created["refresh_token"]},
    )
    assert response.status_code == 204
    assert response.content == b""

    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": created["refresh_token"]}
    )
    assert refreshed.status_code == 401


def test_inactive_user_cannot_log_in(client, db_session):
    register(client)
    user = db_session.query(User).filter_by(email="ada@example.com").one()
    user.is_active = False
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "password123"},
    )
    assert response.status_code == 401


def test_expired_access_token_is_rejected(client):
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(minutes=5),
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
