"""add esperando_pago estado

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-06-08
"""
from alembic import op

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO estado_pedido (codigo, descripcion, orden, es_terminal)
        VALUES ('ESPERANDO_PAGO', 'Esperando confirmación de pago', 0, false)
        ON CONFLICT (codigo) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM estado_pedido WHERE codigo = 'ESPERANDO_PAGO'")
