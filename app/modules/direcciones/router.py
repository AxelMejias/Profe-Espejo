from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, Path, status

from app.modules.direcciones.schemas import (
    DireccionCreate, DireccionUpdate, DireccionResponse, PaginatedDirecciones,
)
from app.modules.direcciones import service
from app.core.dependencies import get_current_user_id
from app.core.unit_of_work import UnitOfWork

router = APIRouter(prefix="/api/v1/direcciones", tags=["Direcciones"])


@router.get("/", response_model=PaginatedDirecciones, summary="Listar mis direcciones")
def listar_direcciones(
    alias: Annotated[Optional[str], Query(max_length=50)] = None,
    page:  Annotated[int, Query(ge=1)] = 1,
    size:  Annotated[int, Query(ge=1, le=100)] = 20,
    usuario_id: int = Depends(get_current_user_id),
):
    with UnitOfWork() as uow:
        return service.get_all(uow, usuario_id=usuario_id, alias=alias, page=page, size=size)


@router.get("/{direccion_id}", response_model=DireccionResponse, summary="Obtener dirección por ID")
def obtener_direccion(
    direccion_id: Annotated[int, Path(ge=1)],
    usuario_id: int = Depends(get_current_user_id),
):
    with UnitOfWork() as uow:
        return service.get_by_id(uow, direccion_id, usuario_id)


@router.post("/", response_model=DireccionResponse, status_code=status.HTTP_201_CREATED, summary="Crear dirección")
def crear_direccion(
    data: DireccionCreate,
    usuario_id: int = Depends(get_current_user_id),
):
    with UnitOfWork() as uow:
        return service.create(uow, data, usuario_id)


@router.put("/{direccion_id}", response_model=DireccionResponse, summary="Actualizar dirección")
def actualizar_direccion(
    direccion_id: Annotated[int, Path(ge=1)],
    data: DireccionUpdate,
    usuario_id: int = Depends(get_current_user_id),
):
    with UnitOfWork() as uow:
        return service.update(uow, direccion_id, data, usuario_id)


@router.patch("/{direccion_id}/principal", response_model=DireccionResponse,
              summary="Marcar dirección como principal (única por usuario)")
def marcar_principal(
    direccion_id: Annotated[int, Path(ge=1)],
    usuario_id: int = Depends(get_current_user_id),
):
    with UnitOfWork() as uow:
        return service.marcar_principal(uow, direccion_id, usuario_id)


@router.delete("/{direccion_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Baja lógica de dirección")
def eliminar_direccion(
    direccion_id: Annotated[int, Path(ge=1)],
    usuario_id: int = Depends(get_current_user_id),
):
    with UnitOfWork() as uow:
        service.delete(uow, direccion_id, usuario_id)