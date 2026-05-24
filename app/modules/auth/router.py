from fastapi import APIRouter, Depends, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.modules.auth.schemas import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse,
    RefreshRequest, LogoutRequest, GoogleAuthRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
)
from app.modules.auth.service import auth_service
from app.core.dependencies import get_current_user_id
from app.core.unit_of_work import UnitOfWork
from app.core.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
limiter = Limiter(key_func=get_remote_address)

# Nombre de la cookie
_COOKIE_NAME = "access_token"


def _set_auth_cookie(response: Response, access_token: str) -> None:
    """Setea el access token como cookie HTTPOnly."""
    response.set_cookie(
        key=_COOKIE_NAME,
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    """Elimina la cookie en el cliente."""
    response.delete_cookie(
        key=_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest):
    with UnitOfWork() as uow:
        return auth_service.register(uow, data)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")
def login(request: Request, response: Response, data: LoginRequest):
    with UnitOfWork() as uow:
        token_response = auth_service.login(uow, data)

    _set_auth_cookie(response, token_response.access_token)

    return token_response


@router.post("/google", response_model=TokenResponse)
def google_login(response: Response, data: GoogleAuthRequest):
    with UnitOfWork() as uow:
        token_response = auth_service.google_login(uow, data.credential)

    _set_auth_cookie(response, token_response.access_token)
    return token_response


@router.post("/refresh", response_model=TokenResponse)
def refresh(response: Response, data: RefreshRequest):
    with UnitOfWork() as uow:
        token_response = auth_service.refresh(uow, data.refresh_token)

    # Actualizar cookie con el nuevo access token
    _set_auth_cookie(response, token_response.access_token)
    return token_response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, data: LogoutRequest):
    with UnitOfWork() as uow:
        auth_service.logout(uow, data.refresh_token)

    # Limpiar cookie del cliente
    _clear_auth_cookie(response)


@router.get("/me", response_model=UserResponse)
def get_me(usuario_id: int = Depends(get_current_user_id)):
    with UnitOfWork() as uow:
        return auth_service.get_me(uow, usuario_id)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(data: ForgotPasswordRequest):
    with UnitOfWork() as uow:
        auth_service.forgot_password(uow, data.email)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(data: ResetPasswordRequest):
    with UnitOfWork() as uow:
        auth_service.reset_password(uow, data.token, data.new_password)