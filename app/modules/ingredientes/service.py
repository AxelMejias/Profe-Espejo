"""
Service de Ingredientes.
Regla: NO crea su propio UoW. Recibe `uow` del router.
"""
import math
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.modules.ingredientes.model import Ingrediente
from app.modules.ingredientes.schemas import (
    IngredienteCreate, IngredienteUpdate, IngredienteResponse, PaginatedIngredientes,
)


def _problem(code: str, detail: str, http_status: int):
    raise HTTPException(
        status_code=http_status,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def get_all(
    uow,
    nombre: Optional[str] = None,
    es_alergeno: Optional[bool] = None,
    es_producto_terminado: Optional[bool] = None,
    unidad_medida: Optional[str] = None,
    stock_bajo: Optional[bool] = None,
    page: int = 1,
    size: int = 20,
) -> PaginatedIngredientes:
    items, total = uow.ingredientes.get_all(
        nombre=nombre, es_alergeno=es_alergeno,
        es_producto_terminado=es_producto_terminado,
        unidad_medida=unidad_medida,
        stock_bajo=stock_bajo,
        page=page, size=size,
    )
    return PaginatedIngredientes(
        items=[IngredienteResponse.model_validate(i) for i in items],
        total=total, page=page, size=size,
        pages=math.ceil(total / size) if total else 0,
    )


def get_by_id(uow, ingrediente_id: int) -> IngredienteResponse:
    ingrediente = uow.ingredientes.get_by_id(ingrediente_id)
    if not ingrediente:
        _problem("INGREDIENTE_NOT_FOUND", f"Ingrediente {ingrediente_id} no encontrado", status.HTTP_404_NOT_FOUND)
    return IngredienteResponse.model_validate(ingrediente)


def create(uow, data: IngredienteCreate) -> IngredienteResponse:
    if uow.ingredientes.get_by_nombre(data.nombre):
        _problem("NOMBRE_CONFLICT", f"Ya existe un ingrediente '{data.nombre}'", status.HTTP_409_CONFLICT)
    try:
        ingrediente = Ingrediente(**data.model_dump())
        uow.ingredientes.add(ingrediente)
        return IngredienteResponse.model_validate(ingrediente)
    except IntegrityError:
        _problem("NOMBRE_CONFLICT", f"Ya existe un ingrediente '{data.nombre}'", status.HTTP_409_CONFLICT)


def update(uow, ingrediente_id: int, data: IngredienteUpdate) -> IngredienteResponse:
    ingrediente = uow.ingredientes.get_by_id(ingrediente_id)
    if not ingrediente:
        _problem("INGREDIENTE_NOT_FOUND", f"Ingrediente {ingrediente_id} no encontrado", status.HTTP_404_NOT_FOUND)
    changes = data.model_dump(exclude_unset=True)
    if "nombre" in changes and changes["nombre"] != ingrediente.nombre:
        if uow.ingredientes.get_by_nombre(changes["nombre"]):
            _problem("NOMBRE_CONFLICT", f"Ya existe un ingrediente '{changes['nombre']}'", status.HTTP_409_CONFLICT)
    for key, value in changes.items():
        setattr(ingrediente, key, value)
    ingrediente.updated_at = datetime.utcnow()
    uow.ingredientes.add(ingrediente)
    return IngredienteResponse.model_validate(ingrediente)


def delete(uow, ingrediente_id: int) -> None:
    ingrediente = uow.ingredientes.get_by_id(ingrediente_id)
    if not ingrediente:
        _problem("INGREDIENTE_NOT_FOUND", f"Ingrediente {ingrediente_id} no encontrado", status.HTTP_404_NOT_FOUND)
    uow.ingredientes.soft_delete(ingrediente)


def reactivar(uow, ingrediente_id: int) -> IngredienteResponse:
    ingrediente = uow.ingredientes.get_by_id_inactivo(ingrediente_id)
    if not ingrediente:
        _problem("INGREDIENTE_NOT_FOUND", f"Ingrediente {ingrediente_id} no encontrado o ya está activo", status.HTTP_404_NOT_FOUND)
    ingrediente.deleted_at = None
    ingrediente.updated_at = datetime.utcnow()
    uow.ingredientes.add(ingrediente)
    return IngredienteResponse.model_validate(ingrediente)


def get_all_activos_for_export(uow) -> list[IngredienteResponse]:
    return [IngredienteResponse.model_validate(i) for i in uow.ingredientes.get_all_activos()]


# ── Importación desde Excel ─────────────────────────────────────────────────────
_BOOL_MAP = {"TRUE", "VERDADERO", "SI", "SÍ", "S", "1"}


def importar_fila(uow, row) -> str:
    """Procesa una fila del Excel de importación de ingredientes.

    Devuelve "creado" u "omitido" (nombre ya existente). Lanza ValueError(motivo)
    si la fila es inválida; el router lo registra como error de esa fila. El router
    aporta solo el parseo del archivo y la transacción por fila (UoW); las reglas de
    negocio (validaciones, dedupe y alta) viven acá.
    """
    nombre = str(row[0]).strip() if row[0] is not None else ""
    descripcion = str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
    unidad_medida = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
    costo_raw = row[3] if len(row) > 3 else None
    stock_raw = row[4] if len(row) > 4 else 0
    minimo_raw = row[5] if len(row) > 5 else 0
    alergeno_raw = str(row[6]).upper().strip() if len(row) > 6 and row[6] is not None else "FALSE"
    terminado_raw = str(row[7]).upper().strip() if len(row) > 7 and row[7] is not None else "FALSE"

    if not nombre:
        raise ValueError("Nombre requerido")
    if not unidad_medida:
        raise ValueError("Unidad de medida requerida")
    if costo_raw is None:
        raise ValueError("Costo unitario requerido")
    costo = float(costo_raw)
    if costo < 0:
        raise ValueError("Costo unitario debe ser >= 0")

    if uow.ingredientes.get_by_nombre(nombre):
        return "omitido"

    ing = Ingrediente(
        nombre=nombre,
        descripcion=descripcion or None,
        unidad_medida=unidad_medida,
        costo_unitario=costo,
        stock_cantidad=float(stock_raw) if stock_raw is not None else 0,
        stock_minimo=float(minimo_raw) if minimo_raw is not None else 0,
        es_alergeno=alergeno_raw in _BOOL_MAP,
        es_producto_terminado=terminado_raw in _BOOL_MAP,
    )
    uow.ingredientes.add(ing)
    return "creado"
