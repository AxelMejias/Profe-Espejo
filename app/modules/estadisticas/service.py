"""
Módulo Estadísticas — dashboard de métricas para el panel admin.

Reglas según la Especificación Técnica v6.0:
  EST-01: Nunca contar pedidos CANCELADO en ingresos ni cantidades.
  EST-02: Usar DetallePedido.subtotal_snap (precios históricos, no actuales).
  EST-03: Solo Pago.mp_status = 'approved' para ingresos confirmados.
  EST-04: Montos DECIMAL(10,2), nunca float.
  EST-05: Filtros por período con BETWEEN sobre date.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List

import sqlalchemy as sa
from sqlmodel import Session, select, func

from app.modules.pedidos.model import Pedido, DetallePedido
from app.modules.pagos.model import Pago
from app.modules.estadisticas.schemas import (
    DashboardResponse, ProductoMasVendido, VentasPorPeriodo,
    PedidosPorEstadoItem, IngresosPorFormaPagoItem,
)

_ESTADO_CANCELADO = "CANCELADO"


def get_pedidos_por_estado(session: Session) -> List[PedidosPorEstadoItem]:
    rows = session.exec(
        select(
            Pedido.estado_codigo,
            func.count(Pedido.id).label("cantidad"),
        )
        .where(Pedido.deleted_at.is_(None))
        .group_by(Pedido.estado_codigo)
        .order_by(Pedido.estado_codigo)
    ).all()
    return [
        PedidosPorEstadoItem(estado_codigo=r.estado_codigo, cantidad=int(r.cantidad))
        for r in rows
    ]


def get_ingresos_por_forma_pago(
    session: Session, fecha_desde: date, fecha_hasta: date
) -> List[IngresosPorFormaPagoItem]:
    fecha_ar = sa.func.date(
        sa.cast(Pedido.created_at, sa.DateTime(timezone=False))
        + sa.text("INTERVAL '-3 hours'")
    )
    rows = session.exec(
        select(
            Pedido.forma_pago_codigo.label("forma_pago"),
            func.coalesce(func.sum(Pedido.total), Decimal("0")).label("total"),
            func.count(Pedido.id).label("cantidad_pedidos"),
        )
        .join(Pago, Pago.pedido_id == Pedido.id)
        .where(
            Pago.mp_status == "approved",
            Pedido.estado_codigo != _ESTADO_CANCELADO,
            Pedido.deleted_at.is_(None),
            fecha_ar.between(fecha_desde, fecha_hasta),
        )
        .group_by(Pedido.forma_pago_codigo)
        .order_by(sa.desc("total"))
    ).all()
    return [
        IngresosPorFormaPagoItem(
            forma_pago=r.forma_pago,
            total=Decimal(str(r.total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            cantidad_pedidos=int(r.cantidad_pedidos),
        )
        for r in rows
    ]


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

    pedidos_por_estado = get_pedidos_por_estado(session)
    ingresos_por_forma_pago = get_ingresos_por_forma_pago(session, fecha_desde, fecha_hasta)

    return DashboardResponse(
        ingreso_total=ingreso_total,
        pedidos_completados=pedidos_completados,
        ticket_promedio=ticket_promedio,
        productos_mas_vendidos=productos_mas_vendidos,
        ventas_por_dia=ventas_por_dia,
        pedidos_por_estado=pedidos_por_estado,
        ingresos_por_forma_pago=ingresos_por_forma_pago,
    )
