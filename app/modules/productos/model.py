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

    # precio_base ya NO es ingresado por el usuario — lo calcula el service (doc §3.2)
    precio_base: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    margen_ganancia: Decimal = Field(
        default=Decimal("0.30"),
        sa_column=Column(sa.Numeric(5, 4), nullable=False, server_default="0.3"),
    )

    imagenes_url: List[str] = Field(
        default_factory=list,
        sa_column=Column(sa.ARRAY(sa.Text()), nullable=False, server_default="{}"),
    )
    # Stock numérico del producto, gestionado por rol STOCK (doc §3.2).
    # Independiente de `disponible` y del stock por insumo.
    stock_cantidad: int = Field(
        default=0,
        sa_column=Column(
            sa.Integer(),
            sa.CheckConstraint("stock_cantidad >= 0", name="ck_producto_stock_no_negativo"),
            nullable=False,
            server_default="0",
        ),
    )
    disponible: bool = Field(default=True)
    destacado: bool = Field(default=False)

    # FK → UnidadMedida (unidad de venta del producto, opcional)
    unidad_venta_id: Optional[int] = Field(default=None, foreign_key="unidad_medida.id")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)

    categorias: List["Categoria"] = Relationship(
        back_populates="productos", link_model=ProductoCategoria
    )
    ingredientes: List["Ingrediente"] = Relationship(
        back_populates="productos", link_model=ProductoIngrediente
    )