from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.categoria import CategoriaResponse


class IngredienteInput(BaseModel):
    ingrediente_id: int = Field(gt=0, description="ID del ingrediente")
    cantidad: float = Field(gt=0, description="Cantidad del ingrediente en el producto")


class IngredienteDeProductoResponse(BaseModel):
    id: int
    nombre: str
    unidad_medida: str
    cantidad: float


class ProductoCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    precio: float = Field(gt=0)
    categoria_ids: List[int] = Field(default_factory=list)
    ingredientes: List[IngredienteInput] = Field(default_factory=list)


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    precio: Optional[float] = Field(default=None, gt=0)


class ProductoListItem(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    precio: float
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProductoResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    precio: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    categorias: List[CategoriaResponse] = []
    ingredientes: List[IngredienteDeProductoResponse] = []
