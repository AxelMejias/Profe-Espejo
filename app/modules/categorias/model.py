from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from app.core.links import ProductoCategoria

if TYPE_CHECKING:
    from app.modules.productos.model import Producto


class Categoria(SQLModel, table=True):
    __tablename__ = "categoria"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    parent_id: Optional[int] = Field(default=None, foreign_key="categoria.id")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)   # soft delete

    productos: List["Producto"] = Relationship(
        back_populates="categorias", link_model=ProductoCategoria
    )
