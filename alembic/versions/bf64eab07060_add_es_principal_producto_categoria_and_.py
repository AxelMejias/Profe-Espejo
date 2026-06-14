"""add_es_principal_producto_categoria_and_update_producto_ingrediente

Revision ID: bf64eab07060
Revises: k1l2m3n4o5p6
Create Date: 2026-06-13 17:27:23.324616

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'bf64eab07060'
down_revision: Union[str, None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('producto_categoria', sa.Column('es_principal', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('producto_ingrediente', sa.Column('unidad_medida_id', sa.Integer(), nullable=True))
    op.alter_column('producto_ingrediente', 'cantidad',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               type_=sa.Numeric(precision=10, scale=3),
               existing_nullable=False)
    op.create_foreign_key('fk_pi_unidad_medida', 'producto_ingrediente', 'unidad_medida', ['unidad_medida_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_pi_unidad_medida', 'producto_ingrediente', type_='foreignkey')
    op.alter_column('producto_ingrediente', 'cantidad',
               existing_type=sa.Numeric(precision=10, scale=3),
               type_=sa.DOUBLE_PRECISION(precision=53),
               existing_nullable=False)
    op.drop_column('producto_ingrediente', 'unidad_medida_id')
    op.drop_column('producto_categoria', 'es_principal')
