"""create pago table

Revision ID: j0k1l2m3n4o5
Revises: 82df92cb76ba
Create Date: 2026-06-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "82df92cb76ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pago",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("pedido_id", sa.BigInteger(), nullable=False),
        sa.Column("mp_payment_id", sa.BigInteger(), nullable=True),
        sa.Column("mp_status", sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False),
        sa.Column("mp_status_detail", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column("external_reference", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("idempotency_key", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("transaction_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("payment_method_id", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedido.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mp_payment_id"),
        sa.UniqueConstraint("external_reference"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_pago_pedido_id"), "pago", ["pedido_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pago_pedido_id"), table_name="pago")
    op.drop_table("pago")
