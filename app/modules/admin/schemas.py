from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class RolResponse(BaseModel):
    codigo: str
    nombre: str

    model_config = {"from_attributes": True}


class UsuarioAdminResponse(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: str
    celular: Optional[str] = None
    roles: List[RolResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedUsuarios(BaseModel):
    items: List[UsuarioAdminResponse]
    total: int
    page: int
    size: int
    pages: int


class UsuarioAdminUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=80)
    apellido: Optional[str] = Field(default=None, min_length=1, max_length=80)
    email: Optional[EmailStr] = None
    celular: Optional[str] = Field(default=None, max_length=20)


class AsignarRolRequest(BaseModel):
    rol_codigo: str = Field(min_length=1, max_length=20)