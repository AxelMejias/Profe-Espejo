"""
conftest.py - Fixtures compartidos para todos los tests del back.

Dos estrategias conviven:
1. Tests de SERVICIO con UoW mockeado (MagicMock) — `make_uow` y los `mock_*`.
2. Tests de INTEGRACIÓN con TestClient (doc §13) — fixtures `client`, `*_headers`,
   `producto_factory`, `pedido_factory`, sobre una base PostgreSQL de test aislada
   (`foodstore_test_db`), separada de la DB de desarrollo.
"""
from unittest.mock import MagicMock

import pytest
from sqlmodel import Session, SQLModel, create_engine, text, select

# ──────────────────────────────────────────────────────────────────────────────
# Infraestructura de tests de INTEGRACIÓN (doc §13)
# ──────────────────────────────────────────────────────────────────────────────

_PG_BASE = "postgresql://postgres:postgres@localhost:5432"
_TEST_DB_NAME = "foodstore_test_db"
_TEST_DB_URL = f"{_PG_BASE}/{_TEST_DB_NAME}"


@pytest.fixture(scope="session")
def _engine():
    """Engine apuntado a una DB PostgreSQL de test aislada. Crea el esquema y seedea
    catálogos una vez por sesión. Repunta el engine global de la app (UoW + get_session)."""
    # 1. Crear la DB de test si no existe
    admin = create_engine(f"{_PG_BASE}/postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _TEST_DB_NAME}
        ).first()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
    admin.dispose()

    eng = create_engine(_TEST_DB_URL)

    # 2. Repuntar el engine global en los 3 módulos que lo bindean al importar
    import app.core.database as db_mod
    import app.core.unit_of_work as uow_mod
    import app.db.seed as seed_mod
    originals = (db_mod.engine, uow_mod.engine, seed_mod.engine)
    db_mod.engine = eng
    uow_mod.engine = eng
    seed_mod.engine = eng

    # 3. Esquema limpio + seed de catálogos (roles, estados, formas pago, unidades, users)
    import main  # noqa: F401 — registra TODOS los modelos en SQLModel.metadata
    SQLModel.metadata.drop_all(eng)
    SQLModel.metadata.create_all(eng)
    seed_mod.seed()

    # 4. Desactivar el rate limiter para no romper la suite con 429
    from app.modules.auth.router import limiter
    limiter.enabled = False

    yield eng

    SQLModel.metadata.drop_all(eng)
    db_mod.engine, uow_mod.engine, seed_mod.engine = originals
    eng.dispose()


@pytest.fixture(scope="session")
def client(_engine):
    """TestClient de FastAPI sobre la DB de test. No usa `with` para no re-disparar
    el lifespan (el esquema y el seed ya los preparó la fixture `_engine`)."""
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def _login(client, email: str, password: str) -> dict:
    """Loguea y devuelve headers Bearer. Limpia la cookie para que no pise el Bearer
    en los requests siguientes (la dependencia prioriza la cookie sobre el header)."""
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def admin_headers(client) -> dict:
    return _login(client, "admin@foodstore.com", "Admin1234!")


@pytest.fixture(scope="session")
def pedidos_headers(client) -> dict:
    return _login(client, "cocina@foodstore.com", "Cocina1234!")


@pytest.fixture(scope="session")
def stock_headers(client) -> dict:
    return _login(client, "stock@foodstore.com", "Stock1234!")


@pytest.fixture(scope="session")
def client_headers(client) -> dict:
    """Usuario CLIENT de test (registrado una vez; si ya existe, solo loguea)."""
    client.post("/api/v1/auth/register", json={
        "nombre": "Cliente", "apellido": "Test",
        "email": "cliente@test.com", "password": "Cliente1234!",
    })
    client.cookies.clear()
    return _login(client, "cliente@test.com", "Cliente1234!")


@pytest.fixture
def producto_factory(_engine):
    """Crea un Producto disponible con stock directamente en la BD de test."""
    from decimal import Decimal
    from app.modules.productos.model import Producto

    created = []

    def _make(nombre="Producto Test", precio_base="1000.00", stock_cantidad=50, disponible=True):
        with Session(_engine) as s:
            p = Producto(
                nombre=nombre,
                descripcion="Producto de test",
                imagenes_url=[],
                precio_base=Decimal(str(precio_base)),
                margen_ganancia=Decimal("0.30"),
                stock_cantidad=stock_cantidad,
                disponible=disponible,
            )
            s.add(p)
            s.commit()
            s.refresh(p)
            created.append(p.id)
            return p

    return _make


@pytest.fixture
def pedido_factory(_engine):
    """Crea un Pedido en PENDIENTE con un DetallePedido, para un usuario y producto dados."""
    from decimal import Decimal
    from app.modules.pedidos.model import Pedido, DetallePedido, HistorialEstadoPedido

    def _make(usuario_id: int, producto, cantidad: int = 1, forma_pago_codigo="EFECTIVO"):
        with Session(_engine) as s:
            precio = Decimal(str(producto.precio_base))
            subtotal = precio * cantidad
            pedido = Pedido(
                usuario_id=usuario_id,
                estado_codigo="PENDIENTE",
                forma_pago_codigo=forma_pago_codigo,
                subtotal=subtotal,
                descuento=Decimal("0.00"),
                costo_envio=Decimal("0.00"),
                total=subtotal,
            )
            s.add(pedido)
            s.flush()
            s.add(DetallePedido(
                pedido_id=pedido.id,
                producto_id=producto.id,
                cantidad=cantidad,
                nombre_snapshot=producto.nombre,
                precio_snapshot=precio,
                subtotal_snap=subtotal,
            ))
            s.add(HistorialEstadoPedido(
                pedido_id=pedido.id,
                estado_desde=None,
                estado_hacia="PENDIENTE",
                usuario_id=usuario_id,
            ))
            s.commit()
            s.refresh(pedido)
            return pedido

    return _make


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
    p.precio_base = precio if precio is not None else Decimal("500.00")
    p.disponible = disponible
    p.stock_cantidad = stock_cantidad
    p.deleted_at = deleted_at
    return p
