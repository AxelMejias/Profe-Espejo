from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship, Column
import sqlalchemy as sa

if TYPE_CHECKING:
    from app.modules.pedidos.model import Pedido


class DireccionEntrega(SQLModel, table=True):
    __tablename__ = "direccion_entrega"

    id: Optional[int] = Field(default=None, primary_key=True)

    # FK → Usuario (sin Relationship recíproca para no modificar el módulo auth)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)

    # Alias humano: "Casa", "Trabajo", "Casa de mamá", etc.
    alias: Optional[str] = Field(default=None, max_length=50)

    linea1: str = Field(min_length=1, max_length=255)
    linea2: Optional[str] = Field(default=None, max_length=255)
    ciudad: str = Field(min_length=1, max_length=100)
    provincia: Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)

    # DECIMAL(9,6) — coordenadas GPS. Opcional; la UI puede no enviarlas.
    latitud: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(sa.Numeric(9, 6), nullable=True),
    )
    longitud: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(sa.Numeric(9, 6), nullable=True),
    )

    es_principal: bool = Field(default=False, description="Solo una principal por usuario (enforced en Service)")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)   # soft delete

    # 1:N → Pedido (un pedido referencia una dirección de envío)
    pedidos: List["Pedido"] = Relationship(back_populates="direccion")