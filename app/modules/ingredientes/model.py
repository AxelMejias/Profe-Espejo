from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship, Column
import sqlalchemy as sa
from app.core.links import ProductoIngrediente

if TYPE_CHECKING:
    from app.modules.productos.model import Producto


class Ingrediente(SQLModel, table=True):
    __tablename__ = "ingrediente"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(min_length=2, max_length=100, unique=True, index=True)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    unidad_medida: str = Field(min_length=1, max_length=50)
    es_alergeno: bool = Field(default=False)

    # ── Campos nuevos Parcial 3 ───────────────────────────────────────────────
    costo_unitario: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    stock_cantidad: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(sa.Numeric(10, 3), nullable=False, server_default="0"),
    )
    stock_minimo: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(sa.Numeric(10, 3), nullable=False, server_default="0"),
    )
    # True cuando el insumo ES un producto terminado (ej: una Coca-Cola)
    es_producto_terminado: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)

    productos: List["Producto"] = Relationship(
        back_populates="ingredientes", link_model=ProductoIngrediente
    )