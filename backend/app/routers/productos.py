from typing import Annotated, Optional, List
from fastapi import APIRouter, Query, Path, status

from app.schemas.producto import (
    ProductoCreate,
    ProductoUpdate,
    ProductoListItem,
    ProductoResponse,
)
from app.services import producto_service
from app.uow.unit_of_work import UnitOfWork

router = APIRouter(prefix="/productos", tags=["Productos"])


@router.get("/", response_model=List[ProductoListItem], summary="Listar productos")
def listar_productos(
    nombre: Annotated[
        Optional[str],
        Query(description="Filtrar por nombre (búsqueda parcial)", max_length=100),
    ] = None,
    precio_min: Annotated[
        Optional[float], Query(ge=0, description="Precio mínimo")
    ] = None,
    precio_max: Annotated[
        Optional[float], Query(ge=0, description="Precio máximo")
    ] = None,
    categoria_id: Annotated[
        Optional[int], Query(ge=1, description="Filtrar por ID de categoría")
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Registros a omitir (paginación)")] = 0,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Máximo de registros a retornar")
    ] = 10,
):
    with UnitOfWork() as uow:
        return producto_service.get_all(
            uow.session,
            nombre=nombre,
            precio_min=precio_min,
            precio_max=precio_max,
            categoria_id=categoria_id,
            offset=offset,
            limit=limit,
        )


@router.get(
    "/{producto_id}",
    response_model=ProductoResponse,
    summary="Obtener producto por ID (con categorías e ingredientes)",
)
def obtener_producto(
    producto_id: Annotated[int, Path(ge=1, description="ID del producto")],
):
    with UnitOfWork() as uow:
        return producto_service.get_by_id(uow.session, producto_id)


@router.post(
    "/",
    response_model=ProductoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo producto con categorías e ingredientes",
)
def crear_producto(data: ProductoCreate):
    with UnitOfWork() as uow:
        return producto_service.create(uow.session, data)


@router.put(
    "/{producto_id}",
    response_model=ProductoResponse,
    summary="Actualizar campos básicos del producto",
)
def actualizar_producto(
    producto_id: Annotated[int, Path(ge=1, description="ID del producto")],
    data: ProductoUpdate,
):
    with UnitOfWork() as uow:
        return producto_service.update(uow.session, producto_id, data)


@router.delete(
    "/{producto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar producto",
)
def eliminar_producto(
    producto_id: Annotated[int, Path(ge=1, description="ID del producto")],
):
    with UnitOfWork() as uow:
        producto_service.delete(uow.session, producto_id)
