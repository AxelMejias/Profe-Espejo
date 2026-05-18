"""
Service de Categorías.
Regla: NO crea su propio UoW. Recibe `uow` del router como parámetro.
"""
import math
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, status

from app.modules.categorias.model import Categoria
from app.modules.categorias.schemas import (
    CategoriaCreate, CategoriaUpdate, CategoriaRead, PaginatedCategorias,
)


def _problem(code: str, detail: str, http_status: int):
    raise HTTPException(
        status_code=http_status,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def get_all(uow, nombre: Optional[str] = None, page: int = 1, size: int = 20) -> PaginatedCategorias:
    items, total = uow.categorias.get_all(nombre=nombre, page=page, size=size)
    return PaginatedCategorias(
        items=[CategoriaRead.model_validate(c) for c in items],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 0,
    )


def get_by_id(uow, categoria_id: int) -> CategoriaRead:
    categoria = uow.categorias.get_by_id(categoria_id)
    if not categoria:
        _problem("CATEGORIA_NOT_FOUND", f"Categoría {categoria_id} no encontrada", status.HTTP_404_NOT_FOUND)
    return CategoriaRead.model_validate(categoria)


def get_subcategorias(uow, parent_id: int) -> list[CategoriaRead]:
    if not uow.categorias.get_by_id(parent_id):
        _problem("CATEGORIA_NOT_FOUND", f"Categoría {parent_id} no encontrada", status.HTTP_404_NOT_FOUND)
    subs = uow.categorias.get_subcategorias(parent_id)
    return [CategoriaRead.model_validate(c) for c in subs]


def create(uow, data: CategoriaCreate) -> CategoriaRead:
    if uow.categorias.get_by_nombre(data.nombre):
        _problem("NOMBRE_CONFLICT", f"Ya existe una categoría '{data.nombre}'", status.HTTP_409_CONFLICT)
    if data.parent_id and not uow.categorias.get_by_id(data.parent_id):
        _problem("PARENT_NOT_FOUND", f"Categoría padre {data.parent_id} no encontrada", status.HTTP_404_NOT_FOUND)
    categoria = Categoria(**data.model_dump())
    uow.categorias.add(categoria)
    return CategoriaRead.model_validate(categoria)


def update(uow, categoria_id: int, data: CategoriaUpdate) -> CategoriaRead:
    categoria = uow.categorias.get_by_id(categoria_id)
    if not categoria:
        _problem("CATEGORIA_NOT_FOUND", f"Categoría {categoria_id} no encontrada", status.HTTP_404_NOT_FOUND)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(categoria, key, value)
    categoria.updated_at = datetime.utcnow()
    uow.categorias.add(categoria)
    return CategoriaRead.model_validate(categoria)


def delete(uow, categoria_id: int) -> None:
    categoria = uow.categorias.get_by_id(categoria_id)
    if not categoria:
        _problem("CATEGORIA_NOT_FOUND", f"Categoría {categoria_id} no encontrada", status.HTTP_404_NOT_FOUND)
    uow.categorias.soft_delete(categoria)
