"""Tests de integración del módulo Unidades de Medida (doc §5/§13) — CRUD y RBAC."""


def test_listar_unidades_autenticado(client, client_headers):
    r = client.get("/api/v1/unidades/", headers=client_headers)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


def test_listar_unidades_sin_auth_401(client):
    r = client.get("/api/v1/unidades/")
    assert r.status_code == 401


def test_crear_unidad_admin(client, admin_headers):
    r = client.post("/api/v1/unidades/", headers=admin_headers,
                    json={"nombre": "docena", "simbolo": "doc", "tipo": "contable"})
    assert r.status_code == 201, r.text
    assert r.json()["simbolo"] == "doc"


def test_crear_unidad_requiere_admin(client, client_headers):
    r = client.post("/api/v1/unidades/", headers=client_headers,
                    json={"nombre": "caja", "simbolo": "cja", "tipo": "contable"})
    assert r.status_code == 403


def test_obtener_unidad_por_id(client, admin_headers):
    uid = client.post("/api/v1/unidades/", headers=admin_headers,
                      json={"nombre": "bandeja", "simbolo": "bnd", "tipo": "contable"}).json()["id"]
    r = client.get(f"/api/v1/unidades/{uid}", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == uid


def test_actualizar_unidad_admin(client, admin_headers):
    uid = client.post("/api/v1/unidades/", headers=admin_headers,
                      json={"nombre": "sobre", "simbolo": "sbr", "tipo": "contable"}).json()["id"]
    r = client.put(f"/api/v1/unidades/{uid}", headers=admin_headers, json={"nombre": "sobre-grande"})
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "sobre-grande"


def test_eliminar_unidad_admin(client, admin_headers):
    uid = client.post("/api/v1/unidades/", headers=admin_headers,
                      json={"nombre": "lata", "simbolo": "lta", "tipo": "contable"}).json()["id"]
    r = client.delete(f"/api/v1/unidades/{uid}", headers=admin_headers)
    assert r.status_code == 204, r.text
