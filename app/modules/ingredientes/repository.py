from typing import List, Optional, Tuple
from sqlmodel import Session, select

from app.core.base_repository import BaseRepository
from app.modules.ingredientes.model import Ingrediente


class IngredienteRepository(BaseRepository[Ingrediente]):

    def __init__(self, session: Session):
        super().__init__(session, Ingrediente)

    def get_by_id(self, ingrediente_id: int) -> Optional[Ingrediente]:
        return self.session.exec(
            select(Ingrediente).where(
                Ingrediente.id == ingrediente_id,
                Ingrediente.deleted_at == None,
            )
        ).first()

    def get_by_nombre(self, nombre: str) -> Optional[Ingrediente]:
        return self.session.exec(
            select(Ingrediente).where(
                Ingrediente.nombre == nombre,
                Ingrediente.deleted_at == None,
            )
        ).first()

    def get_by_nombre_any(self, nombre: str) -> Optional[Ingrediente]:
        """Busca por nombre incluyendo eliminados (para respetar unique constraint)."""
        return self.session.exec(
            select(Ingrediente).where(Ingrediente.nombre == nombre)
        ).first()

    def get_all(
        self,
        nombre: Optional[str] = None,
        es_alergeno: Optional[bool] = None,
        unidad_medida: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Ingrediente], int]:
        query = select(Ingrediente).where(Ingrediente.deleted_at == None)
        if nombre:
            query = query.where(Ingrediente.nombre.icontains(nombre))
        if unidad_medida:
            query = query.where(Ingrediente.unidad_medida.icontains(unidad_medida))
        if es_alergeno is not None:
            query = query.where(Ingrediente.es_alergeno == es_alergeno)
        total = len(self.session.exec(query).all())
        offset = (page - 1) * size
        items = list(self.session.exec(query.offset(offset).limit(size)).all())
        return items, total

    def get_all_activos(self) -> List[Ingrediente]:
        return list(
            self.session.exec(
                select(Ingrediente).where(Ingrediente.deleted_at == None)
            ).all()
        )

    def soft_delete(self, ingrediente: Ingrediente) -> None:
        from datetime import datetime
        ingrediente.deleted_at = datetime.utcnow()
        self.session.add(ingrediente)
        self.session.flush()
