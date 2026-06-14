from typing import List, Optional
from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class ProductoMasVendido(BaseModel):
    producto_id: int
    nombre: str
    cantidad_total: int
    ingreso_total: Decimal


class VentasPorPeriodo(BaseModel):
    fecha: date
    pedidos: int
    ingreso: Decimal


class PedidosPorEstadoItem(BaseModel):
    estado_codigo: str
    cantidad: int


class IngresosPorFormaPagoItem(BaseModel):
    forma_pago: str
    total: Decimal
    cantidad_pedidos: int


class DashboardResponse(BaseModel):
    # Ingresos confirmados (solo pagos approved, EST-03)
    ingreso_total: Decimal
    # Pedidos (excluye CANCELADO, EST-01)
    pedidos_completados: int
    # Promedio por pedido
    ticket_promedio: Decimal
    # Top productos (EST-02: usa subtotal_snap)
    productos_mas_vendidos: List[ProductoMasVendido]
    # Ventas por día en el período
    ventas_por_dia: List[VentasPorPeriodo]
    pedidos_por_estado: List[PedidosPorEstadoItem] = []
    ingresos_por_forma_pago: List[IngresosPorFormaPagoItem] = []
