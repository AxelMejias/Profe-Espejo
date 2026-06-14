"""producto precio_base + stock_cantidad, categoria imagen_url (doc v6 §3.2)

Revision ID: b2f1a7c9d3e0
Revises: 152df1fa29ee
Create Date: 2026-06-14 21:30:00.000000

Alinea el modelo con la Especificación v6.0 (ERD v7):
- Producto.precio → precio_base (rename, preserva datos)
- Producto.stock_cantidad INTEGER NOT NULL DEFAULT 0, CHECK >= 0 (gestionado por rol STOCK)
- Categoria.imagen_url TEXT NULL (URL de Cloudinary)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2f1a7c9d3e0'
down_revision: Union[str, None] = '152df1fa29ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Producto.precio → precio_base (rename preserva los valores existentes)
    op.alter_column('producto', 'precio', new_column_name='precio_base')

    # Producto.stock_cantidad
    op.add_column(
        'producto',
        sa.Column('stock_cantidad', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_check_constraint(
        'ck_producto_stock_no_negativo', 'producto', 'stock_cantidad >= 0',
    )

    # Categoria.imagen_url
    op.add_column('categoria', sa.Column('imagen_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('categoria', 'imagen_url')
    op.drop_constraint('ck_producto_stock_no_negativo', 'producto', type_='check')
    op.drop_column('producto', 'stock_cantidad')
    op.alter_column('producto', 'precio_base', new_column_name='precio')
