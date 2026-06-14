from datetime import date
from typing import List
from fastapi import APIRouter, Depends, Query

from app.core.dependencies import require_role
from app.core.database import get_session
from app.modules.estadisticas import service
from app.modules.estadisticas.schemas import (
    DashboardResponse, PedidosPorEstadoItem, IngresosPorFormaPagoItem,
)

router = APIRouter(prefix="/api/v1/estadisticas", tags=["Estadísticas"])

_ADMIN = Depends(require_role(["ADMIN"]))


@router.get("/dashboard", response_model=DashboardResponse, summary="Dashboard de métricas de ventas")
def get_dashboard(
    fecha_desde: date = Query(..., description="Inicio del período (YYYY-MM-DD)"),
    fecha_hasta: date = Query(..., description="Fin del período (YYYY-MM-DD)"),
    _=_ADMIN,
    session=Depends(get_session),
):
    return service.get_dashboard(session, fecha_desde, fecha_hasta)


@router.get(
    "/pedidos-por-estado",
    response_model=List[PedidosPorEstadoItem],
    summary="Distribución de pedidos por estado actual",
)
def get_pedidos_por_estado(
    _=_ADMIN,
    session=Depends(get_session),
):
    return service.get_pedidos_por_estado(session)


@router.get(
    "/ingresos",
    response_model=List[IngresosPorFormaPagoItem],
    summary="Ingresos confirmados agrupados por forma de pago",
)
def get_ingresos(
    fecha_desde: date = Query(..., description="Inicio del período (YYYY-MM-DD)"),
    fecha_hasta: date = Query(..., description="Fin del período (YYYY-MM-DD)"),
    _=_ADMIN,
    session=Depends(get_session),
):
    return service.get_ingresos_por_forma_pago(session, fecha_desde, fecha_hasta)
