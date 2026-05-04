from typing import List, Optional
from fastapi import HTTPException, status

from app.repositories.categoria_repository import CategoriaRepository
from app.schemas.categoria import CategoriaCreate, CategoriaUpdate, CategoriaResponse
from app.uow.unit_of_work import UnitOfWork


def get_all(
    nombre: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
) -> List[CategoriaResponse]:
    with UnitOfWork() as uow:
        repo = CategoriaRepository(uow.session)
        categorias = repo.get_all(nombre=nombre, offset=offset, limit=limit)
        return [CategoriaResponse.model_validate(c) for c in categorias]


def get_by_id(categoria_id: int) -> CategoriaResponse:
    with UnitOfWork() as uow:
        repo = CategoriaRepository(uow.session)
        categoria = repo.get_by_id(categoria_id)
        if not categoria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Categoría con ID {categoria_id} no encontrada",
            )
        return CategoriaResponse.model_validate(categoria)


def create(data: CategoriaCreate) -> CategoriaResponse:
    with UnitOfWork() as uow:
        repo = CategoriaRepository(uow.session)
        if repo.get_by_nombre(data.nombre):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una categoría con el nombre '{data.nombre}'",
            )
        if data.parent_id and not repo.get_by_id(data.parent_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Categoría padre con ID {data.parent_id} no encontrada",
            )
        categoria = repo.create(data)
        return CategoriaResponse.model_validate(categoria)


def update(categoria_id: int, data: CategoriaUpdate) -> CategoriaResponse:
    with UnitOfWork() as uow:
        repo = CategoriaRepository(uow.session)
        categoria = repo.get_by_id(categoria_id)
        if not categoria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Categoría con ID {categoria_id} no encontrada",
            )
        if data.parent_id and not repo.get_by_id(data.parent_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Categoría padre con ID {data.parent_id} no encontrada",
            )
        categoria = repo.update(categoria, data)
        return CategoriaResponse.model_validate(categoria)


def delete(categoria_id: int) -> None:
    with UnitOfWork() as uow:
        repo = CategoriaRepository(uow.session)
        categoria = repo.get_by_id(categoria_id)
        if not categoria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Categoría con ID {categoria_id} no encontrada",
            )
        repo.delete(categoria)
