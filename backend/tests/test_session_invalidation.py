import os
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("LLM_API_KEY", "test-llm-key")
TEST_DB_PATH = Path(os.environ.get("TEMP", "C:/tmp")) / "task-panda-session-tests.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB_PATH.as_posix()}")

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import hash_password
from app.db import SessionLocal, engine, init_db
from app.main import app
from app.models import Base
from app.routers import auth as auth_router


ADMIN_PASSWORD = "admin-password-123"
USER_PASSWORD = "user-password-123"


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    auth_router._PENDING_TOTP.clear()
    init_db()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _setup_admin(client: TestClient, username: str = "admin") -> None:
    response = client.post(
        "/api/auth/setup",
        json={"username": username, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200


def _login(client: TestClient, username: str, password: str, totp_code: str | None = None) -> str:
    payload = {"username": username, "password": password}
    if totp_code is not None:
        payload["totp_code"] = totp_code
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    cookie = response.cookies.get("focus_session")
    assert cookie
    return cookie


def _authenticated_client(cookie: str) -> TestClient:
    test_client = TestClient(app)
    test_client.cookies.set("focus_session", cookie)
    return test_client


def _assert_cookie_rejected(cookie: str) -> None:
    with _authenticated_client(cookie) as stale_client:
        response = stale_client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid session"


def test_password_change_invalidates_existing_session_and_allows_new_login(client):
    _setup_admin(client)
    old_cookie = _login(client, "admin", ADMIN_PASSWORD)

    authed = _authenticated_client(old_cookie)
    response = authed.post(
        "/api/auth/change-password",
        json={
            "current_password": ADMIN_PASSWORD,
            "new_password": "new-admin-password-123",
        },
    )
    authed.close()
    assert response.status_code == 200

    _assert_cookie_rejected(old_cookie)
    new_cookie = _login(client, "admin", "new-admin-password-123")
    assert new_cookie != old_cookie


def test_admin_password_reset_invalidates_target_users_existing_session(client):
    _setup_admin(client)
    admin_cookie = _login(client, "admin", ADMIN_PASSWORD)
    admin_client = _authenticated_client(admin_cookie)
    create_response = admin_client.post(
        "/api/admin/users",
        json={
            "username": "worker",
            "password": USER_PASSWORD,
            "is_admin": False,
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]
    user_cookie = _login(client, "worker", USER_PASSWORD)

    reset_response = admin_client.post(
        f"/api/admin/users/{user_id}/reset-password",
        json={"new_password": "reset-user-password-123"},
    )
    admin_client.close()
    assert reset_response.status_code == 200

    _assert_cookie_rejected(user_cookie)
    _login(client, "worker", "reset-user-password-123")


def test_disabled_user_is_rejected_even_with_current_session(client):
    _setup_admin(client)
    admin_cookie = _login(client, "admin", ADMIN_PASSWORD)
    admin_client = _authenticated_client(admin_cookie)
    create_response = admin_client.post(
        "/api/admin/users",
        json={
            "username": "worker",
            "password": USER_PASSWORD,
            "is_admin": False,
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]
    user_cookie = _login(client, "worker", USER_PASSWORD)

    disable_response = admin_client.post(f"/api/admin/users/{user_id}/disable")
    admin_client.close()
    assert disable_response.status_code == 200

    with _authenticated_client(user_cookie) as disabled_client:
        response = disabled_client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Account disabled"


def test_totp_confirm_and_disable_each_invalidate_existing_session(client):
    _setup_admin(client)
    initial_cookie = _login(client, "admin", ADMIN_PASSWORD)
    authed = _authenticated_client(initial_cookie)

    setup_response = authed.post("/api/auth/totp/setup")
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]
    confirm_response = authed.post(
        "/api/auth/totp/confirm",
        json={"code": pyotp.TOTP(secret).now()},
    )
    authed.close()
    assert confirm_response.status_code == 200
    _assert_cookie_rejected(initial_cookie)

    totp_cookie = _login(client, "admin", ADMIN_PASSWORD, pyotp.TOTP(secret).now())
    totp_client = _authenticated_client(totp_cookie)
    disable_response = totp_client.post(
        "/api/auth/totp/disable",
        json={"password": ADMIN_PASSWORD},
    )
    totp_client.close()
    assert disable_response.status_code == 200
    _assert_cookie_rejected(totp_cookie)

    _login(client, "admin", ADMIN_PASSWORD)


def test_existing_users_without_session_version_are_backfilled_and_can_login(client):
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                created_at DATETIME,
                last_ritual_date DATE,
                stuck_threshold_days INTEGER DEFAULT 5,
                username VARCHAR(80),
                password_hash VARCHAR(200),
                totp_secret VARCHAR(64),
                is_admin INTEGER NOT NULL DEFAULT 0,
                disabled_at DATETIME,
                approved_at DATETIME,
                welcomed_at DATETIME
            )
        """))
        conn.execute(
            text("""
                INSERT INTO users (
                    id, created_at, username, password_hash, is_admin
                ) VALUES (
                    1, '2026-05-14 00:00:00', :username, :password_hash, 1
                )
            """),
            {
                "username": "legacy",
                "password_hash": hash_password("legacy-password-123"),
            },
        )

    init_db()

    cookie = _login(client, "legacy", "legacy-password-123")
    with _authenticated_client(cookie) as authed:
        response = authed.get("/api/auth/me")
    assert response.status_code == 200
