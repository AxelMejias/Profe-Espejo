"""Tests de integración del módulo Pedidos (doc §13) — FSM, cancelación, historial."""


def _crear_pedido(client, client_headers, producto, cantidad=1):
    r = client.post("/api/v1/pedidos/", headers=client_headers, json={
        "forma_pago_codigo": "EFECTIVO",
        "items": [{"producto_id": producto.id, "cantidad": cantidad}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def test_crear_pedido_nace_pendiente(client, client_headers, producto_factory):
    prod = producto_factory(nombre="Pizza Crear", precio_base="1500.00")
    body = _crear_pedido(client, client_headers, prod, cantidad=2)
    assert body["estado_codigo"] == "PENDIENTE"
    assert body["id"] > 0


def test_avanzar_estado_valido(client, client_headers, pedidos_headers, producto_factory):
    prod = producto_factory(nombre="Burger Avanzar", precio_base="1000.00")
    pedido = _crear_pedido(client, client_headers, prod)

    r = client.patch(f"/api/v1/pedidos/{pedido['id']}/estado", headers=pedidos_headers,
                     json={"estado_hacia": "CONFIRMADO"})
    assert r.status_code == 200, r.text
    assert r.json()["estado_codigo"] == "CONFIRMADO"


def test_avanzar_estado_invalido_rechazado(client, client_headers, pedidos_headers, producto_factory):
    """PENDIENTE → ENTREGADO no es una transición válida del FSM."""
    prod = producto_factory(nombre="Burger Invalida", precio_base="1000.00")
    pedido = _crear_pedido(client, client_headers, prod)

    r = client.patch(f"/api/v1/pedidos/{pedido['id']}/estado", headers=pedidos_headers,
                     json={"estado_hacia": "ENTREGADO"})
    assert r.status_code in (409, 422), r.text


def test_cancelar_pedido_propio(client, client_headers, producto_factory):
    prod = producto_factory(nombre="Burger Cancelar", precio_base="1000.00")
    pedido = _crear_pedido(client, client_headers, prod)

    r = client.delete(f"/api/v1/pedidos/{pedido['id']}", headers=client_headers)
    assert r.status_code == 200, r.text
    assert r.json()["estado_codigo"] == "CANCELADO"


def test_historial_append_only_primer_estado_desde_null(client, client_headers, pedidos_headers, producto_factory):
    prod = producto_factory(nombre="Burger Historial", precio_base="1000.00")
    pedido = _crear_pedido(client, client_headers, prod)
    client.patch(f"/api/v1/pedidos/{pedido['id']}/estado", headers=pedidos_headers,
                 json={"estado_hacia": "CONFIRMADO"})

    r = client.get(f"/api/v1/pedidos/{pedido['id']}/historial", headers=pedidos_headers)
    assert r.status_code == 200, r.text
    hist = r.json()
    assert len(hist) >= 2
    assert hist[0]["estado_desde"] is None  # RN-02
    assert hist[-1]["estado_hacia"] == "CONFIRMADO"


def test_listar_pedidos_sin_auth_401(client):
    r = client.get("/api/v1/pedidos/")
    assert r.status_code == 401


def test_cliente_no_avanza_estado_403(client, client_headers, producto_factory):
    """Avanzar estado es solo ADMIN/PEDIDOS; un CLIENT recibe 403."""
    prod = producto_factory(nombre="Burger RBAC", precio_base="1000.00")
    pedido = _crear_pedido(client, client_headers, prod)

    r = client.patch(f"/api/v1/pedidos/{pedido['id']}/estado", headers=client_headers,
                     json={"estado_hacia": "CONFIRMADO"})
    assert r.status_code == 403
