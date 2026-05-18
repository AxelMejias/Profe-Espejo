from fastapi import APIRouter, Depends, Request, status
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

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest):
    with UnitOfWork() as uow:
        return auth_service.register(uow, data)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")
def login(request: Request, data: LoginRequest):
    with UnitOfWork() as uow:
        return auth_service.login(uow, data)


@router.post("/google", response_model=TokenResponse)
def google_login(data: GoogleAuthRequest):
    with UnitOfWork() as uow:
        return auth_service.google_login(uow, data.credential)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest):
    with UnitOfWork() as uow:
        return auth_service.refresh(uow, data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: LogoutRequest):
    with UnitOfWork() as uow:
        auth_service.logout(uow, data.refresh_token)


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
