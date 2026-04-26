from typing import Annotated, Optional, List
from fastapi import APIRouter, Query, Path, status

from app.schemas.categoria import CategoriaCreate, CategoriaUpdate, CategoriaResponse
from app.services import categoria_service
from app.uow.unit_of_work import UnitOfWork

router = APIRouter(prefix="/categorias", tags=["Categorías"])


@router.get("/", response_model=List[CategoriaResponse], summary="Listar categorías")
def listar_categorias(
    nombre: Annotated[
        Optional[str],
        Query(description="Filtrar por nombre (búsqueda parcial)", max_length=100),
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Registros a omitir (paginación)")] = 0,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Máximo de registros a retornar")
    ] = 10,
):
    with UnitOfWork() as uow:
        return categoria_service.get_all(uow.session, nombre=nombre, offset=offset, limit=limit)


@router.get(
    "/{categoria_id}",
    response_model=CategoriaResponse,
    summary="Obtener categoría por ID",
)
def obtener_categoria(
    categoria_id: Annotated[int, Path(ge=1, description="ID de la categoría")],
):
    with UnitOfWork() as uow:
        return categoria_service.get_by_id(uow.session, categoria_id)


@router.post(
    "/",
    response_model=CategoriaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva categoría",
)
def crear_categoria(data: CategoriaCreate):
    with UnitOfWork() as uow:
        return categoria_service.create(uow.session, data)


@router.put(
    "/{categoria_id}",
    response_model=CategoriaResponse,
    summary="Actualizar categoría",
)
def actualizar_categoria(
    categoria_id: Annotated[int, Path(ge=1, description="ID de la categoría")],
    data: CategoriaUpdate,
):
    with UnitOfWork() as uow:
        return categoria_service.update(uow.session, categoria_id, data)


@router.delete(
    "/{categoria_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar categoría",
)
def eliminar_categoria(
    categoria_id: Annotated[int, Path(ge=1, description="ID de la categoría")],
):
    with UnitOfWork() as uow:
        categoria_service.delete(uow.session, categoria_id)
