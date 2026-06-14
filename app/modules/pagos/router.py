"""
Router de Pagos — webhook IPN de MercadoPago.

El webhook es la FUENTE DE VERDAD del cobro (server-to-server), independiente
del redirect del browser. MP lo invoca con:
  - query: ?type=payment&data.id=<payment_id>   (o ?topic=payment&id=<...>)
  - body:  {"type":"payment","data":{"id":"<payment_id>"}}
  - headers: x-signature, x-request-id  → validación HMAC
"""
from fastapi import APIRouter, Depends, Path, Request, status
from fastapi.responses import RedirectResponse

from app.modules.pagos import service
from app.modules.pagos.schemas import PagoResponse
from app.modules.pedidos import service as pedidos_service
from app.core.unit_of_work import UnitOfWork
from app.core.dependencies import require_role
from app.core.config import settings

router = APIRouter(prefix="/api/v1/pagos", tags=["Pagos"])


@router.get(
    "/redirect/{pedido_id}/{mp_status}",
    summary="Redirect de MercadoPago al frontend",
    include_in_schema=False,
)
async def redirect_after_pago(pedido_id: int, mp_status: str, request: Request):
    """
    MP redirige el browser aquí (back_url HTTPS válida). Nosotros
    hacemos un 302 al frontend localhost con todos los query params.
    """
    fe = settings.FRONTEND_URL
    qs = str(request.url.query)
    url = f"{fe}/pedido-exitoso"
    if qs:
        url += f"?{qs}"
    return RedirectResponse(url=url, status_code=302)


@router.get(
    "/{pedido_id}",
    response_model=PagoResponse,
    summary="Consultar el pago de un pedido",
    dependencies=[Depends(require_role(["ADMIN", "PEDIDOS", "CLIENT"]))],
)
def get_pago(
    pedido_id: int = Path(..., ge=1),
):
    with UnitOfWork() as uow:
        return service.get_pago_by_pedido(uow, pedido_id)


@router.post("/webhook", status_code=status.HTTP_200_OK, summary="Webhook IPN de MercadoPago")
async def mp_webhook(request: Request):
    # ── Extraer topic + data_id de query params o del body ───────────────────
    qp = request.query_params
    topic = qp.get("type") or qp.get("topic")

    try:
        body = await request.json()
    except Exception:
        body = {}

    if not topic:
        topic = body.get("type") or body.get("topic")

    # Para el HMAC, MP firma usando el data.id del BODY (no del query param)
    data = body.get("data") or {}
    data_id = str(data["id"]) if data.get("id") is not None else qp.get("data.id") or qp.get("id")

    if not data_id:
        return {"status": "ignored"}

    x_signature = request.headers.get("x-signature")
    x_request_id = request.headers.get("x-request-id")

    with UnitOfWork() as uow:
        result = service.procesar_webhook(
            uow,
            topic=topic or "",
            data_id=str(data_id),
            x_signature=x_signature,
            x_request_id=x_request_id,
        )

    # ── Notificación WebSocket best-effort cuando el pedido cambió de estado ──
    if result["action"] in ("confirmed", "cancelled"):
        try:
            event = "pago_confirmado" if result["action"] == "confirmed" else None
            await pedidos_service.emit_ws_evento(result["pedido_id"], event=event)
        except Exception:
            pass

    return {"status": "ok", "action": result["action"]}
