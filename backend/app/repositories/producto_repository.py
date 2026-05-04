from typing import List, Optional
from datetime import datetime
from sqlmodel import Session, select
from app.models.producto import Producto
from app.models.categoria import Categoria
from app.models.ingrediente import Ingrediente
from app.models.links import ProductoCategoria, ProductoIngrediente
from app.schemas.producto import ProductoCreate, ProductoUpdate


class ProductoRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(
        self,
        nombre: Optional[str] = None,
        precio_min: Optional[float] = None,
        precio_max: Optional[float] = None,
        categoria_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> List[Producto]:
        query = select(Producto)
        if nombre:
            query = query.where(Producto.nombre.icontains(nombre))
        if precio_min is not None:
            query = query.where(Producto.precio >= precio_min)
        if precio_max is not None:
            query = query.where(Producto.precio <= precio_max)
        if categoria_id is not None:
            query = query.join(ProductoCategoria).where(
                ProductoCategoria.categoria_id == categoria_id
            )
        return list(self.session.exec(query.offset(offset).limit(limit)).all())

    def get_by_id(self, producto_id: int) -> Optional[Producto]:
        return self.session.get(Producto, producto_id)

    def get_by_nombre(self, nombre: str) -> Optional[Producto]:
        return self.session.exec(
            select(Producto).where(Producto.nombre == nombre)
        ).first()

    def get_categoria(self, categoria_id: int) -> Optional[Categoria]:
        return self.session.get(Categoria, categoria_id)

    def get_ingrediente(self, ingrediente_id: int) -> Optional[Ingrediente]:
        return self.session.get(Ingrediente, ingrediente_id)

    def get_links_categoria(self, producto_id: int) -> List[Categoria]:
        stmt = (
            select(Categoria)
            .join(ProductoCategoria, ProductoCategoria.categoria_id == Categoria.id)
            .where(ProductoCategoria.producto_id == producto_id)
        )
        return list(self.session.exec(stmt).all())

    def get_links_ingrediente(self, producto_id: int) -> List[ProductoIngrediente]:
        stmt = select(ProductoIngrediente).where(
            ProductoIngrediente.producto_id == producto_id
        )
        return list(self.session.exec(stmt).all())

    def create(self, data: ProductoCreate) -> Producto:
        producto = Producto(
            nombre=data.nombre,
            descripcion=data.descripcion,
            precio=data.precio,
        )
        self.session.add(producto)
        self.session.flush()
        return producto

    def add_categoria_link(self, producto_id: int, categoria_id: int) -> None:
        self.session.add(
            ProductoCategoria(producto_id=producto_id, categoria_id=categoria_id)
        )

    def add_ingrediente_link(
        self, producto_id: int, ingrediente_id: int, cantidad: float
    ) -> None:
        self.session.add(
            ProductoIngrediente(
                producto_id=producto_id,
                ingrediente_id=ingrediente_id,
                cantidad=cantidad,
            )
        )

    def update(self, producto: Producto, data: ProductoUpdate) -> Producto:
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(producto, key, value)
        producto.updated_at = datetime.utcnow()
        self.session.add(producto)
        self.session.flush()
        self.session.refresh(producto)
        return producto

    def delete(self, producto: Producto) -> None:
        for pc in self.session.exec(
            select(ProductoCategoria).where(
                ProductoCategoria.producto_id == producto.id
            )
        ).all():
            self.session.delete(pc)
        for pi in self.session.exec(
            select(ProductoIngrediente).where(
                ProductoIngrediente.producto_id == producto.id
            )
        ).all():
            self.session.delete(pi)
        self.session.delete(producto)
        self.session.flush()
