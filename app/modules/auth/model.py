from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class Rol(SQLModel, table=True):
    codigo: str = Field(primary_key=True, max_length=20)
    nombre: str = Field(max_length=50, unique=True)
    descripcion: Optional[str] = Field(default=None)


class Usuario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(max_length=80)
    apellido: str = Field(max_length=80)
    email: str = Field(max_length=254, unique=True, index=True)
    password_hash: str = Field(max_length=60)
    celular: Optional[str] = Field(default=None, max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)


class UsuarioRol(SQLModel, table=True):
    __tablename__ = "usuario_rol"
    usuario_id: Optional[int] = Field(foreign_key="usuario.id", primary_key=True)
    rol_codigo: str = Field(foreign_key="rol.codigo", primary_key=True)
    asignado_por_id: Optional[int] = Field(default=None, foreign_key="usuario.id")
    expires_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_token"
    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id")
    token_hash: str = Field(max_length=64, unique=True)
    expires_at: datetime
    revoked_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_token"
    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id")
    token_hash: str = Field(max_length=64, unique=True)
    expires_at: datetime
    used_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
