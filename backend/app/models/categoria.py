from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from app.models.links import ProductoCategoria

if TYPE_CHECKING:
    from app.models.producto import Producto


class Categoria(SQLModel, table=True):
    __tablename__ = "categoria"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(min_length=2, max_length=100, description="Nombre de la categoría")
    descripcion: Optional[str] = Field(
        default=None, max_length=255, description="Descripción de la categoría"
    )

    # Relación N:N con Producto
    productos: List["Producto"] = Relationship(
        back_populates="categorias", link_model=ProductoCategoria
    )
