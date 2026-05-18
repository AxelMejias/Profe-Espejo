from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship, Column
import sqlalchemy as sa
from app.core.links import ProductoCategoria, ProductoIngrediente

if TYPE_CHECKING:
    from app.modules.categorias.model import Categoria
    from app.modules.ingredientes.model import Ingrediente


class Producto(SQLModel, table=True):
    __tablename__ = "producto"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)

    # DECIMAL(10,2) — nunca float para precios
    precio: Decimal = Field(
        sa_column=Column(sa.Numeric(10, 2), nullable=False)
    )

    # Stock y disponibilidad (spec: RN-CA04, RN-CA05)
    stock_cantidad: int = Field(default=0, ge=0, description="Unidades disponibles en stock")
    disponible: bool = Field(default=True, description="Toggle manual de disponibilidad")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)   # soft delete (RN-CA09)

    categorias: List["Categoria"] = Relationship(
        back_populates="productos", link_model=ProductoCategoria
    )
    ingredientes: List["Ingrediente"] = Relationship(
        back_populates="productos", link_model=ProductoIngrediente
    )
