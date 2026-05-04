from typing import Annotated, Optional, List
from fastapi import APIRouter, Query, Path, status

from app.schemas.producto import (
    ProductoCreate,
    ProductoUpdate,
    ProductoListItem,
    ProductoResponse,
)
from app.services import producto_service

router = APIRouter(prefix="/productos", tags=["Productos"])


@router.get("/", response_model=List[ProductoListItem], summary="Listar productos")
def listar_productos(
    nombre: Annotated[
        Optional[str],
        Query(description="Filtrar por nombre (búsqueda parcial)", max_length=100),
    ] = None,
    precio_min: Annotated[Optional[float], Query(ge=0, description="Precio mínimo")] = None,
    precio_max: Annotated[Optional[float], Query(ge=0, description="Precio máximo")] = None,
    categoria_id: Annotated[
        Optional[int], Query(ge=1, description="Filtrar por ID de categoría")
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Registros a omitir")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Máximo de registros")] = 10,
):
    return producto_service.get_all(
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
    return producto_service.get_by_id(producto_id)


@router.post(
    "/",
    response_model=ProductoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo producto con categorías e ingredientes",
)
def crear_producto(data: ProductoCreate):
    return producto_service.create(data)


@router.put(
    "/{producto_id}",
    response_model=ProductoResponse,
    summary="Actualizar campos básicos del producto",
)
def actualizar_producto(
    producto_id: Annotated[int, Path(ge=1, description="ID del producto")],
    data: ProductoUpdate,
):
    return producto_service.update(producto_id, data)


@router.delete(
    "/{producto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar producto",
)
def eliminar_producto(
    producto_id: Annotated[int, Path(ge=1, description="ID del producto")],
):
    producto_service.delete(producto_id)
