"""
Service de UnidadMedida (catálogo).
Regla: NO crea su propio UoW. Recibe `uow` del router.
"""
from datetime import datetime
from fastapi import HTTPException, status

from app.modules.unidades.model import UnidadMedida
from app.modules.unidades.schemas import (
    UnidadMedidaCreate, UnidadMedidaUpdate, UnidadMedidaRead,
)


def _problem(code: str, detail: str, http_status: int):
    raise HTTPException(
        status_code=http_status,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def get_all(uow) -> list[UnidadMedidaRead]:
    return [UnidadMedidaRead.model_validate(u) for u in uow.unidades.get_all()]


def get_by_id(uow, unidad_id: int) -> UnidadMedidaRead:
    unidad = uow.unidades.get_by_id(unidad_id)
    if not unidad:
        _problem("UNIDAD_NOT_FOUND", f"Unidad de medida {unidad_id} no encontrada", status.HTTP_404_NOT_FOUND)
    return UnidadMedidaRead.model_validate(unidad)


def create(uow, data: UnidadMedidaCreate) -> UnidadMedidaRead:
    if uow.unidades.get_by_nombre(data.nombre):
        _problem("NOMBRE_CONFLICT", f"Ya existe una unidad '{data.nombre}'", status.HTTP_409_CONFLICT)
    if uow.unidades.get_by_simbolo(data.simbolo):
        _problem("SIMBOLO_CONFLICT", f"Ya existe una unidad con símbolo '{data.simbolo}'", status.HTTP_409_CONFLICT)

    unidad = UnidadMedida(**data.model_dump())
    uow.unidades.add(unidad)
    return UnidadMedidaRead.model_validate(unidad)


def update(uow, unidad_id: int, data: UnidadMedidaUpdate) -> UnidadMedidaRead:
    unidad = uow.unidades.get_by_id(unidad_id)
    if not unidad:
        _problem("UNIDAD_NOT_FOUND", f"Unidad de medida {unidad_id} no encontrada", status.HTTP_404_NOT_FOUND)

    cambios = data.model_dump(exclude_unset=True)
    # Validar unicidad si cambian nombre/símbolo
    if "nombre" in cambios:
        otra = uow.unidades.get_by_nombre(cambios["nombre"])
        if otra and otra.id != unidad_id:
            _problem("NOMBRE_CONFLICT", f"Ya existe una unidad '{cambios['nombre']}'", status.HTTP_409_CONFLICT)
    if "simbolo" in cambios:
        otra = uow.unidades.get_by_simbolo(cambios["simbolo"])
        if otra and otra.id != unidad_id:
            _problem("SIMBOLO_CONFLICT", f"Ya existe una unidad con símbolo '{cambios['simbolo']}'", status.HTTP_409_CONFLICT)

    for key, value in cambios.items():
        setattr(unidad, key, value)
    uow.unidades.add(unidad)
    return UnidadMedidaRead.model_validate(unidad)


def delete(uow, unidad_id: int) -> None:
    unidad = uow.unidades.get_by_id(unidad_id)
    if not unidad:
        _problem("UNIDAD_NOT_FOUND", f"Unidad de medida {unidad_id} no encontrada", status.HTTP_404_NOT_FOUND)
    uow.unidades.hard_delete(unidad)
