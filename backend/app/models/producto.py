from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from app.models.links import ProductoCategoria, ProductoIngrediente

if TYPE_CHECKING:
    from app.models.categoria import Categoria
    from app.models.ingrediente import Ingrediente


class Producto(SQLModel, table=True):
    __tablename__ = "producto"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(min_length=2, max_length=100, description="Nombre del producto")
    descripcion: Optional[str] = Field(
        default=None, max_length=500, description="Descripción del producto"
    )
    precio: float = Field(gt=0, description="Precio del producto")

    # Relación N:N con Categoria
    categorias: List["Categoria"] = Relationship(
        back_populates="productos", link_model=ProductoCategoria
    )

    # Relación N:N con Ingrediente
    ingredientes: List["Ingrediente"] = Relationship(
        back_populates="productos", link_model=ProductoIngrediente
    )
