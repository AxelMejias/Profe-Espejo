"""
test_pedidos_service.py — Tests para app/modules/pedidos/service.py

El módulo más crítico del proyecto. Cubre:
  - avanzar_estado: todas las transiciones válidas, errores del FSM, permisos
  - cancelar_pedido_cliente: estados permitidos, motivo obligatorio
  - crear_pedido: snapshot, stock, totales, forma de pago, dirección
  - get_all: filtrado por rol (CLIENT vs STAFF)
  - get_by_id: ownership CLIENT vs STAFF
"""
from decimal import Decimal
from unittest.mock import MagicMock, call, patch
import pytest
from fastapi import HTTPException

from app.modules.pedidos import service
from app.modules.pedidos.schemas import PedidoCreate, ItemPedidoRequest
from tests.conftest import make_uow, mock_pedido, mock_producto


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────────────

def _uow_con_pedido(estado: str = "PENDIENTE", usuario_id: int = 1):
    """UoW que devuelve un pedido mockeado con el estado dado."""
    uow = make_uow()
    pedido = mock_pedido(estado_codigo=estado, usuario_id=usuario_id)
    uow.pedidos.get_by_id.return_value = pedido
    uow.pedidos.get_by_id_for_user.return_value = pedido
    uow.estados_pedido.get_by_codigo.return_value = MagicMock()  # estado existe
    uow.pedidos.get_detalles.return_value = []
    uow.pedidos.add.return_value = pedido
    return uow, pedido


# ──────────────────────────────────────────────────────────────────────────────
# avanzar_estado
# ──────────────────────────────────────────────────────────────────────────────

class TestAvanzarEstado:

    # ── Flujo principal válido ────────────────────────────────────────────────

    def test_pendiente_a_confirmado(self):
        uow, pedido = _uow_con_pedido("PENDIENTE")
        result = service.avanzar_estado(uow, 1, "CONFIRMADO", None, 99, ["ADMIN"])
        assert pedido.estado_codigo == "CONFIRMADO"
        uow.pedidos.add_historial.assert_called_once()

    def test_confirmado_a_en_prep(self):
        uow, pedido = _uow_con_pedido("CONFIRMADO")
        service.avanzar_estado(uow, 1, "EN_PREP", None, 99, ["ADMIN"])
        assert pedido.estado_codigo == "EN_PREP"

    def test_en_prep_a_entregado(self):
        uow, pedido = _uow_con_pedido("EN_PREP")
        service.avanzar_estado(uow, 1, "ENTREGADO", None, 99, ["PEDIDOS"])
        assert pedido.estado_codigo == "ENTREGADO"

    def test_cancelar_desde_pendiente(self):
        uow, pedido = _uow_con_pedido("PENDIENTE")
        service.avanzar_estado(uow, 1, "CANCELADO", "Motivo válido", 99, ["ADMIN"])
        assert pedido.estado_codigo == "CANCELADO"

    def test_cancelar_desde_confirmado(self):
        uow, pedido = _uow_con_pedido("CONFIRMADO")
        service.avanzar_estado(uow, 1, "CANCELADO", "Motivo", 99, ["ADMIN"])
        assert pedido.estado_codigo == "CANCELADO"

    def test_cancelar_desde_en_prep(self):
        uow, pedido = _uow_con_pedido("EN_PREP")
        service.avanzar_estado(uow, 1, "CANCELADO", "Motivo", 99, ["ADMIN"])
        assert pedido.estado_codigo == "CANCELADO"

    # ── Registro en historial ─────────────────────────────────────────────────

    def test_guarda_estado_desde_en_historial(self):
        uow, pedido = _uow_con_pedido("PENDIENTE")
        service.avanzar_estado(uow, 1, "CONFIRMADO", None, 99, ["ADMIN"])

        historial_entry = uow.pedidos.add_historial.call_args[0][0]
        assert historial_entry.estado_desde == "PENDIENTE"
        assert historial_entry.estado_hacia == "CONFIRMADO"
        assert historial_entry.usuario_id == 99

    # ── Errores del FSM ───────────────────────────────────────────────────────

    def test_pedido_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.pedidos.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.avanzar_estado(uow, 999, "CONFIRMADO", None, 1, ["ADMIN"])

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "PEDIDO_NOT_FOUND"

    def test_estado_destino_no_existe_lanza_404(self):
        uow, _ = _uow_con_pedido("PENDIENTE")
        uow.estados_pedido.get_by_codigo.return_value = None  # estado no existe

        with pytest.raises(HTTPException) as exc:
            service.avanzar_estado(uow, 1, "ESTADO_INVENTADO", None, 1, ["ADMIN"])

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "ESTADO_NOT_FOUND"

    def test_transicion_invalida_lanza_409(self):
        """No se puede ir de PENDIENTE → ENTREGADO (saltando estados)."""
        uow, _ = _uow_con_pedido("PENDIENTE")

        with pytest.raises(HTTPException) as exc:
            service.avanzar_estado(uow, 1, "ENTREGADO", None, 1, ["ADMIN"])

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "INVALID_TRANSITION"

    def test_estado_terminal_entregado_lanza_409(self):
        """ENTREGADO es terminal — no admite transiciones."""
        uow, _ = _uow_con_pedido("ENTREGADO")

        with pytest.raises(HTTPException) as exc:
            service.avanzar_estado(uow, 1, "PENDIENTE", None, 1, ["ADMIN"])

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "INVALID_TRANSITION"

    def test_estado_terminal_cancelado_lanza_409(self):
        """CANCELADO es terminal — no admite transiciones."""
        uow, _ = _uow_con_pedido("CANCELADO")

        with pytest.raises(HTTPException) as exc:
            service.avanzar_estado(uow, 1, "PENDIENTE", None, 1, ["ADMIN"])

        assert exc.value.status_code == 409

    # ── RN-05: motivo obligatorio para cancelar ───────────────────────────────

    def test_cancelar_sin_motivo_lanza_400(self):
        uow, _ = _uow_con_pedido("PENDIENTE")

        with pytest.raises(HTTPException) as exc:
            service.avanzar_estado(uow, 1, "CANCELADO", None, 1, ["ADMIN"])

        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "MOTIVO_REQUIRED"

    def test_cancelar_motivo_solo_espacios_lanza_400(self):
        uow, _ = _uow_con_pedido("PENDIENTE")

        with pytest.raises(HTTPException) as exc:
            service.avanzar_estado(uow, 1, "CANCELADO", "   ", 1, ["ADMIN"])

        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "MOTIVO_REQUIRED"

    def test_avanzar_sin_cancelar_no_requiere_motivo(self):
        """Para transiciones que no son CANCELADO, el motivo es opcional."""
        uow, pedido = _uow_con_pedido("PENDIENTE")
        service.avanzar_estado(uow, 1, "CONFIRMADO", None, 1, ["ADMIN"])  # No lanza
        assert pedido.estado_codigo == "CONFIRMADO"

    # ── Permisos RBAC ─────────────────────────────────────────────────────────

    def test_rol_sin_permisos_lanza_403(self):
        uow, _ = _uow_con_pedido("PENDIENTE")

        with pytest.raises(HTTPException) as exc:
            service.avanzar_estado(uow, 1, "CONFIRMADO", None, 1, ["CLIENT"])

        assert exc.value.status_code == 403
        assert exc.value.detail["code"] == "FORBIDDEN"

    def test_rol_stock_no_puede_avanzar(self):
        uow, _ = _uow_con_pedido("PENDIENTE")

        with pytest.raises(HTTPException) as exc:
            service.avanzar_estado(uow, 1, "CONFIRMADO", None, 1, ["STOCK"])

        assert exc.value.status_code == 403

    def test_admin_puede_avanzar(self):
        uow, pedido = _uow_con_pedido("PENDIENTE")
        service.avanzar_estado(uow, 1, "CONFIRMADO", None, 1, ["ADMIN"])
        assert pedido.estado_codigo == "CONFIRMADO"

    def test_pedidos_puede_avanzar(self):
        uow, pedido = _uow_con_pedido("CONFIRMADO")
        service.avanzar_estado(uow, 1, "EN_PREP", None, 1, ["PEDIDOS"])
        assert pedido.estado_codigo == "EN_PREP"


# ──────────────────────────────────────────────────────────────────────────────
# cancelar_pedido_cliente
# ──────────────────────────────────────────────────────────────────────────────

class TestCancelarPedidoCliente:

    def _setup(self, estado: str):
        uow = make_uow()
        pedido = mock_pedido(estado_codigo=estado, usuario_id=5)
        uow.pedidos.get_by_id_for_user.return_value = pedido
        uow.pedidos.get_detalles.return_value = []
        uow.pedidos.add.return_value = pedido
        return uow, pedido

    def test_cancelar_desde_pendiente(self):
        uow, pedido = self._setup("PENDIENTE")
        service.cancelar_pedido_cliente(uow, 1, "No lo quiero", cliente_user_id=5)
        assert pedido.estado_codigo == "CANCELADO"

    def test_cancelar_desde_confirmado(self):
        uow, pedido = self._setup("CONFIRMADO")
        service.cancelar_pedido_cliente(uow, 1, "Cambié de opinión", cliente_user_id=5)
        assert pedido.estado_codigo == "CANCELADO"

    def test_no_puede_cancelar_desde_en_prep(self):
        uow, _ = self._setup("EN_PREP")

        with pytest.raises(HTTPException) as exc:
            service.cancelar_pedido_cliente(uow, 1, "Motivo", cliente_user_id=5)

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "INVALID_TRANSITION"

    def test_no_puede_cancelar_entregado(self):
        uow, _ = self._setup("ENTREGADO")

        with pytest.raises(HTTPException) as exc:
            service.cancelar_pedido_cliente(uow, 1, "Motivo", cliente_user_id=5)

        assert exc.value.status_code == 409

    def test_motivo_vacio_lanza_400(self):
        uow, _ = self._setup("PENDIENTE")

        with pytest.raises(HTTPException) as exc:
            service.cancelar_pedido_cliente(uow, 1, "", cliente_user_id=5)

        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "MOTIVO_REQUIRED"

    def test_pedido_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.pedidos.get_by_id_for_user.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.cancelar_pedido_cliente(uow, 999, "Motivo", cliente_user_id=5)

        assert exc.value.status_code == 404

    def test_registra_historial_con_motivo(self):
        uow, pedido = self._setup("PENDIENTE")
        service.cancelar_pedido_cliente(uow, 1, "No tengo hambre", cliente_user_id=5)

        entry = uow.pedidos.add_historial.call_args[0][0]
        assert entry.motivo == "No tengo hambre"
        assert entry.estado_hacia == "CANCELADO"
        assert entry.usuario_id == 5


# ──────────────────────────────────────────────────────────────────────────────
# crear_pedido
# ──────────────────────────────────────────────────────────────────────────────

class TestCrearPedido:

    def _setup_uow_crear(self, stock: int = 10, disponible: bool = True):
        uow = make_uow()

        # Forma de pago habilitada
        forma_pago = MagicMock()
        forma_pago.habilitado = True
        forma_pago.codigo = "EFECTIVO"
        uow.formas_pago.get_by_codigo.return_value = forma_pago

        # Estado PENDIENTE existe
        uow.estados_pedido.get_by_codigo.return_value = MagicMock()

        # Producto disponible con stock
        producto = mock_producto(stock_cantidad=stock, disponible=disponible)
        uow.productos.get_by_id.return_value = producto

        # Pedido creado con detalles vacíos para _build_response
        pedido = mock_pedido()
        uow.pedidos.add.return_value = pedido
        uow.pedidos.get_detalles.return_value = []

        return uow, producto, pedido

    @staticmethod
    def _set_pedido_id(p):
        """Side effect para uow.pedidos.add: asigna id al pedido como haría el ORM flush."""
        p.id = 1
        return p

    def test_crear_pedido_exitoso(self):
        uow, producto, pedido = self._setup_uow_crear(stock=5)
        uow.pedidos.add.side_effect = self._set_pedido_id

        data = PedidoCreate(
            forma_pago_codigo="EFECTIVO",
            items=[ItemPedidoRequest(producto_id=1, cantidad=2)],
        )
        service.crear_pedido(uow, data, usuario_id=1)

        uow.pedidos.add.assert_called_once()
        uow.pedidos.add_historial.assert_called_once()

    def test_descuenta_stock(self):
        """El stock del insumo se reduce según los links producto→insumo."""
        uow, _, _ = self._setup_uow_crear(stock=10)
        uow.pedidos.add.side_effect = self._set_pedido_id

        ing = MagicMock()
        ing.stock_cantidad = Decimal("10")
        link = MagicMock()
        link.ingrediente_id = 99
        link.cantidad = Decimal("1")  # 1 unidad de insumo por unidad de producto
        uow.productos.get_ingrediente_links.return_value = [link]
        uow.ingredientes.get_by_id.return_value = ing

        data = PedidoCreate(
            forma_pago_codigo="EFECTIVO",
            items=[ItemPedidoRequest(producto_id=1, cantidad=3)],
        )
        service.crear_pedido(uow, data, usuario_id=1)

        assert ing.stock_cantidad == Decimal("7")  # 10 - (1 × 3)

    def test_primer_historial_estado_desde_null(self):
        """RN-02: el primer historial tiene estado_desde=None."""
        uow, _, _ = self._setup_uow_crear()
        uow.pedidos.add.side_effect = self._set_pedido_id

        data = PedidoCreate(
            forma_pago_codigo="EFECTIVO",
            items=[ItemPedidoRequest(producto_id=1, cantidad=1)],
        )
        service.crear_pedido(uow, data, usuario_id=1)

        entry = uow.pedidos.add_historial.call_args[0][0]
        assert entry.estado_desde is None
        assert entry.estado_hacia == "PENDIENTE"

    def test_costo_envio_por_defecto(self):
        """Con dirección de entrega, el costo de envío por defecto es $50."""
        uow, producto, _ = self._setup_uow_crear()
        producto.precio = Decimal("100.00")
        uow.direcciones.get_by_id_for_user.return_value = MagicMock()  # dirección válida

        pedido_creado = None
        def capture_pedido(p):
            nonlocal pedido_creado
            pedido_creado = p
            p.id = 1
            return p
        uow.pedidos.add.side_effect = capture_pedido

        data = PedidoCreate(
            forma_pago_codigo="EFECTIVO",
            direccion_id=1,  # con dirección se activa el costo de envío
            items=[ItemPedidoRequest(producto_id=1, cantidad=2)],
        )
        service.crear_pedido(uow, data, usuario_id=1)

        assert pedido_creado.costo_envio == Decimal("50.00")

    def test_forma_pago_no_encontrada_lanza_404(self):
        uow = make_uow()
        uow.formas_pago.get_by_codigo.return_value = None

        data = PedidoCreate(
            forma_pago_codigo="INEXISTENTE",
            items=[ItemPedidoRequest(producto_id=1, cantidad=1)],
        )
        with pytest.raises(HTTPException) as exc:
            service.crear_pedido(uow, data, usuario_id=1)

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "FORMA_PAGO_NOT_FOUND"

    def test_forma_pago_deshabilitada_lanza_409(self):
        uow = make_uow()
        forma_pago = MagicMock()
        forma_pago.habilitado = False
        uow.formas_pago.get_by_codigo.return_value = forma_pago

        data = PedidoCreate(
            forma_pago_codigo="MERCADOPAGO",
            items=[ItemPedidoRequest(producto_id=1, cantidad=1)],
        )
        with pytest.raises(HTTPException) as exc:
            service.crear_pedido(uow, data, usuario_id=1)

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "FORMA_PAGO_DISABLED"

    def test_producto_no_encontrado_lanza_404(self):
        uow = make_uow()
        forma_pago = MagicMock()
        forma_pago.habilitado = True
        uow.formas_pago.get_by_codigo.return_value = forma_pago
        uow.estados_pedido.get_by_codigo.return_value = MagicMock()
        uow.productos.get_by_id.return_value = None  # producto inexistente

        data = PedidoCreate(
            forma_pago_codigo="EFECTIVO",
            items=[ItemPedidoRequest(producto_id=999, cantidad=1)],
        )
        with pytest.raises(HTTPException) as exc:
            service.crear_pedido(uow, data, usuario_id=1)

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "PRODUCTO_NOT_FOUND"

    def test_producto_no_disponible_lanza_409(self):
        uow, _, _ = self._setup_uow_crear(disponible=False)

        data = PedidoCreate(
            forma_pago_codigo="EFECTIVO",
            items=[ItemPedidoRequest(producto_id=1, cantidad=1)],
        )
        with pytest.raises(HTTPException) as exc:
            service.crear_pedido(uow, data, usuario_id=1)

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "PRODUCTO_NO_DISPONIBLE"

    def test_stock_insuficiente_lanza_409(self):
        """El check de stock falla cuando el insumo no alcanza para el pedido."""
        uow, _, _ = self._setup_uow_crear(stock=2)

        # Configurar link e insumo con stock insuficiente
        link = MagicMock()
        link.ingrediente_id = 99
        link.cantidad = Decimal("1")  # 1 unidad de insumo por unidad de producto
        uow.productos.get_ingrediente_links.return_value = [link]

        ing = MagicMock()
        ing.stock_cantidad = Decimal("2")  # solo hay 2 unidades disponibles
        uow.ingredientes.get_by_id.return_value = ing

        data = PedidoCreate(
            forma_pago_codigo="EFECTIVO",
            items=[ItemPedidoRequest(producto_id=1, cantidad=5)],  # pide 5, hay 2
        )
        with pytest.raises(HTTPException) as exc:
            service.crear_pedido(uow, data, usuario_id=1)

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "STOCK_INSUFICIENTE"

    def test_direccion_no_pertenece_al_usuario_lanza_404(self):
        uow, _, _ = self._setup_uow_crear()
        uow.direcciones.get_by_id_for_user.return_value = None  # ownership fail

        data = PedidoCreate(
            forma_pago_codigo="EFECTIVO",
            direccion_id=99,
            items=[ItemPedidoRequest(producto_id=1, cantidad=1)],
        )
        with pytest.raises(HTTPException) as exc:
            service.crear_pedido(uow, data, usuario_id=1)

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "DIRECCION_NOT_FOUND"


# ──────────────────────────────────────────────────────────────────────────────
# get_all — filtrado por rol
# ──────────────────────────────────────────────────────────────────────────────

class TestGetAll:
    def test_staff_ve_todos_los_pedidos(self):
        uow = make_uow()
        uow.pedidos.get_all.return_value = ([], 0)

        service.get_all(uow, requester_user_id=1, requester_roles=["ADMIN"])

        call_kwargs = uow.pedidos.get_all.call_args[1]
        assert call_kwargs.get("usuario_id") is None  # sin filtro de usuario

    def test_pedidos_role_ve_todos(self):
        uow = make_uow()
        uow.pedidos.get_all.return_value = ([], 0)

        service.get_all(uow, requester_user_id=1, requester_roles=["PEDIDOS"])

        call_kwargs = uow.pedidos.get_all.call_args[1]
        assert call_kwargs.get("usuario_id") is None

    def test_client_solo_ve_sus_pedidos(self):
        uow = make_uow()
        uow.pedidos.get_all.return_value = ([], 0)

        service.get_all(uow, requester_user_id=42, requester_roles=["CLIENT"])

        call_kwargs = uow.pedidos.get_all.call_args[1]
        assert call_kwargs.get("usuario_id") == 42

    def test_paginacion_correcta(self):
        uow = make_uow()
        uow.pedidos.get_all.return_value = ([], 30)

        result = service.get_all(uow, requester_user_id=1, requester_roles=["ADMIN"],
                                  page=2, size=10)

        assert result.page == 2
        assert result.pages == 3  # ceil(30/10)


# ──────────────────────────────────────────────────────────────────────────────
# get_by_id — ownership
# ──────────────────────────────────────────────────────────────────────────────

class TestGetById:
    def test_staff_usa_get_by_id(self):
        uow = make_uow()
        pedido = mock_pedido(id=1)
        uow.pedidos.get_by_id.return_value = pedido
        uow.pedidos.get_detalles.return_value = []

        service.get_by_id(uow, 1, requester_user_id=99, requester_roles=["ADMIN"])

        uow.pedidos.get_by_id.assert_called_with(1)
        uow.pedidos.get_by_id_for_user.assert_not_called()

    def test_client_usa_get_by_id_for_user(self):
        uow = make_uow()
        pedido = mock_pedido(id=1, usuario_id=5)
        uow.pedidos.get_by_id_for_user.return_value = pedido
        uow.pedidos.get_detalles.return_value = []

        service.get_by_id(uow, 1, requester_user_id=5, requester_roles=["CLIENT"])

        uow.pedidos.get_by_id_for_user.assert_called_with(1, 5)
        uow.pedidos.get_by_id.assert_not_called()

    def test_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.pedidos.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.get_by_id(uow, 999, requester_user_id=1, requester_roles=["ADMIN"])

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "PEDIDO_NOT_FOUND"


# ──────────────────────────────────────────────────────────────────────────────
# Mapa FSM — validación estructural
# ──────────────────────────────────────────────────────────────────────────────

class TestFSMMap:
    """Tests de caja blanca sobre el mapa de transiciones."""

    def test_estados_terminales_no_tienen_transiciones(self):
        for terminal in ("ENTREGADO", "CANCELADO"):
            assert service._TRANSICIONES_VALIDAS[terminal] == set()

    def test_cancelado_accesible_desde_estados_no_terminales(self):
        """CANCELADO debe ser alcanzable desde PENDIENTE, CONFIRMADO y EN_PREP."""
        for estado in ("PENDIENTE", "CONFIRMADO", "EN_PREP"):
            assert "CANCELADO" in service._TRANSICIONES_VALIDAS[estado], \
                f"CANCELADO debería ser alcanzable desde {estado}"

    def test_en_prep_va_a_entregado_o_cancelado(self):
        assert service._TRANSICIONES_VALIDAS["EN_PREP"] == {"ENTREGADO", "CANCELADO"}

    def test_fsm_tiene_exactamente_cinco_estados(self):
        """FSM v7: exactamente 5 estados, sin EN_CAMINO ni ESPERANDO_PAGO."""
        assert set(service._TRANSICIONES_VALIDAS) == {
            "PENDIENTE", "CONFIRMADO", "EN_PREP", "ENTREGADO", "CANCELADO",
        }

    def test_client_puede_cancelar_desde_estados_abiertos(self):
        """CLIENT puede cancelar desde PENDIENTE y CONFIRMADO."""
        assert set(service._TRANSICIONES_CLIENT) == {"PENDIENTE", "CONFIRMADO"}
        for estado, destinos in service._TRANSICIONES_CLIENT.items():
            assert "CANCELADO" in destinos, (
                f"CANCELADO debería ser alcanzable desde {estado}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# MercadoPago — crear_pedido con forma_pago=MERCADOPAGO
# ──────────────────────────────────────────────────────────────────────────────

class TestCrearPedidoMP:
    """
    Flujo Checkout Pro (preferencia + redirect) con FSM de 5 estados:
      - Al elegir MERCADOPAGO se crea la preferencia vía SDK y se devuelve init_point.
      - El pedido nace en PENDIENTE (sin ESPERANDO_PAGO); el pago lo pasa a CONFIRMADO.
    """

    def _setup_uow_mp(self):
        uow = make_uow()

        forma_pago = MagicMock()
        forma_pago.habilitado = True
        forma_pago.codigo = "MERCADOPAGO"
        uow.formas_pago.get_by_codigo.return_value = forma_pago

        uow.estados_pedido.get_by_codigo.return_value = MagicMock()

        producto = mock_producto(stock_cantidad=10)
        uow.productos.get_by_id.return_value = producto
        uow.productos.get_ingrediente_links.return_value = []

        uow.pedidos.get_detalles.return_value = []
        return uow

    @staticmethod
    def _asignar_id(p):
        p.id = 1
        return p

    @staticmethod
    def _sdk_exitoso():
        sdk = MagicMock()
        sdk.preference.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": "pref_test_abc",
                "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref_test_abc",
            },
        }
        return sdk

    @patch("mercadopago.SDK")
    def test_mp_llama_sdk_y_crea_preferencia(self, mock_sdk_class):
        mock_sdk_class.return_value = self._sdk_exitoso()
        uow = self._setup_uow_mp()
        uow.pedidos.add.side_effect = self._asignar_id

        data = PedidoCreate(
            forma_pago_codigo="MERCADOPAGO",
            items=[ItemPedidoRequest(producto_id=1, cantidad=1)],
        )
        service.crear_pedido(uow, data, usuario_id=1)

        mock_sdk_class.assert_called_once()
        mock_sdk_class.return_value.preference.return_value.create.assert_called_once()

    @patch("mercadopago.SDK")
    def test_mp_devuelve_init_point_en_response(self, mock_sdk_class):
        mock_sdk_class.return_value = self._sdk_exitoso()
        uow = self._setup_uow_mp()
        uow.pedidos.add.side_effect = self._asignar_id

        data = PedidoCreate(
            forma_pago_codigo="MERCADOPAGO",
            items=[ItemPedidoRequest(producto_id=1, cantidad=1)],
        )
        result = service.crear_pedido(uow, data, usuario_id=1)

        assert result.init_point == (
            "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref_test_abc"
        )

    @patch("mercadopago.SDK")
    def test_mp_pedido_nace_pendiente(self, mock_sdk_class):
        mock_sdk_class.return_value = self._sdk_exitoso()
        uow = self._setup_uow_mp()
        pedido_creado = None

        def capturar(p):
            nonlocal pedido_creado
            pedido_creado = p
            p.id = 1
            return p
        uow.pedidos.add.side_effect = capturar

        data = PedidoCreate(
            forma_pago_codigo="MERCADOPAGO",
            items=[ItemPedidoRequest(producto_id=1, cantidad=1)],
        )
        service.crear_pedido(uow, data, usuario_id=1)

        assert pedido_creado.estado_codigo == "PENDIENTE"

    @patch("mercadopago.SDK")
    def test_mp_error_de_sdk_lanza_502(self, mock_sdk_class):
        sdk = MagicMock()
        sdk.preference.return_value.create.return_value = {
            "status": 400,
            "response": {"message": "Invalid credentials"},
        }
        mock_sdk_class.return_value = sdk
        uow = self._setup_uow_mp()
        uow.pedidos.add.side_effect = self._asignar_id

        data = PedidoCreate(
            forma_pago_codigo="MERCADOPAGO",
            items=[ItemPedidoRequest(producto_id=1, cantidad=1)],
        )
        with pytest.raises(HTTPException) as exc:
            service.crear_pedido(uow, data, usuario_id=1)

        assert exc.value.status_code == 502
        assert exc.value.detail["code"] == "MP_PREFERENCE_ERROR"


# ──────────────────────────────────────────────────────────────────────────────
# MercadoPago — verificar_pago_mp
# ──────────────────────────────────────────────────────────────────────────────

class TestVerificarPagoMP:
    """
    Verifica los posibles resultados al consultar el estado de un pago en MP:
      - Pago aprobado / pendiente.
      - Sin pagos registrados → not_found.
      - API de MP no disponible → not_found.
      - Pedido sin forma de pago MP → 400.
      - Pedido no encontrado → 404.
    """

    def _setup(self, forma_pago: str = "MERCADOPAGO", usuario_id: int = 5):
        uow = make_uow()
        pedido = mock_pedido(id=1, usuario_id=usuario_id, forma_pago_codigo=forma_pago)
        uow.pedidos.get_by_id_for_user.return_value = pedido
        return uow

    @patch("mercadopago.SDK")
    def test_pago_aprobado(self, mock_sdk_class):
        sdk = MagicMock()
        sdk.payment.return_value.search.return_value = {
            "status": 200,
            "response": {"results": [{"id": 9901, "status": "approved"}]},
        }
        mock_sdk_class.return_value = sdk
        uow = self._setup()

        result = service.verificar_pago_mp(uow, pedido_id=1, usuario_id=5)

        assert result["status"] == "approved"
        assert result["payment_id"] == 9901

    @patch("mercadopago.SDK")
    def test_pago_pendiente(self, mock_sdk_class):
        sdk = MagicMock()
        sdk.payment.return_value.search.return_value = {
            "status": 200,
            "response": {"results": [{"id": 9902, "status": "pending"}]},
        }
        mock_sdk_class.return_value = sdk
        uow = self._setup()

        result = service.verificar_pago_mp(uow, pedido_id=1, usuario_id=5)

        assert result["status"] == "pending"
        assert result["payment_id"] == 9902

    @patch("mercadopago.SDK")
    def test_sin_pagos_retorna_not_found(self, mock_sdk_class):
        sdk = MagicMock()
        sdk.payment.return_value.search.return_value = {
            "status": 200,
            "response": {"results": []},
        }
        mock_sdk_class.return_value = sdk
        uow = self._setup()

        result = service.verificar_pago_mp(uow, pedido_id=1, usuario_id=5)

        assert result["status"] == "not_found"
        assert result["payment_id"] is None

    @patch("mercadopago.SDK")
    def test_api_mp_falla_retorna_not_found(self, mock_sdk_class):
        sdk = MagicMock()
        sdk.payment.return_value.search.return_value = {
            "status": 500,
            "response": {},
        }
        mock_sdk_class.return_value = sdk
        uow = self._setup()

        result = service.verificar_pago_mp(uow, pedido_id=1, usuario_id=5)

        assert result["status"] == "not_found"
        assert result["payment_id"] is None

    def test_pedido_no_usa_mp_lanza_400(self):
        uow = self._setup(forma_pago="EFECTIVO")

        with pytest.raises(HTTPException) as exc:
            service.verificar_pago_mp(uow, pedido_id=1, usuario_id=5)

        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "NOT_MP_PAYMENT"

    def test_pedido_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.pedidos.get_by_id_for_user.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.verificar_pago_mp(uow, pedido_id=999, usuario_id=5)

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "PEDIDO_NOT_FOUND"
