"""parcial3_insumos_stock

Revision ID: d4e5f6a7b8c9
Revises: b1c2d3e4f5a6
Create Date: 2026-05-26 00:00:00.000000

Agrega campos de insumo a la tabla ingrediente y margen_ganancia a producto.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ingrediente: nuevos campos de insumo ──────────────────────────────────
    op.add_column("ingrediente", sa.Column("costo_unitario",        sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("ingrediente", sa.Column("stock_cantidad",         sa.Numeric(10, 3), nullable=False, server_default="0"))
    op.add_column("ingrediente", sa.Column("stock_minimo",           sa.Numeric(10, 3), nullable=False, server_default="0"))
    op.add_column("ingrediente", sa.Column("es_producto_terminado",  sa.Boolean(),      nullable=False, server_default="false"))

    # ── producto: agregar margen, el campo precio ya existe ───────────────────
    op.add_column("producto", sa.Column("margen_ganancia", sa.Numeric(5, 4), nullable=False, server_default="0.3"))

    # ── producto: eliminar stock_cantidad (ahora está en ingrediente) ─────────
    op.drop_column("producto", "stock_cantidad")


def downgrade() -> None:
    op.add_column("producto", sa.Column("stock_cantidad", sa.Integer(), nullable=False, server_default="0"))
    op.drop_column("producto", "margen_ganancia")
    op.drop_column("ingrediente", "es_producto_terminado")
    op.drop_column("ingrediente", "stock_minimo")
    op.drop_column("ingrediente", "stock_cantidad")
    op.drop_column("ingrediente", "costo_unitario")