from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────────────

class ItemPedidoRequest(BaseModel):
    """Item enviado por el cliente al crear el pedido."""
    producto_id: int = Field(gt=0)
    cantidad: int = Field(ge=1)
    personalizacion: Optional[List[int]] = Field(
        default=None,
        description="IDs de Ingrediente removidos (solo válido si es_removible=true)",
    )


class PedidoCreate(BaseModel):
    direccion_id: Optional[int] = Field(default=None, gt=0)
    forma_pago_codigo: str = Field(min_length=1, max_length=20)
    items: List[ItemPedidoRequest] = Field(min_length=1)
    notas: Optional[str] = Field(default=None, max_length=500)


class AvanzarEstadoRequest(BaseModel):
    """
    Body para POST /pedidos/{id}/avanzar y /cancelar.
    Si estado_hacia == 'CANCELADO', motivo es obligatorio (RN-05).
    """
    estado_hacia: str = Field(min_length=1, max_length=20)
    motivo: Optional[str] = Field(default=None, max_length=500)
    restaurar_stock: bool = Field(
        default=True,
        description="Si True, devuelve el stock de los insumos al cancelar.",
    )


class CancelarPedidoRequest(BaseModel):
    """Body para que el CLIENT cancele su propio pedido (PENDIENTE/CONFIRMADO)."""
    motivo: str = Field(min_length=1, max_length=500)
    restaurar_stock: bool = Field(
        default=True,
        description="Si True, devuelve el stock de los insumos al cancelar.",
    )


# ── Response schemas ─────────────────────────────────────────────────────────

class DetallePedidoResponse(BaseModel):
    producto_id: int
    cantidad: int
    nombre_snapshot: str
    precio_snapshot: Decimal
    subtotal_snap: Decimal
    personalizacion: Optional[List[int]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HistorialEstadoResponse(BaseModel):
    id: int
    estado_desde: Optional[str] = None
    estado_hacia: str
    usuario_id: Optional[int] = None
    motivo: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PedidoListItem(BaseModel):
    id: int
    usuario_id: int
    estado_codigo: str
    forma_pago_codigo: str
    total: Decimal
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PedidoResponse(BaseModel):
    id: int
    usuario_id: int
    direccion_id: Optional[int] = None
    estado_codigo: str
    forma_pago_codigo: str
    subtotal: Decimal
    descuento: Decimal
    costo_envio: Decimal
    total: Decimal
    notas: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    detalles: List[DetallePedidoResponse] = []

    model_config = {"from_attributes": True}


class PaginatedPedidos(BaseModel):
    items: List[PedidoListItem]
    total: int
    page: int
    size: int
    pages: int


# ── Catálogos (para que el frontend pueble selects) ──────────────────────────

class EstadoPedidoResponse(BaseModel):
    codigo: str
    descripcion: str
    orden: int
    es_terminal: bool

    model_config = {"from_attributes": True}


class FormaPagoResponse(BaseModel):
    codigo: str
    descripcion: str
    habilitado: bool

    model_config = {"from_attributes": True}