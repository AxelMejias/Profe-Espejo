from typing import List
from datetime import date
from decimal import Decimal
from pydantic import BaseModel


# ── Schemas legacy del /dashboard (lo sigue usando el front por ahora) ──────────
class ProductoMasVendido(BaseModel):
    producto_id: int
    nombre: str
    cantidad_total: int
    ingreso_total: Decimal


class VentasPorPeriodo(BaseModel):
    fecha: date
    pedidos: int
    ingreso: Decimal


class DashboardResponse(BaseModel):
    ingreso_total: Decimal
    pedidos_completados: int
    ticket_promedio: Decimal
    productos_mas_vendidos: List[ProductoMasVendido]
    ventas_por_dia: List[VentasPorPeriodo]


# ── Schemas de los 5 endpoints de la Especificación v6.0 (§11) ──────────────────

class VentasPeriodoItem(BaseModel):
    """GET /estadisticas/ventas — una fila por período (LineChart)."""
    periodo: date
    total_ventas: Decimal
    cantidad_pedidos: int


class ProductoTopItem(BaseModel):
    """GET /estadisticas/productos-top — ranking (BarChart). EST-02: subtotal_snap."""
    producto_id: int
    nombre: str
    cantidad_vendida: int
    ingresos: Decimal


class PedidosEstadoItem(BaseModel):
    """GET /estadisticas/pedidos-por-estado — distribución (PieChart)."""
    estado_codigo: str
    cantidad: int


class IngresosFormaPagoItem(BaseModel):
    """GET /estadisticas/ingresos — por forma de pago (BarChart horizontal)."""
    forma_pago_codigo: str
    total: Decimal
    cantidad: int


class ResumenResponse(BaseModel):
    """GET /estadisticas/resumen — KPI cards."""
    ventas_hoy: Decimal
    ticket_promedio: Decimal
    pedidos_activos: int
    ventas_mes: Decimal
