"""Tests de integración del módulo Auth (doc §13.2/§13.3) con TestClient."""


def test_register_crea_usuario(client):
    r = client.post("/api/v1/auth/register", json={
        "nombre": "Nuevo", "apellido": "Usuario",
        "email": "nuevo_reg@test.com", "password": "Password123",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "nuevo_reg@test.com"
    assert "password_hash" not in body  # nunca exponer el hash


def test_login_devuelve_token_valido(client):
    r = client.post("/api/v1/auth/login", json={
        "email": "admin@foodstore.com", "password": "Admin1234!",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60  # doc §6.1
    client.cookies.clear()


def test_login_credenciales_invalidas_401(client):
    r = client.post("/api/v1/auth/login", json={
        "email": "admin@foodstore.com", "password": "incorrecta",
    })
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_me_devuelve_usuario_actual(client, admin_headers):
    r = client.get("/api/v1/auth/me", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "admin@foodstore.com"


def test_me_sin_token_401(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_rate_limit_login_429(client):
    """Doc §4.3: 5 intentos / 15 min en login → el 6° devuelve 429."""
    from app.modules.auth.router import limiter
    limiter.enabled = True
    try:
        codes = []
        for _ in range(7):
            r = client.post("/api/v1/auth/login", json={
                "email": "noexiste@test.com", "password": "x",
            })
            codes.append(r.status_code)
        assert 429 in codes, f"esperaba un 429 entre los intentos, hubo: {codes}"
    finally:
        limiter.enabled = False
        client.cookies.clear()
