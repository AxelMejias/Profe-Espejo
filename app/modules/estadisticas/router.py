from datetime import date
from typing import List
from fastapi import APIRouter, Depends, Query

from app.core.dependencies import require_role
from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.modules.estadisticas import service
from app.modules.estadisticas.schemas import (
    DashboardResponse, VentasPeriodoItem, ProductoTopItem,
    PedidosEstadoItem, IngresosFormaPagoItem, ResumenResponse,
    AlertasStockResponse,
)

router = APIRouter(prefix="/api/v1/estadisticas", tags=["Estadísticas"])

_ADMIN = Depends(require_role(["ADMIN"]))


# ── Dashboard combinado (legacy — lo consume el front actual) ───────────────────
@router.get("/dashboard", response_model=DashboardResponse, summary="Dashboard combinado de métricas")
def get_dashboard(
    fecha_desde: date = Query(..., description="Inicio del período (YYYY-MM-DD)"),
    fecha_hasta: date = Query(..., description="Fin del período (YYYY-MM-DD)"),
    _=_ADMIN,
    session=Depends(get_session),
):
    return service.get_dashboard(session, fecha_desde, fecha_hasta)


# ── Los 5 endpoints de la Especificación v6.0 (§11.3) ───────────────────────────
@router.get("/ventas", response_model=List[VentasPeriodoItem], summary="Ventas por período (LineChart)")
def get_ventas(
    desde: date = Query(..., description="Inicio del período (YYYY-MM-DD)"),
    hasta: date = Query(..., description="Fin del período (YYYY-MM-DD)"),
    agrupacion: str = Query("day", pattern="^(day|week|month)$"),
    _=_ADMIN,
    session=Depends(get_session),
):
    return service.get_ventas(session, desde, hasta, agrupacion)


@router.get("/productos-top", response_model=List[ProductoTopItem], summary="Top productos vendidos (BarChart)")
def get_productos_top(
    desde: date = Query(..., description="Inicio del período (YYYY-MM-DD)"),
    hasta: date = Query(..., description="Fin del período (YYYY-MM-DD)"),
    limit: int = Query(5, ge=1, le=50),
    _=_ADMIN,
    session=Depends(get_session),
):
    return service.get_productos_top(session, desde, hasta, limit)


@router.get("/pedidos-por-estado", response_model=List[PedidosEstadoItem], summary="Distribución de pedidos por estado (PieChart)")
def get_pedidos_por_estado(
    _=_ADMIN,
    session=Depends(get_session),
):
    return service.get_pedidos_por_estado(session)


@router.get("/ingresos", response_model=List[IngresosFormaPagoItem], summary="Ingresos por forma de pago (BarChart)")
def get_ingresos(
    desde: date = Query(..., description="Inicio del período (YYYY-MM-DD)"),
    hasta: date = Query(..., description="Fin del período (YYYY-MM-DD)"),
    _=_ADMIN,
    session=Depends(get_session),
):
    return service.get_ingresos(session, desde, hasta)


@router.get("/resumen", response_model=ResumenResponse, summary="KPIs del negocio (cards)")
def get_resumen(
    _=_ADMIN,
    session=Depends(get_session),
):
    return service.get_resumen(session)


@router.get("/alertas-stock", response_model=AlertasStockResponse, summary="Avisos de reposición (ingredientes bajo mínimo y productos sin stock)")
def get_alertas_stock(_=_ADMIN):
    with UnitOfWork() as uow:
        return service.get_alertas_stock(uow)
