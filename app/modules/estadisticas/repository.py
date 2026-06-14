"""
Repository de Estadísticas — queries de solo lectura sobre las tablas existentes.

Reglas de negocio (Especificación v6.0 §11):
  EST-01: nunca incluir pedidos CANCELADO en ingresos ni cantidades.
  EST-02: usar DetallePedido.subtotal_snap para ingresos por producto.
  EST-03: solo pagos con mp_status = 'approved' cuentan como ingreso confirmado.
  EST-05: filtros de período con BETWEEN sobre date (created_at convertido a hora AR).
"""
from datetime import date
import sqlalchemy as sa
from sqlmodel import Session, select, func

from app.modules.pedidos.model import Pedido, DetallePedido
from app.modules.pagos.model import Pago

_ESTADO_CANCELADO = "CANCELADO"
_ESTADOS_ACTIVOS = ("PENDIENTE", "CONFIRMADO", "EN_PREP")
_AGRUPACIONES = {"day", "week", "month"}


def _ar_ts():
    """created_at (UTC) → timestamp en hora Argentina (UTC-3)."""
    return sa.cast(Pedido.created_at, sa.DateTime(timezone=False)) + sa.text("INTERVAL '-3 hours'")


def _ar_date():
    return sa.func.date(_ar_ts())


class EstadisticasRepository:
    """Recibe la sesión (no abre la suya). Todas las queries son de solo lectura."""

    def __init__(self, session: Session):
        self.session = session

    # ── Filtro base: pedidos con pago aprobado, no cancelados, no borrados ──────
    def _filtros_ingreso(self):
        return [
            Pago.mp_status == "approved",                 # EST-03
            Pedido.estado_codigo != _ESTADO_CANCELADO,    # EST-01
            Pedido.deleted_at.is_(None),
        ]

    # ── Ventas por período (LineChart) ─────────────────────────────────────────
    def get_ventas_periodo(self, desde: date, hasta: date, agrupacion: str = "day"):
        if agrupacion not in _AGRUPACIONES:
            agrupacion = "day"
        periodo = sa.func.date_trunc(agrupacion, _ar_ts()).label("periodo")
        return self.session.exec(
            select(
                periodo,
                func.coalesce(func.sum(Pedido.total), 0).label("total_ventas"),
                func.count(func.distinct(Pedido.id)).label("cantidad_pedidos"),
            )
            .join(Pago, Pago.pedido_id == Pedido.id)
            .where(*self._filtros_ingreso(), _ar_date().between(desde, hasta))  # EST-05
            .group_by(periodo)
            .order_by(periodo)
        ).all()

    # ── Top productos (BarChart) — EST-02: subtotal_snap ───────────────────────
    def get_productos_top(self, desde: date, hasta: date, limit: int = 5):
        return self.session.exec(
            select(
                DetallePedido.producto_id,
                DetallePedido.nombre_snapshot.label("nombre"),
                func.sum(DetallePedido.cantidad).label("cantidad_vendida"),
                func.sum(DetallePedido.subtotal_snap).label("ingresos"),
            )
            .join(Pedido, Pedido.id == DetallePedido.pedido_id)
            .join(Pago, Pago.pedido_id == Pedido.id)
            .where(*self._filtros_ingreso(), _ar_date().between(desde, hasta))
            .group_by(DetallePedido.producto_id, DetallePedido.nombre_snapshot)
            .order_by(sa.desc("cantidad_vendida"))
            .limit(limit)
        ).all()

    # ── Distribución por estado (PieChart) — GROUP BY simple, todos los pedidos ─
    def get_pedidos_por_estado(self):
        return self.session.exec(
            select(
                Pedido.estado_codigo,
                func.count(Pedido.id).label("cantidad"),
            )
            .where(Pedido.deleted_at.is_(None))
            .group_by(Pedido.estado_codigo)
            .order_by(sa.desc("cantidad"))
        ).all()

    # ── Ingresos por forma de pago (BarChart horizontal) ───────────────────────
    def get_ingresos_por_forma_pago(self, desde: date, hasta: date):
        return self.session.exec(
            select(
                Pedido.forma_pago_codigo,
                func.coalesce(func.sum(Pedido.total), 0).label("total"),
                func.count(func.distinct(Pedido.id)).label("cantidad"),
            )
            .join(Pago, Pago.pedido_id == Pedido.id)
            .where(*self._filtros_ingreso(), _ar_date().between(desde, hasta))
            .group_by(Pedido.forma_pago_codigo)
            .order_by(sa.desc("total"))
        ).all()

    # ── KPIs del resumen (cada uno es una query separada) ──────────────────────
    def get_ventas_total_rango(self, desde: date, hasta: date):
        """(suma_total, cantidad_pedidos) de pedidos con ingreso confirmado en el rango."""
        return self.session.exec(
            select(
                func.coalesce(func.sum(Pedido.total), 0),
                func.count(func.distinct(Pedido.id)),
            )
            .join(Pago, Pago.pedido_id == Pedido.id)
            .where(*self._filtros_ingreso(), _ar_date().between(desde, hasta))
        ).one()

    def get_pedidos_activos(self) -> int:
        total = self.session.exec(
            select(func.count(Pedido.id)).where(
                Pedido.deleted_at.is_(None),
                Pedido.estado_codigo.in_(_ESTADOS_ACTIVOS),
            )
        ).one()
        return int(total)
