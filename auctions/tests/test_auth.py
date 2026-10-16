import uuid

from fastapi.testclient import TestClient
from app.main import app


def _unique_email():
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


def test_register_creates_session(client):
    email = _unique_email()
    response = client.post(
        "/api/auth/register", json={"email": email, "password": "correct-horse"}
    )
    assert response.status_code == 201, response.text
    assert response.json()["email"] == email

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_duplicate_email_is_rejected(client):
    email = _unique_email()
    client.post(
        "/api/auth/register", json={"email": email, "password": "correct-horse"}
    )
    response = client.post(
        "/api/auth/register", json={"email": email, "password": "another-pass"}
    )
    assert response.status_code == 409, response.text


def test_short_password_is_rejected(client):
    response = client.post(
        "/api/auth/register", json={"email": _unique_email(), "password": "short"}
    )
    assert response.status_code == 422, response.text


def test_login_wrong_password_rejected(client):
    email = _unique_email()
    client.post(
        "/api/auth/register", json={"email": email, "password": "right-password"}
    )
    fresh = TestClient(app)  # без сессии, оставшейся после регистрации
    response = fresh.post(
        "/api/auth/login", json={"email": email, "password": "wrong-password"}
    )
    assert response.status_code == 401, response.text


def test_login_success(client):
    email = _unique_email()
    client.post(
        "/api/auth/register", json={"email": email, "password": "right-password"}
    )
    fresh = TestClient(app)
    response = fresh.post(
        "/api/auth/login", json={"email": email, "password": "right-password"}
    )
    assert response.status_code == 200, response.text
    assert fresh.get("/api/auth/me").status_code == 200


def test_logout_clears_session(client):
    client.post(
        "/api/auth/register",
        json={"email": _unique_email(), "password": "correct-horse"},
    )
    assert client.get("/api/auth/me").status_code == 200
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_me_without_login_is_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_existing_endpoints_stay_open_without_login(client):
    # Аутентификация ничего не блокирует — все прежние ручки доступны анонимно.
    assert client.get("/api/auctions").status_code == 200
    assert client.get("/api/lots").status_code == 200
    assert client.get("/api/sellers").status_code == 200
    assert client.get("/api/buyers").status_code == 200
    assert client.get("/api/sales").status_code == 200
    assert client.get("/api/reports/revenue").status_code == 200
