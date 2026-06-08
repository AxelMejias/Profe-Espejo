import json
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, Path, status, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from jose import JWTError

from app.modules.pedidos.schemas import (
    PedidoCreate, PedidoResponse, PaginatedPedidos,
    AvanzarEstadoRequest, CancelarPedidoRequest,
    HistorialEstadoResponse, EstadoPedidoResponse, FormaPagoResponse,
)
from app.modules.pedidos import service
from app.core.config import settings
from app.core.dependencies import (
    get_current_user_id, get_current_user_payload, require_role,
)
from app.core.security import decode_access_token
from app.core.unit_of_work import UnitOfWork

router = APIRouter(prefix="/api/v1/pedidos", tags=["Pedidos"])

# Aliases RBAC siguiendo la convención del codebase
_AUTENTICADO = Depends(require_role(["ADMIN", "PEDIDOS", "CLIENT"]))
_STAFF       = Depends(require_role(["ADMIN", "PEDIDOS"]))
_CLIENT      = Depends(require_role(["CLIENT"]))


# ──────────────────────────────────────────────────────────────────────────────
# Catálogos (para que el frontend pueble los selects)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/estados", response_model=list[EstadoPedidoResponse], summary="Listar estados del FSM")
def listar_estados(_=_AUTENTICADO):
    with UnitOfWork() as uow:
        return service.listar_estados(uow)


@router.get("/formas-pago", response_model=list[FormaPagoResponse], summary="Listar formas de pago habilitadas")
def listar_formas_pago(_=_AUTENTICADO):
    with UnitOfWork() as uow:
        return service.listar_formas_pago(uow)


# ──────────────────────────────────────────────────────────────────────────────
# Listado y detalle
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedPedidos, summary="Listar pedidos")
def listar_pedidos(
    estado_codigo: Annotated[Optional[str], Query(max_length=20)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    payload: dict = Depends(get_current_user_payload),
):
    """
    CLIENT ⇒ solo ve sus pedidos.
    ADMIN / PEDIDOS ⇒ ven todos.
    El filtrado lo hace el service según el payload del JWT.
    """
    with UnitOfWork() as uow:
        return service.get_all(
            uow,
            requester_user_id=int(payload["sub"]),
            requester_roles=payload.get("roles", []),
            estado_codigo=estado_codigo,
            page=page, size=size,
        )


# ──────────────────────────────────────────────────────────────────────────────
# MercadoPago back_url callbacks (sin auth — redireccionados por el browser)
# MP llama: GET /mp-callback/{success|failure|pending}?pedido_id=X&payment_id=Y&...
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/mp-callback/{result_status}", summary="Redirect de MercadoPago tras el pago")
async def mp_callback(
    result_status: str,
    pedido_id: int,
    payment_id: Optional[int] = None,
    collection_id: Optional[int] = None,
):
    pid = payment_id or collection_id
    frontend = settings.FRONTEND_URL

    if result_status == "success":
        with UnitOfWork() as uow:
            result = service.confirmar_pago_mp(uow, pedido_id)
        await service.emit_ws_evento(result.id, result.estado_codigo, result.model_dump(mode="json"))
        url = f"{frontend}/pedido-exitoso?collection_status=approved&external_reference={pedido_id}&payment_id={pid or ''}"

    elif result_status == "failure":
        with UnitOfWork() as uow:
            service.cancelar_pago_mp(uow, pedido_id)
        url = f"{frontend}/pedido-exitoso?collection_status=failure&external_reference={pedido_id}"

    else:  # pending
        url = f"{frontend}/pedido-exitoso?collection_status=pending&external_reference={pedido_id}"

    return RedirectResponse(url=url, status_code=302)


@router.post("/{pedido_id}/confirmar-pago-mp", response_model=PedidoResponse,
             summary="Confirmar pago MP desde el frontend (ESPERANDO_PAGO → PENDIENTE)")
async def confirmar_pago_mp(
    pedido_id: Annotated[int, Path(ge=1)],
    usuario_id: int = Depends(get_current_user_id),
    _=_CLIENT,
):
    with UnitOfWork() as uow:
        result = service.confirmar_pago_mp(uow, pedido_id)
    await service.emit_ws_evento(result.id, result.estado_codigo, result.model_dump(mode="json"))
    return result


@router.get("/{pedido_id}", response_model=PedidoResponse, summary="Obtener pedido por ID")
def obtener_pedido(
    pedido_id: Annotated[int, Path(ge=1)],
    payload: dict = Depends(get_current_user_payload),
):
    with UnitOfWork() as uow:
        return service.get_by_id(
            uow, pedido_id,
            requester_user_id=int(payload["sub"]),
            requester_roles=payload.get("roles", []),
        )


@router.get("/{pedido_id}/verificar-pago", summary="Verificar estado de pago en MercadoPago")
def verificar_pago(
    pedido_id: Annotated[int, Path(ge=1)],
    usuario_id: int = Depends(get_current_user_id),
    _=_AUTENTICADO,
):
    with UnitOfWork() as uow:
        return service.verificar_pago_mp(uow, pedido_id, usuario_id)


@router.get("/{pedido_id}/historial",
            response_model=list[HistorialEstadoResponse],
            summary="Historial completo de transiciones del pedido")
def obtener_historial(
    pedido_id: Annotated[int, Path(ge=1)],
    payload: dict = Depends(get_current_user_payload),
):
    with UnitOfWork() as uow:
        return service.get_historial(
            uow, pedido_id,
            requester_user_id=int(payload["sub"]),
            requester_roles=payload.get("roles", []),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Creación (cualquier autenticado) — el CLIENT es el principal, pero ADMIN
# también puede crear en nombre del usuario actual.
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/", response_model=PedidoResponse, status_code=status.HTTP_201_CREATED,
             summary="Crear pedido desde el carrito")
async def crear_pedido(
    data: PedidoCreate,
    usuario_id: int = Depends(get_current_user_id),
    _=_AUTENTICADO,
):
    with UnitOfWork() as uow:
        result = service.crear_pedido(uow, data, usuario_id)
    await service.emit_ws_evento(result.id, result.estado_codigo, result.model_dump(mode="json"))
    return result


# ──────────────────────────────────────────────────────────────────────────────
# FSM — avanzar estado (ADMIN / PEDIDOS)
# El router solo desempaqueta el body; la validación es 100% del service.
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{pedido_id}/avanzar", response_model=PedidoResponse,
             summary="Avanzar estado del pedido (ADMIN / PEDIDOS)")
async def avanzar_estado(
    pedido_id: Annotated[int, Path(ge=1)],
    data: AvanzarEstadoRequest,
    payload: dict = Depends(get_current_user_payload),
    _=_STAFF,
):
    with UnitOfWork() as uow:
        result = service.avanzar_estado(
            uow,
            pedido_id=pedido_id,
            estado_hacia=data.estado_hacia,
            motivo=data.motivo,
            actor_user_id=int(payload["sub"]),
            actor_roles=payload.get("roles", []),
            restaurar_stock=data.restaurar_stock,
        )
    await service.emit_ws_evento(result.id, result.estado_codigo, result.model_dump(mode="json"))
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Cancelar (CLIENT sobre su propio pedido, solo PENDIENTE / CONFIRMADO)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{pedido_id}/cancelar", response_model=PedidoResponse,
             summary="Cancelar pedido propio (CLIENT)")
async def cancelar_pedido(
    pedido_id: Annotated[int, Path(ge=1)],
    data: CancelarPedidoRequest,
    usuario_id: int = Depends(get_current_user_id),
    _=_CLIENT,
):
    with UnitOfWork() as uow:
        result = service.cancelar_pedido_cliente(
            uow, pedido_id, data.motivo,
            cliente_user_id=usuario_id,
            restaurar_stock=data.restaurar_stock,
        )
    await service.emit_ws_evento(result.id, result.estado_codigo, result.model_dump(mode="json"))
    return result


# ──────────────────────────────────────────────────────────────────────────────
# WebSocket — canal bidireccional autenticado para tiempo real
#
# URL:  ws://<host>/api/v1/pedidos/ws
# Auth: cookie httpOnly "access_token" (se envía automáticamente por el browser)
#
# Mensajes cliente → backend:
#   {"action": "subscribe-order",   "order_id": 5}
#   {"action": "unsubscribe-order", "order_id": 5}
#
# Mensajes backend → cliente:
#   {"event": "NUEVO_PEDIDO",          "data": {...pedido...}}
#   {"event": "PEDIDO_CONFIRMADO",     "data": {...pedido...}}
#   {"event": "PEDIDO_EN_PREPARACION", "data": {...pedido...}}
#   {"event": "PEDIDO_EN_CAMINO",      "data": {...pedido...}}
#   {"event": "PEDIDO_ENTREGADO",      "data": {...pedido...}}
#   {"event": "PEDIDO_CANCELADO",      "data": {...pedido...}}
#   {"event": "SUBSCRIBED",            "data": {"order_id": 5}}
#   {"event": "ERROR",                 "data": {"detail": "..."}}
# ──────────────────────────────────────────────────────────────────────────────

_WS_STAFF_ROLES = {"ADMIN", "PEDIDOS"}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    from app.core.websocket import manager

    # 1. Leer token de la cookie httpOnly
    token = websocket.cookies.get("access_token")
    if not token:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token requerido")
        return

    # 2. Validar JWT
    try:
        payload = decode_access_token(token)
    except JWTError:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token inválido o expirado")
        return

    user_id_str = payload.get("sub")
    roles: list[str] = payload.get("roles", [])

    if not user_id_str:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token inválido")
        return

    user_id = int(user_id_str)

    # 3. Conectar: la primera sala es el rol primario; las demás se agregan al espejo
    primary_role = roles[0].lower() if roles else "client"
    await manager.connect(websocket, role=primary_role, user_id=user_id)
    for role in roles[1:]:
        manager._join_room(websocket, f"role:{role.lower()}")

    # 4. Bucle de mensajes
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