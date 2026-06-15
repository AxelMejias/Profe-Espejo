"""Tests del módulo Productos (doc §5.2/§13) — lectura pública, stock derivado y RBAC."""

from datetime import datetime
from decimal import Decimal

from app.modules.productos.schemas import ProductoRead, InsumoEnProductoRead


def _insumo(cantidad, stock_actual):
    return InsumoEnProductoRead(
        ingrediente_id=1, nombre="Insumo", cantidad=Decimal(str(cantidad)),
        unidad_medida="UNIDAD", costo_unitario=Decimal("1.00"),
        subtotal=Decimal("1.00"), stock_actual=Decimal(str(stock_actual)),
        es_producto_terminado=False,
    )


def _producto_read(insumos):
    return ProductoRead(
        id=1, nombre="Burger", descripcion=None, imagenes_url=[],
        precio_base=Decimal("1000.00"), margen_ganancia=Decimal("0.30"),
        costo_total_insumos=Decimal("0.00"), disponible=True,
        categorias=[], insumos=insumos, created_at=datetime.utcnow(),
    )


def test_stock_disponible_es_el_minimo_producible():
    # Insumo A: 10 / 2 = 5 ; Insumo B: 9 / 3 = 3  → mínimo producible = 3
    p = _producto_read([_insumo(cantidad=2, stock_actual=10),
                        _insumo(cantidad=3, stock_actual=9)])
    assert p.model_dump()["stock_disponible"] == 3


def test_stock_disponible_cero_si_un_insumo_se_agota():
    # Si un insumo de la receta está en 0, el producto no se puede producir.
    p = _producto_read([_insumo(cantidad=2, stock_actual=10),
                        _insumo(cantidad=1, stock_actual=0)])
    assert p.model_dump()["stock_disponible"] == 0


def test_stock_disponible_none_sin_receta():
    p = _producto_read([])
    assert p.model_dump()["stock_disponible"] is None


def test_listar_productos_publico_sin_auth(client):
    # Doc §5.2: el catálogo es PÚBLICO (navegable sin autenticación).
    r = client.get("/api/v1/productos/")
    assert r.status_code == 200, r.text
    assert "items" in r.json()


def test_obtener_producto_publico_sin_auth(client, producto_factory):
    prod = producto_factory(nombre="Burger Detalle", precio_base="1200.00", stock_cantidad=33)
    r = client.get(f"/api/v1/productos/{prod.id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "precio_base" in body
    assert body["stock_cantidad"] == 33


def test_stock_no_es_editable_endpoint_eliminado(client, stock_headers, producto_factory):
    # El stock del producto se deriva de los insumos: el endpoint de edición
    # manual fue eliminado (ya no existe PATCH /productos/{id}/stock).
    prod = producto_factory(nombre="Burger Stock A")
    r = client.patch(f"/api/v1/productos/{prod.id}/stock", headers=stock_headers,
                     json={"stock_cantidad": 99})
    assert r.status_code == 404  # la ruta /{id}/stock ya no existe


def test_listar_categorias_publico_sin_auth(client):
    # Doc §5.2: catálogo público — las categorías también se leen sin auth.
    r = client.get("/api/v1/categorias/")
    assert r.status_code == 200, r.text
    assert "items" in r.json()


def test_toggle_disponibilidad_admin(client, admin_headers, producto_factory):
    prod = producto_factory(nombre="Burger Disp", disponible=True)
    r = client.patch(f"/api/v1/productos/{prod.id}/disponibilidad", headers=admin_headers,
                     json={"disponible": False})
    assert r.status_code == 200, r.text
    assert r.json()["disponible"] is False


# ── Endpoints semánticos de imágenes e insumos (doc §5.2) ──────────────────────

def test_actualizar_imagenes_admin(client, admin_headers, producto_factory):
    prod = producto_factory(nombre="Burger Imagenes")
    urls = ["https://cdn.test/x.png", "https://cdn.test/y.png"]
    r = client.patch(f"/api/v1/productos/{prod.id}/imagenes", headers=admin_headers,
                     json={"imagenes_url": urls})
    assert r.status_code == 200, r.text
    assert r.json()["imagenes_url"] == urls


def test_actualizar_imagenes_requiere_admin(client, client_headers, producto_factory):
    prod = producto_factory(nombre="Burger Imagenes RBAC")
    r = client.patch(f"/api/v1/productos/{prod.id}/imagenes", headers=client_headers,
                     json={"imagenes_url": []})
    assert r.status_code == 403


def test_listar_ingredientes_producto_publico(client):
    items = client.get("/api/v1/productos/?size=50").json()["items"]
    con_insumos = [p for p in items if p.get("insumos")]
    assert con_insumos, "el seed debe tener productos con insumos"
    pid = con_insumos[0]["id"]
    r = client.get(f"/api/v1/productos/{pid}/ingredientes")
    assert r.status_code == 200, r.text
    insumos = r.json()
    assert isinstance(insumos, list) and len(insumos) >= 1
    assert "nombre" in insumos[0] and "cantidad" in insumos[0]


def test_asociar_ingrediente_admin(client, admin_headers, producto_factory):
    prod = producto_factory(nombre="Burger Asociar")
    ing_id = client.get("/api/v1/ingredientes/", headers=admin_headers).json()["items"][0]["id"]
    r = client.post(f"/api/v1/productos/{prod.id}/ingredientes", headers=admin_headers,
                    json={"ingrediente_id": ing_id, "cantidad": "2.5"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ingrediente_id"] == ing_id
    assert body["unidad_medida_id"] > 0  # FK NN resuelta automáticamente
    insumos = client.get(f"/api/v1/productos/{prod.id}/ingredientes").json()
    assert any(i["ingrediente_id"] == ing_id for i in insumos)


def test_asociar_ingrediente_duplicado_409(client, admin_headers, producto_factory):
    prod = producto_factory(nombre="Burger Asociar Dup")
    ing_id = client.get("/api/v1/ingredientes/", headers=admin_headers).json()["items"][0]["id"]
    client.post(f"/api/v1/productos/{prod.id}/ingredientes", headers=admin_headers,
                json={"ingrediente_id": ing_id, "cantidad": "1"})
    r = client.post(f"/api/v1/productos/{prod.id}/ingredientes", headers=admin_headers,
                    json={"ingrediente_id": ing_id, "cantidad": "1"})
    assert r.status_code == 409, r.text
