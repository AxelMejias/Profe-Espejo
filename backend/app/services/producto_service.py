from typing import List, Optional
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.producto import Producto
from app.models.categoria import Categoria
from app.models.ingrediente import Ingrediente
from app.models.links import ProductoCategoria, ProductoIngrediente
from app.schemas.producto import (
    ProductoCreate,
    ProductoUpdate,
    ProductoListItem,
    ProductoResponse,
    CategoriaResponse,
    IngredienteDeProductoResponse,
)


def _build_response(session: Session, producto: Producto) -> ProductoResponse:
    """
    Construye un ProductoResponse con sus categorías e ingredientes (con cantidad).
    Debe llamarse dentro del contexto de sesión activa.
    """
    # Cargar categorías via relación N:N
    cats_stmt = (
        select(Categoria)
        .join(ProductoCategoria, ProductoCategoria.categoria_id == Categoria.id)
        .where(ProductoCategoria.producto_id == producto.id)
    )
    categorias = session.exec(cats_stmt).all()

    # Cargar ingredientes junto con su cantidad desde la tabla intermedia
    pi_stmt = select(ProductoIngrediente).where(
        ProductoIngrediente.producto_id == producto.id
    )
    pi_links = session.exec(pi_stmt).all()

    ingredientes_resp = []
    for pi in pi_links:
        ing = session.get(Ingrediente, pi.ingrediente_id)
        if ing:
            ingredientes_resp.append(
                IngredienteDeProductoResponse(
                    id=ing.id,
                    nombre=ing.nombre,
                    unidad_medida=ing.unidad_medida,
                    cantidad=pi.cantidad,
                )
            )

    return ProductoResponse(
        id=producto.id,
        nombre=producto.nombre,
        descripcion=producto.descripcion,
        precio=producto.precio,
        categorias=[CategoriaResponse.model_validate(c) for c in categorias],
        ingredientes=ingredientes_resp,
    )


def get_all(
    session: Session,
    nombre: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    categoria_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 10,
) -> List[ProductoListItem]:
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
    productos = session.exec(query.offset(offset).limit(limit)).all()
    return [ProductoListItem.model_validate(p) for p in productos]


def get_by_id(session: Session, producto_id: int) -> ProductoResponse:
    producto = session.get(Producto, producto_id)
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto con ID {producto_id} no encontrado",
        )
    return _build_response(session, producto)


def create(session: Session, data: ProductoCreate) -> ProductoResponse:
    # Verificar nombre duplicado
    existing = session.exec(
        select(Producto).where(Producto.nombre == data.nombre)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un producto con el nombre '{data.nombre}'",
        )

    # Crear producto con campos básicos
    producto = Producto(
        nombre=data.nombre,
        descripcion=data.descripcion,
        precio=data.precio,
    )
    session.add(producto)
    session.flush()  # Obtener el ID generado

    # Asociar categorías
    for cat_id in data.categoria_ids:
        if not session.get(Categoria, cat_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Categoría con ID {cat_id} no encontrada",
            )
        session.add(ProductoCategoria(producto_id=producto.id, categoria_id=cat_id))

    # Asociar ingredientes con cantidad
    for ing_input in data.ingredientes:
        if not session.get(Ingrediente, ing_input.ingrediente_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ingrediente con ID {ing_input.ingrediente_id} no encontrado",
            )
        session.add(
            ProductoIngrediente(
                producto_id=producto.id,
                ingrediente_id=ing_input.ingrediente_id,
                cantidad=ing_input.cantidad,
            )
        )

    session.flush()
    session.refresh(producto)
    return _build_response(session, producto)


def update(session: Session, producto_id: int, data: ProductoUpdate) -> ProductoResponse:
    producto = session.get(Producto, producto_id)
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto con ID {producto_id} no encontrado",
        )
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(producto, key, value)
    session.add(producto)
    session.flush()
    session.refresh(producto)
    return _build_response(session, producto)


def delete(session: Session, producto_id: int) -> None:
    producto = session.get(Producto, producto_id)
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto con ID {producto_id} no encontrado",
        )
    # Eliminar relaciones primero
    session.exec(
        select(ProductoCategoria).where(ProductoCategoria.producto_id == producto_id)
    )
    for pc in session.exec(
        select(ProductoCategoria).where(ProductoCategoria.producto_id == producto_id)
    ).all():
        session.delete(pc)

    for pi in session.exec(
        select(ProductoIngrediente).where(ProductoIngrediente.producto_id == producto_id)
    ).all():
        session.delete(pi)

    session.delete(producto)
    session.flush()
