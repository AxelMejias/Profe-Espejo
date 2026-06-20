from datetime import datetime
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from app.core.security import decode_access_token

security = HTTPBearer(auto_error=False)


def _problem(code: str, detail: str, status_code: int):
    raise HTTPException(
        status_code=status_code,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def get_current_user_payload(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    Estrategia dual:
    1. Busca el JWT en la cookie HTTPOnly 'access_token' (módulo Admin).
    2. Si no hay cookie, busca el header Authorization: Bearer (módulo Store).
    Lanza 401 si no encuentra ninguno o el token es inválido.
    """
    token: Optional[str] = None

    # 1️⃣ Cookie HTTPOnly (prioridad — más seguro)
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        token = cookie_token
    # 2️⃣ Fallback: Authorization header
    elif credentials and credentials.credentials:
        token = credentials.credentials

    if not token:
        _problem("NOT_AUTHENTICATED", "No autenticado", status.HTTP_401_UNAUTHORIZED)

    try:
        payload = decode_access_token(token)
    except JWTError:
        _problem("INVALID_TOKEN", "Token inválido o expirado", status.HTTP_401_UNAUTHORIZED)

    # El token es válido, pero la cuenta/roles pudieron cambiar después de emitirlo.
    # Se valida contra la BD para que tanto la BAJA como los CAMBIOS DE ROL tengan
    # efecto INMEDIATO, aunque el JWT siga vigente con datos viejos.
    sub = payload.get("sub")
    if sub is not None:
        from app.core.unit_of_work import UnitOfWork
        with UnitOfWork() as uow:
            if uow.usuarios.get_by_id(int(sub)) is None:
                _problem(
                    "USER_INACTIVE",
                    "Tu cuenta fue dada de baja",
                    status.HTTP_401_UNAUTHORIZED,
                )
            # Roles frescos desde la BD: pisan el claim del token (que puede estar
            # desactualizado si un admin agregó/quitó un rol).
            roles = uow.usuarios.get_roles(int(sub))
            payload["roles"] = [r.codigo for r in roles]

    return payload


def get_current_user_id(payload: dict = Depends(get_current_user_payload)) -> int:
    user_id = payload.get("sub")
    if user_id is None:
        _problem("INVALID_TOKEN", "Token sin subject", status.HTTP_401_UNAUTHORIZED)
    return int(user_id)


def require_role(roles: list[str]):
    """
    Dependencia factory para RBAC.
    Uso: Depends(require_role(["ADMIN", "STOCK"]))
    """
    def dependency(payload: dict = Depends(get_current_user_payload)) -> dict:
        user_roles = payload.get("roles", [])
        if not any(r in user_roles for r in roles):
            _problem(
                "FORBIDDEN",
                f"Se requiere uno de los roles: {', '.join(roles)}",
                status.HTTP_403_FORBIDDEN,
            )
        return payload
    return dependency