"""
Módulo pagos — entidad Pago.

Registro de cada intento de cobro contra MercadoPago Checkout API.
Implementa el patrón Idempotent Payment del ERD v7:
  - `idempotency_key` (UUID generado por el backend) se envía a MP en el header
    `X-Idempotency-Key` al crear la preferencia → evita cobros duplicados.
  - El webhook IPN (fuente de verdad del cobro) actualiza `mp_status` y los
    datos del pago server-to-server, independiente del redirect del browser.
"""
from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field, Column
import sqlalchemy as sa


class Pago(SQLModel, table=True):
    __tablename__ = "pago"

    id: Optional[int] = Field(default=None, primary_key=True)

    # FK → Pedido (un Pago pertenece a un único Pedido)
    pedido_id: int = Field(foreign_key="pedido.id", index=True)

    # ── Datos de MercadoPago (los completa/actualiza el webhook) ─────────────
    # BigInteger: los payment_id de MP superan el rango de INTEGER (32 bits).
    mp_payment_id:    Optional[int] = Field(
        default=None, sa_column=Column(sa.BigInteger(), unique=True, nullable=True)
    )
    mp_status:        str           = Field(default="pending", max_length=30)
    mp_status_detail: Optional[str] = Field(default=None, max_length=100)

    # external_reference = str(pedido.id) — usado para mapear el pago de vuelta
    external_reference: str = Field(max_length=100, unique=True)

    # UUID generado por el backend, enviado a MP como X-Idempotency-Key
    idempotency_key: str = Field(max_length=100, unique=True)

    transaction_amount: Decimal = Field(
        sa_column=Column(sa.Numeric(10, 2), nullable=False)
    )
    payment_method_id: Optional[str] = Field(default=None, max_length=50)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
