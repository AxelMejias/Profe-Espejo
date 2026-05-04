from typing import List, Optional
from fastapi import HTTPException, status

from app.repositories.ingrediente_repository import IngredienteRepository
from app.schemas.ingrediente import IngredienteCreate, IngredienteUpdate, IngredienteResponse
from app.uow.unit_of_work import UnitOfWork


def get_all(
    nombre: Optional[str] = None,
    unidad_medida: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
) -> List[IngredienteResponse]:
    with UnitOfWork() as uow:
        repo = IngredienteRepository(uow.session)
        ingredientes = repo.get_all(
            nombre=nombre, unidad_medida=unidad_medida, offset=offset, limit=limit
        )
        return [IngredienteResponse.model_validate(i) for i in ingredientes]


def get_by_id(ingrediente_id: int) -> IngredienteResponse:
    with UnitOfWork() as uow:
        repo = IngredienteRepository(uow.session)
        ingrediente = repo.get_by_id(ingrediente_id)
        if not ingrediente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ingrediente con ID {ingrediente_id} no encontrado",
            )
        return IngredienteResponse.model_validate(ingrediente)


def create(data: IngredienteCreate) -> IngredienteResponse:
    with UnitOfWork() as uow:
        repo = IngredienteRepository(uow.session)
        if repo.get_by_nombre(data.nombre):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un ingrediente con el nombre '{data.nombre}'",
            )
        ingrediente = repo.create(data)
        return IngredienteResponse.model_validate(ingrediente)


def update(ingrediente_id: int, data: IngredienteUpdate) -> IngredienteResponse:
    with UnitOfWork() as uow:
        repo = IngredienteRepository(uow.session)
        ingrediente = repo.get_by_id(ingrediente_id)
        if not ingrediente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ingrediente con ID {ingrediente_id} no encontrado",
            )
        ingrediente = repo.update(ingrediente, data)
        return IngredienteResponse.model_validate(ingrediente)


def delete(ingrediente_id: int) -> None:
    with UnitOfWork() as uow:
        repo = IngredienteRepository(uow.session)
        ingrediente = repo.get_by_id(ingrediente_id)
        if not ingrediente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ingrediente con ID {ingrediente_id} no encontrado",
            )
        repo.delete(ingrediente)
