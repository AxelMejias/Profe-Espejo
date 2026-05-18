from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class CategoriaCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    parent_id: Optional[int] = Field(default=None, gt=0)


class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    parent_id: Optional[int] = Field(default=None, gt=0)


class CategoriaRead(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    parent_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedCategorias(BaseModel):
    items: List[CategoriaRead]
    total: int
    page: int
    size: int
    pages: int
