from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class IngredienteCreate(BaseModel):
    nombre: str = Field(min_length=3, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    unidad_medida: str = Field(min_length=1, max_length=50)
    es_alergeno: bool = False
    costo_unitario: Decimal = Field(default=Decimal("0.00"), ge=0)
    stock_cantidad: Decimal = Field(default=Decimal("0.00"), ge=0)
    stock_minimo: Decimal = Field(default=Decimal("0.00"), ge=0)
    es_producto_terminado: bool = False


class IngredienteUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=3, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    unidad_medida: Optional[str] = Field(default=None, min_length=1, max_length=50)
    es_alergeno: Optional[bool] = None
    costo_unitario: Optional[Decimal] = Field(default=None, ge=0)
    stock_cantidad: Optional[Decimal] = Field(default=None, ge=0)
    stock_minimo: Optional[Decimal] = Field(default=None, ge=0)
    es_producto_terminado: Optional[bool] = None


class IngredienteResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    unidad_medida: str
    es_alergeno: bool
    costo_unitario: Decimal
    stock_cantidad: Decimal
    stock_minimo: Decimal
    es_producto_terminado: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedIngredientes(BaseModel):
    items: List[IngredienteResponse]
    total: int
    page: int
    size: int
    pages: int