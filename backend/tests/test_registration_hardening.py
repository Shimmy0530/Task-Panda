import pytest
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import app
from app.models import User
from app.routers import auth as auth_router


ADMIN_PASSWORD = "admin-password-123"
REGISTER_PASSWORD = "register-password-123"


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _setup_admin(client: TestClient) -> None:
    response = client.post(
        "/api/auth/setup",
        json={"username": "admin", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200


def test_first_register_after_setup_succeeds(client):
    _setup_admin(client)
    response = client.post(
        "/api/auth/register",
        json={"username": "newcomer", "password": REGISTER_PASSWORD},
    )
    assert response.status_code == 201
    assert response.json() == {"ok": True, "pending": True}


def test_register_is_rate_limited_per_ip(client):
    """A burst from the same client IP is cut off after the per-window cap."""
    _setup_admin(client)
    for i in range(auth_router._REGISTER_MAX_PER_WINDOW):
        response = client.post(
            "/api/auth/register",
            json={"username": f"user{i}", "password": REGISTER_PASSWORD},
        )
        assert response.status_code == 201

    blocked = client.post(
        "/api/auth/register",
        json={"username": "one-too-many", "password": REGISTER_PASSWORD},
    )
    assert blocked.status_code == 429
    assert "registration attempts" in blocked.json()["detail"].lower()


def test_register_blocked_when_pending_cap_reached(client, db_session):
    """Once the users table holds the max outstanding pending rows, a fresh
    registration (from an unthrottled IP) is refused with 429."""
    _setup_admin(client)
    for i in range(auth_router._MAX_PENDING_ACCOUNTS):
        db_session.add(
            User(
                username=f"pending{i}",
                password_hash=hash_password(REGISTER_PASSWORD),
                is_admin=False,
                approved_at=None,
            )
        )
    db_session.commit()

    # Distinct X-Real-IP so the per-IP limiter isn't what trips here.
    response = client.post(
        "/api/auth/register",
        json={"username": "overflow", "password": REGISTER_PASSWORD},
        headers={"X-Real-IP": "203.0.113.7"},
    )
    assert response.status_code == 429
    assert "pending registrations" in response.json()["detail"].lower()
