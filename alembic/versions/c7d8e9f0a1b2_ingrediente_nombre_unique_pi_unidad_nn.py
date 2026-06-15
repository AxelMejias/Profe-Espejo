"""ingrediente.nombre UNIQUE + producto_ingrediente.unidad_medida_id NOT NULL (doc v7 §3.2)

Revision ID: c7d8e9f0a1b2
Revises: b2f1a7c9d3e0
Create Date: 2026-06-15 16:30:00.000000

Alinea constraints faltantes con el ERD v7:
- Ingrediente.nombre UNIQUE.
- ProductoIngrediente.unidad_medida_id NOT NULL (con backfill desde la unidad
  del insumo; fallback a 'ud').
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'b2f1a7c9d3e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ingrediente.nombre UNIQUE
    op.create_index(op.f('ix_ingrediente_nombre'), 'ingrediente', ['nombre'], unique=True)

    # 2. ProductoIngrediente.unidad_medida_id → NOT NULL (backfill primero)
    #    Resuelve la unidad desde el texto libre del insumo (símbolo o nombre).
    op.execute("""
        UPDATE producto_ingrediente AS pi
        SET unidad_medida_id = um.id
        FROM ingrediente AS i, unidad_medida AS um
        WHERE pi.ingrediente_id = i.id
          AND (lower(um.simbolo) = lower(i.unidad_medida) OR lower(um.nombre) = lower(i.unidad_medida))
          AND pi.unidad_medida_id IS NULL
    """)
    #    Fallback a 'ud' para lo que no haya matcheado.
    op.execute("""
        UPDATE producto_ingrediente
        SET unidad_medida_id = (SELECT id FROM unidad_medida WHERE simbolo = 'ud' LIMIT 1)
        WHERE unidad_medida_id IS NULL
          AND EXISTS (SELECT 1 FROM unidad_medida WHERE simbolo = 'ud')
    """)
    op.alter_column('producto_ingrediente', 'unidad_medida_id',
                    existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    op.alter_column('producto_ingrediente', 'unidad_medida_id',
                    existing_type=sa.Integer(), nullable=True)
    op.drop_index(op.f('ix_ingrediente_nombre'), table_name='ingrediente')
