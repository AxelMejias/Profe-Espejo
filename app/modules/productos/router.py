from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, Path, Body, status

from app.modules.productos.schemas import (
    ProductoCreate, ProductoUpdate, ProductoListItem, ProductoResponse,
)
from app.modules.productos import service
from app.core.dependencies import require_role
from app.core.unit_of_work import UnitOfWork

# ✅ Prefix correcto: /api/v1/productos
router = APIRouter(prefix="/api/v1/productos", tags=["Productos"])

_PUBLICO = Depends(require_role(["ADMIN", "STOCK", "PEDIDOS", "CLIENT"]))
_ADMIN   = Depends(require_role(["ADMIN", "STOCK"]))


@router.get("/", summary="Listar productos")
def listar_productos(
    nombre:       Annotated[Optional[str],   Query(max_length=100)] = None,
    precio_min:   Annotated[Optional[float], Query(ge=0)]           = None,
    precio_max:   Annotated[Optional[float], Query(ge=0)]           = None,
    categoria_id: Annotated[Optional[int],   Query(ge=1)]           = None,
    solo_disponibles: Annotated[bool, Query()]                      = True,
    page:         Annotated[int, Query(ge=1)]                       = 1,
    size:         Annotated[int, Query(ge=1, le=100)]               = 20,
    _=_PUBLICO,
):
    with UnitOfWork() as uow:
        return service.get_all(
            uow, nombre=nombre, precio_min=precio_min, precio_max=precio_max,
            categoria_id=categoria_id, solo_disponibles=solo_disponibles,
            page=page, size=size,
        )


@router.get("/{producto_id}", response_model=ProductoResponse, summary="Obtener producto por ID")
def obtener_producto(producto_id: Annotated[int, Path(ge=1)], _=_PUBLICO):
    with UnitOfWork() as uow:
        return service.get_by_id(uow, producto_id)


@router.post("/", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED, summary="Crear producto")
def crear_producto(data: ProductoCreate, _=_ADMIN):
    with UnitOfWork() as uow:
        return service.create(uow, data)


@router.put("/{producto_id}", response_model=ProductoResponse, summary="Actualizar producto")
def actualizar_producto(
    producto_id: Annotated[int, Path(ge=1)],
    data: ProductoUpdate,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.update(uow, producto_id, data)


@router.patch("/{producto_id}/disponibilidad", response_model=ProductoResponse, summary="Toggle disponibilidad")
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
