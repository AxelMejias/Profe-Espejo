"""Tests de integración del WebSocket (doc §9/§13) — auth por query param y canales."""
import pytest
from starlette.websockets import WebSocketDisconnect


def _token(headers: dict) -> str:
    return headers["Authorization"].split()[1]


def test_ws_pedidos_conecta_con_token_valido(client, admin_headers):
    with client.websocket_connect(f"/ws/pedidos?token={_token(admin_headers)}") as ws:
        ws.close()


def test_ws_pedidos_sin_token_cierra_4001(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/pedidos") as ws:
            ws.receive_text()
    assert exc.value.code == 4001


def test_ws_pedidos_token_invalido_cierra_4001(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/pedidos?token=token-invalido") as ws:
            ws.receive_text()
    assert exc.value.code == 4001


def test_ws_admin_conecta_staff(client, pedidos_headers):
    with client.websocket_connect(f"/ws/admin/pedidos?token={_token(pedidos_headers)}") as ws:
        ws.close()


def test_ws_admin_rechaza_cliente_4003(client, client_headers):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/admin/pedidos?token={_token(client_headers)}") as ws:
            ws.receive_text()
    assert exc.value.code == 4003


def test_ws_emite_evento_al_actualizar_precio_ingrediente(client, admin_headers):
    """Cambiar el costo de un ingrediente emite 'ingrediente_actualizado' al staff
    conectado, para que las pestañas abiertas refresquen ingredientes y productos."""
    # Crear el ingrediente ANTES de abrir el socket (su evento 'creado' no nos interesa).
    iid = client.post("/api/v1/ingredientes/", headers=admin_headers, json={
        "nombre": "Insumo WS Precio", "unidad_medida": "g", "costo_unitario": "10.00",
        "stock_cantidad": "100.000", "stock_minimo": "5.000",
    }).json()["id"]

    with client.websocket_connect(f"/ws/admin/pedidos?token={_token(admin_headers)}") as ws:
        r = client.put(f"/api/v1/ingredientes/{iid}", headers=admin_headers,
                       json={"costo_unitario": "99.00"})
        assert r.status_code == 200, r.text
        evento = ws.receive_json()

    assert evento["event"] == "ingrediente_actualizado"
    assert evento["ingrediente_id"] == iid
