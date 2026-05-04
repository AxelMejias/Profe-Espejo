from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from app.models.links import ProductoCategoria

if TYPE_CHECKING:
    from app.models.producto import Producto


class Categoria(SQLModel, table=True):
    __tablename__ = "categoria"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(min_length=2, max_length=100, description="Nombre de la categoria")
    descripcion: Optional[str] = Field(default=None, max_length=255)

    # Relacion reflexiva: ID del padre (NULL = categoria raiz)
    parent_id: Optional[int] = Field(
        default=None, foreign_key="categoria.id", description="ID de la categoria padre"
    )

    # Campos de auditoria
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    # Relacion reflexiva - subcategorias (hijos)
    subcategorias: List["Categoria"] = Relationship(
        back_populates="padre",
        sa_relationship_kwargs={
            "foreign_keys": "[Categoria.parent_id]",
        },
    )

    # Relacion reflexiva - padre
    padre: Optional["Categoria"] = Relationship(
        back_populates="subcategorias",
        sa_relationship_kwargs={
            "foreign_keys": "[Categoria.parent_id]",
            "remote_side": "[Categoria.id]",
        },
    )

    # Relacion N:N con Producto
    productos: List["Producto"] = Relationship(
        back_populates="categorias", link_model=ProductoCategoria
    )
