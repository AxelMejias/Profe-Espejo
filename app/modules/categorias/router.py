from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, Path, status

from app.modules.categorias.schemas import CategoriaCreate, CategoriaUpdate, CategoriaRead, PaginatedCategorias
from app.modules.categorias import service
from app.core.dependencies import require_role
from app.core.unit_of_work import UnitOfWork

router = APIRouter(prefix="/api/v1/categorias", tags=["Categorías"])

# Roles que pueden leer (público funciona también, pero requerimos al menos login)
_LEER  = Depends(require_role(["ADMIN", "STOCK", "PEDIDOS", "CLIENT"]))
_ADMIN = Depends(require_role(["ADMIN", "STOCK"]))


@router.get("/", response_model=PaginatedCategorias, summary="Listar categorías")
def listar_categorias(
    nombre: Annotated[Optional[str], Query(max_length=100)] = None,
    page:   Annotated[int, Query(ge=1)] = 1,
    size:   Annotated[int, Query(ge=1, le=100)] = 20,
    _=_LEER,
):
    with UnitOfWork() as uow:
        return service.get_all(uow, nombre=nombre, page=page, size=size)


@router.get("/{categoria_id}", response_model=CategoriaRead, summary="Obtener categoría por ID")
def obtener_categoria(
    categoria_id: Annotated[int, Path(ge=1)],
    _=_LEER,
):
    with UnitOfWork() as uow:
        return service.get_by_id(uow, categoria_id)


@router.get("/{categoria_id}/subcategorias", response_model=list[CategoriaRead])
def listar_subcategorias(
    categoria_id: Annotated[int, Path(ge=1)],
    _=_LEER,
):
    with UnitOfWork() as uow:
        return service.get_subcategorias(uow, categoria_id)


@router.post("/", response_model=CategoriaRead, status_code=status.HTTP_201_CREATED, summary="Crear categoría")
def crear_categoria(data: CategoriaCreate, _=_ADMIN):
    with UnitOfWork() as uow:
        return service.create(uow, data)


@router.put("/{categoria_id}", response_model=CategoriaRead, summary="Actualizar categoría")
def actualizar_categoria(
    categoria_id: Annotated[int, Path(ge=1)],
    data: CategoriaUpdate,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.update(uow, categoria_id, data)


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Baja lógica de categoría")
def eliminar_categoria(
    categoria_id: Annotated[int, Path(ge=1)],
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        service.delete(uow, categoria_id)
