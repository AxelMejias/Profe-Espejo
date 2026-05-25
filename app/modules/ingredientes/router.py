from io import BytesIO
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from fastapi.responses import StreamingResponse
import openpyxl

from app.modules.ingredientes.schemas import (
    IngredienteCreate, IngredienteUpdate, IngredienteResponse, PaginatedIngredientes,
)
from app.modules.ingredientes import service
from app.core.dependencies import require_role
from app.core.unit_of_work import UnitOfWork

router = APIRouter(prefix="/api/v1/ingredientes", tags=["Ingredientes"])

_LEER  = Depends(require_role(["ADMIN", "STOCK", "COCINERO", "CLIENT"]))
_ADMIN = Depends(require_role(["ADMIN", "STOCK"]))


@router.get("/exportar", summary="Exportar ingredientes activos a Excel")
def exportar_ingredientes(_=_ADMIN):
    with UnitOfWork() as uow:
        ingredientes = service.get_all_activos_for_export(uow)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ingredientes"
    ws.append(["ID", "Nombre", "Descripción", "Unidad de medida", "Es alérgeno", "Creado en"])
    for ing in ingredientes:
        ws.append([
            ing.id, ing.nombre, ing.descripcion or "",
            ing.unidad_medida, "Sí" if ing.es_alergeno else "No",
            ing.created_at.strftime("%Y-%m-%d %H:%M"),
        ])
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ingredientes.xlsx"},
    )


@router.get("/", response_model=PaginatedIngredientes, summary="Listar ingredientes")
def listar_ingredientes(
    nombre:        Annotated[Optional[str],  Query(max_length=100)] = None,
    unidad_medida: Annotated[Optional[str],  Query(max_length=50)]  = None,
    es_alergeno:   Annotated[Optional[bool], Query()]               = None,
    page:          Annotated[int, Query(ge=1)]                      = 1,
    size:          Annotated[int, Query(ge=1, le=100)]              = 20,
    _=_LEER,
):
    with UnitOfWork() as uow:
        return service.get_all(uow, nombre=nombre, es_alergeno=es_alergeno,
                               unidad_medida=unidad_medida, page=page, size=size)
    
@router.get(
    "/inactivos",
    response_model=PaginatedIngredientes,
    summary="Listar ingredientes dados de baja (soft delete)",
)
def listar_ingredientes_inactivos(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        items, total = uow.ingredientes.get_all_inactivos(page=page, size=size)
        import math
        return PaginatedIngredientes(
            items=[IngredienteResponse.model_validate(i) for i in items],
            total=total, page=page, size=size,
            pages=math.ceil(total / size) if total else 0,
        )


@router.get("/{ingrediente_id}", response_model=IngredienteResponse, summary="Obtener ingrediente por ID")
def obtener_ingrediente(ingrediente_id: Annotated[int, Path(ge=1)], _=_LEER):
    with UnitOfWork() as uow:
        return service.get_by_id(uow, ingrediente_id)


@router.post("/", response_model=IngredienteResponse, status_code=status.HTTP_201_CREATED, summary="Crear ingrediente")
def crear_ingrediente(data: IngredienteCreate, _=_ADMIN):
    with UnitOfWork() as uow:
        return service.create(uow, data)


@router.put("/{ingrediente_id}", response_model=IngredienteResponse, summary="Actualizar ingrediente")
def actualizar_ingrediente(
    ingrediente_id: Annotated[int, Path(ge=1)],
    data: IngredienteUpdate,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.update(uow, ingrediente_id, data)


@router.patch("/{ingrediente_id}/reactivar", response_model=IngredienteResponse, summary="Reactivar ingrediente dado de baja")
def reactivar_ingrediente(ingrediente_id: Annotated[int, Path(ge=1)], _=_ADMIN):
    with UnitOfWork() as uow:
        return service.reactivar(uow, ingrediente_id)


@router.delete("/{ingrediente_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Baja lógica de ingrediente")
def eliminar_ingrediente(ingrediente_id: Annotated[int, Path(ge=1)], _=_ADMIN):
    with UnitOfWork() as uow:
        service.delete(uow, ingrediente_id)
