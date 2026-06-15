from decimal import Decimal
from sqlmodel import Session, select
from app.core.database import engine
from app.core.security import hash_password

from app.modules.auth.model import Rol, Usuario, UsuarioRol
from app.modules.pedidos.model import EstadoPedido, FormaPago
from app.modules.unidades.model import UnidadMedida
from app.modules.direcciones.model import DireccionEntrega  # noqa: F401 — registra el mapper
from app.modules.categorias.model import Categoria
from app.modules.ingredientes.model import Ingrediente
from app.modules.productos.model import Producto
from app.core.links import ProductoCategoria, ProductoIngrediente


def seed():
    with Session(engine) as session:
        _seed_roles(session)
        _seed_estados_pedido(session)
        _seed_formas_pago(session)
        _seed_unidades(session)
        _seed_admin(session)
        _seed_cocina(session)
        _seed_stock(session)
        _seed_cliente(session)
        _seed_catalogo(session)
        print("Seed completado.")


def _seed_unidades(session: Session):
    unidades = [
        UnidadMedida(nombre="kilogramo", simbolo="kg",        tipo="peso"),
        UnidadMedida(nombre="gramo",     simbolo="g",         tipo="peso"),
        UnidadMedida(nombre="litro",     simbolo="L",         tipo="volumen"),
        UnidadMedida(nombre="mililitro", simbolo="ml",        tipo="volumen"),
        UnidadMedida(nombre="unidad",    simbolo="ud",        tipo="contable"),
        UnidadMedida(nombre="porción",   simbolo="porciones", tipo="contable"),
    ]
    for u in unidades:
        if not session.exec(select(UnidadMedida).where(UnidadMedida.nombre == u.nombre)).first():
            session.add(u)
    session.commit()


def _seed_roles(session: Session):
    roles = [
        Rol(codigo="ADMIN",   nombre="Administrador",      descripcion="Acceso total al sistema"),
        Rol(codigo="STOCK",   nombre="Gestor de Stock",    descripcion="Gestión de inventario"),
        Rol(codigo="PEDIDOS",  nombre="Gestor de Pedidos",  descripcion="Ver y avanzar estados de pedidos"),
        Rol(codigo="CLIENT",  nombre="Cliente",            descripcion="Cliente de la tienda"),
    ]
    for rol in roles:
        if not session.exec(select(Rol).where(Rol.codigo == rol.codigo)).first():
            session.add(rol)
    session.commit()


def _seed_estados_pedido(session: Session):
    # FSM v7 — exactamente 5 estados (se elimina EN_CAMINO de v5; sin ESPERANDO_PAGO).
    estados = [
        EstadoPedido(codigo="PENDIENTE",  descripcion="Pendiente de confirmación", orden=1, es_terminal=False),
        EstadoPedido(codigo="CONFIRMADO", descripcion="Confirmado",                orden=2, es_terminal=False),
        EstadoPedido(codigo="EN_PREP",    descripcion="En preparación",            orden=3, es_terminal=False),
        EstadoPedido(codigo="ENTREGADO",  descripcion="Entregado",                 orden=4, es_terminal=True),
        EstadoPedido(codigo="CANCELADO",  descripcion="Cancelado",                 orden=5, es_terminal=True),
    ]
    for estado in estados:
        if not session.exec(select(EstadoPedido).where(EstadoPedido.codigo == estado.codigo)).first():
            session.add(estado)
    session.commit()


def _seed_formas_pago(session: Session):
    # MercadoPago Checkout PRO operativo (módulo pagos + webhook IPN).
    formas = [
        FormaPago(codigo="EFECTIVO",     descripcion="Efectivo",                  habilitado=True),
        FormaPago(codigo="TRANSFERENCIA", descripcion="Transferencia bancaria",     habilitado=True),
        FormaPago(codigo="MERCADOPAGO",  descripcion="MercadoPago",                habilitado=True),
    ]
    for forma in formas:
        if not session.exec(select(FormaPago).where(FormaPago.codigo == forma.codigo)).first():
            session.add(forma)
    session.commit()


def _seed_usuario(session: Session, *, nombre, apellido, email, password, rol):
    """Crea un usuario con un rol asignado si todavía no existe (idempotente)."""
    if session.exec(select(Usuario).where(Usuario.email == email)).first():
        return
    u = Usuario(nombre=nombre, apellido=apellido, email=email, password_hash=hash_password(password))
    session.add(u)
    session.flush()
    session.add(UsuarioRol(usuario_id=u.id, rol_codigo=rol))
    session.commit()


def _seed_admin(session: Session):
    _seed_usuario(session, nombre="Admin", apellido="FoodStore",
                  email="admin@foodstore.com", password="Admin1234!", rol="ADMIN")


def _seed_cocina(session: Session):
    _seed_usuario(session, nombre="Carlos", apellido="Cocina",
                  email="cocina@foodstore.com", password="Cocina1234!", rol="PEDIDOS")


def _seed_stock(session: Session):
    _seed_usuario(session, nombre="Laura", apellido="Stock",
                  email="stock@foodstore.com", password="Stock1234!", rol="STOCK")


def _seed_cliente(session: Session):
    # Cuenta de cliente pre-creada: permite probar la tienda sin registrarse ni usar Google.
    _seed_usuario(session, nombre="Cliente", apellido="Demo",
                  email="cliente@foodstore.com", password="Cliente1234!", rol="CLIENT")


# ── Catálogo ────────────────────────────────────────────────────────────────────

_IMG = "https://res.cloudinary.com/dy5cbcgcj/image/upload"

# Categorías: (nombre, descripcion, nombre_padre|None)
_CATEGORIAS = [
    ("Comidas",      None,                          None),
    ("Bebidas",      None,                          None),
    ("Hamburguesas", None,                          "Comidas"),
    ("Combos",       "Arma tu combo completo",      "Comidas"),
    ("Empanadas",    None,                          "Comidas"),
    ("Sandwich",     None,                          "Comidas"),
    ("Refrescos",    "Fríos y calientes",           "Bebidas"),
    ("Postres",      "Dulces para cerrar",          "Bebidas"),
    ("Jugos",        "Jugos Frescos y Naturales",   "Bebidas"),
]

# Insumos: (nombre, unidad_medida, es_alergeno, costo_unitario, stock, es_producto_terminado, descripcion)
_INSUMOS = [
    ("Medallon de carne 150g",  "UNIDAD", False, "2500", "998",  False, "Medallon de carne vacuna, 150g."),
    ("Pan brioche",             "UNIDAD", True,  "1000", "998",  False, "Pan artesanal con semillas de sesamo"),
    ("Hoja de lechuga",         "UNIDAD", False, "150",  "1000", False, "Lechuga fresca"),
    ("Tomate",                  "UNIDAD", False, "300",  "997",  False, "Tomate fresco en rodajas"),
    ("Queso cheddar",           "UNIDAD", True,  "700",  "998",  False, "Feta de queso cheddar madurado, 25g"),
    ("Aros de cebolla",         "UNIDAD", False, "250",  "996",  False, "Cebolla en aros"),
    ("Panceta",                 "G",      False, "12",   "960",  False, "Panceta ahumada crocante"),
    ("Salsa BBQ",               "G",      False, "10",   "985",  False, "Salsa barbecue ahumada"),
    ("Ketchup",                 "G",      False, "6",    "985",  False, "Salsa de tomate"),
    ("Mayonesa",                "G",      True,  "8",    "970",  False, "Mayonesa casera"),
    ("Chocolate",               "G",      True,  "10",   "1000", False, "Cobertura de chocolate negro"),
    ("Harina de trigo",         "G",      True,  "4",    "1000", False, "Harina"),
    ("Huevo",                   "UNIDAD", True,  "300",  "999",  False, "Huevo de gallina"),
    ("Azucar",                  "G",      False, "4",    "1000", False, "Azucar refinada"),
    ("Helado de vainilla",      "G",      True,  "12",   "1000", False, "Crema de vainilla artesanal"),
    ("Crema de leche",          "ML",     True,  "8",    "1000", False, "Crema para reposteria"),
    ("Naranja",                 "UNIDAD", False, "1350", "1000", False, "Naranja fresca exprimida"),
    ("Tapa de empanada",        "UNIDAD", False, "200",  "999",  False, "Base crocante para el relleno de empanada."),
    ("Carne Picada",            "G",      False, "4",    "930",  False, "Carne picada de vaca de calidad."),
    ("Cebolla",                 "G",      False, "3",    "999",  False, "Cebolla fresca rehogada. 30g."),
    ("Aceitunas",               "UNIDAD", False, "50",   "998",  False, "Aceitunas verdes picadas"),
    # Botellas: productos terminados (se compran y revenden tal cual).
    ("Botella de Agua Mineral", "UNIDAD", False, "1540", "1000", True,  "Botella de Agua Mineral sin gas, 500ml"),
    ("Botella de Coca Cola",    "UNIDAD", False, "1923", "994",  True,  "Botella de Coca Cola chica, 500ml"),
    ("Pan de Miga",             "UNIDAD", False, "200",  "998",  False, "Rebanadas de pan de miga, 50g"),
    ("Jamón cocido",            "G",      False, "6",    "950",  False, "Fetas de Jamón cocido"),
    ("Queso Barra",             "G",      False, "6",    "950",  False, "Fetas de queso barra"),
]

# Productos: (nombre, descripcion, categoria, destacado, imagen, receta[(insumo, cantidad)])
_PRODUCTOS = [
    ("Hamburguesa Clasica",
     "Pan brioche, Medallon de carne 150g, Mayonesa, Ketchup, Queso cheddar, Tomate, Aros de cebolla",
     "Hamburguesas", True, f"{_IMG}/v1780891530/foodstore/productos/vqkfdlpz7cvi6muah6t1.png",
     [("Medallon de carne 150g", 1), ("Pan brioche", 1), ("Tomate", 2), ("Queso cheddar", 1),
      ("Aros de cebolla", 2), ("Ketchup", 15), ("Mayonesa", 15)]),
    ("Hamburguesa Doble Completa",
     "Pan brioche, Queso cheddar, Aros de cebolla, Panceta, Tomate, Hoja de lechuga, Ketchup, Mayonesa, Huevo, Medallon de carne 150g",
     "Hamburguesas", False, f"{_IMG}/v1780892598/foodstore/productos/nnvz8pkmfnwqmmdpwatg.png",
     [("Medallon de carne 150g", 2), ("Pan brioche", 1), ("Hoja de lechuga", 1), ("Tomate", 2),
      ("Queso cheddar", 2), ("Aros de cebolla", 3), ("Panceta", 50), ("Ketchup", 20),
      ("Mayonesa", 20), ("Huevo", 1)]),
    ("Hamburguesa BBQ",
     "Tomate, Medallon de carne 150g, Aros de cebolla, Salsa BBQ, Panceta, Queso cheddar, Pan brioche",
     "Hamburguesas", False, f"{_IMG}/v1780892493/foodstore/productos/skgplk54oqy5wknprzm5.png",
     [("Medallon de carne 150g", 1), ("Pan brioche", 1), ("Tomate", 2), ("Queso cheddar", 1),
      ("Aros de cebolla", 2), ("Panceta", 40), ("Salsa BBQ", 15)]),
    ("Coca-Cola", "Botella de Coca Cola",
     "Refrescos", False, f"{_IMG}/v1780892224/foodstore/productos/kcjrltvyfi9lnojutjci.png",
     [("Botella de Coca Cola", 1)]),
    ("Agua Mineral", "Botella de Agua Mineral",
     "Refrescos", True, f"{_IMG}/v1780871209/foodstore/productos/i7ijixu9qnnhfqsdmfva.jpg",
     [("Botella de Agua Mineral", 1)]),
    ("Jugo de Naranja", "Naranja",
     "Jugos", True, f"{_IMG}/v1780891578/foodstore/productos/ofqjkakr1rqna7rxmlls.jpg",
     [("Naranja", 2)]),
    ("Brownie con helado",
     "Crema de leche, Chocolate, Huevo, Azucar, Helado de vainilla, Harina de trigo",
     "Postres", False, f"{_IMG}/v1780892135/foodstore/productos/twzk3vsk12bvyqzjfn92.png",
     [("Chocolate", 90), ("Harina de trigo", 50), ("Huevo", 2), ("Azucar", 60),
      ("Helado de vainilla", 130), ("Crema de leche", 50)]),
    ("Combo Clasico",
     "Ketchup, Medallon de carne 150g, Pan brioche, Tomate, Queso cheddar, Mayonesa, Aros de cebolla",
     "Combos", False, f"{_IMG}/v1780892752/foodstore/productos/aauvwbpccxokld7blpsh.png",
     [("Medallon de carne 150g", 1), ("Pan brioche", 1), ("Tomate", 1), ("Queso cheddar", 1),
      ("Aros de cebolla", 2), ("Ketchup", 15), ("Mayonesa", 15)]),
    ("Empanada de Carne",
     "Huevo, Tapa de empanada, Carne Picada, Cebolla, Aceitunas",
     "Empanadas", False, f"{_IMG}/v1780891886/foodstore/productos/cwkbd3njx8yy5nm5g9n8.png",
     [("Huevo", 1), ("Tapa de empanada", 1), ("Carne Picada", 70), ("Cebolla", 1), ("Aceitunas", 2)]),
    ("Sandwich de Jamón y Queso",
     "Pan de Miga, Jamón cocido, Queso Barra, Mayonesa",
     "Sandwich", True, f"{_IMG}/v1780892010/foodstore/productos/coehkvccfouxqu4jpd5l.webp",
     [("Mayonesa", 15), ("Pan de Miga", 2), ("Jamón cocido", 50), ("Queso Barra", 50)]),
]

# Insumos que el cliente puede quitar de un producto (personalización del pedido).
_REMOVIBLES = {"Tomate", "Hoja de lechuga", "Queso cheddar", "Aros de cebolla", "Ketchup", "Mayonesa", "Panceta"}

_MARGEN = Decimal("0.30")


def _seed_catalogo(session: Session):
    """
    Catálogo completo de la tienda (categorías jerárquicas, insumos con stock y
    productos con receta). Idempotente: si ya hay productos cargados, no hace nada.
    El stock es por INSUMO; el stock de cada producto se deriva de sus insumos.
    El precio se calcula: costo total de insumos × (1 + margen).
    """
    if session.exec(select(Producto)).first():
        return  # ya hay productos cargados

    # Categorías (padres primero para resolver parent_id)
    cats: dict[str, Categoria] = {}
    for nombre, desc, padre in _CATEGORIAS:
        c = Categoria(nombre=nombre, descripcion=desc,
                      parent_id=cats[padre].id if padre else None)
        session.add(c)
        session.flush()
        cats[nombre] = c

    # Insumos
    insumos: dict[str, Ingrediente] = {}
    for nombre, unidad, alergeno, costo, stock, terminado, desc in _INSUMOS:
        ing = Ingrediente(
            nombre=nombre,
            descripcion=desc,
            unidad_medida=unidad,
            costo_unitario=Decimal(costo),
            stock_cantidad=Decimal(stock),
            stock_minimo=Decimal("10"),
            es_alergeno=alergeno,
            es_producto_terminado=terminado,
        )
        session.add(ing)
        insumos[nombre] = ing
    session.flush()

    ud = session.exec(select(UnidadMedida).where(UnidadMedida.simbolo == "ud")).first()
    unidad_venta_id = ud.id if ud else None

    # Resolución de la unidad de la receta (ProductoIngrediente.unidad_medida_id es NN)
    unidades_all = session.exec(select(UnidadMedida)).all()

    def _unidad_receta(texto: str) -> int:
        t = (texto or "").strip().lower()
        for u in unidades_all:
            if u.simbolo.lower() == t or u.nombre.lower() == t:
                return u.id
        return ud.id  # fallback: unidad

    # Productos
    for nombre, desc, categoria, destacado, imagen, receta in _PRODUCTOS:
        costo = sum(insumos[n].costo_unitario * Decimal(str(c)) for n, c in receta)
        precio = (costo * (Decimal("1") + _MARGEN)).quantize(Decimal("0.01"))
        p = Producto(
            nombre=nombre,
            descripcion=desc,
            imagenes_url=[imagen],
            precio_base=precio,
            margen_ganancia=_MARGEN,
            disponible=True,
            destacado=destacado,
            unidad_venta_id=unidad_venta_id,
        )
        session.add(p)
        session.flush()
        session.add(ProductoCategoria(producto_id=p.id, categoria_id=cats[categoria].id, es_principal=True))
        for n, c in receta:
            session.add(ProductoIngrediente(
                producto_id=p.id,
                ingrediente_id=insumos[n].id,
                cantidad=Decimal(str(c)),
                es_removible=(n in _REMOVIBLES),
                unidad_medida_id=_unidad_receta(insumos[n].unidad_medida),
            ))

    session.commit()
    print(f"Seed de catálogo completado ({len(_PRODUCTOS)} productos, {len(_INSUMOS)} insumos).")


if __name__ == "__main__":
    seed()
