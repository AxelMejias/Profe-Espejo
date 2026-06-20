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


def test_baja_de_insumo_deja_producto_sin_stock(client, admin_headers):
    """Si un insumo de la receta se da de baja, el producto figura SIN STOCK
    (stock_disponible = 0) y el insumo sigue visible (activo=False) sin que el costo
    baje. Al reactivar el insumo, el producto recupera su stock."""
    def crear_ing(nombre, costo, stock):
        return client.post("/api/v1/ingredientes/", headers=admin_headers, json={
            "nombre": nombre, "unidad_medida": "u", "costo_unitario": costo,
            "stock_cantidad": stock, "stock_minimo": "0.000",
        }).json()["id"]

    a = crear_ing("Cheddar Baja Test", "10.00", "100.000")   # se dará de baja
    b = crear_ing("Pan Baja Test", "5.00", "100.000")

    pid = client.post("/api/v1/productos/", headers=admin_headers, json={
        "nombre": "Hamburguesa Baja Test", "margen_ganancia": "0.30",
        "insumos": [
            {"ingrediente_id": a, "cantidad": "2"},
            {"ingrediente_id": b, "cantidad": "1"},
        ],
    }).json()["id"]

    antes = client.get(f"/api/v1/productos/{pid}").json()
    assert antes["stock_disponible"] == 50      # min(100//2, 100//1)
    assert Decimal(antes["precio_base"]) == Decimal("32.50")   # (2*10 + 1*5) * 1.30

    # Baja del cheddar.
    assert client.delete(f"/api/v1/ingredientes/{a}", headers=admin_headers).status_code == 204

    dur = client.get(f"/api/v1/productos/{pid}").json()
    assert dur["stock_disponible"] == 0, "el producto debe quedar sin stock"
    # El insumo NO se quita de la receta: sigue listado pero marcado inactivo.
    cheddar = next(i for i in dur["insumos"] if i["ingrediente_id"] == a)
    assert cheddar["activo"] is False
    assert Decimal(cheddar["stock_actual"]) == 0
    # El costo (y por ende el precio) no bajan artificialmente.
    assert Decimal(dur["costo_total_insumos"]) == Decimal("25.00")
    assert Decimal(dur["precio_base"]) == Decimal("32.50")

    # Reactivar el insumo restaura el stock del producto.
    assert client.patch(f"/api/v1/ingredientes/{a}/reactivar", headers=admin_headers).status_code == 200
    despues = client.get(f"/api/v1/productos/{pid}").json()
    assert despues["stock_disponible"] == 50
    assert next(i for i in despues["insumos"] if i["ingrediente_id"] == a)["activo"] is True


def test_filtro_con_stock_y_sin_stock(client, admin_headers):
    """El filtro con_stock separa productos producibles (stock > 0) de los que están
    sin stock (algún insumo agotado o dado de baja)."""
    def crear_ing(nombre, costo, stock):
        return client.post("/api/v1/ingredientes/", headers=admin_headers, json={
            "nombre": nombre, "unidad_medida": "u", "costo_unitario": costo,
            "stock_cantidad": stock, "stock_minimo": "0.000",
        }).json()["id"]

    a = crear_ing("Filtro Stock A", "10.00", "100.000")
    b = crear_ing("Filtro Stock B", "10.00", "1.000")   # stock bajo

    # Con stock: solo insumo A (100 // 2 = 50 producibles).
    p_con = client.post("/api/v1/productos/", headers=admin_headers, json={
        "nombre": "Producto Con Stock", "margen_ganancia": "0.30",
        "insumos": [{"ingrediente_id": a, "cantidad": "2"}],
    }).json()["id"]
    # Sin stock: el insumo B requiere 5 pero hay 1.
    p_sin = client.post("/api/v1/productos/", headers=admin_headers, json={
        "nombre": "Producto Sin Stock", "margen_ganancia": "0.30",
        "insumos": [{"ingrediente_id": a, "cantidad": "2"}, {"ingrediente_id": b, "cantidad": "5"}],
    }).json()["id"]

    ids_con = {p["id"] for p in client.get("/api/v1/productos/?con_stock=true&size=100").json()["items"]}
    assert p_con in ids_con and p_sin not in ids_con

    ids_sin = {p["id"] for p in client.get("/api/v1/productos/?con_stock=false&size=100").json()["items"]}
    assert p_sin in ids_sin and p_con not in ids_sin

    # Dar de baja el insumo A deja a "Producto Con Stock" sin stock también.
    client.delete(f"/api/v1/ingredientes/{a}", headers=admin_headers)
    ids_sin2 = {p["id"] for p in client.get("/api/v1/productos/?con_stock=false&size=100").json()["items"]}
    assert p_con in ids_sin2


def test_editar_producto_conserva_o_quita_insumo_dado_de_baja(client, admin_headers):
    """Editar un producto con un insumo discontinuado no rompe (no 404): se puede
    guardar conservándolo (queda sin stock) o quitándolo de la receta."""
    def crear_ing(nombre, costo, stock):
        return client.post("/api/v1/ingredientes/", headers=admin_headers, json={
            "nombre": nombre, "unidad_medida": "u", "costo_unitario": costo,
            "stock_cantidad": stock, "stock_minimo": "0.000",
        }).json()["id"]

    a = crear_ing("Cheddar Edit Baja", "10.00", "100.000")
    b = crear_ing("Pan Edit Baja", "5.00", "100.000")
    pid = client.post("/api/v1/productos/", headers=admin_headers, json={
        "nombre": "Hamburguesa Edit Baja", "margen_ganancia": "0.30",
        "insumos": [{"ingrediente_id": a, "cantidad": "2"}, {"ingrediente_id": b, "cantidad": "1"}],
    }).json()["id"]
    client.delete(f"/api/v1/ingredientes/{a}", headers=admin_headers)

    # 1) Guardar conservando el insumo dado de baja (lo que manda el form si no se quita).
    r = client.put(f"/api/v1/productos/{pid}", headers=admin_headers, json={
        "margen_ganancia": "0.30",
        "insumos": [{"ingrediente_id": a, "cantidad": "2"}, {"ingrediente_id": b, "cantidad": "1"}],
    })
    assert r.status_code == 200, r.text
    body = client.get(f"/api/v1/productos/{pid}").json()
    assert body["stock_disponible"] == 0
    assert any(i["ingrediente_id"] == a and i["activo"] is False for i in body["insumos"])

    # 2) Quitar el insumo dado de baja → queda solo el pan, con stock.
    r = client.put(f"/api/v1/productos/{pid}", headers=admin_headers, json={
        "margen_ganancia": "0.30",
        "insumos": [{"ingrediente_id": b, "cantidad": "1"}],
    })
    assert r.status_code == 200, r.text
    body = client.get(f"/api/v1/productos/{pid}").json()
    assert all(i["ingrediente_id"] != a for i in body["insumos"])
    assert body["stock_disponible"] == 100   # 100 // 1


def test_cambio_costo_ingrediente_recalcula_precio_producto(client, admin_headers):
    """Al subir el costo de un insumo, el precio_base del producto que lo usa se
    recalcula y persiste: precio = costo_insumos * (1 + margen)."""
    # Insumo a $10
    ing_id = client.post("/api/v1/ingredientes/", headers=admin_headers, json={
        "nombre": "Insumo Recalc Precio", "unidad_medida": "u", "costo_unitario": "10.00",
        "stock_cantidad": "100.000", "stock_minimo": "0.000",
    }).json()["id"]

    # Producto: 2 unidades del insumo, margen 30% → precio = 2*10*1.3 = 26.00
    pid = client.post("/api/v1/productos/", headers=admin_headers, json={
        "nombre": "Producto Recalc Precio", "margen_ganancia": "0.30",
        "insumos": [{"ingrediente_id": ing_id, "cantidad": "2"}],
    }).json()["id"]
    assert Decimal(client.get(f"/api/v1/productos/{pid}").json()["precio_base"]) == Decimal("26.00")

    # Sube el costo del insumo a $20 → precio = 2*20*1.3 = 52.00
    r = client.put(f"/api/v1/ingredientes/{ing_id}", headers=admin_headers,
                   json={"costo_unitario": "20.00"})
    assert r.status_code == 200, r.text

    body = client.get(f"/api/v1/productos/{pid}").json()
    assert Decimal(body["precio_base"]) == Decimal("52.00")
    assert Decimal(body["costo_total_insumos"]) == Decimal("40.00")
