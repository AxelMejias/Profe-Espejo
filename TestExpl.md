# TestExpl — Explicación de Tests: Integración MercadoPago

## Contexto

La integración con MercadoPago Checkout Pro está implementada en `app/modules/pedidos/service.py`.
El módulo `pagos/` existe pero sigue siendo un placeholder vacío; toda la lógica real de pago vive en `pedidos`.

Hay dos funciones que requieren tests:

| Función | Qué hace |
|---|---|
| `_crear_preferencia_mp(pedido, detalles)` | Crea una preferencia en la API de MP al crear un pedido con MERCADOPAGO. Devuelve `(preference_id, init_point)`. |
| `verificar_pago_mp(uow, pedido_id, usuario_id)` | Consulta la API de pagos de MP para saber si el pedido fue pagado. Lo llama el frontend al cerrar el popup de checkout. |

---

## Estrategia de tests

Los tests **no** usan base de datos real. Siguen la misma estrategia del resto del proyecto:

- El **UoW** (Unit of Work) es un `MagicMock` que simula todos los repositorios.
- El **SDK de MercadoPago** se mockea con `unittest.mock.patch("mercadopago.SDK")` para que no haya llamadas reales a la API de MP.
- No se necesita access token válido: el mock del SDK acepta cualquier argumento.

---

## Tests nuevos en `tests/test_pedidos_service.py`

Se agregaron **10 tests** organizados en dos clases.

---

### Clase `TestCrearPedidoMP` (4 tests)

Cubre el comportamiento de `crear_pedido` cuando `forma_pago_codigo = "MERCADOPAGO"`.

---

#### `test_mp_llama_sdk_y_crea_preferencia`

**Qué verifica:** Cuando se crea un pedido con MERCADOPAGO, el servicio debe:
1. Instanciar `mercadopago.SDK` (con el access token configurado).
2. Llamar a `sdk.preference().create(...)` exactamente una vez.

**Setup:** SDK mockeado que responde `status: 201` con `id` e `init_point`.

**Resultado esperado:** `mock_sdk_class.assert_called_once()` pasa, `create.assert_called_once()` pasa.

**Por qué importa:** Garantiza que el flujo de creación de preferencia se ejecuta; sin este test, podría silenciarse silenciosamente si se rompe la condición `if data.forma_pago_codigo == "MERCADOPAGO"`.

---

#### `test_mp_guarda_preference_id_en_pedido`

**Qué verifica:** El `preference_id` devuelto por MP se almacena en `pedido.mp_preference_id` antes de persistir el pedido por segunda vez.

**Setup:** SDK mockeado devuelve `"id": "pref_test_abc"`. Se captura el argumento del último `uow.pedidos.add()`.

**Resultado esperado:** `pedido_persistido.mp_preference_id == "pref_test_abc"`.

**Por qué importa:** Sin este campo no es posible consultar el estado del pago ni reconciliar webhooks de MP con el pedido.

---

#### `test_mp_devuelve_init_point_en_response`

**Qué verifica:** El `PedidoResponse` retornado por `crear_pedido` incluye el `init_point` (URL del checkout de MP).

**Setup:** SDK mockeado devuelve un `init_point` de prueba.

**Resultado esperado:** `result.init_point == "https://www.mercadopago.com.ar/checkout/..."`.

**Por qué importa:** El frontend usa este campo para abrir el popup de pago. Si no se devuelve, el cliente no puede completar el pago.

---

#### `test_mp_error_de_sdk_lanza_502`

**Qué verifica:** Si la API de MP devuelve un status de error (ej. `400`), el servicio debe lanzar `HTTP 502 Bad Gateway`.

**Setup:** SDK mockeado responde `status: 400`.

**Resultado esperado:**
```
HTTPException(status_code=502, detail={"code": "MP_PREFERENCE_ERROR", ...})
```

**Por qué importa:** El cliente no debe ver un 500 genérico. El 502 es el código correcto para "el servicio externo falló", y el código de error permite al frontend mostrar un mensaje útil.

---

### Clase `TestVerificarPagoMP` (6 tests)

Cubre `verificar_pago_mp`, que el frontend llama al cerrar el popup de checkout para saber si el pago fue procesado.

---

#### `test_pago_aprobado`

**Qué verifica:** Cuando MP devuelve un pago con `status: "approved"`, la función retorna ese estado y el `payment_id`.

**Resultado esperado:**
```python
{"status": "approved", "payment_id": 9901}
```

---

#### `test_pago_pendiente`

**Qué verifica:** Cuando MP devuelve `status: "pending"` (pago iniciado pero no confirmado), la función lo propaga tal cual.

**Resultado esperado:**
```python
{"status": "pending", "payment_id": 9902}
```

**Por qué importa:** El frontend distingue entre `approved` y `pending` para mostrar mensajes distintos al usuario.

---

#### `test_sin_pagos_retorna_not_found`

**Qué verifica:** Si MP responde `200` pero con `results: []` (el cliente no llegó a pagar), la función devuelve `not_found`.

**Resultado esperado:**
```python
{"status": "not_found", "payment_id": None}
```

**Por qué importa:** Es el caso más común cuando el usuario abre el popup pero lo cierra sin pagar.

---

#### `test_api_mp_falla_retorna_not_found`

**Qué verifica:** Si la API de MP devuelve un status de error (ej. `500`), la función **no lanza excepción** sino que devuelve `not_found` con `payment_id: null`.

**Resultado esperado:**
```python
{"status": "not_found", "payment_id": None}
```

**Por qué importa:** Un fallo temporal de MP no debe romper el flujo del frontend. El cliente puede reintentar más tarde.

---

#### `test_pedido_no_usa_mp_lanza_400`

**Qué verifica:** Si se intenta verificar el pago de un pedido cuya forma de pago **no** es MERCADOPAGO (ej. EFECTIVO), el servicio lanza `HTTP 400`.

**Resultado esperado:**
```
HTTPException(status_code=400, detail={"code": "NOT_MP_PAYMENT", ...})
```

**Por qué importa:** Previene llamadas innecesarias a la API de MP y da un mensaje claro si el frontend llama al endpoint equivocado.

---

#### `test_pedido_no_encontrado_lanza_404`

**Qué verifica:** Si el `pedido_id` no existe o no pertenece al usuario, el servicio lanza `HTTP 404`.

**Resultado esperado:**
```
HTTPException(status_code=404, detail={"code": "PEDIDO_NOT_FOUND", ...})
```

**Por qué importa:** Control de acceso: un cliente no puede consultar el estado de pago de un pedido ajeno.

---

## Resumen de cobertura

| # | Test | Función | Resultado esperado |
|---|------|---------|-------------------|
| 1 | `test_mp_llama_sdk_y_crea_preferencia` | `crear_pedido` | SDK instanciado + `create()` llamado |
| 2 | `test_mp_guarda_preference_id_en_pedido` | `crear_pedido` | `pedido.mp_preference_id = "pref_test_abc"` |
| 3 | `test_mp_devuelve_init_point_en_response` | `crear_pedido` | `result.init_point` = URL de MP |
| 4 | `test_mp_error_de_sdk_lanza_502` | `crear_pedido` | `HTTPException 502 MP_PREFERENCE_ERROR` |
| 5 | `test_pago_aprobado` | `verificar_pago_mp` | `{"status": "approved", "payment_id": 9901}` |
| 6 | `test_pago_pendiente` | `verificar_pago_mp` | `{"status": "pending", "payment_id": 9902}` |
| 7 | `test_sin_pagos_retorna_not_found` | `verificar_pago_mp` | `{"status": "not_found", "payment_id": None}` |
| 8 | `test_api_mp_falla_retorna_not_found` | `verificar_pago_mp` | `{"status": "not_found", "payment_id": None}` |
| 9 | `test_pedido_no_usa_mp_lanza_400` | `verificar_pago_mp` | `HTTPException 400 NOT_MP_PAYMENT` |
| 10 | `test_pedido_no_encontrado_lanza_404` | `verificar_pago_mp` | `HTTPException 404 PEDIDO_NOT_FOUND` |

**Total de tests en el proyecto después de estos cambios: 171**
(161 previos + 10 nuevos de MercadoPago)

---

## Cómo correr solo los tests de MP

```bash
# Solo la clase de crear pedido con MP
pytest tests/test_pedidos_service.py::TestCrearPedidoMP -v

# Solo la clase de verificar pago
pytest tests/test_pedidos_service.py::TestVerificarPagoMP -v

# Todos los tests de pedidos
pytest tests/test_pedidos_service.py -v
```
