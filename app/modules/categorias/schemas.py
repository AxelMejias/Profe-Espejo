from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class CategoriaCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    parent_id: Optional[int] = Field(default=None, gt=0)
    imagen_url: Optional[str] = Field(default=None)


class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    parent_id: Optional[int] = Field(default=None, gt=0)
    imagen_url: Optional[str] = Field(default=None)


class CategoriaRead(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    parent_id: Optional[int] = None
    imagen_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedCategorias(BaseModel):
    items: List[CategoriaRead]
    total: int
    page: int
    size: int
    pages: int

class CategoriaTree(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    parent_id: Optional[int] = None
    children: List["CategoriaTree"] = Field(default_factory=list)

    model_config = {"from_attributes": True}

# Necesario para que Pydantic resuelva la auto-referencia
CategoriaTree.model_rebuild()