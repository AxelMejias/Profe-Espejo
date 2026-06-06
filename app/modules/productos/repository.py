from typing import List, Optional, Tuple
from sqlmodel import Session, select
from datetime import datetime

from app.modules.productos.model import Producto
from app.modules.categorias.model import Categoria
from app.modules.ingredientes.model import Ingrediente
from app.core.links import ProductoCategoria, ProductoIngrediente
from app.core.base_repository import BaseRepository


class ProductoRepository(BaseRepository[Producto]):

    def __init__(self, session: Session):
        super().__init__(session, Producto)

    def get_by_id(self, producto_id: int) -> Optional[Producto]:
        return self.session.exec(
            select(Producto).where(
                Producto.id == producto_id,
                Producto.deleted_at == None,
            )
        ).first()

    def get_by_nombre(self, nombre: str) -> Optional[Producto]:
        return self.session.exec(
            select(Producto).where(
                Producto.nombre == nombre,
                Producto.deleted_at == None,
            )
        ).first()

    def get_all(
        self,
        nombre: Optional[str] = None,
        precio_min: Optional[float] = None,
        precio_max: Optional[float] = None,
        categoria_ids: Optional[List[int]] = None,
        solo_disponibles: bool = True,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Producto], int]:
        query = select(Producto).where(Producto.deleted_at == None)
        if solo_disponibles:
            query = query.where(Producto.disponible == True)
        if nombre:
            query = query.where(Producto.nombre.icontains(nombre))
        if precio_min is not None:
            query = query.where(Producto.precio >= precio_min)
        if precio_max is not None:
            query = query.where(Producto.precio <= precio_max)
        if categoria_ids:
            query = query.join(ProductoCategoria).where(
                ProductoCategoria.categoria_id.in_(categoria_ids)
            ).distinct()
        total = len(self.session.exec(query).all())
        offset = (page - 1) * size
        items = list(self.session.exec(query.offset(offset).limit(size)).all())
        return items, total

    def get_categorias(self, producto_id: int) -> List[Categoria]:
        stmt = (
            select(Categoria)
            .join(ProductoCategoria, ProductoCategoria.categoria_id == Categoria.id)
            .where(ProductoCategoria.producto_id == producto_id)
        )
        return list(self.session.exec(stmt).all())

    def get_ingrediente_links(self, producto_id: int) -> List[ProductoIngrediente]:
        return list(
            self.session.exec(
                select(ProductoIngrediente).where(
                    ProductoIngrediente.producto_id == producto_id
                )
            ).all()
        )

    def add_categoria_link(self, producto_id: int, categoria_id: int) -> None:
        self.session.add(ProductoCategoria(producto_id=producto_id, categoria_id=categoria_id))
        self.session.flush()

    def add_ingrediente_link(self, producto_id: int, ingrediente_id: int, cantidad: float) -> None:
        self.session.add(
            ProductoIngrediente(
                producto_id=producto_id,
                ingrediente_id=ingrediente_id,
                cantidad=cantidad,
            )
        )
        self.session.flush()

    def delete_categoria_links(self, producto_id: int) -> None:
        for pc in self.session.exec(
            select(ProductoCategoria).where(ProductoCategoria.producto_id == producto_id)
        ).all():
            self.session.delete(pc)
        self.session.flush()

    def get_all_inactivos(
        self,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Producto], int]:
        query = select(Producto).where(Producto.deleted_at != None)
        total = len(self.session.exec(query).all())
        offset = (page - 1) * size
        items = list(self.session.exec(query.offset(offset).limit(size)).all())
        return items, total
    
    def get_by_id_inactivo(self, producto_id: int) -> Optional[Producto]:
        return self.session.exec(
            select(Producto).where(
                Producto.id == producto_id,
                Producto.deleted_at != None,
        )
    ).first()

    def delete_ingrediente_links(self, producto_id: int) -> None:
        for pi in self.session.exec(
            select(ProductoIngrediente).where(ProductoIngrediente.producto_id == producto_id)
        ).all():
            self.session.delete(pi)
        self.session.flush()

    def soft_delete(self, producto: Producto) -> None:
        producto.deleted_at = datetime.utcnow()
        self.session.add(producto)
        self.session.flush()