from typing import Optional, List
from pydantic import BaseModel, Field
from app.schemas.categoria import CategoriaResponse


class IngredienteInput(BaseModel):
    """Ingrediente con cantidad para el cuerpo de creación/edición de un producto."""
    ingrediente_id: int = Field(gt=0, description="ID del ingrediente")
    cantidad: float = Field(gt=0, description="Cantidad del ingrediente en el producto")


class IngredienteDeProductoResponse(BaseModel):
    """Ingrediente con su cantidad dentro de un producto (para el response)."""
    id: int
    nombre: str
    unidad_medida: str
    cantidad: float


class ProductoCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100, description="Nombre del producto")
    descripcion: Optional[str] = Field(default=None, max_length=500)
    precio: float = Field(gt=0, description="Precio del producto")
    categoria_ids: List[int] = Field(default_factory=list, description="IDs de categorías asociadas")
    ingredientes: List[IngredienteInput] = Field(
        default_factory=list, description="Ingredientes con sus cantidades"
    )


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    precio: Optional[float] = Field(default=None, gt=0)


class ProductoListItem(BaseModel):
    """Schema simplificado para el listado de productos (sin relaciones)."""
    id: int
    nombre: str
    descripcion: Optional[str] = None
    precio: float

    model_config = {"from_attributes": True}


class ProductoResponse(BaseModel):
    """Schema completo con categorías e ingredientes (con cantidad)."""
    id: int
    nombre: str
    descripcion: Optional[str] = None
    precio: float
    categorias: List[CategoriaResponse] = []
    ingredientes: List[IngredienteDeProductoResponse] = []
