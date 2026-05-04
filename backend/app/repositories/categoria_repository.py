from typing import List, Optional
from datetime import datetime
from sqlmodel import Session, select
from app.models.categoria import Categoria
from app.schemas.categoria import CategoriaCreate, CategoriaUpdate


class CategoriaRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(
        self,
        nombre: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> List[Categoria]:
        query = select(Categoria)
        if nombre:
            query = query.where(Categoria.nombre.icontains(nombre))
        return list(self.session.exec(query.offset(offset).limit(limit)).all())

    def get_by_id(self, categoria_id: int) -> Optional[Categoria]:
        return self.session.get(Categoria, categoria_id)

    def get_by_nombre(self, nombre: str) -> Optional[Categoria]:
        return self.session.exec(
            select(Categoria).where(Categoria.nombre == nombre)
        ).first()

    def create(self, data: CategoriaCreate) -> Categoria:
        categoria = Categoria(**data.model_dump())
        self.session.add(categoria)
        self.session.flush()
        self.session.refresh(categoria)
        return categoria

    def update(self, categoria: Categoria, data: CategoriaUpdate) -> Categoria:
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(categoria, key, value)
        categoria.updated_at = datetime.utcnow()
        self.session.add(categoria)
        self.session.flush()
        self.session.refresh(categoria)
        return categoria

    def delete(self, categoria: Categoria) -> None:
        self.session.delete(categoria)
        self.session.flush()
