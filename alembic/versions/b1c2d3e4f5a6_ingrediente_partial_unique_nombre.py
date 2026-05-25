"""ingrediente_partial_unique_nombre

Revision ID: b1c2d3e4f5a6
Revises: a9b3c1d2e4f5
Create Date: 2026-05-25 00:00:00.000000

Reemplaza el UNIQUE global en ingrediente.nombre por un índice parcial
que solo aplica a registros activos (deleted_at IS NULL).
Esto permite reusar nombres de ingredientes eliminados (soft delete).
"""
from typing import Sequence, Union
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a9b3c1d2e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ingrediente_nombre_key", "ingrediente", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_ingrediente_nombre_activo "
        "ON ingrediente (nombre) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_ingrediente_nombre_activo")
    op.create_unique_constraint("ingrediente_nombre_key", "ingrediente", ["nombre"])
