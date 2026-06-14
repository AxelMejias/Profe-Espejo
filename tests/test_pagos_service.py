"""
test_pagos_service.py — Tests para app/modules/pagos/service.py

Dominio crítico (facturación). Cubre:
  - validar_firma_webhook: HMAC-SHA256 con MP_WEBHOOK_SECRET (válida / inválida / sin secret)
  - procesar_webhook: firma inválida (401), topic ignorado, approved → confirma,
                      rejected → cancela, idempotencia (no re-dispara)
  - crear_preferencia_y_pago: persiste Pago con idempotency_key, devuelve init_point,
                              error del SDK → 502
"""
import hashlib
import hmac
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.pagos import service
from app.core.config import settings
from tests.conftest import make_uow


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_SECRET = "test_webhook_secret"


def _firma_valida(data_id: str, x_request_id: str, ts: str = "1700000000") -> str:
    """Genera un header x-signature válido calculando el HMAC de forma independiente."""
    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    v1 = hmac.new(_SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def _mock_pago(mp_status: str = "pending"):
    p = MagicMock()
    p.mp_status = mp_status
    p.mp_payment_id = None
    p.pedido_id = 1
    return p


def _mp_get(status: str = "approved"):
    """SDK mock cuyo payment().get() devuelve un pago con el status dado."""
    sdk = MagicMock()
    sdk.payment.return_value.get.return_value = {
        "status": 200,
        "response": {
            "id": 9901,
            "status": status,
            "status_detail": "accredited",
            "external_reference": "1",
            "payment_method_id": "visa",
            "transaction_amount": 500.0,
        },
    }
    return sdk


# ──────────────────────────────────────────────────────────────────────────────
# validar_firma_webhook
# ──────────────────────────────────────────────────────────────────────────────

class TestValidarFirmaWebhook:

    def test_firma_valida(self, monkeypatch):
        monkeypatch.setattr(settings, "MP_WEBHOOK_SECRET", _SECRET)
        xsig = _firma_valida("123456", "req-abc")
        assert service.validar_firma_webhook(xsig, "req-abc", "123456") is True

    def test_firma_alterada_rechazada(self, monkeypatch):
        monkeypatch.setattr(settings, "MP_WEBHOOK_SECRET", _SECRET)
        assert service.validar_firma_webhook("ts=1700000000,v1=deadbeef", "req-abc", "123456") is False

    def test_request_id_distinto_rechazado(self, monkeypatch):
        monkeypatch.setattr(settings, "MP_WEBHOOK_SECRET", _SECRET)
        xsig = _firma_valida("123456", "req-abc")
        assert service.validar_firma_webhook(xsig, "OTRO-request-id", "123456") is False

    def test_sin_secret_configurado_rechaza(self, monkeypatch):
        monkeypatch.setattr(settings, "MP_WEBHOOK_SECRET", "")
        xsig = _firma_valida("123456", "req-abc")
        assert service.validar_firma_webhook(xsig, "req-abc", "123456") is False

    def test_header_ausente_rechaza(self, monkeypatch):
        monkeypatch.setattr(settings, "MP_WEBHOOK_SECRET", _SECRET)
        assert service.validar_firma_webhook(None, "req-abc", "123456") is False


# ──────────────────────────────────────────────────────────────────────────────
# procesar_webhook
# ──────────────────────────────────────────────────────────────────────────────

class TestProcesarWebhook:

    @patch("app.modules.pagos.service.validar_firma_webhook", return_value=False)
    def test_firma_invalida_lanza_401(self, _mock_firma):
        uow = make_uow()
        with pytest.raises(HTTPException) as exc:
            service.procesar_webhook(
                uow, topic="payment", data_id="9901",
                x_signature="bad", x_request_id="r",
            )
        assert exc.value.status_code == 401
        assert exc.value.detail["code"] == "INVALID_SIGNATURE"

    @patch("app.modules.pagos.service.validar_firma_webhook", return_value=True)
    def test_topic_no_payment_se_ignora(self, _mock_firma):
        uow = make_uow()
        result = service.procesar_webhook(
            uow, topic="merchant_order", data_id="1",
            x_signature="x", x_request_id="r",
        )
        assert result["action"] == "ignored"

    @patch("app.modules.pedidos.service.confirmar_pago_mp")
    @patch("mercadopago.SDK")
    @patch("app.modules.pagos.service.validar_firma_webhook", return_value=True)
    def test_approved_confirma_pedido(self, _firma, mock_sdk, mock_confirmar):
        mock_sdk.return_value = _mp_get("approved")
        uow = make_uow()
        pago = _mock_pago("pending")
        uow.pagos.get_by_external_reference.return_value = pago

        result = service.procesar_webhook(
            uow, topic="payment", data_id="9901",
            x_signature="x", x_request_id="r",
        )

        assert result["action"] == "confirmed"
        assert result["pedido_id"] == 1
        assert pago.mp_status == "approved"
        assert pago.mp_payment_id == 9901
        mock_confirmar.assert_called_once_with(uow, 1)

    @patch("app.modules.pedidos.service.cancelar_pago_mp")
    @patch("mercadopago.SDK")
    @patch("app.modules.pagos.service.validar_firma_webhook", return_value=True)
    def test_rejected_cancela_pedido(self, _firma, mock_sdk, mock_cancelar):
        mock_sdk.return_value = _mp_get("rejected")
        uow = make_uow()
        uow.pagos.get_by_external_reference.return_value = _mock_pago("pending")

        result = service.procesar_webhook(
            uow, topic="payment", data_id="9901",
            x_signature="x", x_request_id="r",
        )

        assert result["action"] == "cancelled"
        mock_cancelar.assert_called_once_with(uow, 1)

    @patch("app.modules.pedidos.service.confirmar_pago_mp")
    @patch("mercadopago.SDK")
    @patch("app.modules.pagos.service.validar_firma_webhook", return_value=True)
    def test_idempotente_no_reconfirma(self, _firma, mock_sdk, mock_confirmar):
        """Webhook duplicado: el Pago ya está approved ⇒ no se vuelve a confirmar."""
        mock_sdk.return_value = _mp_get("approved")
        uow = make_uow()
        uow.pagos.get_by_external_reference.return_value = _mock_pago("approved")

        result = service.procesar_webhook(
            uow, topic="payment", data_id="9901",
            x_signature="x", x_request_id="r",
        )

        assert result["action"] == "noop"
        mock_confirmar.assert_not_called()

    @patch("mercadopago.SDK")
    @patch("app.modules.pagos.service.validar_firma_webhook", return_value=True)
    def test_pago_inexistente_se_ignora(self, _firma, mock_sdk):
        mock_sdk.return_value = _mp_get("approved")
        uow = make_uow()
        uow.pagos.get_by_external_reference.return_value = None

        result = service.procesar_webhook(
            uow, topic="payment", data_id="9901",
            x_signature="x", x_request_id="r",
        )
        assert result["action"] == "ignored"


# ──────────────────────────────────────────────────────────────────────────────
# crear_preferencia_y_pago
# ──────────────────────────────────────────────────────────────────────────────

class TestCrearPreferenciaYPago:

    @staticmethod
    def _pedido(id: int = 1, total=Decimal("500.00"), costo_envio=Decimal("0.00")):
        p = MagicMock()
        p.id = id
        p.total = total
        p.costo_envio = costo_envio
        return p

    @staticmethod
    def _detalle():
        d = MagicMock()
        d.producto_id = 1
        d.nombre_snapshot = "Burger"
        d.cantidad = 1
        d.precio_snapshot = Decimal("500.00")
        return d

    @staticmethod
    def _sdk_exitoso():
        sdk = MagicMock()
        sdk.preference.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": "pref_test_abc",
                "init_point": "https://mp.com/checkout?pref_id=pref_test_abc",
            },
        }
        return sdk

    @patch("mercadopago.SDK")
    def test_devuelve_init_point(self, mock_sdk):
        mock_sdk.return_value = self._sdk_exitoso()
        uow = make_uow()
        init_point = service.crear_preferencia_y_pago(uow, self._pedido(), [self._detalle()])
        assert init_point == "https://mp.com/checkout?pref_id=pref_test_abc"

    @patch("mercadopago.SDK")
    def test_persiste_pago_con_idempotency_key(self, mock_sdk):
        mock_sdk.return_value = self._sdk_exitoso()
        uow = make_uow()
        service.crear_preferencia_y_pago(uow, self._pedido(), [self._detalle()])

        uow.pagos.add.assert_called_once()
        pago = uow.pagos.add.call_args[0][0]
        assert pago.external_reference == "1"
        assert pago.idempotency_key  # no vacío
        assert pago.transaction_amount == Decimal("500.00")
        assert pago.mp_status == "pending"

    @patch("mercadopago.SDK")
    def test_envia_header_idempotencia_a_mp(self, mock_sdk):
        sdk = self._sdk_exitoso()
        mock_sdk.return_value = sdk
        uow = make_uow()
        service.crear_preferencia_y_pago(uow, self._pedido(), [self._detalle()])

        # create(preference_data, request_options) — el 2do arg lleva el header
        _, kwargs = sdk.preference.return_value.create.call_args, sdk.preference.return_value.create.call_args
        call = sdk.preference.return_value.create.call_args
        request_options = call[0][1] if len(call[0]) > 1 else call[1].get("request_options")
        assert request_options is not None
        assert "x-idempotency-key" in request_options.custom_headers

    @patch("app.modules.pagos.service._get_ngrok_url", return_value=None)
    @patch("mercadopago.SDK")
    def test_notification_url_desde_env(self, mock_sdk, _ngrok, monkeypatch):
        """Sin ngrok, usa MP_NOTIFICATION_URL del .env como notification_url."""
        sdk = self._sdk_exitoso()
        mock_sdk.return_value = sdk
        monkeypatch.setattr(settings, "MP_NOTIFICATION_URL", "https://midominio.com/api/v1/pagos/webhook")
        uow = make_uow()

        service.crear_preferencia_y_pago(uow, self._pedido(), [self._detalle()])

        preference_data = sdk.preference.return_value.create.call_args[0][0]
        assert preference_data["notification_url"] == "https://midominio.com/api/v1/pagos/webhook"

    @patch("app.modules.pagos.service._get_ngrok_url", return_value="https://abc123.ngrok.io")
    @patch("mercadopago.SDK")
    def test_notification_url_prioriza_ngrok(self, mock_sdk, _ngrok, monkeypatch):
        """Con ngrok activo, el webhook apunta al túnel (ignora MP_NOTIFICATION_URL)."""
        sdk = self._sdk_exitoso()
        mock_sdk.return_value = sdk
        monkeypatch.setattr(settings, "MP_NOTIFICATION_URL", "https://midominio.com/api/v1/pagos/webhook")
        uow = make_uow()

        service.crear_preferencia_y_pago(uow, self._pedido(), [self._detalle()])

        preference_data = sdk.preference.return_value.create.call_args[0][0]
        assert preference_data["notification_url"] == "https://abc123.ngrok.io/api/v1/pagos/webhook"

    @patch("app.modules.pagos.service._get_ngrok_url", return_value=None)
    @patch("mercadopago.SDK")
    def test_sin_url_omite_notification_url(self, mock_sdk, _ngrok, monkeypatch):
        """Sin ngrok ni env → no se envía notification_url (cae a la config del panel)."""
        sdk = self._sdk_exitoso()
        mock_sdk.return_value = sdk
        monkeypatch.setattr(settings, "MP_NOTIFICATION_URL", "")
        uow = make_uow()

        service.crear_preferencia_y_pago(uow, self._pedido(), [self._detalle()])

        preference_data = sdk.preference.return_value.create.call_args[0][0]
        assert "notification_url" not in preference_data

    @patch("app.modules.pagos.service._get_ngrok_url", return_value="https://abc123.ngrok.io")
    @patch("mercadopago.SDK")
    def test_back_urls_pasan_por_el_redirect_del_backend(self, mock_sdk, _ngrok):
        """Con ngrok, los back_urls apuntan al endpoint redirect del backend (HTTPS válida
        para MP). Ese endpoint hace luego un 302 al frontend (/pedido-exitoso)."""
        sdk = self._sdk_exitoso()
        mock_sdk.return_value = sdk
        uow = make_uow()
        pedido = self._pedido()

        service.crear_preferencia_y_pago(uow, pedido, [self._detalle()])

        pd = sdk.preference.return_value.create.call_args[0][0]
        for key in ("success", "failure", "pending"):
            url = pd["back_urls"][key]
            assert url == f"https://abc123.ngrok.io/api/v1/pagos/redirect/{pedido.id}/{key}"

    @patch("app.modules.pagos.service._get_ngrok_url", return_value=None)
    @patch("mercadopago.SDK")
    def test_auto_return_omitido_sin_ngrok(self, mock_sdk, _ngrok):
        """auto_return requiere back_urls HTTPS (las provee ngrok). Sin ngrok corriendo,
        los back_urls caen a localhost y auto_return se omite (MP lo rechazaría)."""
        sdk = self._sdk_exitoso()
        mock_sdk.return_value = sdk
        uow = make_uow()

        service.crear_preferencia_y_pago(uow, self._pedido(), [self._detalle()])

        pd = sdk.preference.return_value.create.call_args[0][0]
        assert "auto_return" not in pd

    @patch("app.modules.pagos.service._get_ngrok_url", return_value="https://abc123.ngrok.io")
    @patch("mercadopago.SDK")
    def test_auto_return_presente_con_ngrok(self, mock_sdk, _ngrok):
        """Con ngrok (back_urls HTTPS), se incluye auto_return='approved'."""
        sdk = self._sdk_exitoso()
        mock_sdk.return_value = sdk
        uow = make_uow()

        service.crear_preferencia_y_pago(uow, self._pedido(), [self._detalle()])

        pd = sdk.preference.return_value.create.call_args[0][0]
        assert pd.get("auto_return") == "approved"

    @patch("app.modules.pagos.service._get_ngrok_url", return_value=None)
    @patch("mercadopago.SDK")
    def test_incluye_envio_como_item(self, mock_sdk, _ngrok):
        """El costo de envío se agrega como ítem → MP cobra el total del pedido."""
        sdk = self._sdk_exitoso()
        mock_sdk.return_value = sdk
        uow = make_uow()
        pedido = self._pedido(total=Decimal("550.00"), costo_envio=Decimal("50.00"))

        service.crear_preferencia_y_pago(uow, pedido, [self._detalle()])

        items = sdk.preference.return_value.create.call_args[0][0]["items"]
        envios = [i for i in items if i["title"] == "Envío"]
        assert len(envios) == 1
        assert envios[0]["unit_price"] == 50.0
        suma = sum(i["unit_price"] * i["quantity"] for i in items)
        assert suma == 550.0  # coincide con pedido.total

    @patch("app.modules.pagos.service._get_ngrok_url", return_value=None)
    @patch("mercadopago.SDK")
    def test_sin_envio_no_agrega_item(self, mock_sdk, _ngrok):
        """Retiro en local (costo_envio=0) → no se agrega ítem de envío."""
        sdk = self._sdk_exitoso()
        mock_sdk.return_value = sdk
        uow = make_uow()
        pedido = self._pedido(total=Decimal("500.00"), costo_envio=Decimal("0.00"))

        service.crear_preferencia_y_pago(uow, pedido, [self._detalle()])

        items = sdk.preference.return_value.create.call_args[0][0]["items"]
        assert all(i["title"] != "Envío" for i in items)

    @patch("mercadopago.SDK")
    def test_error_sdk_lanza_502(self, mock_sdk):
        sdk = MagicMock()
        sdk.preference.return_value.create.return_value = {
            "status": 400,
            "response": {"message": "Invalid credentials"},
        }
        mock_sdk.return_value = sdk
        uow = make_uow()

        with pytest.raises(HTTPException) as exc:
            service.crear_preferencia_y_pago(uow, self._pedido(), [self._detalle()])

        assert exc.value.status_code == 502
        assert exc.value.detail["code"] == "MP_PREFERENCE_ERROR"
