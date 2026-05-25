"""
Service de Pedidos.
Regla: NO crea su propio UoW. Recibe `uow` del router.

Responsabilidades clave:
- Validación del FSM (mapa _TRANSICIONES_VALIDAS) — ÚNICO lugar donde se valida.
- Snapshot pattern al crear DetallePedido (nombre y precio inmutables).
- Decremento de stock atómico dentro del mismo UoW (rollback si algo falla).
- Append a HistorialEstadoPedido en cada transición (incluida la creación).
- Enforcement de RN-02 (primer historial: estado_desde=NULL).
- Enforcement de RN-05 (motivo obligatorio si estado_hacia=CANCELADO).
- Control de permisos por rol según la transición solicitada.
"""
import math
from datetime import datetime
from decimal import Decimal
from typing import Optional, Set
from fastapi import HTTPException, status

from app.modules.pedidos.model import (
    Pedido, DetallePedido, HistorialEstadoPedido,
)
from app.modules.pedidos.schemas import (
    PedidoCreate, PedidoResponse, PedidoListItem, PaginatedPedidos,
    DetallePedidoResponse, HistorialEstadoResponse,
    EstadoPedidoResponse, FormaPagoResponse,
)


# ──────────────────────────────────────────────────────────────────────────────
# FSM — mapa de transiciones válidas (única fuente de verdad)
# ──────────────────────────────────────────────────────────────────────────────
# Lee así: desde estado X → cualquiera de estos estados Y es válido.
# Cualquier transición fuera de este mapa lanza 409 INVALID_TRANSITION.

_TRANSICIONES_VALIDAS: dict[str, Set[str]] = {
    "PENDIENTE":  {"CONFIRMADO", "CANCELADO"},
    "CONFIRMADO": {"EN_PREP",    "CANCELADO"},
    "EN_PREP":    {"EN_CAMINO",  "CANCELADO"},  # CANCELADO desde aquí: solo ADMIN/COCINERO
    "EN_CAMINO":  {"ENTREGADO"},
    "ENTREGADO":  set(),                         # terminal
    "CANCELADO":  set(),                         # terminal
}

# Transiciones permitidas al rol CLIENT sobre su propio pedido.
# El CLIENT solo puede cancelar (y solo desde PENDIENTE o CONFIRMADO).
_TRANSICIONES_CLIENT: dict[str, Set[str]] = {
    "PENDIENTE":  {"CANCELADO"},
    "CONFIRMADO": {"CANCELADO"},
}

# Costo de envío por default (RN: snapshot al crear el pedido)
_COSTO_ENVIO_DEFAULT = Decimal("50.00")

# Códigos de estado usados como constantes (evita typos)
_ESTADO_PENDIENTE = "PENDIENTE"
_ESTADO_CANCELADO = "CANCELADO"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _problem(code: str, detail: str, http_status: int):
    raise HTTPException(
        status_code=http_status,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def _build_response(uow, pedido: Pedido) -> PedidoResponse:
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
    )


# ──────────────────────────────────────────────────────────────────────────────
# Catálogos (para que el frontend pueble selects)
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
    ADMIN / COCINERO ⇒ ven todos.
    """
    es_staff = any(r in ("ADMIN", "COCINERO") for r in requester_roles)
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
    es_staff = any(r in ("ADMIN", "COCINERO") for r in requester_roles)
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
    es_staff = any(r in ("ADMIN", "COCINERO") for r in requester_roles)
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
# Crear pedido (transacción atómica vía UoW)
# ──────────────────────────────────────────────────────────────────────────────

def crear_pedido(uow, data: PedidoCreate, usuario_id: int) -> PedidoResponse:
    """
    Flujo atómico — si CUALQUIER paso falla, el UoW hace rollback de todo:

    1. Validar forma_pago existe y está habilitada.
    2. Validar dirección (si se envía) pertenece al usuario.
    3. Para cada item:
         a. Cargar producto (soft-delete-aware, disponible=true).
         b. Validar stock_cantidad >= cantidad.
         c. Snapshot: capturar nombre y precio actuales.
         d. Decrementar stock_cantidad.
    4. Calcular subtotal / total y persistir Pedido con estado=PENDIENTE.
    5. Insertar todos los DetallePedido (con snapshot inmutable).
    6. Insertar primer HistorialEstadoPedido (estado_desde=NULL — RN-02).
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

    # 2. Dirección (opcional — pedidos para retiro en local no la requieren)
    if data.direccion_id is not None:
        direccion = uow.direcciones.get_by_id_for_user(data.direccion_id, usuario_id)
        if not direccion:
            _problem("DIRECCION_NOT_FOUND",
                     f"Dirección {data.direccion_id} no encontrada para este usuario",
                     status.HTTP_404_NOT_FOUND)

    # 3. Estado PENDIENTE debe existir en el catálogo (validación de integridad del seed)
    if not uow.estados_pedido.get_by_codigo(_ESTADO_PENDIENTE):
        _problem("ESTADO_NOT_FOUND",
                 "Catálogo de estados no inicializado (ejecutar seed)",
                 status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 4. Procesar items: snapshot + decremento de stock
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
        if producto.stock_cantidad < item.cantidad:
            _problem("STOCK_INSUFICIENTE",
                     f"Stock insuficiente para '{producto.nombre}': "
                     f"disponible {producto.stock_cantidad}, solicitado {item.cantidad}",
                     status.HTTP_409_CONFLICT)

        # ── Snapshot inmutable (RN-04) ───────────────────────────────────────
        precio_snap = producto.precio
        subtotal_item = precio_snap * item.cantidad

        detalles_a_insertar.append(DetallePedido(
            producto_id=producto.id,
            cantidad=item.cantidad,
            nombre_snapshot=producto.nombre,
            precio_snapshot=precio_snap,
            subtotal_snap=subtotal_item,
            personalizacion=item.personalizacion,
        ))

        # Decrementar stock (parte de la misma transacción)
        producto.stock_cantidad -= item.cantidad
        producto.updated_at = datetime.utcnow()
        uow.productos.add(producto)

        subtotal += subtotal_item

    # 5. Calcular totales y persistir Pedido
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
    uow.pedidos.add(pedido)   # flush ⇒ pedido.id ya disponible

    # 6. Insertar detalles con el pedido_id recién generado
    for detalle in detalles_a_insertar:
        detalle.pedido_id = pedido.id
        uow.pedidos.add_detalle(detalle)

    # 7. Primer historial — RN-02: estado_desde=NULL en la creación
    uow.pedidos.add_historial(HistorialEstadoPedido(
        pedido_id=pedido.id,
        estado_desde=None,
        estado_hacia=_ESTADO_PENDIENTE,
        usuario_id=usuario_id,
        motivo=None,
    ))

    return _build_response(uow, pedido)


# ──────────────────────────────────────────────────────────────────────────────
# Avanzar estado (ADMIN / COCINERO) — núcleo de la máquina de estados
# ──────────────────────────────────────────────────────────────────────────────

def avanzar_estado(
    uow,
    pedido_id: int,
    estado_hacia: str,
    motivo: Optional[str],
    actor_user_id: int,
    actor_roles: list[str],
) -> PedidoResponse:
    """
    Validación 100% en service (NUNCA en router):
    - El pedido existe y no está borrado.
    - El estado_hacia existe en el catálogo.
    - La transición desde el estado actual al estado_hacia es válida (FSM).
    - El motivo es obligatorio si estado_hacia = CANCELADO (RN-05).
    - El rol del actor tiene permiso para esta transición específica.

    Operación atómica:
    - UPDATE Pedido.estado_codigo
    - INSERT HistorialEstadoPedido
    Ambas viajan en la misma transacción del UoW. Si una falla, ambas se revierten.
    """
    pedido = uow.pedidos.get_by_id(pedido_id)
    if not pedido:
        _problem("PEDIDO_NOT_FOUND", f"Pedido {pedido_id} no encontrado", status.HTTP_404_NOT_FOUND)

    # Validar destino existe en catálogo
    if not uow.estados_pedido.get_by_codigo(estado_hacia):
        _problem("ESTADO_NOT_FOUND", f"Estado '{estado_hacia}' no existe", status.HTTP_404_NOT_FOUND)

    # Validar transición está en el mapa FSM
    transiciones_permitidas = _TRANSICIONES_VALIDAS.get(pedido.estado_codigo, set())
    if estado_hacia not in transiciones_permitidas:
        _problem(
            "INVALID_TRANSITION",
            f"Transición inválida: {pedido.estado_codigo} → {estado_hacia}. "
            f"Permitidas: {sorted(transiciones_permitidas) or 'ninguna (estado terminal)'}",
            status.HTTP_409_CONFLICT,
        )

    # RN-05: motivo obligatorio si se cancela
    if estado_hacia == _ESTADO_CANCELADO and not (motivo and motivo.strip()):
        _problem("MOTIVO_REQUIRED",
                 "El motivo es obligatorio para cancelar un pedido",
                 status.HTTP_400_BAD_REQUEST)

    # Permisos: ADMIN puede todo; COCINERO puede avanzar el flujo principal
    # (CONFIRMADO → EN_PREP → EN_CAMINO → ENTREGADO) y cancelar.
    es_admin    = "ADMIN" in actor_roles
    es_cocinero = "COCINERO" in actor_roles
    if not (es_admin or es_cocinero):
        _problem("FORBIDDEN",
                 "Solo ADMIN o COCINERO pueden avanzar el estado de un pedido",
                 status.HTTP_403_FORBIDDEN)

    # Aplicar transición + audit trail (mismo UoW = misma transacción)
    estado_desde = pedido.estado_codigo
    pedido.estado_codigo = estado_hacia
    pedido.updated_at = datetime.utcnow()
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
# Cancelar pedido (CLIENT sobre su propio pedido)
# ──────────────────────────────────────────────────────────────────────────────

def cancelar_pedido_cliente(
    uow,
    pedido_id: int,
    motivo: str,
    cliente_user_id: int,
) -> PedidoResponse:
    """
    Variante para el rol CLIENT. Solo puede cancelar:
    - sus propios pedidos
    - desde estado PENDIENTE o CONFIRMADO

    Reutiliza la misma lógica de avanzar_estado pero con permisos del CLIENT.
    """
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

    estado_desde = pedido.estado_codigo
    pedido.estado_codigo = _ESTADO_CANCELADO
    pedido.updated_at = datetime.utcnow()
    uow.pedidos.add(pedido)

    uow.pedidos.add_historial(HistorialEstadoPedido(
        pedido_id=pedido.id,
        estado_desde=estado_desde,
        estado_hacia=_ESTADO_CANCELADO,
        usuario_id=cliente_user_id,
        motivo=motivo,
    ))

    return _build_response(uow, pedido)