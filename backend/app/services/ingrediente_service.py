from typing import List, Optional
from sqlmodel import Session, select
from fastapi import HTTPException, status

from app.models.ingrediente import Ingrediente
from app.schemas.ingrediente import IngredienteCreate, IngredienteUpdate, IngredienteResponse


def get_all(
    session: Session,
    nombre: Optional[str] = None,
    unidad_medida: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
) -> List[IngredienteResponse]:
    query = select(Ingrediente)
    if nombre:
        query = query.where(Ingrediente.nombre.icontains(nombre))
    if unidad_medida:
        query = query.where(Ingrediente.unidad_medida.icontains(unidad_medida))
    ingredientes = session.exec(query.offset(offset).limit(limit)).all()
    return [IngredienteResponse.model_validate(i) for i in ingredientes]


def get_by_id(session: Session, ingrediente_id: int) -> IngredienteResponse:
    ingrediente = session.get(Ingrediente, ingrediente_id)
    if not ingrediente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingrediente con ID {ingrediente_id} no encontrado",
        )
    return IngredienteResponse.model_validate(ingrediente)


def create(session: Session, data: IngredienteCreate) -> IngredienteResponse:
    existing = session.exec(
        select(Ingrediente).where(Ingrediente.nombre == data.nombre)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un ingrediente con el nombre '{data.nombre}'",
        )
    ingrediente = Ingrediente(**data.model_dump())
    session.add(ingrediente)
    session.flush()
    session.refresh(ingrediente)
    return IngredienteResponse.model_validate(ingrediente)


def update(session: Session, ingrediente_id: int, data: IngredienteUpdate) -> IngredienteResponse:
    ingrediente = session.get(Ingrediente, ingrediente_id)
    if not ingrediente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingrediente con ID {ingrediente_id} no encontrado",
        )
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(ingrediente, key, value)
    session.add(ingrediente)
    session.flush()
    session.refresh(ingrediente)
    return IngredienteResponse.model_validate(ingrediente)


def delete(session: Session, ingrediente_id: int) -> None:
    ingrediente = session.get(Ingrediente, ingrediente_id)
    if not ingrediente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingrediente con ID {ingrediente_id} no encontrado",
        )
    session.delete(ingrediente)
    session.flush()
