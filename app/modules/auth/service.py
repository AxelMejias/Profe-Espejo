import hashlib
import secrets
import httpx
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from app.modules.auth.model import Usuario, RefreshToken, UsuarioRol, PasswordResetToken
from app.modules.auth.schemas import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse, RolResponse,
)
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.config import settings


def _problem(code: str, detail: str, http_status: int):
    raise HTTPException(
        status_code=http_status,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def _build_user_response(usuario: Usuario, roles) -> UserResponse:
    return UserResponse(
        id=usuario.id,
        nombre=usuario.nombre,
        apellido=usuario.apellido,
        email=usuario.email,
        celular=usuario.celular,
        roles=[RolResponse(codigo=r.codigo, nombre=r.nombre) for r in roles],
        created_at=usuario.created_at,
    )


class AuthService:
    def register(self, uow, data: RegisterRequest) -> UserResponse:
        if uow.usuarios.get_by_email(data.email):
            _problem("EMAIL_CONFLICT", "El email ya está registrado", status.HTTP_409_CONFLICT)

        usuario = Usuario(
            nombre=data.nombre,
            apellido=data.apellido,
            email=data.email,
            password_hash=hash_password(data.password),
            celular=data.celular,
        )
        usuario = uow.usuarios.add(usuario)
        uow.usuarios.add_rol(UsuarioRol(usuario_id=usuario.id, rol_codigo="CLIENT"))

        roles = uow.usuarios.get_roles(usuario.id)
        return _build_user_response(usuario, roles)

    def login(self, uow, data: LoginRequest) -> TokenResponse:
        usuario = uow.usuarios.get_by_email(data.email)

        # RN-AU08: no diferenciar "email no existe" vs "password incorrecta"
        if not usuario or not verify_password(data.password, usuario.password_hash):
            _problem("INVALID_CREDENTIALS", "Credenciales inválidas", status.HTTP_401_UNAUTHORIZED)

        roles = uow.usuarios.get_roles(usuario.id)
        access_token = create_access_token({
            "sub": str(usuario.id),
            "email": usuario.email,
            "roles": [r.codigo for r in roles],
        })

        raw_refresh = create_refresh_token()
        uow.refresh_tokens.add(RefreshToken(
            usuario_id=usuario.id,
            token_hash=hashlib.sha256(raw_refresh.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ))

        return TokenResponse(access_token=access_token, refresh_token=raw_refresh)

    def refresh(self, uow, raw_token: str) -> TokenResponse:
        token_obj = uow.refresh_tokens.get_active_by_token(raw_token)

        if not token_obj:
            _problem("INVALID_REFRESH_TOKEN", "Refresh token inválido o ya utilizado", status.HTTP_401_UNAUTHORIZED)

        if token_obj.expires_at < datetime.utcnow():
            uow.refresh_tokens.revoke(token_obj)
            _problem("REFRESH_TOKEN_EXPIRED", "Refresh token expirado", status.HTTP_401_UNAUTHORIZED)

        # Rotación: revocar el anterior, emitir uno nuevo
        uow.refresh_tokens.revoke(token_obj)

        usuario = uow.usuarios.get_by_id(token_obj.usuario_id)
        roles = uow.usuarios.get_roles(usuario.id)
        access_token = create_access_token({
            "sub": str(usuario.id),
            "email": usuario.email,
            "roles": [r.codigo for r in roles],
        })

        new_raw = create_refresh_token()
        uow.refresh_tokens.add(RefreshToken(
            usuario_id=usuario.id,
            token_hash=hashlib.sha256(new_raw.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ))

        return TokenResponse(access_token=access_token, refresh_token=new_raw)

    def logout(self, uow, raw_token: str) -> None:
        token_obj = uow.refresh_tokens.get_active_by_token(raw_token)
        if token_obj:
            uow.refresh_tokens.revoke(token_obj)

    def google_login(self, uow, credential: str) -> TokenResponse:
        try:
            payload = google_id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError:
            _problem("INVALID_GOOGLE_TOKEN", "Token de Google inválido o expirado", status.HTTP_401_UNAUTHORIZED)

        email = payload.get("email")
        if not email:
            _problem("GOOGLE_NO_EMAIL", "No se pudo obtener el email de Google", status.HTTP_400_BAD_REQUEST)

        usuario = uow.usuarios.get_by_email(email)
        if not usuario:
            usuario = Usuario(
                nombre=payload.get("given_name", ""),
                apellido=payload.get("family_name", ""),
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
            )
            usuario = uow.usuarios.add(usuario)
            uow.usuarios.add_rol(UsuarioRol(usuario_id=usuario.id, rol_codigo="CLIENT"))

        roles = uow.usuarios.get_roles(usuario.id)
        access_token = create_access_token({
            "sub": str(usuario.id),
            "email": usuario.email,
            "roles": [r.codigo for r in roles],
        })

        raw_refresh = create_refresh_token()
        uow.refresh_tokens.add(RefreshToken(
            usuario_id=usuario.id,
            token_hash=hashlib.sha256(raw_refresh.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ))

        return TokenResponse(access_token=access_token, refresh_token=raw_refresh)

    def forgot_password(self, uow, email: str) -> None:
        usuario = uow.usuarios.get_by_email(email)
        if not usuario:
            return  # No revelar si el email existe o no

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        uow.reset_tokens.add(PasswordResetToken(
            usuario_id=usuario.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        ))

        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
        try:
            httpx.post(settings.N8N_WEBHOOK_URL, json={
                "email": usuario.email,
                "nombre": usuario.nombre,
                "reset_link": reset_link,
            }, timeout=5)
        except Exception:
            pass  # Si n8n falla, no rompemos el flujo

    def reset_password(self, uow, raw_token: str, new_password: str) -> None:
        token_obj = uow.reset_tokens.get_valid_by_token(raw_token)
        if not token_obj:
            _problem("INVALID_RESET_TOKEN", "Token inválido o expirado", status.HTTP_400_BAD_REQUEST)

        usuario = uow.usuarios.get_by_id(token_obj.usuario_id)
        if not usuario:
            _problem("USER_NOT_FOUND", "Usuario no encontrado", status.HTTP_404_NOT_FOUND)

        usuario.password_hash = hash_password(new_password)
        usuario.updated_at = datetime.utcnow()
        uow.session.add(usuario)
        uow.reset_tokens.mark_used(token_obj)

    def get_me(self, uow, usuario_id: int) -> UserResponse:
        usuario = uow.usuarios.get_by_id(usuario_id)
        if not usuario:
            _problem("USER_NOT_FOUND", "Usuario no encontrado", status.HTTP_404_NOT_FOUND)
        roles = uow.usuarios.get_roles(usuario.id)
        return _build_user_response(usuario, roles)


auth_service = AuthService()
