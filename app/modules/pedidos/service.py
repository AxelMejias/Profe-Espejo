"""
Service de Pedidos.
Regla: NO crea su propio UoW. Recibe `uow` del router.
"""
import math
from datetime import datetime, timezone
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

# FSM v7 — exactamente 5 estados (se elimina EN_CAMINO; sin ESPERANDO_PAGO).
_TRANSICIONES_VALIDAS: dict[str, Set[str]] = {
    "PENDIENTE":  {"CONFIRMADO", "CANCELADO"},
    "CONFIRMADO": {"EN_PREP",    "CANCELADO"},
    "EN_PREP":    {"ENTREGADO",  "CANCELADO"},
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
        "ENTREGADO": {"ADMIN", "PEDIDOS"},
        "CANCELADO": {"ADMIN", "PEDIDOS"},
    },
}

# Roles que ven todos los pedidos (no solo los propios)
_ROLES_STAFF = {"ADMIN", "PEDIDOS"}

_TRANSICIONES_CLIENT: dict[str, Set[str]] = {
    "PENDIENTE":  {"CANCELADO"},
    "CONFIRMADO": {"CANCELADO"},
}

_COSTO_ENVIO_DEFAULT    = Decimal("50.00")
_ESTADO_PENDIENTE       = "PENDIENTE"
_ESTADO_CONFIRMADO      = "CONFIRMADO"
_ESTADO_EN_PREP         = "EN_PREP"
_ESTADO_CANCELADO       = "CANCELADO"
_FORMA_PAGO_MP          = "MERCADOPAGO"


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
    # Exponer init_point mientras el pago MP no se confirmó (para reintentar el checkout)
    resolved_init_point = init_point or (
        pedido.mp_init_point
        if (pedido.forma_pago_codigo == _FORMA_PAGO_MP and pedido.estado_codigo == _ESTADO_PENDIENTE)
        else None
    )
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
        init_point=resolved_init_point,
    )


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

        precio_snap   = producto.precio_base
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

    # NOTA: el stock NO se descuenta al crear el pedido. El inventario se consume
    # recién cuando el pedido se CONFIRMA (pago aprobado o confirmación del staff),
    # vía _descontar_stock_pedido. Acá solo se valida que haya stock disponible.

    # Calcular totales y persistir Pedido
    descuento = Decimal("0.00")
    costo_envio = _COSTO_ENVIO_DEFAULT if data.direccion_id is not None else Decimal("0.00")
    total = subtotal - descuento + costo_envio

    # FSM v7: todo pedido nace en PENDIENTE. El pago MP (webhook/redirect) lo
    # avanza a CONFIRMADO si se aprueba, o lo cancela si se rechaza.
    estado_inicial = _ESTADO_PENDIENTE

    pedido = Pedido(
        usuario_id=usuario_id,
        direccion_id=data.direccion_id,
        estado_codigo=estado_inicial,
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
        estado_hacia=estado_inicial,
        usuario_id=usuario_id,
        motivo=None,
    ))

    # MercadoPago (Checkout Pro): crear preferencia + registro Pago → init_point para el redirect.
    # El pedido queda PENDIENTE hasta que el pago se confirma (webhook / back_url → CONFIRMADO).
    init_point = None
    if data.forma_pago_codigo == _FORMA_PAGO_MP:
        from app.modules.pagos import service as pagos_service
        init_point = pagos_service.crear_preferencia_y_pago(uow, pedido, detalles_a_insertar)

    return _build_response(uow, pedido, init_point=init_point)


# ──────────────────────────────────────────────────────────────────────────────
# Restaurar stock al cancelar
# ──────────────────────────────────────────────────────────────────────────────

def _insumos_requeridos_pedido(uow, pedido: Pedido) -> dict[int, Decimal]:
    """Insumos (ingrediente_id → cantidad total) que consume el pedido, según sus
    detalles y las recetas actuales de los productos."""
    detalles = uow.pedidos.get_detalles(pedido.id)
    acumulado: dict[int, Decimal] = {}
    for detalle in detalles:
        links = uow.productos.get_ingrediente_links(detalle.producto_id)
        for link in links:
            cantidad = Decimal(str(link.cantidad)) * detalle.cantidad
            acumulado[link.ingrediente_id] = (
                acumulado.get(link.ingrediente_id, Decimal("0")) + cantidad
            )
    return acumulado


def _restaurar_stock_pedido(uow, pedido: Pedido) -> None:
    """Devuelve al stock los insumos que el pedido había descontado (al cancelar)."""
    for ing_id, cantidad in _insumos_requeridos_pedido(uow, pedido).items():
        ing = uow.ingredientes.get_by_id(ing_id)
        if not ing:
            continue
        ing.stock_cantidad += cantidad
        ing.updated_at = datetime.utcnow()
        uow.ingredientes.add(ing)


def _descontar_stock_pedido(uow, pedido: Pedido, validar: bool = True) -> None:
    """
    Descuenta del stock los insumos del pedido. Se llama al CONFIRMAR el pedido
    (pago aprobado / confirmación manual del staff), NO al crearlo: el inventario
    se consume cuando el pedido se paga, no cuando se crea en PENDIENTE.

    - validar=True (confirmación manual del staff): re-valida que haya stock y
      rechaza con 409 si no alcanza (el stock pudo cambiar desde la creación).
    - validar=False (pago MP ya aprobado): descuenta best-effort sin bloquear
      (el cobro ya se hizo) y nunca deja stock negativo.
    """
    requerido = _insumos_requeridos_pedido(uow, pedido)
    if validar:
        for ing_id, cantidad in requerido.items():
            ing = uow.ingredientes.get_by_id(ing_id)
            if not ing:
                _problem("PRODUCTO_NO_DISPONIBLE",
                         "Uno o más productos del pedido ya no están disponibles.",
                         status.HTTP_409_CONFLICT)
            if ing.stock_cantidad < cantidad:
                _problem("STOCK_INSUFICIENTE",
                         f"Stock insuficiente para insumo '{ing.nombre}': "
                         f"disponible {ing.stock_cantidad}, requerido {cantidad}",
                         status.HTTP_409_CONFLICT)
    for ing_id, cantidad in requerido.items():
        ing = uow.ingredientes.get_by_id(ing_id)
        if not ing:
            continue
        nuevo = ing.stock_cantidad - cantidad
        ing.stock_cantidad = nuevo if validar else max(Decimal("0"), nuevo)
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

    # Descontar stock al CONFIRMAR (no en la creación): el inventario se consume
    # cuando el pedido se paga/confirma. Re-valida que haya stock suficiente.
    if estado_hacia == _ESTADO_CONFIRMADO:
        _descontar_stock_pedido(uow, pedido, validar=True)

    # Restaurar stock al CANCELAR, según el estado del que viene:
    #  - PENDIENTE: nunca se descontó stock → no se restaura nada.
    #  - CONFIRMADO: reservado pero no preparado → se restaura siempre.
    #  - EN_PREP: los insumos pudieron consumirse en la cocina → lo decide el staff.
    if estado_hacia == _ESTADO_CANCELADO:
        if pedido.estado_codigo == _ESTADO_EN_PREP:
            if restaurar_stock:
                _restaurar_stock_pedido(uow, pedido)
        elif pedido.estado_codigo == _ESTADO_CONFIRMADO:
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

    # Restaurar stock solo si el pedido ya lo había descontado (estaba CONFIRMADO).
    # En PENDIENTE el stock nunca se descontó → no hay nada que restaurar. El cliente
    # NO decide esto (el parámetro restaurar_stock no aplica acá), lo que evita el
    # exploit de crear/cancelar pedidos sin pagar para vaciar el inventario.
    if pedido.estado_codigo == _ESTADO_CONFIRMADO:
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

# Roles de staff notificados en cada transición (rooms de rol del canal admin)
_ROLES_STAFF_WS = ["pedidos", "admin"]


def _tipo_evento(estado_nuevo: str) -> str:
    """Mapea el estado destino al tipo de evento §9.4."""
    if estado_nuevo == _ESTADO_CANCELADO:
        return "pedido_cancelado"
    return "estado_cambiado"


async def emit_ws_evento(pedido_id: int, event: Optional[str] = None) -> None:
    """
    Emite un evento WS con el formato §9.4 a la room del pedido y a las rooms de
    rol del staff. Se llama desde el router DESPUÉS de que el UoW commitea.

    Lee la última fila de HistorialEstadoPedido (append-only, fuente de verdad de
    la transición) para construir estado_anterior/nuevo, usuario_id y motivo.
    Si `event` se pasa explícito (p. ej. 'pago_confirmado') tiene prioridad.
    No lanza excepciones — si no hay conexiones activas, es silencioso.
    """
    from app.core.websocket import manager
    from app.core.unit_of_work import UnitOfWork

    # Construir el payload DENTRO del contexto: al cerrar el UoW la sesión se
    # cierra y los objetos quedan detached (no se pueden leer sus atributos).
    with UnitOfWork() as uow:
        historial = uow.pedidos.get_historial(pedido_id)
        if not historial:
            return
        ultimo = historial[-1]
        estado_nuevo = ultimo.estado_hacia
        ts = ultimo.created_at or datetime.utcnow()
        payload = {
            "event": event or _tipo_evento(estado_nuevo),
            "pedido_id": pedido_id,
            "estado_anterior": ultimo.estado_desde,
            "estado_nuevo": estado_nuevo,
            "usuario_id": ultimo.usuario_id,
            "motivo": ultimo.motivo,
            "timestamp": ts.replace(tzinfo=timezone.utc).isoformat(),
        }

    await manager.broadcast_to_order(pedido_id, payload)
    await manager.broadcast_to_roles(_ROLES_STAFF_WS, payload)


# ──────────────────────────────────────────────────────────────────────────────
# Callbacks de MercadoPago (llamados desde el redirect del backend)
# ──────────────────────────────────────────────────────────────────────────────

def confirmar_pago_mp(uow, pedido_id: int) -> PedidoResponse:
    """PENDIENTE → CONFIRMADO al aprobarse el pago. Idempotente: si ya avanzó, no repite."""
    pedido = uow.pedidos.get_by_id(pedido_id)
    if not pedido:
        _problem("PEDIDO_NOT_FOUND", f"Pedido {pedido_id} no encontrado", status.HTTP_404_NOT_FOUND)

    if pedido.estado_codigo != _ESTADO_PENDIENTE:
        # Ya confirmado/avanzado: solo aseguramos que el Pago quede como approved
        _marcar_pago_approved(uow, pedido_id)
        return _build_response(uow, pedido)

    # Pago MP aprobado → descontar stock (best-effort: el cobro ya se hizo,
    # no bloqueamos la confirmación; nunca se deja stock negativo).
    _descontar_stock_pedido(uow, pedido, validar=False)

    estado_desde         = pedido.estado_codigo
    pedido.estado_codigo = _ESTADO_CONFIRMADO
    pedido.updated_at    = datetime.utcnow()
    uow.pedidos.add(pedido)

    uow.pedidos.add_historial(HistorialEstadoPedido(
        pedido_id=pedido.id,
        estado_desde=estado_desde,
        estado_hacia=_ESTADO_CONFIRMADO,
        usuario_id=None,
        motivo="Pago confirmado por MercadoPago",
    ))

    _marcar_pago_approved(uow, pedido_id)
    return _build_response(uow, pedido)


def _marcar_pago_approved(uow, pedido_id: int) -> None:
    """Actualiza Pago.mp_status a 'approved' si existe y no lo está ya."""
    from datetime import datetime as _dt
    pago = uow.pagos.get_by_pedido_id(pedido_id)
    if pago and pago.mp_status != "approved":
        pago.mp_status = "approved"
        pago.updated_at = _dt.utcnow()
        uow.pagos.add(pago)


def cancelar_pago_mp(uow, pedido_id: int) -> None:
    """Pedido MP en PENDIENTE → CANCELADO al rechazarse el pago, y restaura stock. Idempotente."""
    pedido = uow.pedidos.get_by_id(pedido_id)
    if (
        not pedido
        or pedido.forma_pago_codigo != _FORMA_PAGO_MP
        or pedido.estado_codigo != _ESTADO_PENDIENTE
    ):
        return

    # El pedido estaba en PENDIENTE → nunca se descontó stock (se descuenta al
    # confirmar), así que no hay nada que restaurar al rechazarse el pago.

    estado_desde         = pedido.estado_codigo
    pedido.estado_codigo = _ESTADO_CANCELADO
    pedido.updated_at    = datetime.utcnow()
    uow.pedidos.add(pedido)

    uow.pedidos.add_historial(HistorialEstadoPedido(
        pedido_id=pedido.id,
        estado_desde=estado_desde,
        estado_hacia=_ESTADO_CANCELADO,
        usuario_id=None,
        motivo="Pago cancelado o rechazado en MercadoPago",
    ))


# ──────────────────────────────────────────────────────────────────────────────
# Verificar pago en MP (legacy — mantenido por compatibilidad)
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