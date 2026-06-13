from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


# ── Sub-schemas para el maestro-detalle ───────────────────────────────────────

class InsumoEnProductoCreate(BaseModel):
    """Un renglón del detalle al crear/actualizar un producto."""
    ingrediente_id: int = Field(gt=0)
    cantidad: Decimal = Field(gt=0)


class InsumoEnProductoRead(BaseModel):
    """Un renglón del detalle al leer un producto."""
    ingrediente_id: int
    nombre: str
    cantidad: Decimal
    unidad_medida: str
    costo_unitario: Decimal
    subtotal: Decimal          # cantidad * costo_unitario
    stock_actual: Decimal
    es_producto_terminado: bool

    model_config = {"from_attributes": True}


# ── Schemas principales ────────────────────────────────────────────────────────

class ProductoCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    image_url: Optional[str] = Field(default=None, max_length=500)
    margen_ganancia: Decimal = Field(ge=Decimal("0"), le=Decimal("10"))
    disponible: bool = True
    unidad_venta_id: Optional[int] = Field(default=None, gt=0)
    categoria_ids: List[int] = Field(default_factory=list)
    insumos: List[InsumoEnProductoCreate] = Field(min_length=1)


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    image_url: Optional[str] = Field(default=None, max_length=500)
    margen_ganancia: Optional[Decimal] = Field(default=None, ge=0, le=10)
    disponible: Optional[bool] = None
    unidad_venta_id: Optional[int] = Field(default=None, gt=0)
    categoria_ids: Optional[List[int]] = None
    insumos: Optional[List[InsumoEnProductoCreate]] = None


class CategoriaSimple(BaseModel):
    id: int
    nombre: str
    parent_id: Optional[int] = None

    model_config = {"from_attributes": True}


class ProductoRead(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    image_url: Optional[str] = None
    precio: Decimal                    # calculado: costo_total * (1 + margen)
    margen_ganancia: Decimal
    costo_total_insumos: Decimal       # suma de subtotales
    disponible: bool
    destacado: bool = False
    unidad_venta_id: Optional[int] = None
    unidad_venta_simbolo: Optional[str] = None
    categorias: List[CategoriaSimple]
    insumos: List[InsumoEnProductoRead]
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedProductos(BaseModel):
    items: List[ProductoRead]
    total: int
    page: int
    size: int
    pages: int