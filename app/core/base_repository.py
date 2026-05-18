from typing import Generic, Optional, Type, TypeVar
from sqlmodel import SQLModel, Session, select

T = TypeVar("T", bound=SQLModel)


class BaseRepository(Generic[T]):
    """
    Repositorio genérico con operaciones CRUD base.
    Las subclases sobreescriben get_by_id para aplicar
    filtros adicionales (ej: soft delete con deleted_at IS NULL).

    Regla de oro: este repo recibe la sesión del UoW — nunca
    abre ni cierra su propia sesión.
    """

    def __init__(self, session: Session, model: Type[T]):
        self.session = session
        self.model = model

    def get_by_id(self, entity_id: int) -> Optional[T]:
        return self.session.get(self.model, entity_id)

    def add(self, entity: T) -> T:
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    def hard_delete(self, entity: T) -> None:
        self.session.delete(entity)
        self.session.flush()
