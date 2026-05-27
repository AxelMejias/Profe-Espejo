from typing import Annotated, Optional
import math
from fastapi import APIRouter, Depends, Query, Path, Body, status

from app.modules.productos.schemas import (
    ProductoCreate, ProductoUpdate, ProductoRead, PaginatedProductos,
)
from app.modules.productos import service
from app.core.dependencies import require_role
from app.core.unit_of_work import UnitOfWork

router = APIRouter(prefix="/api/v1/productos", tags=["Productos"])

_PUBLICO = Depends(require_role(["ADMIN", "STOCK", "COCINERO", "CLIENT"]))
_ADMIN   = Depends(require_role(["ADMIN", "STOCK"]))


@router.get("/", response_model=PaginatedProductos, summary="Listar productos")
def listar_productos(
    nombre:           Annotated[Optional[str],   Query(max_length=100)] = None,
    precio_min:       Annotated[Optional[float], Query(ge=0)]           = None,
    precio_max:       Annotated[Optional[float], Query(ge=0)]           = None,
    categoria_id:     Annotated[Optional[int],   Query(ge=1)]           = None,
    solo_disponibles: Annotated[bool, Query()]                          = True,
    page:             Annotated[int, Query(ge=1)]                       = 1,
    size:             Annotated[int, Query(ge=1, le=100)]               = 20,
    _=_PUBLICO,
):
    with UnitOfWork() as uow:
        return service.get_all(
            uow, nombre=nombre, precio_min=precio_min, precio_max=precio_max,
            categoria_id=categoria_id, solo_disponibles=solo_disponibles,
            page=page, size=size,
        )


@router.get("/inactivos", response_model=PaginatedProductos, summary="Listar productos inactivos")
def listar_productos_inactivos(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        items, total = uow.productos.get_all_inactivos(page=page, size=size)
        return PaginatedProductos(
            items=[service._build_response(uow, p) for p in items],
            total=total, page=page, size=size,
            pages=math.ceil(total / size) if total else 0,
        )


@router.get("/{producto_id}", response_model=ProductoRead, summary="Obtener producto por ID")
def obtener_producto(producto_id: Annotated[int, Path(ge=1)], _=_PUBLICO):
    with UnitOfWork() as uow:
        return service.get_by_id(uow, producto_id)


@router.post("/", response_model=ProductoRead, status_code=status.HTTP_201_CREATED, summary="Crear producto")
def crear_producto(data: ProductoCreate, _=_ADMIN):
    with UnitOfWork() as uow:
        return service.create(uow, data)


@router.put("/{producto_id}", response_model=ProductoRead, summary="Actualizar producto")
def actualizar_producto(
    producto_id: Annotated[int, Path(ge=1)],
    data: ProductoUpdate,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.update(uow, producto_id, data)


@router.patch("/{producto_id}/reactivar", response_model=ProductoRead, summary="Reactivar producto inactivo")
def reactivar_producto(producto_id: Annotated[int, Path(ge=1)], _=_ADMIN):
    with UnitOfWork() as uow:
        return service.reactivar(uow, producto_id)


@router.patch("/{producto_id}/disponibilidad", response_model=ProductoRead, summary="Toggle disponibilidad")
def toggle_disponibilidad(
    producto_id: Annotated[int, Path(ge=1)],
    disponible: bool = Body(..., embed=True),
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.toggle_disponibilidad(uow, producto_id, disponible)


@router.delete("/{producto_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Baja lógica de producto")
def eliminar_producto(producto_id: Annotated[int, Path(ge=1)], _=_ADMIN):
    with UnitOfWork() as uow:
        service.delete(uow, producto_id)