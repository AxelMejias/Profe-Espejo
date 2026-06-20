import math
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, status

from app.modules.auth.model import UsuarioRol
from app.modules.admin.schemas import (
    UsuarioAdminResponse, PaginatedUsuarios,
    UsuarioAdminUpdate, RolResponse,
)


def _problem(code: str, detail: str, http_status: int):
    raise HTTPException(
        status_code=http_status,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def _build_response(uow, usuario) -> UsuarioAdminResponse:
    roles = uow.usuarios_admin.get_roles(usuario.id)
    return UsuarioAdminResponse(
        id=usuario.id,
        nombre=usuario.nombre,
        apellido=usuario.apellido,
        email=usuario.email,
        celular=usuario.celular,
        roles=[RolResponse(codigo=r.codigo, nombre=r.nombre) for r in roles],
        created_at=usuario.created_at,
        updated_at=usuario.updated_at,
        deleted_at=usuario.deleted_at,
    )


def get_all(
    uow,
    rol_codigo: Optional[str] = None,
    solo_inactivos: bool = False,
    page: int = 1,
    size: int = 20,
) -> PaginatedUsuarios:
    items, total = uow.usuarios_admin.get_all(
        rol_codigo=rol_codigo, solo_inactivos=solo_inactivos, page=page, size=size,
    )
    return PaginatedUsuarios(
        items=[_build_response(uow, u) for u in items],
        total=total, page=page, size=size,
        pages=math.ceil(total / size) if total else 0,
    )


def get_by_id(uow, usuario_id: int) -> UsuarioAdminResponse:
    usuario = uow.usuarios_admin.get_by_id(usuario_id)
    if not usuario:
        _problem("USER_NOT_FOUND", f"Usuario {usuario_id} no encontrado", status.HTTP_404_NOT_FOUND)
    return _build_response(uow, usuario)


def update(uow, usuario_id: int, data: UsuarioAdminUpdate) -> UsuarioAdminResponse:
    usuario = uow.usuarios_admin.get_by_id(usuario_id)
    if not usuario:
        _problem("USER_NOT_FOUND", f"Usuario {usuario_id} no encontrado", status.HTTP_404_NOT_FOUND)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(usuario, key, value)
    usuario.updated_at = datetime.utcnow()
    uow.usuarios_admin.add(usuario)
    return _build_response(uow, usuario)


def delete(uow, usuario_id: int) -> None:
    usuario = uow.usuarios_admin.get_by_id(usuario_id)
    if not usuario:
        _problem("USER_NOT_FOUND", f"Usuario {usuario_id} no encontrado", status.HTTP_404_NOT_FOUND)

    # Guard: nunca dejar al sistema sin administrador (cubre "no borrarte si sos el único admin").
    if uow.usuarios_admin.has_rol(usuario_id, "ADMIN") and uow.usuarios_admin.count_active_admins() <= 1:
        _problem(
            "LAST_ADMIN",
            "No podés eliminar al último administrador del sistema",
            status.HTTP_403_FORBIDDEN,
        )

    uow.usuarios_admin.soft_delete(usuario)
    # Revocar los refresh tokens activos: la baja debe cortar la sesión de inmediato,
    # sin que el usuario pueda renovar su access token desde el store.
    uow.refresh_tokens.revoke_all_for_user(usuario_id)


def reactivar(uow, usuario_id: int) -> UsuarioAdminResponse:
    usuario = uow.usuarios_admin.get_by_id_inactivo(usuario_id)
    if not usuario:
        _problem(
            "USER_NOT_FOUND",
            f"Usuario {usuario_id} no encontrado o ya está activo",
            status.HTTP_404_NOT_FOUND,
        )
    uow.usuarios_admin.reactivar(usuario)
    return _build_response(uow, usuario)


def asignar_rol(uow, usuario_id: int, rol_codigo: str, actor_id: int) -> UsuarioAdminResponse:
    usuario = uow.usuarios_admin.get_by_id(usuario_id)
    if not usuario:
        _problem("USER_NOT_FOUND", f"Usuario {usuario_id} no encontrado", status.HTTP_404_NOT_FOUND)

    # Verificar que el rol existe
    rol = uow.usuarios_admin.get_rol(rol_codigo)
    if not rol:
        _problem("ROL_NOT_FOUND", f"Rol '{rol_codigo}' no existe", status.HTTP_404_NOT_FOUND)

    if uow.usuarios_admin.has_rol(usuario_id, rol_codigo):
        _problem("ROL_ALREADY_ASSIGNED", f"El usuario ya tiene el rol '{rol_codigo}'", status.HTTP_409_CONFLICT)

    uow.usuarios_admin.add_rol(
        UsuarioRol(usuario_id=usuario_id, rol_codigo=rol_codigo, asignado_por_id=actor_id)
    )
    return _build_response(uow, usuario)


def remover_rol(uow, usuario_id: int, rol_codigo: str) -> UsuarioAdminResponse:
    usuario = uow.usuarios_admin.get_by_id(usuario_id)
    if not usuario:
        _problem("USER_NOT_FOUND", f"Usuario {usuario_id} no encontrado", status.HTTP_404_NOT_FOUND)

    # Guard: no quitar el rol ADMIN al último administrador del sistema.
    if (
        rol_codigo == "ADMIN"
        and uow.usuarios_admin.has_rol(usuario_id, "ADMIN")
        and uow.usuarios_admin.count_active_admins() <= 1
    ):
        _problem(
            "LAST_ADMIN",
            "No podés quitar el rol de administrador al último admin del sistema",
            status.HTTP_403_FORBIDDEN,
        )

    removed = uow.usuarios_admin.remove_rol(usuario_id, rol_codigo)
    if not removed:
        _problem("ROL_NOT_ASSIGNED", f"El usuario no tiene el rol '{rol_codigo}'", status.HTTP_404_NOT_FOUND)

    return _build_response(uow, usuario)