"""
Módulo unidades — entidad UnidadMedida (catálogo, ERD v7).

Catálogo de unidades de venta/medida (kg, g, L, ml, ud, porciones).
Referenciado por Producto.unidad_venta_id. El símbolo se muestra en la UI
(ej: "$ 12.50 / kg"); el tipo permite agrupar/filtrar en administración.
"""
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class UnidadMedida(SQLModel, table=True):
    __tablename__ = "unidad_medida"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(max_length=50, unique=True, index=True)
    simbolo: str = Field(max_length=10, unique=True)
    tipo: str = Field(max_length=20, description="peso | volumen | contable …")
    created_at: datetime = Field(default_factory=datetime.utcnow)
