from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class DireccionCreate(BaseModel):
    alias: Optional[str] = Field(default=None, max_length=50)
    linea1: str = Field(min_length=1, max_length=255)
    linea2: Optional[str] = Field(default=None, max_length=255)
    ciudad: str = Field(min_length=1, max_length=100)
    provincia: Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    latitud: Optional[Decimal] = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitud: Optional[Decimal] = Field(default=None, ge=-180, le=180, decimal_places=6)
    es_principal: bool = False


class DireccionUpdate(BaseModel):
    alias: Optional[str] = Field(default=None, max_length=50)
    linea1: Optional[str] = Field(default=None, min_length=1, max_length=255)
    linea2: Optional[str] = Field(default=None, max_length=255)
    ciudad: Optional[str] = Field(default=None, min_length=1, max_length=100)
    provincia: Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    latitud: Optional[Decimal] = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitud: Optional[Decimal] = Field(default=None, ge=-180, le=180, decimal_places=6)


class DireccionResponse(BaseModel):
    id: int
    usuario_id: int
    alias: Optional[str] = None
    linea1: str
    linea2: Optional[str] = None
    ciudad: str
    provincia: Optional[str] = None
    codigo_postal: Optional[str] = None
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    es_principal: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedDirecciones(BaseModel):
    items: List[DireccionResponse]
    total: int
    page: int
    size: int
    pages: int