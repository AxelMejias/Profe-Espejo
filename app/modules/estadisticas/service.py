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

from sqlmodel import Session

from app.modules.estadisticas.repository import EstadisticasRepository
from app.modules.estadisticas.schemas import (
    DashboardResponse, ProductoMasVendido, VentasPorPeriodo,
    VentasPeriodoItem, ProductoTopItem, PedidosEstadoItem,
    IngresosFormaPagoItem, ResumenResponse, AlertasStockResponse,
)
from app.modules.productos import service as productos_service


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


def get_alertas_stock(uow) -> AlertasStockResponse:
    """Conteos para los avisos de reposición del dashboard.

    Reutiliza el filtro `con_stock=False` del catálogo de productos (mismo criterio
    que el "Sin stock" de la tienda) y el conteo de ingredientes bajo mínimo del
    repositorio, para no duplicar la regla de negocio.
    """
    productos_sin_stock = productos_service.get_all(
        uow, solo_disponibles=False, con_stock=False, page=1, size=1
    ).total
    ingredientes_stock_bajo = uow.ingredientes.count_stock_bajo()
    return AlertasStockResponse(
        ingredientes_stock_bajo=ingredientes_stock_bajo,
        productos_sin_stock=productos_sin_stock,
    )


def get_dashboard(session: Session, fecha_desde: date, fecha_hasta: date) -> DashboardResponse:
    # Reglas de negocio (mapeo a schema, redondeo, ticket promedio) acá; las queries
    # viven en el repository (EST-01/03/05 aplicados en _pedidos_aprobados_subq).
    repo = EstadisticasRepository(session)

    # ── Ingreso total y conteo de pedidos ─────────────────────────────────────
    resumen = repo.get_dashboard_resumen(fecha_desde, fecha_hasta)
    ingreso_total = _q(resumen.ingreso)
    pedidos_completados = int(resumen.pedidos)
    ticket_promedio = (
        (ingreso_total / pedidos_completados).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if pedidos_completados > 0
        else Decimal("0.00")
    )

    # ── Productos más vendidos (EST-02: subtotal_snap) ────────────────────────
    productos_mas_vendidos = [
        ProductoMasVendido(
            producto_id=r.producto_id,
            nombre=r.nombre_snapshot,
            cantidad_total=int(r.cantidad_total),
            ingreso_total=_q(r.ingreso_total),
        )
        for r in repo.get_dashboard_top_productos(fecha_desde, fecha_hasta, limit=5)
    ]

    # ── Ventas por día (EST-05: agrupado por date) ────────────────────────────
    ventas_por_dia = [
        VentasPorPeriodo(
            fecha=r.fecha,
            pedidos=int(r.pedidos),
            ingreso=_q(r.ingreso),
        )
        for r in repo.get_dashboard_ventas_por_dia(fecha_desde, fecha_hasta)
    ]

    return DashboardResponse(
        ingreso_total=ingreso_total,
        pedidos_completados=pedidos_completados,
        ticket_promedio=ticket_promedio,
        productos_mas_vendidos=productos_mas_vendidos,
        ventas_por_dia=ventas_por_dia,
    )
