from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


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
