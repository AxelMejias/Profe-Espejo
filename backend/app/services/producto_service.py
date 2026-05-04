from typing import List, Optional
from fastapi import HTTPException, status

from app.repositories.producto_repository import ProductoRepository
from app.schemas.producto import (
    ProductoCreate,
    ProductoUpdate,
    ProductoListItem,
    ProductoResponse,
    CategoriaResponse,
    IngredienteDeProductoResponse,
)
from app.uow.unit_of_work import UnitOfWork


def _build_response(repo: ProductoRepository, producto_id: int) -> ProductoResponse:
    from app.models.producto import Producto
    producto = repo.get_by_id(producto_id)
    categorias = repo.get_links_categoria(producto_id)
    pi_links = repo.get_links_ingrediente(producto_id)

    ingredientes_resp = []
    for pi in pi_links:
        ing = repo.get_ingrediente(pi.ingrediente_id)
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
        created_at=producto.created_at,
        updated_at=producto.updated_at,
        categorias=[CategoriaResponse.model_validate(c) for c in categorias],
        ingredientes=ingredientes_resp,
    )


def get_all(
    nombre: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    categoria_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 10,
) -> List[ProductoListItem]:
    with UnitOfWork() as uow:
        repo = ProductoRepository(uow.session)
        productos = repo.get_all(
            nombre=nombre,
            precio_min=precio_min,
            precio_max=precio_max,
            categoria_id=categoria_id,
            offset=offset,
            limit=limit,
        )
        return [ProductoListItem.model_validate(p) for p in productos]


def get_by_id(producto_id: int) -> ProductoResponse:
    with UnitOfWork() as uow:
        repo = ProductoRepository(uow.session)
        if not repo.get_by_id(producto_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con ID {producto_id} no encontrado",
            )
        return _build_response(repo, producto_id)


def create(data: ProductoCreate) -> ProductoResponse:
    with UnitOfWork() as uow:
        repo = ProductoRepository(uow.session)
        if repo.get_by_nombre(data.nombre):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un producto con el nombre '{data.nombre}'",
            )
        producto = repo.create(data)
        for cat_id in data.categoria_ids:
            if not repo.get_categoria(cat_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Categoría con ID {cat_id} no encontrada",
                )
            repo.add_categoria_link(producto.id, cat_id)
        for ing_input in data.ingredientes:
            if not repo.get_ingrediente(ing_input.ingrediente_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Ingrediente con ID {ing_input.ingrediente_id} no encontrado",
                )
            repo.add_ingrediente_link(
                producto.id, ing_input.ingrediente_id, ing_input.cantidad
            )
        uow.session.flush()
        uow.session.refresh(producto)
        return _build_response(repo, producto.id)


def update(producto_id: int, data: ProductoUpdate) -> ProductoResponse:
    with UnitOfWork() as uow:
        repo = ProductoRepository(uow.session)
        producto = repo.get_by_id(producto_id)
        if not producto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con ID {producto_id} no encontrado",
            )
        repo.update(producto, data)
        return _build_response(repo, producto_id)


def delete(producto_id: int) -> None:
    with UnitOfWork() as uow:
        repo = ProductoRepository(uow.session)
        producto = repo.get_by_id(producto_id)
        if not producto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con ID {producto_id} no encontrado",
            )
        repo.delete(producto)
