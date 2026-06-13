"""
Router de Pagos — webhook IPN de MercadoPago.

El webhook es la FUENTE DE VERDAD del cobro (server-to-server), independiente
del redirect del browser. MP lo invoca con:
  - query: ?type=payment&data.id=<payment_id>   (o ?topic=payment&id=<...>)
  - body:  {"type":"payment","data":{"id":"<payment_id>"}}
  - headers: x-signature, x-request-id  → validación HMAC
"""
from fastapi import APIRouter, Request, status

from app.modules.pagos import service
from app.modules.pedidos import service as pedidos_service
from app.core.unit_of_work import UnitOfWork

router = APIRouter(prefix="/api/v1/pagos", tags=["Pagos"])


@router.post("/webhook", status_code=status.HTTP_200_OK, summary="Webhook IPN de MercadoPago")
async def mp_webhook(request: Request):
    # ── Extraer topic + data_id de query params o del body ───────────────────
    qp = request.query_params
    topic = qp.get("type") or qp.get("topic")
    data_id = qp.get("data.id") or qp.get("id")

    if not topic or not data_id:
        try:
            body = await request.json()
        except Exception:
            body = {}
        topic = topic or body.get("type") or body.get("topic")
        data = body.get("data") or {}
        if data_id is None and data.get("id") is not None:
            data_id = str(data.get("id"))

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
            with UnitOfWork() as uow:
                pedido = pedidos_service.get_by_id(
                    uow,
                    result["pedido_id"],
                    requester_user_id=0,
                    requester_roles=["ADMIN"],
                )
            await pedidos_service.emit_ws_evento(
                pedido.id, pedido.estado_codigo, pedido.model_dump(mode="json")
            )
        except Exception:
            pass

    return {"status": "ok", "action": result["action"]}
