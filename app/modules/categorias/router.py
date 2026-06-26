from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, Path, status

from app.modules.categorias.schemas import (
    CategoriaCreate, CategoriaUpdate, CategoriaRead, PaginatedCategorias, CategoriaTree,
)
from app.modules.categorias import service
from app.core.dependencies import require_role
from app.core.unit_of_work import UnitOfWork
from app.core.websocket import emit_catalogo_evento

router = APIRouter(prefix="/api/v1/categorias", tags=["Categorías"])

# Lecturas del catálogo de categorías: PÚBLICAS (coherente con el catálogo de
# productos público, doc §5.2). Las escrituras siguen siendo solo ADMIN.
_ADMIN = Depends(require_role(["ADMIN"]))


@router.get("/tree", response_model=list[CategoriaTree], summary="Árbol recursivo de categorías")
def obtener_arbol():
    with UnitOfWork() as uow:
        return service.get_tree(uow)


@router.get("/", response_model=PaginatedCategorias, summary="Listar categorías")
def listar_categorias(
    nombre: Annotated[Optional[str], Query(max_length=100)] = None,
    page:   Annotated[int, Query(ge=1)] = 1,
    size:   Annotated[int, Query(ge=1, le=100)] = 20,
):
    with UnitOfWork() as uow:
        return service.get_all(uow, nombre=nombre, page=page, size=size)


@router.get(
    "/inactivos",
    response_model=PaginatedCategorias,
    summary="Listar categorías dadas de baja (soft delete)",
)
def listar_categorias_inactivas(
    nombre: Annotated[Optional[str], Query(max_length=100)] = None,
    page:   Annotated[int, Query(ge=1)] = 1,
    size:   Annotated[int, Query(ge=1, le=100)] = 20,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.get_all_inactivos(uow, nombre=nombre, page=page, size=size)


@router.get("/{categoria_id}", response_model=CategoriaRead, summary="Obtener categoría por ID")
def obtener_categoria(categoria_id: Annotated[int, Path(ge=1)]):
    with UnitOfWork() as uow:
        return service.get_by_id(uow, categoria_id)


@router.get("/{categoria_id}/subcategorias", response_model=list[CategoriaRead])
def listar_subcategorias(categoria_id: Annotated[int, Path(ge=1)]):
    with UnitOfWork() as uow:
        return service.get_subcategorias(uow, categoria_id)


@router.post("/", response_model=CategoriaRead, status_code=status.HTTP_201_CREATED, summary="Crear categoría")
async def crear_categoria(data: CategoriaCreate, _=_ADMIN):
    with UnitOfWork() as uow:
        result = service.create(uow, data)
    # Aviso en vivo: la tienda pública y las pestañas admin refrescan el árbol/lista
    # de categorías sin recargar.
    await emit_catalogo_evento("categoria_creada", categoria_id=result.id)
    return result


@router.put("/{categoria_id}", response_model=CategoriaRead, summary="Actualizar categoría")
async def actualizar_categoria(
    categoria_id: Annotated[int, Path(ge=1)],
    data: CategoriaUpdate,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        result = service.update(uow, categoria_id, data)
    await emit_catalogo_evento("categoria_actualizada", categoria_id=result.id)
    return result


@router.patch(
    "/{categoria_id}/reactivar",
    response_model=CategoriaRead,
    summary="Reactivar una categoría dada de baja",
)
async def reactivar_categoria(categoria_id: Annotated[int, Path(ge=1)], _=_ADMIN):
    with UnitOfWork() as uow:
        result = service.reactivar(uow, categoria_id)
    await emit_catalogo_evento("categoria_actualizada", categoria_id=result.id)
    return result


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Baja lógica de categoría")
async def eliminar_categoria(categoria_id: Annotated[int, Path(ge=1)], _=_ADMIN):
    with UnitOfWork() as uow:
        service.delete(uow, categoria_id)
    await emit_catalogo_evento("categoria_eliminada", categoria_id=categoria_id)