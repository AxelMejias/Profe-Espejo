from typing import Annotated, Optional, List
from fastapi import APIRouter, Query, Path, status

from app.schemas.ingrediente import IngredienteCreate, IngredienteUpdate, IngredienteResponse
from app.services import ingrediente_service
from app.uow.unit_of_work import UnitOfWork

router = APIRouter(prefix="/ingredientes", tags=["Ingredientes"])


@router.get("/", response_model=List[IngredienteResponse], summary="Listar ingredientes")
def listar_ingredientes(
    nombre: Annotated[
        Optional[str],
        Query(description="Filtrar por nombre (búsqueda parcial)", max_length=100),
    ] = None,
    unidad_medida: Annotated[
        Optional[str],
        Query(description="Filtrar por unidad de medida", max_length=50),
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Registros a omitir (paginación)")] = 0,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Máximo de registros a retornar")
    ] = 10,
):
    with UnitOfWork() as uow:
        return ingrediente_service.get_all(
            uow.session,
            nombre=nombre,
            unidad_medida=unidad_medida,
            offset=offset,
            limit=limit,
        )


@router.get(
    "/{ingrediente_id}",
    response_model=IngredienteResponse,
    summary="Obtener ingrediente por ID",
)
def obtener_ingrediente(
    ingrediente_id: Annotated[int, Path(ge=1, description="ID del ingrediente")],
):
    with UnitOfWork() as uow:
        return ingrediente_service.get_by_id(uow.session, ingrediente_id)


@router.post(
    "/",
    response_model=IngredienteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo ingrediente",
)
def crear_ingrediente(data: IngredienteCreate):
    with UnitOfWork() as uow:
        return ingrediente_service.create(uow.session, data)


@router.put(
    "/{ingrediente_id}",
    response_model=IngredienteResponse,
    summary="Actualizar ingrediente",
)
def actualizar_ingrediente(
    ingrediente_id: Annotated[int, Path(ge=1, description="ID del ingrediente")],
    data: IngredienteUpdate,
):
    with UnitOfWork() as uow:
        return ingrediente_service.update(uow.session, ingrediente_id, data)


@router.delete(
    "/{ingrediente_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar ingrediente",
)
def eliminar_ingrediente(
    ingrediente_id: Annotated[int, Path(ge=1, description="ID del ingrediente")],
):
    with UnitOfWork() as uow:
        ingrediente_service.delete(uow.session, ingrediente_id)
