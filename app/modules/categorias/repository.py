import math
from typing import List, Optional, Tuple
from sqlmodel import Session, select

from app.core.base_repository import BaseRepository
from app.modules.categorias.model import Categoria


class CategoriaRepository(BaseRepository[Categoria]):

    def __init__(self, session: Session):
        super().__init__(session, Categoria)

    def get_by_id(self, categoria_id: int) -> Optional[Categoria]:
        return self.session.exec(
            select(Categoria).where(
                Categoria.id == categoria_id,
                Categoria.deleted_at == None,
            )
        ).first()

    def get_by_nombre(self, nombre: str) -> Optional[Categoria]:
        return self.session.exec(
            select(Categoria).where(
                Categoria.nombre == nombre,
                Categoria.deleted_at == None,
            )
        ).first()

    def get_all(
        self,
        nombre: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Categoria], int]:
        query = select(Categoria).where(Categoria.deleted_at == None)
        if nombre:
            query = query.where(Categoria.nombre.icontains(nombre))
        total = len(self.session.exec(query).all())
        offset = (page - 1) * size
        items = list(self.session.exec(query.offset(offset).limit(size)).all())
        return items, total

    def get_subcategorias(self, parent_id: int) -> List[Categoria]:
        return list(
            self.session.exec(
                select(Categoria).where(
                    Categoria.parent_id == parent_id,
                    Categoria.deleted_at == None,
                )
            ).all()
        )

    def soft_delete(self, categoria: Categoria) -> None:
        from datetime import datetime
        categoria.deleted_at = datetime.utcnow()
        self.session.add(categoria)
        self.session.flush()
