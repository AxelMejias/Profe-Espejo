"""Tests de integración del módulo Productos (doc §5.2/§13) — lectura, stock y RBAC."""


def test_listar_productos_autenticado(client, client_headers):
    # NOTA: el código exige autenticación para el catálogo (el front también lo
    # gatea con ProtectedRoute). El PDF §5.2 lo marca "Público" → divergencia de
    # diseño a decidir con el equipo. El test refleja el comportamiento ACTUAL.
    r = client.get("/api/v1/productos/", headers=client_headers)
    assert r.status_code == 200, r.text
    assert "items" in r.json()


def test_listar_productos_sin_auth_401(client):
    r = client.get("/api/v1/productos/")
    assert r.status_code == 401


def test_obtener_producto_por_id(client, client_headers, producto_factory):
    prod = producto_factory(nombre="Burger Detalle", precio_base="1200.00", stock_cantidad=33)
    r = client.get(f"/api/v1/productos/{prod.id}", headers=client_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "precio_base" in body
    assert body["stock_cantidad"] == 33


def test_actualizar_stock_rol_stock(client, stock_headers, producto_factory):
    prod = producto_factory(nombre="Burger Stock A", stock_cantidad=10)
    r = client.patch(f"/api/v1/productos/{prod.id}/stock", headers=stock_headers,
                     json={"stock_cantidad": 99})
    assert r.status_code == 200, r.text
    assert r.json()["stock_cantidad"] == 99


def test_actualizar_stock_cliente_403(client, client_headers, producto_factory):
    prod = producto_factory(nombre="Burger Stock B")
    r = client.patch(f"/api/v1/productos/{prod.id}/stock", headers=client_headers,
                     json={"stock_cantidad": 5})
    assert r.status_code == 403


def test_actualizar_stock_negativo_rechazado(client, stock_headers, producto_factory):
    prod = producto_factory(nombre="Burger Stock C")
    r = client.patch(f"/api/v1/productos/{prod.id}/stock", headers=stock_headers,
                     json={"stock_cantidad": -5})
    assert r.status_code == 422  # Field(ge=0) en StockUpdate


def test_toggle_disponibilidad_admin(client, admin_headers, producto_factory):
    prod = producto_factory(nombre="Burger Disp", disponible=True)
    r = client.patch(f"/api/v1/productos/{prod.id}/disponibilidad", headers=admin_headers,
                     json={"disponible": False})
    assert r.status_code == 200, r.text
    assert r.json()["disponible"] is False
