"""
WebSocket /ws/pedidos — especificación TPI v6.0 sección 9.

URL:  ws://<host>/ws/pedidos
Auth: JWT via query param ?token=<access_token>

Emite eventos de cambio de estado de pedidos en tiempo real.
Canales: role:{rol} (automático) y order:{id} (suscripción manual).
"""
import json
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from jose.exceptions import ExpiredSignatureError

from app.core.security import decode_access_token
from app.core.websocket import manager
from app.core.unit_of_work import UnitOfWork

router = APIRouter(tags=["WebSocket"])

_WS_STAFF_ROLES = {"ADMIN", "PEDIDOS"}


@router.websocket("/ws/pedidos")
async def ws_pedidos(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    # 1. Validar JWT del query param
    # 4001 = token expirado (el cliente puede refrescar y reintentar)
    # 1008 = token malformado o inválido (no reintentar)
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        await websocket.accept()
        await websocket.close(code=4001, reason="Token expirado")
        return
    except JWTError:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token inválido")
        return

    user_id_str = payload.get("sub")
    roles: list[str] = payload.get("roles", [])

    if not user_id_str:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token inválido")
        return

    user_id = int(user_id_str)

    # 2. Conectar: sala primaria por rol, salas adicionales para roles extra
    primary_role = roles[0].lower() if roles else "client"
    await manager.connect(websocket, role=primary_role, user_id=user_id)
    for role in roles[1:]:
        manager._join_room(websocket, f"role:{role.lower()}")

    # 3. Bucle de mensajes
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action")

            if action == "subscribe-order":
                order_id = msg.get("order_id")
                if not isinstance(order_id, int):
                    continue

                # Clientes solo pueden suscribirse a sus propios pedidos
                if not any(r in _WS_STAFF_ROLES for r in roles):
                    with UnitOfWork() as uow:
                        pedido = uow.pedidos.get_by_id_for_user(order_id, user_id)
                    if not pedido:
                        await websocket.send_json({
                            "event": "ERROR",
                            "data": {"detail": "No autorizado para este pedido"},
                        })
                        continue

                manager.join_order_room(websocket, order_id)
                await websocket.send_json({
                    "event": "SUBSCRIBED",
                    "data": {"order_id": order_id},
                })

            elif action == "unsubscribe-order":
                order_id = msg.get("order_id")
                if isinstance(order_id, int):
                    manager.leave_order_room(websocket, order_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
