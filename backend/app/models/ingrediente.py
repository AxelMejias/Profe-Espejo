from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from app.models.links import ProductoIngrediente

if TYPE_CHECKING:
    from app.models.producto import Producto


class Ingrediente(SQLModel, table=True):
    __tablename__ = "ingrediente"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(min_length=2, max_length=100, description="Nombre del ingrediente")
    unidad_medida: str = Field(
        min_length=1, max_length=50, description="Unidad de medida (kg, g, ml, unidad, etc.)"
    )

    # Relación N:N con Producto
    productos: List["Producto"] = Relationship(
        back_populates="ingredientes", link_model=ProductoIngrediente
    )
