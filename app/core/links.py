"""
Tablas pivot N:N compartidas entre módulos.
Se centralizan aquí para evitar imports circulares.
"""
from typing import Optional
from decimal import Decimal
from sqlmodel import SQLModel, Field, Column
import sqlalchemy as sa


class ProductoCategoria(SQLModel, table=True):
    __tablename__ = "producto_categoria"

    producto_id: Optional[int] = Field(
        default=None, foreign_key="producto.id", primary_key=True
    )
    categoria_id: Optional[int] = Field(
        default=None, foreign_key="categoria.id", primary_key=True
    )
    es_principal: bool = Field(default=False, description="Categoría principal del producto")


class ProductoIngrediente(SQLModel, table=True):
    __tablename__ = "producto_ingrediente"

    producto_id: Optional[int] = Field(
        default=None, foreign_key="producto.id", primary_key=True
    )
    ingrediente_id: Optional[int] = Field(
        default=None, foreign_key="ingrediente.id", primary_key=True
    )
    cantidad: Decimal = Field(
        sa_column=Column(sa.Numeric(10, 3), nullable=False),
        description="Cantidad del ingrediente en el producto",
    )
    es_removible: bool = Field(default=False, description="Si el cliente puede excluirlo")
    unidad_medida_id: int = Field(
        foreign_key="unidad_medida.id", nullable=False, description="Unidad de medida de la cantidad (doc v7, NN)"
    )
