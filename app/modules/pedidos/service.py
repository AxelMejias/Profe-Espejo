"""
Service de Pedidos.
Regla: NO crea su propio UoW. Recibe `uow` del router.
"""
import math
from datetime import datetime
from decimal import Decimal
from typing import Optional, Set
from fastapi import HTTPException, status

from app.core.config import settings
from app.modules.pedidos.model import Pedido, DetallePedido, HistorialEstadoPedido
from app.modules.pedidos.schemas import (
    PedidoCreate, PedidoResponse, PedidoListItem, PaginatedPedidos,
    DetallePedidoResponse, HistorialEstadoResponse,
    EstadoPedidoResponse, FormaPagoResponse,
)

# ──────────────────────────────────────────────────────────────────────────────
# FSM — mapa de transiciones válidas (única fuente de verdad)
# ──────────────────────────────────────────────────────────────────────────────

_TRANSICIONES_VALIDAS: dict[str, Set[str]] = {
    "PENDIENTE":  {"CONFIRMADO", "CANCELADO"},
    "CONFIRMADO": {"EN_PREP",    "CANCELADO"},
    "EN_PREP":    {"EN_CAMINO",  "CANCELADO"},
    "EN_CAMINO":  {"ENTREGADO"},
    "ENTREGADO":  set(),                         # terminal
    "CANCELADO":  set(),                         # terminal
}

# RBAC por transición: estado_desde → estado_hacia → roles autorizados
_PERMISOS_TRANSICION: dict[str, dict[str, Set[str]]] = {
    "PENDIENTE":  {
        "CONFIRMADO": {"ADMIN", "PEDIDOS"},
        "CANCELADO":  {"ADMIN", "PEDIDOS"},
    },
    "CONFIRMADO": {
        "EN_PREP":   {"ADMIN", "PEDIDOS"},
        "CANCELADO": {"ADMIN"},
    },
    "EN_PREP":    {
        "EN_CAMINO": {"ADMIN", "PEDIDOS"},
        "CANCELADO": {"ADMIN", "PEDIDOS"},
    },
    "EN_CAMINO":  {
        "ENTREGADO": {"ADMIN", "PEDIDOS"},
    },
}

# Roles que ven todos los pedidos (no solo los propios)
_ROLES_STAFF = {"ADMIN", "PEDIDOS"}

_TRANSICIONES_CLIENT: dict[str, Set[str]] = {
    "PENDIENTE":  {"CANCELADO"},
    "CONFIRMADO": {"CANCELADO"},
}

_COSTO_ENVIO_DEFAULT = Decimal("50.00")
_ESTADO_PENDIENTE    = "PENDIENTE"
_ESTADO_CANCELADO    = "CANCELADO"
_FORMA_PAGO_MP       = "MERCADOPAGO"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _problem(code: str, detail: str, http_status: int):
    raise HTTPException(
        status_code=http_status,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def _build_response(uow, pedido: Pedido, init_point: Optional[str] = None) -> PedidoResponse:
    detalles = uow.pedidos.get_detalles(pedido.id)
    return PedidoResponse(
        id=pedido.id,
        usuario_id=pedido.usuario_id,
        direccion_id=pedido.direccion_id,
        estado_codigo=pedido.estado_codigo,
        forma_pago_codigo=pedido.forma_pago_codigo,
        subtotal=pedido.subtotal,
        descuento=pedido.descuento,
        costo_envio=pedido.costo_envio,
        total=pedido.total,
        notas=pedido.notas,
        created_at=pedido.created_at,
        updated_at=pedido.updated_at,
        detalles=[DetallePedidoResponse.model_validate(d) for d in detalles],
        init_point=init_point,
    )


def _crear_preferencia_mp(pedido: Pedido, detalles: list) -> tuple[str, str]:
    """Crea una preferencia en MercadoPago. Retorna (preference_id, init_point)."""
    import mercadopago
    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)

    preference_data = {
        "items": [
            {
                "id": str(d.producto_id),
                "title": d.nombre_snapshot,
                "quantity": int(d.cantidad),
                "unit_price": float(d.precio_snapshot),
                "currency_id": "ARS",
            }
            for d in detalles
        ],
        "back_urls": {
            "success": f"{settings.FRONTEND_URL}/pedido-exitoso",
            "failure": f"{settings.FRONTEND_URL}/pedido-exitoso",
            "pending": f"{settings.FRONTEND_URL}/pedido-exitoso",
        },
        "external_reference": str(pedido.id),
        "statement_descriptor": "Food Store",
    }

    response = sdk.preference().create(preference_data)
    if response["status"] not in (200, 201):
        mp_error = response.get("response", {})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "detail": f"MP error {response['status']}: {mp_error}",
                "code": "MP_PREFERENCE_ERROR",
            },
        )

    preference = response["response"]
    checkout_url = preference["init_point"]
    return preference["id"], checkout_url


# ──────────────────────────────────────────────────────────────────────────────
# Catálogos
# ──────────────────────────────────────────────────────────────────────────────

def listar_estados(uow) -> list[EstadoPedidoResponse]:
    return [EstadoPedidoResponse.model_validate(e) for e in uow.estados_pedido.get_all()]


def listar_formas_pago(uow) -> list[FormaPagoResponse]:
    return [FormaPagoResponse.model_validate(f) for f in uow.formas_pago.get_all_habilitadas()]


# ──────────────────────────────────────────────────────────────────────────────
# Queries
# ──────────────────────────────────────────────────────────────────────────────

def get_all(
    uow,
    requester_user_id: int,
    requester_roles: list[str],
    estado_codigo: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> PaginatedPedidos:
    """
    CLIENT ⇒ solo ve sus pedidos.
    ADMIN / PEDIDOS ⇒ ven todos.
    """
    es_staff = any(r in _ROLES_STAFF for r in requester_roles)
    items, total = uow.pedidos.get_all(
        usuario_id=None if es_staff else requester_user_id,
        estado_codigo=estado_codigo,
        page=page, size=size,
    )
    return PaginatedPedidos(
        items=[PedidoListItem.model_validate(p) for p in items],
        total=total, page=page, size=size,
        pages=math.ceil(total / size) if total else 0,
    )


def get_by_id(
    uow,
    pedido_id: int,
    requester_user_id: int,
    requester_roles: list[str],
) -> PedidoResponse:
    es_staff = any(r in _ROLES_STAFF for r in requester_roles)
    pedido = (
        uow.pedidos.get_by_id(pedido_id)
        if es_staff else
        uow.pedidos.get_by_id_for_user(pedido_id, requester_user_id)
    )
    if not pedido:
        _problem("PEDIDO_NOT_FOUND", f"Pedido {pedido_id} no encontrado", status.HTTP_404_NOT_FOUND)
    return _build_response(uow, pedido)


def get_historial(
    uow,
    pedido_id: int,
    requester_user_id: int,
    requester_roles: list[str],
) -> list[HistorialEstadoResponse]:
    # Reutiliza el check de acceso de get_by_id
    es_staff = any(r in _ROLES_STAFF for r in requester_roles)
    pedido = (
        uow.pedidos.get_by_id(pedido_id)
        if es_staff else
        uow.pedidos.get_by_id_for_user(pedido_id, requester_user_id)
    )
    if not pedido:
        _problem("PEDIDO_NOT_FOUND", f"Pedido {pedido_id} no encontrado", status.HTTP_404_NOT_FOUND)
    historial = uow.pedidos.get_historial(pedido_id)
    return [HistorialEstadoResponse.model_validate(h) for h in historial]


# ──────────────────────────────────────────────────────────────────────────────
# Crear pedido — validación de stock por INSUMO (Parcial 3)
# ──────────────────────────────────────────────────────────────────────────────

def _calcular_requerimientos_insumos(
    uow, items: list
) -> dict[int, Decimal]:
    """
    Dado un listado de items del pedido, acumula cuántas unidades
    de cada insumo se necesitan en total considerando todos los productos
    y sus cantidades pedidas.
    Retorna: { ingrediente_id: cantidad_total_requerida }
    """
    requerido: dict[int, Decimal] = {}

    for item in items:
        links = uow.productos.get_ingrediente_links(item.producto_id)
        for link in links:
            clave = link.ingrediente_id
            cantidad = Decimal(str(link.cantidad)) * item.cantidad
            requerido[clave] = requerido.get(clave, Decimal("0")) + cantidad

    return requerido


def crear_pedido(uow, data: PedidoCreate, usuario_id: int) -> PedidoResponse:
    """
    Flujo atómico:
    1. Validar forma de pago y dirección.
    2. Validar que cada producto existe y está disponible.
    3. Calcular requerimientos de insumos agregados por todo el pedido.
    4. Validar stock de insumos — si falta alguno lanza 422 con detalle.
    5. Decrementar stock de los insumos involucrados.
    6. Persistir Pedido + DetallePedido + HistorialEstadoPedido.
    """
    # 1. Forma de pago
    forma_pago = uow.formas_pago.get_by_codigo(data.forma_pago_codigo)
    if not forma_pago:
        _problem("FORMA_PAGO_NOT_FOUND",
                 f"Forma de pago '{data.forma_pago_codigo}' no encontrada",
                 status.HTTP_404_NOT_FOUND)
    if not forma_pago.habilitado:
        _problem("FORMA_PAGO_DISABLED",
                 f"Forma de pago '{data.forma_pago_codigo}' está deshabilitada",
                 status.HTTP_409_CONFLICT)

    # 2. Dirección
    if data.direccion_id is not None:
        if not uow.direcciones.get_by_id_for_user(data.direccion_id, usuario_id):
            _problem("DIRECCION_NOT_FOUND",
                     f"Dirección {data.direccion_id} no encontrada para este usuario",
                     status.HTTP_404_NOT_FOUND)

    if not uow.estados_pedido.get_by_codigo(_ESTADO_PENDIENTE):
        _problem("ESTADO_NOT_FOUND",
                 "Catálogo de estados no inicializado (ejecutar seed)",
                 status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 3. Validar productos y preparar snapshots
    detalles_a_insertar: list[DetallePedido] = []
    subtotal = Decimal("0.00")

    for item in data.items:
        producto = uow.productos.get_by_id(item.producto_id)
        if not producto:
            _problem("PRODUCTO_NOT_FOUND",
                     f"Producto {item.producto_id} no encontrado",
                     status.HTTP_404_NOT_FOUND)
        if not producto.disponible:
            _problem("PRODUCTO_NO_DISPONIBLE",
                     f"Producto '{producto.nombre}' no está disponible",
                     status.HTTP_409_CONFLICT)

        precio_snap   = producto.precio
        subtotal_item = precio_snap * item.cantidad
        subtotal     += subtotal_item

        detalles_a_insertar.append(DetallePedido(
            producto_id=producto.id,
            cantidad=item.cantidad,
            nombre_snapshot=producto.nombre,
            precio_snapshot=precio_snap,
            subtotal_snap=subtotal_item,
            personalizacion=item.personalizacion,
        ))

    # 4. Validar stock de insumos
    requerido = _calcular_requerimientos_insumos(uow, data.items)
    for ing_id, cantidad_req in requerido.items():
        ing = uow.ingredientes.get_by_id(ing_id)
        if not ing:
            # Ingrediente dado de baja → avisar en términos de disponibilidad de producto
            _problem(
                "PRODUCTO_NO_DISPONIBLE",
                "Uno o más productos del pedido no están disponibles actualmente "
                "porque contienen ingredientes dados de baja. "
                "Actualizá la página e intentá con otro producto.",
                status.HTTP_409_CONFLICT,
            )
        if ing.stock_cantidad < cantidad_req:
            _problem(
                "STOCK_INSUFICIENTE",
                f"Stock insuficiente para insumo '{ing.nombre}': "
                f"disponible {ing.stock_cantidad}, requerido {cantidad_req}",
                status.HTTP_409_CONFLICT,
            )

    # 5. Decrementar stock de insumos
    for ing_id, cantidad_req in requerido.items():
        ing = uow.ingredientes.get_by_id(ing_id)
        ing.stock_cantidad -= cantidad_req
        ing.updated_at = datetime.utcnow()
        uow.ingredientes.add(ing)

    # 6. Calcular totales y persistir Pedido
    descuento = Decimal("0.00")
    costo_envio = _COSTO_ENVIO_DEFAULT if data.direccion_id is not None else Decimal("0.00")
    total = subtotal - descuento + costo_envio

    pedido = Pedido(
        usuario_id=usuario_id,
        direccion_id=data.direccion_id,
        estado_codigo=_ESTADO_PENDIENTE,
        forma_pago_codigo=data.forma_pago_codigo,
        subtotal=subtotal,
        descuento=descuento,
        costo_envio=costo_envio,
        total=total,
        notas=data.notas,
    )
    uow.pedidos.add(pedido)

    for detalle in detalles_a_insertar:
        detalle.pedido_id = pedido.id
        uow.pedidos.add_detalle(detalle)

    uow.pedidos.add_historial(HistorialEstadoPedido(
        pedido_id=pedido.id,
        estado_desde=None,
        estado_hacia=_ESTADO_PENDIENTE,
        usuario_id=usuario_id,
        motivo=None,
    ))

    # 7. MercadoPago: crear preferencia de pago si corresponde
    init_point = None
    if data.forma_pago_codigo == _FORMA_PAGO_MP:
        preference_id, init_point = _crear_preferencia_mp(pedido, detalles_a_insertar)
        pedido.mp_preference_id = preference_id
        uow.pedidos.add(pedido)

    return _build_response(uow, pedido, init_point=init_point)


# ──────────────────────────────────────────────────────────────────────────────
# Restaurar stock al cancelar
# ──────────────────────────────────────────────────────────────────────────────

def _restaurar_stock_pedido(uow, pedido: Pedido) -> None:
    """
    Incrementa el stock de cada insumo según lo consumido al crear el pedido.
    Usa los ingrediente_links actuales del producto × la cantidad del detalle.
    """
    detalles = uow.pedidos.get_detalles(pedido.id)
    acumulado: dict[int, Decimal] = {}

    for detalle in detalles:
        links = uow.productos.get_ingrediente_links(detalle.producto_id)
        for link in links:
            cantidad = Decimal(str(link.cantidad)) * detalle.cantidad
            acumulado[link.ingrediente_id] = (
                acumulado.get(link.ingrediente_id, Decimal("0")) + cantidad
            )

    for ing_id, cantidad in acumulado.items():
        ing = uow.ingredientes.get_by_id(ing_id)
        if not ing:
            continue
        ing.stock_cantidad += cantidad
        ing.updated_at = datetime.utcnow()
        uow.ingredientes.add(ing)


# ──────────────────────────────────────────────────────────────────────────────
# Avanzar estado (ADMIN / PEDIDOS) — núcleo de la máquina de estados
# ──────────────────────────────────────────────────────────────────────────────

def avanzar_estado(
    uow,
    pedido_id: int,
    estado_hacia: str,
    motivo: Optional[str],
    actor_user_id: int,
    actor_roles: list[str],
    restaurar_stock: bool = True,
) -> PedidoResponse:
    pedido = uow.pedidos.get_by_id(pedido_id)
    if not pedido:
        _problem("PEDIDO_NOT_FOUND", f"Pedido {pedido_id} no encontrado", status.HTTP_404_NOT_FOUND)

    if not uow.estados_pedido.get_by_codigo(estado_hacia):
        _problem("ESTADO_NOT_FOUND", f"Estado '{estado_hacia}' no existe", status.HTTP_404_NOT_FOUND)

    transiciones_permitidas = _TRANSICIONES_VALIDAS.get(pedido.estado_codigo, set())
    if estado_hacia not in transiciones_permitidas:
        _problem(
            "INVALID_TRANSITION",
            f"Transición inválida: {pedido.estado_codigo} → {estado_hacia}. "
            f"Permitidas: {sorted(transiciones_permitidas) or 'ninguna (estado terminal)'}",
            status.HTTP_409_CONFLICT,
        )

    if estado_hacia == _ESTADO_CANCELADO and not (motivo and motivo.strip()):
        _problem("MOTIVO_REQUIRED",
                 "El motivo es obligatorio para cancelar un pedido",
                 status.HTTP_400_BAD_REQUEST)

    # RBAC por transición específica
    roles_permitidos = _PERMISOS_TRANSICION.get(pedido.estado_codigo, {}).get(estado_hacia, set())
    if not any(r in roles_permitidos for r in actor_roles):
        _problem(
            "FORBIDDEN",
            f"Tu rol no tiene permiso para la transición {pedido.estado_codigo} → {estado_hacia}. "
            f"Roles requeridos: {sorted(roles_permitidos)}",
            status.HTTP_403_FORBIDDEN,
        )

    if estado_hacia == _ESTADO_CANCELADO and restaurar_stock:
        _restaurar_stock_pedido(uow, pedido)

    estado_desde          = pedido.estado_codigo
    pedido.estado_codigo  = estado_hacia
    pedido.updated_at     = datetime.utcnow()
    uow.pedidos.add(pedido)

    uow.pedidos.add_historial(HistorialEstadoPedido(
        pedido_id=pedido.id,
        estado_desde=estado_desde,
        estado_hacia=estado_hacia,
        usuario_id=actor_user_id,
        motivo=motivo,
    ))

    return _build_response(uow, pedido)


# ──────────────────────────────────────────────────────────────────────────────
# Cancelar pedido (CLIENT)
# ──────────────────────────────────────────────────────────────────────────────

def cancelar_pedido_cliente(
    uow,
    pedido_id: int,
    motivo: str,
    cliente_user_id: int,
    restaurar_stock: bool = True,
) -> PedidoResponse:
    pedido = uow.pedidos.get_by_id_for_user(pedido_id, cliente_user_id)
    if not pedido:
        _problem("PEDIDO_NOT_FOUND", f"Pedido {pedido_id} no encontrado", status.HTTP_404_NOT_FOUND)

    transiciones_cliente = _TRANSICIONES_CLIENT.get(pedido.estado_codigo, set())
    if _ESTADO_CANCELADO not in transiciones_cliente:
        _problem(
            "INVALID_TRANSITION",
            f"No podés cancelar un pedido en estado '{pedido.estado_codigo}'. "
            f"Solo se permite desde PENDIENTE o CONFIRMADO.",
            status.HTTP_409_CONFLICT,
        )

    if not motivo or not motivo.strip():
        _problem("MOTIVO_REQUIRED",
                 "El motivo es obligatorio para cancelar un pedido",
                 status.HTTP_400_BAD_REQUEST)

    if restaurar_stock:
        _restaurar_stock_pedido(uow, pedido)

    estado_desde         = pedido.estado_codigo
    pedido.estado_codigo = _ESTADO_CANCELADO
    pedido.updated_at    = datetime.utcnow()
    uow.pedidos.add(pedido)

    uow.pedidos.add_historial(HistorialEstadoPedido(
        pedido_id=pedido.id,
        estado_desde=estado_desde,
        estado_hacia=_ESTADO_CANCELADO,
        usuario_id=cliente_user_id,
        motivo=motivo,
    ))

    return _build_response(uow, pedido)


# ──────────────────────────────────────────────────────────────────────────────
# WebSocket — emisión de eventos en tiempo real
# ──────────────────────────────────────────────────────────────────────────────

_EVENTOS_WS: dict[str, str] = {
    "PENDIENTE":  "NUEVO_PEDIDO",
    "CONFIRMADO": "PEDIDO_CONFIRMADO",
    "EN_PREP":    "PEDIDO_EN_PREPARACION",
    "EN_CAMINO":  "PEDIDO_EN_CAMINO",
    "ENTREGADO":  "PEDIDO_ENTREGADO",
    "CANCELADO":  "PEDIDO_CANCELADO",
}

# Roles de staff notificados en cada transición
_ROLES_POR_ESTADO: dict[str, list[str]] = {
    "PENDIENTE":  ["pedidos", "admin"],
    "CONFIRMADO": ["pedidos", "admin"],
    "EN_PREP":    ["pedidos", "admin"],
    "EN_CAMINO":  ["pedidos", "admin"],
    "ENTREGADO":  ["pedidos", "admin"],
    "CANCELADO":  ["pedidos", "admin"],
}


async def emit_ws_evento(pedido_id: int, estado: str, data: dict) -> None:
    """
    Emite un evento WS a la room del pedido y a las rooms de rol del staff.
    Se llama desde el router DESPUÉS de que el UoW commitea el cambio.
    No lanza excepciones — si no hay conexiones activas, es silencioso.
    """
    from app.core.websocket import manager

    event_type = _EVENTOS_WS.get(estado)
    if not event_type:
        return

    await manager.broadcast_to_order(pedido_id, event_type, data)

    roles = _ROLES_POR_ESTADO.get(estado, [])
    if roles:
        await manager.broadcast_to_roles(roles, event_type, data)


# ──────────────────────────────────────────────────────────────────────────────
# Verificar pago en MP (polling desde el frontend al cerrar el popup)
# ──────────────────────────────────────────────────────────────────────────────

def verificar_pago_mp(uow, pedido_id: int, usuario_id: int) -> dict:
    """Consulta la API de pagos de MP para saber si el pedido fue pagado."""
    import mercadopago

    pedido = uow.pedidos.get_by_id_for_user(pedido_id, usuario_id)
    if not pedido:
        _problem("PEDIDO_NOT_FOUND", f"Pedido {pedido_id} no encontrado", status.HTTP_404_NOT_FOUND)

    if pedido.forma_pago_codigo != _FORMA_PAGO_MP:
        _problem("NOT_MP_PAYMENT", "Este pedido no usa MercadoPago", status.HTTP_400_BAD_REQUEST)

    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
    result = sdk.payment().search({
        "external_reference": str(pedido_id),
        "sort": "date_created",
        "criteria": "desc",
    })

    if result["status"] != 200:
        return {"status": "not_found", "payment_id": None}

    payments = result["response"].get("results", [])
    if not payments:
        return {"status": "not_found", "payment_id": None}

    payment = payments[0]
    return {
        "status": payment.get("status", "unknown"),
        "payment_id": payment.get("id"),
    }