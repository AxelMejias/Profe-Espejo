from typing import Annotated
from fastapi import APIRouter, Depends, Path, status

from app.modules.unidades.schemas import (
    UnidadMedidaCreate, UnidadMedidaUpdate, UnidadMedidaRead,
)
from app.modules.unidades import service
from app.core.dependencies import require_role
from app.core.unit_of_work import UnitOfWork

router = APIRouter(prefix="/api/v1/unidades", tags=["Unidades de Medida"])

_LEER  = Depends(require_role(["ADMIN", "STOCK", "PEDIDOS", "CLIENT"]))
_ADMIN = Depends(require_role(["ADMIN"]))


@router.get("/", response_model=list[UnidadMedidaRead], summary="Listar unidades de medida")
def listar_unidades(_=_LEER):
    with UnitOfWork() as uow:
        return service.get_all(uow)


@router.get("/{unidad_id}", response_model=UnidadMedidaRead, summary="Obtener unidad por ID")
def obtener_unidad(unidad_id: Annotated[int, Path(ge=1)], _=_LEER):
    with UnitOfWork() as uow:
        return service.get_by_id(uow, unidad_id)


@router.post("/", response_model=UnidadMedidaRead, status_code=status.HTTP_201_CREATED, summary="Crear unidad")
def crear_unidad(data: UnidadMedidaCreate, _=_ADMIN):
    with UnitOfWork() as uow:
        return service.create(uow, data)


@router.put("/{unidad_id}", response_model=UnidadMedidaRead, summary="Actualizar unidad")
def actualizar_unidad(unidad_id: Annotated[int, Path(ge=1)], data: UnidadMedidaUpdate, _=_ADMIN):
    with UnitOfWork() as uow:
        return service.update(uow, unidad_id, data)


@router.delete("/{unidad_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar unidad")
def eliminar_unidad(unidad_id: Annotated[int, Path(ge=1)], _=_ADMIN):
    with UnitOfWork() as uow:
        service.delete(uow, unidad_id)
