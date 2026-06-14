from datetime import date
from fastapi import APIRouter, Depends, Query

from app.core.dependencies import require_role
from app.core.database import get_session
from app.modules.estadisticas import service
from app.modules.estadisticas.schemas import DashboardResponse

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
