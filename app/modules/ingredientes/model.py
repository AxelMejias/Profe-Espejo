from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from app.core.links import ProductoIngrediente

if TYPE_CHECKING:
    from app.modules.productos.model import Producto


class Ingrediente(SQLModel, table=True):
    __tablename__ = "ingrediente"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(min_length=2, max_length=100, unique=True)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    unidad_medida: str = Field(min_length=1, max_length=50)
    es_alergeno: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)

    productos: List["Producto"] = Relationship(
        back_populates="ingredientes", link_model=ProductoIngrediente
    )
