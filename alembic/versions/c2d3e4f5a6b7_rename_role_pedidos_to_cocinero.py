"""rename_role_pedidos_to_cocinero

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-25 00:00:00.000000

Renombra el rol PEDIDOS → COCINERO en las tablas rol y usuario_rol.
Se actualiza usuario_rol primero para respetar la FK (no hay ON UPDATE CASCADE).
"""
from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Insertar el nuevo rol (así la FK de usuario_rol puede apuntar a él)
    op.execute(
        "INSERT INTO rol (codigo, nombre, descripcion) "
        "VALUES ('COCINERO', 'Cocinero', 'Gestión y avance de pedidos') "
        "ON CONFLICT (codigo) DO NOTHING"
    )
    # 2. Redirigir las asignaciones existentes
    op.execute("UPDATE usuario_rol SET rol_codigo = 'COCINERO' WHERE rol_codigo = 'PEDIDOS'")
    # 3. Eliminar el rol viejo (ya sin referencias)
    op.execute("DELETE FROM rol WHERE codigo = 'PEDIDOS'")


def downgrade() -> None:
    op.execute(
        "INSERT INTO rol (codigo, nombre, descripcion) "
        "VALUES ('PEDIDOS', 'Gestor de Pedidos', 'Gestión de pedidos') "
        "ON CONFLICT (codigo) DO NOTHING"
    )
    op.execute("UPDATE usuario_rol SET rol_codigo = 'PEDIDOS' WHERE rol_codigo = 'COCINERO'")
    op.execute("DELETE FROM rol WHERE codigo = 'COCINERO'")
