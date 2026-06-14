"""Tests de integración del módulo Estadísticas (doc §11/§13) — 5 endpoints, solo ADMIN."""

_PERIODO = {"desde": "2026-01-01", "hasta": "2026-12-31"}


def test_resumen_requiere_admin(client, client_headers):
    r = client.get("/api/v1/estadisticas/resumen", headers=client_headers)
    assert r.status_code == 403


def test_resumen_ok(client, admin_headers):
    r = client.get("/api/v1/estadisticas/resumen", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), dict)


def test_ventas_por_periodo(client, admin_headers):
    r = client.get("/api/v1/estadisticas/ventas", headers=admin_headers, params={**_PERIODO, "agrupacion": "day"})
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_productos_top(client, admin_headers):
    r = client.get("/api/v1/estadisticas/productos-top", headers=admin_headers, params=_PERIODO)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_ingresos_por_forma_pago(client, admin_headers):
    r = client.get("/api/v1/estadisticas/ingresos", headers=admin_headers, params=_PERIODO)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_pedidos_por_estado_incluye_cancelado(client, client_headers, admin_headers, producto_factory):
    """EST: la distribución por estado refleja un pedido cancelado."""
    prod = producto_factory(nombre="Burger Estado", precio_base="1000.00")
    r = client.post("/api/v1/pedidos/", headers=client_headers, json={
        "forma_pago_codigo": "EFECTIVO",
        "items": [{"producto_id": prod.id, "cantidad": 1}],
    })
    pid = r.json()["id"]
    client.delete(f"/api/v1/pedidos/{pid}", headers=client_headers)  # → CANCELADO

    r2 = client.get("/api/v1/estadisticas/pedidos-por-estado", headers=admin_headers)
    assert r2.status_code == 200, r2.text
    estados = {row["estado_codigo"]: row["cantidad"] for row in r2.json()}
    assert estados.get("CANCELADO", 0) >= 1


def test_estadisticas_sin_auth_401(client):
    r = client.get("/api/v1/estadisticas/resumen")
    assert r.status_code == 401
