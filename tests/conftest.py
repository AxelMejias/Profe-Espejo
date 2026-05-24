"""
conftest.py - Fixtures compartidos para todos los tests del back.

Estrategia: tests de servicio con UoW mockeado (unittest.mock.MagicMock).
No necesitamos base de datos real.
"""
from unittest.mock import MagicMock


def make_uow() -> MagicMock:
    """Crea un UoW completamente mockeado."""
    uow = MagicMock()
    return uow


def mock_usuario(
    id: int = 1,
    nombre: str = "Juan",
    apellido: str = "Perez",
    email: str = "juan@test.com",
    password_hash: str = "$2b$12$fakehash",
    deleted_at=None,
):
    u = MagicMock()
    u.id = id
    u.nombre = nombre
    u.apellido = apellido
    u.email = email
    u.password_hash = password_hash
    u.celular = None
    u.deleted_at = deleted_at
    u.created_at = "2024-01-01T00:00:00"
    u.updated_at = None
    return u


def mock_rol(codigo: str = "CLIENT", nombre: str = "Cliente"):
    r = MagicMock()
    r.codigo = codigo
    r.nombre = nombre
    return r


def mock_pedido(
    id: int = 1,
    usuario_id: int = 1,
    estado_codigo: str = "PENDIENTE",
    forma_pago_codigo: str = "EFECTIVO",
    deleted_at=None,
):
    from decimal import Decimal
    p = MagicMock()
    p.id = id
    p.usuario_id = usuario_id
    p.estado_codigo = estado_codigo
    p.forma_pago_codigo = forma_pago_codigo
    p.direccion_id = None
    p.subtotal = Decimal("100.00")
    p.descuento = Decimal("0.00")
    p.costo_envio = Decimal("50.00")
    p.total = Decimal("150.00")
    p.notas = None
    p.deleted_at = deleted_at
    p.created_at = "2024-01-01T00:00:00"
    p.updated_at = None
    return p


def mock_producto(
    id: int = 1,
    nombre: str = "Burger",
    precio=None,
    disponible: bool = True,
    stock_cantidad: int = 10,
    deleted_at=None,
):
    from decimal import Decimal
    p = MagicMock()
    p.id = id
    p.nombre = nombre
    p.precio = precio if precio is not None else Decimal("500.00")
    p.disponible = disponible
    p.stock_cantidad = stock_cantidad
    p.deleted_at = deleted_at
    return p
