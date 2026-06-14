"""
Endpoints WebSocket de pedidos (doc §9).

Dos canales, ambos autenticados por query param `?token=<jwt>`:

  • ws://<host>/ws/pedidos        → canal del cliente. Se suscribe a sus propios
                                     pedidos con {"action":"subscribe-order","order_id":N}.
  • ws://<host>/ws/admin/pedidos  → canal del staff (ADMIN / PEDIDOS). Recibe todos
                                     los eventos de pedidos vía rooms de rol.

Códigos de cierre:
  4001  Token ausente / inválido / expirado → el front debe refrescar y reconectar.
  4003  Autenticado pero sin rol suficiente para el canal admin.

Formato de evento emitido (§9.4) — ver app/modules/pedidos/service.emit_ws_evento:
  {event, pedido_id, estado_anterior, estado_nuevo, usuario_id, motivo, timestamp}
"""
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.security import decode_access_token
from app.core.unit_of_work import UnitOfWork
from app.core.websocket import manager

router = APIRouter(tags=["WebSocket"])

_STAFF_ROLES = {"ADMIN", "PEDIDOS"}

# Códigos de cierre de la aplicación (rango 4000-4999, libres para la app).
_WS_UNAUTHORIZED = 4001   # token ausente/inválido/expirado → refrescar y reconectar
_WS_FORBIDDEN    = 4003   # autenticado pero sin rol para el canal


async def _autenticar(websocket: WebSocket) -> Optional[tuple[int, list[str]]]:
    """
    Valida el JWT del query param `?token=`. Devuelve (user_id, roles) o None.
    En el caso None ya dejó el socket aceptado y cerrado con el código 4001.
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.accept()
        await websocket.close(code=_WS_UNAUTHORIZED, reason="Token requerido")
        return None

    try:
        payload = decode_access_token(token)
    except JWTError:
        await websocket.accept()
        await websocket.close(code=_WS_UNAUTHORIZED, reason="Token inválido o expirado")
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        await websocket.accept()
        await websocket.close(code=_WS_UNAUTHORIZED, reason="Token inválido")
        return None

    return int(user_id_str), payload.get("roles", [])


@router.websocket("/ws/pedidos")
async def ws_pedidos(websocket: WebSocket):
    """Canal del cliente: el usuario se suscribe a sus propios pedidos."""
    auth = await _autenticar(websocket)
    if auth is None:
        return
    user_id, roles = auth
    es_staff = any(r in _STAFF_ROLES for r in roles)

    primary_role = roles[0].lower() if roles else "client"
    await manager.connect(websocket, role=primary_role, user_id=user_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action")
            order_id = msg.get("order_id")

            if action == "subscribe-order" and isinstance(order_id, int):
                # El cliente solo puede suscribirse a sus propios pedidos.
                if not es_staff:
                    with UnitOfWork() as uow:
                        pedido = uow.pedidos.get_by_id_for_user(order_id, user_id)
                    if not pedido:
                        await websocket.send_json(
                            {"event": "error", "detail": "No autorizado para este pedido"}
                        )
                        continue
                manager.join_order_room(websocket, order_id)
                await websocket.send_json({"event": "subscribed", "order_id": order_id})

            elif action == "unsubscribe-order" and isinstance(order_id, int):
                manager.leave_order_room(websocket, order_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


@router.websocket("/ws/admin/pedidos")
async def ws_admin_pedidos(websocket: WebSocket):
    """Canal del staff: recibe todos los eventos de pedidos (rooms de rol)."""
    auth = await _autenticar(websocket)
    if auth is None:
        return
    user_id, roles = auth

    if not any(r in _STAFF_ROLES for r in roles):
        await websocket.accept()
        await websocket.close(code=_WS_FORBIDDEN, reason="Requiere rol ADMIN o PEDIDOS")
        return

    # Une el socket a todas las rooms de rol del usuario (admin / pedidos).
    primary_role = roles[0].lower()
    await manager.connect(websocket, role=primary_role, user_id=user_id)
    for role in roles[1:]:
        manager._join_room(websocket, f"role:{role.lower()}")

    try:
        # El staff no se suscribe a órdenes puntuales; solo escucha. Mantener vivo.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
