from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class UnidadMedidaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=50)
    simbolo: str = Field(min_length=1, max_length=10)
    tipo: str = Field(min_length=1, max_length=20)


class UnidadMedidaUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=50)
    simbolo: Optional[str] = Field(default=None, min_length=1, max_length=10)
    tipo: Optional[str] = Field(default=None, min_length=1, max_length=20)


class UnidadMedidaRead(BaseModel):
    id: int
    nombre: str
    simbolo: str
    tipo: str
    created_at: datetime

    model_config = {"from_attributes": True}
