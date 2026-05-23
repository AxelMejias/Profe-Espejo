"""
Service de Direcciones de Entrega.
Regla: NO crea su propio UoW. Recibe `uow` del router.
Toda dirección está siempre asociada al usuario autenticado;
no hay endpoints cross-user (excepto operaciones admin futuras).
"""
import math
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, status

from app.modules.direcciones.model import DireccionEntrega
from app.modules.direcciones.schemas import (
    DireccionCreate, DireccionUpdate, DireccionResponse, PaginatedDirecciones,
)


def _problem(code: str, detail: str, http_status: int):
    raise HTTPException(
        status_code=http_status,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def get_all(
    uow,
    usuario_id: int,
    alias: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> PaginatedDirecciones:
    items, total = uow.direcciones.get_all_by_user(
        usuario_id=usuario_id, alias=alias, page=page, size=size,
    )
    return PaginatedDirecciones(
        items=[DireccionResponse.model_validate(d) for d in items],
        total=total, page=page, size=size,
        pages=math.ceil(total / size) if total else 0,
    )


def get_by_id(uow, direccion_id: int, usuario_id: int) -> DireccionResponse:
    direccion = uow.direcciones.get_by_id_for_user(direccion_id, usuario_id)
    if not direccion:
        _problem("DIRECCION_NOT_FOUND", f"Dirección {direccion_id} no encontrada", status.HTTP_404_NOT_FOUND)
    return DireccionResponse.model_validate(direccion)


def create(uow, data: DireccionCreate, usuario_id: int) -> DireccionResponse:
    # Si el cliente marca esta como principal, primero desmarcamos las otras
    # — todo dentro del mismo UoW, una sola transacción atómica.
    if data.es_principal:
        uow.direcciones.unset_all_principal_for_user(usuario_id)

    direccion = DireccionEntrega(
        **data.model_dump(),
        usuario_id=usuario_id,
    )
    uow.direcciones.add(direccion)
    return DireccionResponse.model_validate(direccion)


def update(uow, direccion_id: int, data: DireccionUpdate, usuario_id: int) -> DireccionResponse:
    direccion = uow.direcciones.get_by_id_for_user(direccion_id, usuario_id)
    if not direccion:
        _problem("DIRECCION_NOT_FOUND", f"Dirección {direccion_id} no encontrada", status.HTTP_404_NOT_FOUND)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(direccion, key, value)
    direccion.updated_at = datetime.utcnow()
    uow.direcciones.add(direccion)
    return DireccionResponse.model_validate(direccion)


def marcar_principal(uow, direccion_id: int, usuario_id: int) -> DireccionResponse:
    """
    Marca una dirección como principal. Garantiza la invariante:
    exactamente una dirección principal por usuario (o cero).
    """
    direccion = uow.direcciones.get_by_id_for_user(direccion_id, usuario_id)
    if not direccion:
        _problem("DIRECCION_NOT_FOUND", f"Dirección {direccion_id} no encontrada", status.HTTP_404_NOT_FOUND)

    # 1. Desmarcar todas las que estén marcadas
    uow.direcciones.unset_all_principal_for_user(usuario_id)

    # 2. Marcar la solicitada
    direccion.es_principal = True
    direccion.updated_at = datetime.utcnow()
    uow.direcciones.add(direccion)
    return DireccionResponse.model_validate(direccion)


def delete(uow, direccion_id: int, usuario_id: int) -> None:
    direccion = uow.direcciones.get_by_id_for_user(direccion_id, usuario_id)
    if not direccion:
        _problem("DIRECCION_NOT_FOUND", f"Dirección {direccion_id} no encontrada", status.HTTP_404_NOT_FOUND)
    uow.direcciones.soft_delete(direccion)