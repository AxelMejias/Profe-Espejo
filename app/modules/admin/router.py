from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, Path, status

from app.modules.admin.schemas import (
    UsuarioAdminResponse, PaginatedUsuarios,
    UsuarioAdminUpdate, AsignarRolRequest,
)
from app.modules.admin import service
from app.core.dependencies import require_role, get_current_user_id
from app.core.unit_of_work import UnitOfWork

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

_ADMIN = Depends(require_role(["ADMIN"]))


@router.get(
    "/usuarios",
    response_model=PaginatedUsuarios,
    summary="Listar usuarios (paginado, filtro por rol)",
)
def listar_usuarios(
    rol_codigo: Annotated[Optional[str], Query(max_length=20)] = None,
    solo_inactivos: Annotated[bool, Query()] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.get_all(
            uow, rol_codigo=rol_codigo, solo_inactivos=solo_inactivos, page=page, size=size,
        )


@router.get(
    "/usuarios/{usuario_id}",
    response_model=UsuarioAdminResponse,
    summary="Obtener usuario por ID",
)
def obtener_usuario(
    usuario_id: Annotated[int, Path(ge=1)],
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.get_by_id(uow, usuario_id)


@router.put(
    "/usuarios/{usuario_id}",
    response_model=UsuarioAdminResponse,
    summary="Actualizar datos de un usuario",
)
def actualizar_usuario(
    usuario_id: Annotated[int, Path(ge=1)],
    data: UsuarioAdminUpdate,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.update(uow, usuario_id, data)


@router.delete(
    "/usuarios/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Baja lógica de un usuario",
)
def eliminar_usuario(
    usuario_id: Annotated[int, Path(ge=1)],
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        service.delete(uow, usuario_id)


@router.patch(
    "/usuarios/{usuario_id}/reactivar",
    response_model=UsuarioAdminResponse,
    summary="Reactivar un usuario dado de baja",
)
def reactivar_usuario(
    usuario_id: Annotated[int, Path(ge=1)],
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.reactivar(uow, usuario_id)


@router.post(
    "/usuarios/{usuario_id}/roles",
    response_model=UsuarioAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Asignar rol a un usuario",
)
def asignar_rol(
    usuario_id: Annotated[int, Path(ge=1)],
    data: AsignarRolRequest,
    actor_id: int = Depends(get_current_user_id),
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.asignar_rol(uow, usuario_id, data.rol_codigo, actor_id)


@router.delete(
    "/usuarios/{usuario_id}/roles/{rol_codigo}",
    response_model=UsuarioAdminResponse,
    summary="Remover rol de un usuario",
)
def remover_rol(
    usuario_id: Annotated[int, Path(ge=1)],
    rol_codigo: str,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.remover_rol(uow, usuario_id, rol_codigo)