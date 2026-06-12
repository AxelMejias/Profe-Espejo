"""create pedidos tables (direccion_entrega, estado_pedido, forma_pago, pedido, detalle_pedido, historial_estado_pedido)

Revision ID: f7g8h9i0j1k2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY

revision = "f7g8h9i0j1k2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "direccion_entrega",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("alias", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column("linea1", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("linea2", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("ciudad", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("provincia", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column("codigo_postal", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=True),
        sa.Column("latitud", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitud", sa.Numeric(9, 6), nullable=True),
        sa.Column("es_principal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_direccion_entrega_usuario_id", "direccion_entrega", ["usuario_id"])

    op.create_table(
        "estado_pedido",
        sa.Column("codigo", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("descripcion", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("es_terminal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("codigo"),
    )

    op.create_table(
        "forma_pago",
        sa.Column("codigo", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("descripcion", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("habilitado", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("codigo"),
    )

    op.create_table(
        "pedido",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("direccion_id", sa.Integer(), nullable=True),
        sa.Column("estado_codigo", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("forma_pago_codigo", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("descuento", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("costo_envio", sa.Numeric(10, 2), nullable=False, server_default=sa.text("50")),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("notas", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["direccion_id"], ["direccion_entrega.id"]),
        sa.ForeignKeyConstraint(["estado_codigo"], ["estado_pedido.codigo"]),
        sa.ForeignKeyConstraint(["forma_pago_codigo"], ["forma_pago.codigo"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pedido_usuario_id", "pedido", ["usuario_id"])
    op.create_index("ix_pedido_estado_codigo", "pedido", ["estado_codigo"])

    op.create_table(
        "detalle_pedido",
        sa.Column("pedido_id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("nombre_snapshot", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("precio_snapshot", sa.Numeric(10, 2), nullable=False),
        sa.Column("subtotal_snap", sa.Numeric(10, 2), nullable=False),
        sa.Column("personalizacion", PG_ARRAY(sa.Integer()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedido.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["producto.id"]),
        sa.PrimaryKeyConstraint("pedido_id", "producto_id"),
    )

    op.create_table(
        "historial_estado_pedido",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pedido_id", sa.Integer(), nullable=False),
        sa.Column("estado_desde", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
        sa.Column("estado_hacia", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("motivo", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["estado_desde"], ["estado_pedido.codigo"]),
        sa.ForeignKeyConstraint(["estado_hacia"], ["estado_pedido.codigo"]),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedido.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_historial_estado_pedido_pedido_id", "historial_estado_pedido", ["pedido_id"])


def downgrade() -> None:
    op.drop_table("historial_estado_pedido")
    op.drop_table("detalle_pedido")
    op.drop_table("pedido")
    op.drop_table("forma_pago")
    op.drop_table("estado_pedido")
    op.drop_index("ix_direccion_entrega_usuario_id", table_name="direccion_entrega")
    op.drop_table("direccion_entrega")
