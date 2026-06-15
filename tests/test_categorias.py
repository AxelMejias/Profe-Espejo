"""Tests de integración del módulo Categorías (doc §5/§13) — CRUD, jerarquía y RBAC."""


def test_arbol_categorias_publico(client):
    # El catálogo de categorías es público (doc §5.2).
    r = client.get("/api/v1/categorias/tree")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_crear_categoria_sin_auth_401(client):
    r = client.post("/api/v1/categorias/", json={"nombre": "Cat Anon"})
    assert r.status_code == 401


def test_crear_categoria_requiere_admin(client, client_headers):
    r = client.post("/api/v1/categorias/", headers=client_headers, json={"nombre": "Cat Cliente"})
    assert r.status_code == 403


def test_crear_categoria_admin(client, admin_headers):
    r = client.post("/api/v1/categorias/", headers=admin_headers,
                    json={"nombre": "Categoria Test Crear", "descripcion": "desc"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["nombre"] == "Categoria Test Crear"
    assert body["id"] > 0


def test_obtener_categoria_por_id(client, admin_headers):
    cid = client.post("/api/v1/categorias/", headers=admin_headers,
                      json={"nombre": "Categoria Test Detalle"}).json()["id"]
    r = client.get(f"/api/v1/categorias/{cid}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == cid


def test_actualizar_categoria_admin(client, admin_headers):
    cid = client.post("/api/v1/categorias/", headers=admin_headers,
                      json={"nombre": "Categoria Test Update"}).json()["id"]
    r = client.put(f"/api/v1/categorias/{cid}", headers=admin_headers,
                   json={"nombre": "Categoria Renombrada"})
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Categoria Renombrada"


def test_eliminar_categoria_admin(client, admin_headers):
    cid = client.post("/api/v1/categorias/", headers=admin_headers,
                      json={"nombre": "Categoria Test Borrar"}).json()["id"]
    r = client.delete(f"/api/v1/categorias/{cid}", headers=admin_headers)
    assert r.status_code == 204, r.text
    # Soft delete: ya no se obtiene.
    assert client.get(f"/api/v1/categorias/{cid}").status_code == 404
