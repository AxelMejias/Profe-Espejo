"""Tests de integración del módulo Pagos (doc §5.4/§13) — Checkout PRO."""


def test_crear_pago_devuelve_501_checkout_pro(client, client_headers):
    """El flujo es Checkout PRO (redirect): /pagos/crear es un stub 501 documentado."""
    r = client.post("/api/v1/pagos/crear", headers=client_headers, json={
        "pedido_id": 1, "token": "fake-token", "cuotas": 1, "payment_method_id": "visa",
    })
    assert r.status_code == 501, r.text
    assert r.json()["detail"]["code"] == "CHECKOUT_PRO_FLOW"


def test_crear_pago_requiere_rol_client(client, admin_headers):
    r = client.post("/api/v1/pagos/crear", headers=admin_headers, json={
        "pedido_id": 1, "token": "fake", "cuotas": 1, "payment_method_id": "visa",
    })
    assert r.status_code == 403


def test_get_pago_inexistente_404(client, admin_headers):
    r = client.get("/api/v1/pagos/999999", headers=admin_headers)
    assert r.status_code == 404


def test_get_pago_sin_auth_401(client):
    r = client.get("/api/v1/pagos/1")
    assert r.status_code == 401


def test_webhook_sin_datos_no_rompe(client):
    """El webhook IPN no debe lanzar 500 ante un payload vacío/sin firma."""
    r = client.post("/api/v1/pagos/webhook", json={})
    assert r.status_code in (200, 400, 401), r.text
