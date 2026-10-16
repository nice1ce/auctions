def test_register_creates_session(client):
    response = client.post(
        "/api/auth/register", json={"email": "new@test.com", "password": "password123"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@test.com"
    assert "session" in response.cookies


def test_duplicate_email_is_rejected(client):
    client.post(
        "/api/auth/register", json={"email": "dup@test.com", "password": "password123"}
    )
    response = client.post(
        "/api/auth/register", json={"email": "dup@test.com", "password": "password123"}
    )
    assert response.status_code == 409


def test_login_wrong_password_rejected(client):
    client.post(
        "/api/auth/register",
        json={"email": "login@test.com", "password": "password123"},
    )
    response = client.post(
        "/api/auth/login", json={"email": "login@test.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401


def test_login_success(client):
    client.post(
        "/api/auth/register",
        json={"email": "success@test.com", "password": "password123"},
    )
    response = client.post(
        "/api/auth/login", json={"email": "success@test.com", "password": "password123"}
    )
    assert response.status_code == 200
    assert "session" in response.cookies


def test_logout_clears_session(client):
    client.post(
        "/api/auth/register",
        json={"email": "logout@test.com", "password": "password123"},
    )
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
