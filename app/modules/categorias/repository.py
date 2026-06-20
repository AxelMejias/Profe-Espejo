import math
from typing import List, Optional, Tuple
from sqlmodel import Session, select
from sqlalchemy import func

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

    def get_all_inactivos(
        self,
        nombre: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Categoria], int]:
        query = select(Categoria).where(Categoria.deleted_at != None)
        if nombre:
            query = query.where(Categoria.nombre.icontains(nombre))
        total = len(self.session.exec(query).all())
        offset = (page - 1) * size
        items = list(self.session.exec(query.offset(offset).limit(size)).all())
        return items, total

    def get_by_id_inactivo(self, categoria_id: int) -> Optional[Categoria]:
        return self.session.exec(
            select(Categoria).where(
                Categoria.id == categoria_id,
                Categoria.deleted_at != None,
            )
        ).first()

    def get_subcategorias(self, parent_id: int) -> List[Categoria]:
        return list(
            self.session.exec(
                select(Categoria).where(
                    Categoria.parent_id == parent_id,
                    Categoria.deleted_at == None,
                )
            ).all()
        )

    def get_by_ids(self, ids: list[int]) -> List[Categoria]:
        if not ids:
            return []
        return list(
            self.session.exec(
                select(Categoria).where(
                    Categoria.id.in_(ids),
                    Categoria.deleted_at == None,
                )
            ).all()
        )

    def count_active_products(self, categoria_ids: List[int]) -> int:
        """Cuántos productos activos tienen al menos una de estas categorías asignada."""
        if not categoria_ids:
            return 0
        from app.modules.productos.model import Producto
        from app.core.links import ProductoCategoria
        count = self.session.exec(
            select(func.count(Producto.id.distinct()))
            .join(ProductoCategoria, ProductoCategoria.producto_id == Producto.id)
            .where(
                ProductoCategoria.categoria_id.in_(categoria_ids),
                Producto.deleted_at == None,
            )
        ).one()
        return count or 0

    def get_descendant_ids(self, categoria_id: int) -> List[int]:
        """Retorna el ID dado más todos los IDs de sus subcategorías (recursivo)."""
        result = [categoria_id]
        queue = [categoria_id]
        while queue:
            parent_id = queue.pop()
            children = self.get_subcategorias(parent_id)
            for child in children:
                result.append(child.id)
                queue.append(child.id)
        return result

    def soft_delete(self, categoria: Categoria) -> None:
        from datetime import datetime
        categoria.deleted_at = datetime.utcnow()
        self.session.add(categoria)
        self.session.flush()

    def reactivar(self, categoria: Categoria) -> None:
        from datetime import datetime
        categoria.deleted_at = None
        categoria.updated_at = datetime.utcnow()
        self.session.add(categoria)
        self.session.flush()
