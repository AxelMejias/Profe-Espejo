"""Tests de integración del módulo Admin (doc §5/§13) — gestión de usuarios y roles (RBAC)."""


def _registrar(client, email):
    r = client.post("/api/v1/auth/register", json={
        "nombre": "Test", "apellido": "User", "email": email, "password": "Test1234!",
    })
    # El register puede setear cookie de sesión; la limpiamos para no pisar el Bearer del admin.
    client.cookies.clear()
    return r


def test_listar_usuarios_sin_auth_401(client):
    r = client.get("/api/v1/admin/usuarios")
    assert r.status_code == 401


def test_listar_usuarios_requiere_admin(client, client_headers):
    r = client.get("/api/v1/admin/usuarios", headers=client_headers)
    assert r.status_code == 403


def test_listar_usuarios_admin(client, admin_headers):
    r = client.get("/api/v1/admin/usuarios", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 1


def test_obtener_usuario_por_id(client, admin_headers):
    uid = _registrar(client, "admin_detalle@test.com").json()["id"]
    r = client.get(f"/api/v1/admin/usuarios/{uid}", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == uid


def test_asignar_y_remover_rol(client, admin_headers):
    uid = _registrar(client, "admin_rol@test.com").json()["id"]
    r = client.post(f"/api/v1/admin/usuarios/{uid}/roles", headers=admin_headers,
                    json={"rol_codigo": "STOCK"})
    assert r.status_code == 201, r.text
    assert any(rol["codigo"] == "STOCK" for rol in r.json()["roles"])
    r = client.delete(f"/api/v1/admin/usuarios/{uid}/roles/STOCK", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert all(rol["codigo"] != "STOCK" for rol in r.json()["roles"])


def test_actualizar_usuario(client, admin_headers):
    uid = _registrar(client, "admin_update@test.com").json()["id"]
    r = client.put(f"/api/v1/admin/usuarios/{uid}", headers=admin_headers,
                   json={"nombre": "Renombrado"})
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Renombrado"


def test_eliminar_usuario(client, admin_headers):
    uid = _registrar(client, "admin_delete@test.com").json()["id"]
    r = client.delete(f"/api/v1/admin/usuarios/{uid}", headers=admin_headers)
    assert r.status_code == 204, r.text
