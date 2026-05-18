from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class CategoriaResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    parent_id: Optional[int] = None

    model_config = {"from_attributes": True}


class IngredienteInput(BaseModel):
    ingrediente_id: int = Field(gt=0)
    cantidad: float = Field(gt=0)


class IngredienteDeProductoResponse(BaseModel):
    id: int
    nombre: str
    unidad_medida: str
    cantidad: float

    model_config = {"from_attributes": True}


class ProductoCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    precio: Decimal = Field(gt=0, decimal_places=2)
    stock_cantidad: int = Field(default=0, ge=0)
    disponible: bool = Field(default=True)
    categoria_ids: List[int] = Field(default_factory=list)
    ingredientes: List[IngredienteInput] = Field(default_factory=list)


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    precio: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2)
    stock_cantidad: Optional[int] = Field(default=None, ge=0)
    disponible: Optional[bool] = None


class ProductoListItem(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    precio: Decimal
    stock_cantidad: int
    disponible: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProductoResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    precio: Decimal
    stock_cantidad: int
    disponible: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    categorias: List[CategoriaResponse] = []
    ingredientes: List[IngredienteDeProductoResponse] = []

    model_config = {"from_attributes": True}