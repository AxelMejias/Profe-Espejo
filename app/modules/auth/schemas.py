from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

from app.core.config import settings


class RegisterRequest(BaseModel):
    nombre: str
    apellido: str
    email: EmailStr
    password: str
    celular: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class GoogleAuthRequest(BaseModel):
    credential: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # Vida del access token en segundos (doc §6.1). Default derivado de settings,
    # así login/refresh/google lo heredan sin tener que pasarlo explícito.
    expires_in: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


class RolResponse(BaseModel):
    codigo: str
    nombre: str


class UserResponse(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: str
    celular: Optional[str]
    roles: List[RolResponse]
    created_at: datetime
