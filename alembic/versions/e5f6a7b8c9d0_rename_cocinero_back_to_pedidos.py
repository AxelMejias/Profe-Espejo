"""rename_cocinero_back_to_pedidos

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-06 00:00:00.000000

Revierte el rename PEDIDOS→COCINERO.
El rol vuelve a llamarse PEDIDOS con nombre "Gestor de Pedidos"
para alinearse con la documentación del sistema.
"""
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Insertar el rol PEDIDOS (por si no existe)
    op.execute(
        "INSERT INTO rol (codigo, nombre, descripcion) "
        "VALUES ('PEDIDOS', 'Gestor de Pedidos', 'Ver y avanzar estados de pedidos') "
        "ON CONFLICT (codigo) DO NOTHING"
    )
    # 2. Redirigir asignaciones existentes: COCINERO → PEDIDOS
    op.execute("UPDATE usuario_rol SET rol_codigo = 'PEDIDOS' WHERE rol_codigo = 'COCINERO'")
    # 3. Eliminar el rol COCINERO (ya sin referencias)
    op.execute("DELETE FROM rol WHERE codigo = 'COCINERO'")


def downgrade() -> None:
    op.execute(
        "INSERT INTO rol (codigo, nombre, descripcion) "
        "VALUES ('COCINERO', 'Cocinero', 'Gestión y avance de pedidos') "
        "ON CONFLICT (codigo) DO NOTHING"
    )
    op.execute("UPDATE usuario_rol SET rol_codigo = 'COCINERO' WHERE rol_codigo = 'PEDIDOS'")
    op.execute("DELETE FROM rol WHERE codigo = 'PEDIDOS'")
