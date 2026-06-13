"""create unidad_medida table + producto.unidad_venta_id

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-06-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unidad_medida",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("nombre", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("simbolo", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False),
        sa.Column("tipo", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre"),
        sa.UniqueConstraint("simbolo"),
    )
    op.create_index(op.f("ix_unidad_medida_nombre"), "unidad_medida", ["nombre"], unique=True)
    op.add_column("producto", sa.Column("unidad_venta_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_producto_unidad_venta", "producto", "unidad_medida", ["unidad_venta_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_producto_unidad_venta", "producto", type_="foreignkey")
    op.drop_column("producto", "unidad_venta_id")
    op.drop_index(op.f("ix_unidad_medida_nombre"), table_name="unidad_medida")
    op.drop_table("unidad_medida")
