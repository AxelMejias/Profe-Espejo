"""add mp_preference_id to pedido and enable MERCADOPAGO

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa

revision = "g7h8i9j0k1l2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pedido", sa.Column("mp_preference_id", sa.String(200), nullable=True))
    op.execute("UPDATE forma_pago SET habilitado = TRUE WHERE codigo = 'MERCADOPAGO'")


def downgrade() -> None:
    op.drop_column("pedido", "mp_preference_id")
    op.execute("UPDATE forma_pago SET habilitado = FALSE WHERE codigo = 'MERCADOPAGO'")
