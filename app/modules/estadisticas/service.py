"""
Módulo Estadísticas — dashboard de métricas para el panel admin.

Reglas según la Especificación Técnica v6.0:
  EST-01: Nunca contar pedidos CANCELADO en ingresos ni cantidades.
  EST-02: Usar DetallePedido.subtotal_snap (precios históricos, no actuales).
  EST-03: Solo Pago.mp_status = 'approved' para ingresos confirmados.
  EST-04: Montos DECIMAL(10,2), nunca float.
  EST-05: Filtros por período con BETWEEN sobre date.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

import sqlalchemy as sa
from sqlmodel import Session, select, func

from app.modules.pedidos.model import Pedido, DetallePedido
from app.modules.pagos.model import Pago
from app.modules.estadisticas.repository import EstadisticasRepository
from app.modules.estadisticas.schemas import (
    DashboardResponse, ProductoMasVendido, VentasPorPeriodo,
    VentasPeriodoItem, ProductoTopItem, PedidosEstadoItem,
    IngresosFormaPagoItem, ResumenResponse,
)

_ESTADO_CANCELADO = "CANCELADO"


# ── Helpers ────────────────────────────────────────────────────────────────────
def _q(value) -> Decimal:
    """EST-04: todo monto como DECIMAL(10,2), nunca float nativo."""
    return Decimal(str(value if value is not None else 0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _as_date(v) -> date:
    return v.date() if isinstance(v, datetime) else v


def _hoy_ar() -> date:
    """Fecha de hoy en hora Argentina (UTC-3)."""
    return (datetime.utcnow() - timedelta(hours=3)).date()


# ── Los 5 endpoints de la Especificación v6.0 (§11.3) ───────────────────────────
def get_ventas(session: Session, desde: date, hasta: date, agrupacion: str = "day") -> list[VentasPeriodoItem]:
    repo = EstadisticasRepository(session)
    return [
        VentasPeriodoItem(
            periodo=_as_date(r.periodo),
            total_ventas=_q(r.total_ventas),
            cantidad_pedidos=int(r.cantidad_pedidos),
        )
        for r in repo.get_ventas_periodo(desde, hasta, agrupacion)
    ]


def get_productos_top(session: Session, desde: date, hasta: date, limit: int = 5) -> list[ProductoTopItem]:
    repo = EstadisticasRepository(session)
    return [
        ProductoTopItem(
            producto_id=r.producto_id,
            nombre=r.nombre,
            cantidad_vendida=int(r.cantidad_vendida),
            ingresos=_q(r.ingresos),
        )
        for r in repo.get_productos_top(desde, hasta, limit)
    ]


def get_pedidos_por_estado(session: Session) -> list[PedidosEstadoItem]:
    repo = EstadisticasRepository(session)
    return [
        PedidosEstadoItem(estado_codigo=r.estado_codigo, cantidad=int(r.cantidad))
        for r in repo.get_pedidos_por_estado()
    ]


def get_ingresos(session: Session, desde: date, hasta: date) -> list[IngresosFormaPagoItem]:
    repo = EstadisticasRepository(session)
    return [
        IngresosFormaPagoItem(
            forma_pago_codigo=r.forma_pago_codigo,
            total=_q(r.total),
            cantidad=int(r.cantidad),
        )
        for r in repo.get_ingresos_por_forma_pago(desde, hasta)
    ]


def get_resumen(session: Session) -> ResumenResponse:
    repo = EstadisticasRepository(session)
    hoy = _hoy_ar()
    inicio_mes = hoy.replace(day=1)

    total_hoy, _cant_hoy = repo.get_ventas_total_rango(hoy, hoy)
    total_mes, cant_mes = repo.get_ventas_total_rango(inicio_mes, hoy)
    ticket = (Decimal(str(total_mes)) / cant_mes) if cant_mes else Decimal("0")

    return ResumenResponse(
        ventas_hoy=_q(total_hoy),
        ticket_promedio=_q(ticket),
        pedidos_activos=repo.get_pedidos_activos(),
        ventas_mes=_q(total_mes),
    )


def get_dashboard(session: Session, fecha_desde: date, fecha_hasta: date) -> DashboardResponse:
    # EST-03: solo pedidos con pago approved
    # EST-01: excluir CANCELADO
    # EST-05: BETWEEN sobre date

    # Convertir created_at (UTC) a hora Argentina antes de extraer la fecha
    fecha_ar = sa.func.date(
        sa.cast(Pedido.created_at, sa.DateTime(timezone=False))
        + sa.text("INTERVAL '-3 hours'")
    )

    pedidos_aprobados = (
        select(Pedido.id, Pedido.total, fecha_ar.label("fecha"))
        .join(Pago, Pago.pedido_id == Pedido.id)
        .where(
            Pago.mp_status == "approved",
            Pedido.estado_codigo != _ESTADO_CANCELADO,
            Pedido.deleted_at.is_(None),
            fecha_ar.between(fecha_desde, fecha_hasta),
        )
    ).subquery()

    # ── Ingreso total y conteo de pedidos ─────────────────────────────────────
    resumen = session.exec(
        select(
            func.coalesce(func.sum(pedidos_aprobados.c.total), Decimal("0")).label("ingreso"),
            func.count(pedidos_aprobados.c.id).label("pedidos"),
        )
    ).one()

    ingreso_total = Decimal(str(resumen.ingreso)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    pedidos_completados = int(resumen.pedidos)
    ticket_promedio = (
        (ingreso_total / pedidos_completados).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if pedidos_completados > 0
        else Decimal("0.00")
    )

    # ── Productos más vendidos (EST-02: subtotal_snap) ────────────────────────
    top_rows = session.exec(
        select(
            DetallePedido.producto_id,
            DetallePedido.nombre_snapshot,
            func.sum(DetallePedido.cantidad).label("cantidad_total"),
            func.sum(DetallePedido.subtotal_snap).label("ingreso_total"),
        )
        .where(DetallePedido.pedido_id.in_(select(pedidos_aprobados.c.id)))
        .group_by(DetallePedido.producto_id, DetallePedido.nombre_snapshot)
        .order_by(sa.desc("cantidad_total"))
        .limit(5)
    ).all()

    productos_mas_vendidos = [
        ProductoMasVendido(
            producto_id=r.producto_id,
            nombre=r.nombre_snapshot,
            cantidad_total=int(r.cantidad_total),
            ingreso_total=Decimal(str(r.ingreso_total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )
        for r in top_rows
    ]

    # ── Ventas por día (EST-05: agrupado por date) ────────────────────────────
    dias_rows = session.exec(
        select(
            pedidos_aprobados.c.fecha,
            func.count(pedidos_aprobados.c.id).label("pedidos"),
            func.sum(pedidos_aprobados.c.total).label("ingreso"),
        )
        .group_by(pedidos_aprobados.c.fecha)
        .order_by(pedidos_aprobados.c.fecha)
    ).all()

    ventas_por_dia = [
        VentasPorPeriodo(
            fecha=r.fecha,
            pedidos=int(r.pedidos),
            ingreso=Decimal(str(r.ingreso)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )
        for r in dias_rows
    ]

    return DashboardResponse(
        ingreso_total=ingreso_total,
        pedidos_completados=pedidos_completados,
        ticket_promedio=ticket_promedio,
        productos_mas_vendidos=productos_mas_vendidos,
        ventas_por_dia=ventas_por_dia,
    )
