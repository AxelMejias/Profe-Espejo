from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from app.core.security import decode_access_token

security = HTTPBearer()


def _problem(code: str, detail: str, status_code: int):
    raise HTTPException(
        status_code=status_code,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    try:
        return decode_access_token(credentials.credentials)
    except JWTError:
        _problem("INVALID_TOKEN", "Token inválido o expirado", status.HTTP_401_UNAUTHORIZED)


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
