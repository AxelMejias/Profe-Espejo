from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship, Column
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY

if TYPE_CHECKING:
    from app.modules.direcciones.model import DireccionEntrega


# ──────────────────────────────────────────────────────────────────────────────
# Catálogos (PK semántica — seed obligatorio en app/db/seed.py)
# ──────────────────────────────────────────────────────────────────────────────

class EstadoPedido(SQLModel, table=True):
    """
    Catálogo de estados del FSM de pedidos.
    PK = codigo (legible en logs y payloads JWT, no surrogate ID).
    """
    __tablename__ = "estado_pedido"

    codigo: str = Field(primary_key=True, max_length=20)
    descripcion: str = Field(max_length=80)
    orden: int = Field(description="Orden secuencial en el flujo principal")
    es_terminal: bool = Field(default=False, description="True ⇒ 0 transiciones salientes")

    pedidos: List["Pedido"] = Relationship(back_populates="estado")


class FormaPago(SQLModel, table=True):
    """
    Catálogo de formas de pago. PK = codigo.
    Existe a nivel estructura para respetar el diagrama UML;
    su lógica funcional (pasarela MercadoPago) está excluida del Parcial 2.
    """
    __tablename__ = "forma_pago"

    codigo: str = Field(primary_key=True, max_length=20)
    descripcion: str = Field(max_length=80)
    habilitado: bool = Field(default=True, description="False ⇒ oculto en formularios de nuevo pedido")

    pedidos: List["Pedido"] = Relationship(back_populates="forma_pago")


# ──────────────────────────────────────────────────────────────────────────────
# Pedido — entidad principal del dominio de ventas
# ──────────────────────────────────────────────────────────────────────────────

class Pedido(SQLModel, table=True):
    __tablename__ = "pedido"

    id: Optional[int] = Field(default=None, primary_key=True)

    # FK → Usuario (sin Relationship recíproca: no se modifica el módulo auth)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)

    # FK → DireccionEntrega (opcional: pedidos para retiro en local pueden no tener)
    direccion_id: Optional[int] = Field(default=None, foreign_key="direccion_entrega.id")

    estado_codigo:     str = Field(foreign_key="estado_pedido.codigo", index=True)
    forma_pago_codigo: str = Field(foreign_key="forma_pago.codigo")

    # ── Snapshot monetario (inmutable desde la creación, RN-04) ──────────────
    subtotal:    Decimal = Field(sa_column=Column(sa.Numeric(10, 2), nullable=False))
    descuento:   Decimal = Field(default=Decimal("0.00"),  sa_column=Column(sa.Numeric(10, 2), nullable=False, default=0))
    costo_envio: Decimal = Field(default=Decimal("50.00"), sa_column=Column(sa.Numeric(10, 2), nullable=False, default=50))
    total:       Decimal = Field(sa_column=Column(sa.Numeric(10, 2), nullable=False))

    notas: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)

    # ── Relaciones (back_populates en ambas puntas) ──────────────────────────
    estado:     Optional["EstadoPedido"]      = Relationship(back_populates="pedidos")
    forma_pago: Optional["FormaPago"]         = Relationship(back_populates="pedidos")
    direccion:  Optional["DireccionEntrega"]  = Relationship(back_populates="pedidos")
    detalles:   List["DetallePedido"]         = Relationship(
        back_populates="pedido",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    historial:  List["HistorialEstadoPedido"] = Relationship(
        back_populates="pedido",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "HistorialEstadoPedido.created_at"},
    )


# ──────────────────────────────────────────────────────────────────────────────
# DetallePedido — items inmutables con snapshot pattern (RN-04)
# ──────────────────────────────────────────────────────────────────────────────

class DetallePedido(SQLModel, table=True):
    """
    Fila INMUTABLE por diseño: sin updated_at, sin método update() en el repo.
    El snapshot de nombre y precio garantiza integridad histórica del pedido
    aunque después el producto cambie de precio o se elimine (soft delete).
    """
    __tablename__ = "detalle_pedido"

    # PK compuesta
    pedido_id:   Optional[int] = Field(default=None, foreign_key="pedido.id",   primary_key=True)
    producto_id: Optional[int] = Field(default=None, foreign_key="producto.id", primary_key=True)

    cantidad: int = Field(ge=1, description="Unidades del producto en este item")

    # ── Snapshot inmutable desde la creación ─────────────────────────────────
    nombre_snapshot:  str     = Field(max_length=200, description="Nombre del producto al momento de la compra")
    precio_snapshot:  Decimal = Field(sa_column=Column(sa.Numeric(10, 2), nullable=False))
    subtotal_snap:    Decimal = Field(sa_column=Column(sa.Numeric(10, 2), nullable=False))

    # IDs de Ingrediente removidos por el cliente (solo válido para
    # ProductoIngrediente.es_removible = true). Ej: [3, 7] = sin tomate, sin queso.
    personalizacion: Optional[List[int]] = Field(
        default=None,
        sa_column=Column(PG_ARRAY(sa.Integer), nullable=True),
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    # NO updated_at — fila inmutable por diseño

    pedido: Optional["Pedido"] = Relationship(back_populates="detalles")


# ──────────────────────────────────────────────────────────────────────────────
# HistorialEstadoPedido — audit trail APPEND-ONLY (RN-03)
# ──────────────────────────────────────────────────────────────────────────────

class HistorialEstadoPedido(SQLModel, table=True):
    """
    Ledger de auditoría: solo se le hace INSERT, jamás UPDATE ni DELETE.
    El estado actual del pedido se reconstruye con
        ORDER BY created_at ASC LIMIT 1 DESC
    pero por performance también se cachea en Pedido.estado_codigo.

    Invariantes:
    - RN-02: el primer registro de cada pedido tiene estado_desde = NULL
    - RN-03: append-only (no hay métodos update/delete en el repository)
    - RN-05: motivo obligatorio si estado_hacia = CANCELADO (enforced en service)
    """
    __tablename__ = "historial_estado_pedido"

    id: Optional[int] = Field(default=None, primary_key=True)

    pedido_id:     int           = Field(foreign_key="pedido.id", index=True)
    estado_desde:  Optional[str] = Field(default=None, foreign_key="estado_pedido.codigo")
    estado_hacia:  str           = Field(foreign_key="estado_pedido.codigo")

    # Quién hizo la transición. NULL ⇒ actor del sistema (webhook, job automático).
    usuario_id: Optional[int] = Field(default=None, foreign_key="usuario.id")

    motivo: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    # NO updated_at, NO deleted_at — append-only

    pedido: Optional["Pedido"] = Relationship(back_populates="historial")