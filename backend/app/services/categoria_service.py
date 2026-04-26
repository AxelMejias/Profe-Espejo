from typing import List, Optional
from sqlmodel import Session, select
from fastapi import HTTPException, status

from app.models.categoria import Categoria
from app.schemas.categoria import CategoriaCreate, CategoriaUpdate, CategoriaResponse


def get_all(
    session: Session,
    nombre: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
) -> List[CategoriaResponse]:
    query = select(Categoria)
    if nombre:
        query = query.where(Categoria.nombre.icontains(nombre))
    categorias = session.exec(query.offset(offset).limit(limit)).all()
    return [CategoriaResponse.model_validate(c) for c in categorias]


def get_by_id(session: Session, categoria_id: int) -> CategoriaResponse:
    categoria = session.get(Categoria, categoria_id)
    if not categoria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoría con ID {categoria_id} no encontrada",
        )
    return CategoriaResponse.model_validate(categoria)


def create(session: Session, data: CategoriaCreate) -> CategoriaResponse:
    existing = session.exec(
        select(Categoria).where(Categoria.nombre == data.nombre)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una categoría con el nombre '{data.nombre}'",
        )
    categoria = Categoria(**data.model_dump())
    session.add(categoria)
    session.flush()
    session.refresh(categoria)
    return CategoriaResponse.model_validate(categoria)


def update(session: Session, categoria_id: int, data: CategoriaUpdate) -> CategoriaResponse:
    categoria = session.get(Categoria, categoria_id)
    if not categoria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoría con ID {categoria_id} no encontrada",
        )
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(categoria, key, value)
    session.add(categoria)
    session.flush()
    session.refresh(categoria)
    return CategoriaResponse.model_validate(categoria)


def delete(session: Session, categoria_id: int) -> None:
    categoria = session.get(Categoria, categoria_id)
    if not categoria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoría con ID {categoria_id} no encontrada",
        )
    session.delete(categoria)
    session.flush()
