"""
Service de Productos.
Regla: NO crea su propio UoW. Recibe `uow` del router.
"""
import math
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, status

from app.modules.productos.model import Producto
from app.modules.productos.schemas import (
    ProductoCreate, ProductoUpdate, ProductoListItem, ProductoResponse,
    CategoriaResponse, IngredienteDeProductoResponse,
)


def _problem(code: str, detail: str, http_status: int):
    raise HTTPException(
        status_code=http_status,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def _build_response(uow, producto: Producto) -> ProductoResponse:
    categorias = uow.productos.get_categorias(producto.id)
    pi_links = uow.productos.get_ingrediente_links(producto.id)
    ingredientes_resp = []
    for pi in pi_links:
        ing = uow.ingredientes.get_by_id(pi.ingrediente_id)
        if ing:
            ingredientes_resp.append(
                IngredienteDeProductoResponse(
                    id=ing.id, nombre=ing.nombre,
                    unidad_medida=ing.unidad_medida, cantidad=pi.cantidad,
                )
            )
    return ProductoResponse(
        id=producto.id, nombre=producto.nombre, descripcion=producto.descripcion,
        precio=producto.precio, stock_cantidad=producto.stock_cantidad,
        disponible=producto.disponible,
        created_at=producto.created_at, updated_at=producto.updated_at,
        categorias=[CategoriaResponse.model_validate(c) for c in categorias],
        ingredientes=ingredientes_resp,
    )


def get_all(
    uow,
    nombre: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    categoria_id: Optional[int] = None,
    solo_disponibles: bool = True,
    page: int = 1,
    size: int = 20,
):
    items, total = uow.productos.get_all(
        nombre=nombre, precio_min=precio_min, precio_max=precio_max,
        categoria_id=categoria_id, solo_disponibles=solo_disponibles,
        page=page, size=size,
    )
    return {
        "items": [ProductoListItem.model_validate(p) for p in items],
        "total": total, "page": page, "size": size,
        "pages": math.ceil(total / size) if total else 0,
    }


def get_by_id(uow, producto_id: int) -> ProductoResponse:
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    return _build_response(uow, producto)


def create(uow, data: ProductoCreate) -> ProductoResponse:
    if uow.productos.get_by_nombre(data.nombre):
        _problem("NOMBRE_CONFLICT", f"Ya existe un producto '{data.nombre}'", status.HTTP_409_CONFLICT)
    producto = Producto(
        nombre=data.nombre, descripcion=data.descripcion,
        precio=data.precio, stock_cantidad=data.stock_cantidad,
        disponible=data.disponible,
    )
    uow.productos.add(producto)
    for cat_id in (data.categoria_ids or []):
        if not uow.categorias.get_by_id(cat_id):
            _problem("CATEGORIA_NOT_FOUND", f"Categoría {cat_id} no encontrada", status.HTTP_404_NOT_FOUND)
        uow.productos.add_categoria_link(producto.id, cat_id)
    for ing_input in (data.ingredientes or []):
        if not uow.ingredientes.get_by_id(ing_input.ingrediente_id):
            _problem("INGREDIENTE_NOT_FOUND", f"Ingrediente {ing_input.ingrediente_id} no encontrado", status.HTTP_404_NOT_FOUND)
        uow.productos.add_ingrediente_link(producto.id, ing_input.ingrediente_id, ing_input.cantidad)
    uow.flush()
    return _build_response(uow, producto)


def update(uow, producto_id: int, data: ProductoUpdate) -> ProductoResponse:
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    simple = data.model_dump(exclude_unset=True, exclude={"categoria_ids", "ingredientes"})
    for key, value in simple.items():
        setattr(producto, key, value)
    producto.updated_at = datetime.utcnow()
    uow.productos.add(producto)
    if data.categoria_ids is not None:
        uow.productos.delete_categoria_links(producto_id)
        for cat_id in data.categoria_ids:
            if not uow.categorias.get_by_id(cat_id):
                _problem("CATEGORIA_NOT_FOUND", f"Categoría {cat_id} no encontrada", status.HTTP_404_NOT_FOUND)
            uow.productos.add_categoria_link(producto_id, cat_id)
    if data.ingredientes is not None:
        uow.productos.delete_ingrediente_links(producto_id)
        for ing_input in data.ingredientes:
            if not uow.ingredientes.get_by_id(ing_input.ingrediente_id):
                _problem("INGREDIENTE_NOT_FOUND", f"Ingrediente {ing_input.ingrediente_id} no encontrado", status.HTTP_404_NOT_FOUND)
            uow.productos.add_ingrediente_link(producto_id, ing_input.ingrediente_id, ing_input.cantidad)
    uow.flush()
    return _build_response(uow, producto)


def toggle_disponibilidad(uow, producto_id: int, disponible: bool) -> ProductoResponse:
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    producto.disponible = disponible
    producto.updated_at = datetime.utcnow()
    uow.productos.add(producto)
    return _build_response(uow, producto)


def delete(uow, producto_id: int) -> None:
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    uow.productos.soft_delete(producto)

def reactivar(uow, producto_id: int) -> ProductoResponse:
    producto = uow.productos.get_by_id_inactivo(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    producto.deleted_at = None
    producto.disponible = True
    producto.updated_at = datetime.utcnow()
    uow.productos.add(producto)
    return _build_response(uow, producto)
