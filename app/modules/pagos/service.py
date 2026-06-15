"""
Service de Pagos — MercadoPago Checkout API.

Regla: NO crea su propio UoW. Recibe `uow` del router.

Responsabilidades:
  - crear_preferencia_y_pago: crea la preferencia de pago (con idempotencia)
    y persiste el registro Pago en estado 'pending'.
  - validar_firma_webhook: valida la firma X-Signature del webhook IPN (HMAC-SHA256).
  - procesar_webhook: fuente de verdad del cobro. Consulta el pago en MP,
    actualiza el Pago y avanza/cancela el Pedido vía el FSM de pedidos.
"""
import hashlib
import hmac
import json as _json
import urllib.request
import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.modules.pagos.model import Pago

_FORMA_PAGO_MP = "MERCADOPAGO"


def get_pago_by_pedido(uow, pedido_id: int):
    """Retorna el pago asociado al pedido o lanza 404."""
    pago = uow.pagos.get_by_pedido_id(pedido_id)
    if not pago:
        _problem("PAGO_NOT_FOUND", f"No existe un pago para el pedido {pedido_id}", status.HTTP_404_NOT_FOUND)
    return pago


def _problem(code: str, detail: str, http_status: int):
    raise HTTPException(
        status_code=http_status,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


# ──────────────────────────────────────────────────────────────────────────────
# Creación de preferencia + registro de Pago
# ──────────────────────────────────────────────────────────────────────────────

def _get_ngrok_url() -> Optional[str]:
    """Retorna la URL pública HTTPS de ngrok si está corriendo, o None."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1) as r:
            data = _json.loads(r.read())
        for tunnel in data.get("tunnels", []):
            if tunnel.get("proto") == "https":
                return tunnel["public_url"].rstrip("/")
    except Exception:
        pass
    return None


def crear_preferencia_y_pago(uow, pedido, detalles: list) -> str:
    """
    Crea una preferencia en MercadoPago con clave de idempotencia y persiste
    un registro Pago en estado 'pending'. Retorna el init_point (URL de checkout).

    El idempotency_key se envía a MP en el header X-Idempotency-Key para que un
    reintento del cliente no genere un segundo cobro.
    """
    import mercadopago

    idempotency_key = str(uuid.uuid4())
    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)

    ngrok_url = _get_ngrok_url()

    # Webhook IPN (server-to-server): ngrok tiene prioridad; si no, MP_NOTIFICATION_URL.
    # Si ninguna está disponible, se omite y MP usa la URL configurada en el panel.
    if ngrok_url:
        notification_url = f"{ngrok_url}/api/v1/pagos/webhook"
    else:
        notification_url = settings.MP_NOTIFICATION_URL or None

    # back_urls = redirect del BROWSER → apuntan al backend ngrok (HTTPS válida
    # para MP). El endpoint /redirect/{id}/{status} hace un 302 al frontend.
    # Si ngrok no está corriendo, caen directo al frontend (sin auto_return).
    be = ngrok_url or settings.BACKEND_URL or "http://localhost:8000"
    back_urls = {
        "success": f"{be}/api/v1/pagos/redirect/{pedido.id}/success",
        "failure": f"{be}/api/v1/pagos/redirect/{pedido.id}/failure",
        "pending": f"{be}/api/v1/pagos/redirect/{pedido.id}/pending",
    }

    items = [
        {
            "id": str(d.producto_id),
            "title": d.nombre_snapshot,
            "quantity": int(d.cantidad),
            "unit_price": float(d.precio_snapshot),
            "currency_id": "ARS",
        }
        for d in detalles
    ]

    # Envío como ítem aparte → la suma de ítems coincide con el total del pedido
    # (MP cobra la suma de items; el subtotal de productos no incluye el envío).
    costo_envio = float(pedido.costo_envio or 0)
    if costo_envio > 0:
        items.append({
            "id": "envio",
            "title": "Envío",
            "quantity": 1,
            "unit_price": costo_envio,
            "currency_id": "ARS",
        })

    preference_data = {
        "items": items,
        "back_urls": back_urls,
        "external_reference": str(pedido.id),
        "statement_descriptor": "Food Store",
        # auto_return requiere back_urls HTTPS — ngrok lo provee
        **({"auto_return": "approved"} if ngrok_url else {}),
        **({"notification_url": notification_url} if notification_url else {}),
    }

    request_options = mercadopago.config.RequestOptions(
        custom_headers={"x-idempotency-key": idempotency_key}
    )
    response = sdk.preference().create(preference_data, request_options)
    if response["status"] not in (200, 201):
        mp_error = response.get("response", {})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "detail": f"MP error {response['status']}: {mp_error}",
                "code": "MP_PREFERENCE_ERROR",
            },
        )

    preference = response["response"]
    init_point = preference["init_point"]

    # Persistir el registro de Pago (pending hasta que el webhook confirme)
    pago = Pago(
        pedido_id=pedido.id,
        external_reference=str(pedido.id),
        idempotency_key=idempotency_key,
        transaction_amount=pedido.total,
        mp_status="pending",
    )
    uow.pagos.add(pago)

    # Persistir referencias de MP en el pedido (último add → coherente con tests)
    pedido.mp_preference_id = preference["id"]
    pedido.mp_init_point = init_point
    uow.pedidos.add(pedido)

    return init_point


# ──────────────────────────────────────────────────────────────────────────────
# Webhook IPN — validación de firma + procesamiento
# ──────────────────────────────────────────────────────────────────────────────

def validar_firma_webhook(
    x_signature: Optional[str],
    x_request_id: Optional[str],
    data_id: str,
) -> bool:
    """
    Valida la firma del webhook según el esquema de MercadoPago:
        manifest = "id:<data.id>;request-id:<x-request-id>;ts:<ts>;"
        v1 = HMAC_SHA256(MP_WEBHOOK_SECRET, manifest)
    El header x-signature tiene el formato "ts=<ts>,v1=<hash>".

    Seguro por defecto: sin secret configurado o sin firma ⇒ rechaza.
    """
    secret = settings.MP_WEBHOOK_SECRET
    if not secret or not x_signature:
        return False

    partes = dict(
        p.split("=", 1) for p in x_signature.split(",") if "=" in p
    )
    ts = partes.get("ts")
    v1 = partes.get("v1")
    if not ts or not v1:
        return False

    manifest = f"id:{data_id};request-id:{x_request_id or ''};ts:{ts};"
    esperado = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)


def procesar_webhook(
    uow,
    *,
    topic: str,
    data_id: str,
    x_signature: Optional[str],
    x_request_id: Optional[str],
) -> dict:
    """
    Procesa una notificación IPN de MercadoPago (fuente de verdad del cobro).

    Retorna un dict con la acción tomada:
      {"action": "confirmed"|"cancelled"|"noop"|"pending"|"ignored", "pedido_id": int|None}

    - Valida la firma (401 si es inválida).
    - Solo procesa topic == "payment".
    - Consulta el pago real en MP, actualiza el Pago e (idempotente) avanza el Pedido.
    """
    # MP no firma merchant_order igual que payment → ignorar sin validar firma
    if topic != "payment":
        return {"action": "ignored", "pedido_id": None}

    # Ack 200 sin procesar: NO actuamos sobre una notificación cuya firma no valida
    # (seguridad intacta), pero acusamos recibo para que MP no reintente
    # (práctica estándar de webhooks; evita tormentas de reintentos en el log).
    if not validar_firma_webhook(x_signature, x_request_id, data_id):
        return {"action": "unverified", "pedido_id": None}

    import mercadopago
    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
    result = sdk.payment().get(data_id)
    if result.get("status") != 200:
        return {"action": "ignored", "pedido_id": None}

    payment = result["response"]
    external_reference = payment.get("external_reference")
    if not external_reference:
        return {"action": "ignored", "pedido_id": None}

    pago = uow.pagos.get_by_external_reference(external_reference)
    if not pago:
        return {"action": "ignored", "pedido_id": None}

    ya_aprobado = pago.mp_status == "approved"
    nuevo_status = payment.get("status", "unknown")

    # Actualizar el registro de Pago
    pago.mp_payment_id    = payment.get("id")
    pago.mp_status        = nuevo_status
    pago.mp_status_detail = payment.get("status_detail")
    pago.payment_method_id = payment.get("payment_method_id")
    pago.updated_at = datetime.utcnow()
    uow.pagos.add(pago)

    pedido_id = int(external_reference)

    if nuevo_status == "approved":
        # Idempotencia: si ya estaba aprobado, no re-disparar la transición
        if ya_aprobado:
            return {"action": "noop", "pedido_id": pedido_id}
        from app.modules.pedidos import service as pedidos_service
        pedidos_service.confirmar_pago_mp(uow, pedido_id)
        return {"action": "confirmed", "pedido_id": pedido_id}

    if nuevo_status in ("rejected", "cancelled"):
        from app.modules.pedidos import service as pedidos_service
        pedidos_service.cancelar_pago_mp(uow, pedido_id)
        return {"action": "cancelled", "pedido_id": pedido_id}

    return {"action": "pending", "pedido_id": pedido_id}
