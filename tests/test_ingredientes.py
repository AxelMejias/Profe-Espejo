"""Tests de integración del módulo Ingredientes (doc §5/§13) — CRUD, stock y RBAC."""


def _crear(client, headers, nombre):
    return client.post("/api/v1/ingredientes/", headers=headers, json={
        "nombre": nombre, "unidad_medida": "g", "costo_unitario": "10.00",
        "stock_cantidad": "100.000", "stock_minimo": "5.000",
    })


def test_listar_ingredientes_staff(client, admin_headers):
    r = client.get("/api/v1/ingredientes/", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 1


def test_listar_ingredientes_sin_auth_401(client):
    r = client.get("/api/v1/ingredientes/")
    assert r.status_code == 401


def test_crear_ingrediente_admin(client, admin_headers):
    r = _crear(client, admin_headers, "Insumo Test Crear")
    assert r.status_code == 201, r.text
    assert r.json()["nombre"] == "Insumo Test Crear"


def test_crear_ingrediente_requiere_admin(client, client_headers):
    r = _crear(client, client_headers, "Insumo Cliente")
    assert r.status_code == 403


def test_actualizar_ingrediente_stock_rol_stock(client, admin_headers, stock_headers):
    iid = _crear(client, admin_headers, "Insumo Test Stock").json()["id"]
    # El rol STOCK puede actualizar (PUT) — incluye el stock.
    r = client.put(f"/api/v1/ingredientes/{iid}", headers=stock_headers,
                   json={"stock_cantidad": "250.000"})
    assert r.status_code == 200, r.text
    assert float(r.json()["stock_cantidad"]) == 250.0


def test_obtener_ingrediente_por_id(client, admin_headers):
    iid = _crear(client, admin_headers, "Insumo Test Detalle").json()["id"]
    r = client.get(f"/api/v1/ingredientes/{iid}", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == iid


def test_eliminar_ingrediente_admin(client, admin_headers):
    iid = _crear(client, admin_headers, "Insumo Test Borrar").json()["id"]
    r = client.delete(f"/api/v1/ingredientes/{iid}", headers=admin_headers)
    assert r.status_code == 204, r.text
